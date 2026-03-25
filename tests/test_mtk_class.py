#!/usr/bin/env python3
"""Tests for mtk_class.py preloader patching refactoring."""
import unittest
from unittest.mock import MagicMock, patch
from mtkclient.Library.mtk_class import Mtk


class TestApplyPreloaderPatches(unittest.TestCase):
    """Tests for the _apply_preloader_patches method and its callers."""

    def _make_mtk_instance(self):
        """Create a minimal Mtk instance without full initialization."""
        with patch.object(Mtk, '__init__', lambda self, **kw: None):
            mtk = Mtk.__new__(Mtk)
        mtk.info = MagicMock()
        mtk.warning = MagicMock()
        return mtk

    def test_apply_patches_hex_pattern_found(self):
        """Test that hex string patches are applied when pattern is found."""
        mtk = self._make_mtk_instance()
        # "A3687BB12846" -> "0123A3602846" (oppo security patch)
        pattern_bytes = bytes.fromhex("A3687BB12846")
        data = b"\x00" * 10 + pattern_bytes + b"\x00" * 10
        patches = [("A3687BB12846", "0123A3602846", "oppo security")]

        result = mtk._apply_preloader_patches(data, patches)

        expected_patch = bytes.fromhex("0123A3602846")
        self.assertEqual(result[10:10 + len(expected_patch)], expected_patch)
        mtk.info.assert_called_once()
        mtk.warning.assert_not_called()

    def test_apply_patches_hex_pattern_not_found(self):
        """Test warning when no patches match."""
        mtk = self._make_mtk_instance()
        data = b"\x00" * 100
        patches = [("A3687BB12846", "0123A3602846", "oppo security")]

        result = mtk._apply_preloader_patches(data, patches)

        self.assertEqual(result, bytearray(data))
        mtk.warning.assert_called_once_with("Failed to patch preloader security")

    def test_apply_patches_binary_pattern_found(self):
        """Test that binary (regex-like) patches are applied when found."""
        mtk = self._make_mtk_instance()
        binary_pattern = b"\x14\x2C\xF6\xAB\xFE\xE7"
        replacement = b"\x00\x00\x00\x00\x00\x00"
        data = b"\xFF" * 5 + binary_pattern + b"\xFF" * 5
        patches = [(binary_pattern, replacement, "hash_check3")]

        result = mtk._apply_preloader_patches(data, patches)

        self.assertEqual(result[5:5 + len(replacement)], replacement)
        mtk.info.assert_called_once()

    def test_apply_patches_multiple_patches(self):
        """Test that multiple patches can be applied in one call."""
        mtk = self._make_mtk_instance()
        pattern1 = bytes.fromhex("A3687BB12846")
        pattern2 = bytes.fromhex("10B50C680268")
        data = bytearray(b"\x00" * 10 + pattern1 + b"\x00" * 10 + pattern2 + b"\x00" * 10)
        patches = [
            ("A3687BB12846", "0123A3602846", "oppo security"),
            ("10B50C680268", "10B5012010BD", "ram blacklist"),
        ]

        result = mtk._apply_preloader_patches(data, patches)

        expected1 = bytes.fromhex("0123A3602846")
        expected2 = bytes.fromhex("10B5012010BD")
        self.assertEqual(result[10:10 + len(expected1)], expected1)
        offset2 = 10 + len(pattern1) + 10
        self.assertEqual(result[offset2:offset2 + len(expected2)], expected2)
        self.assertEqual(mtk.info.call_count, 2)

    def test_da1_includes_extra_patches(self):
        """Test that DA1 includes the extra patches (hash_check, etc.)."""
        mtk = self._make_mtk_instance()
        # Create data containing a DA1-only pattern
        pattern = bytes.fromhex("040007C0")
        data = b"\x00" * 10 + pattern + b"\x00" * 10

        result_da1 = mtk.patch_preloader_security_da1(data)
        expected = bytes.fromhex("00000000")
        self.assertEqual(result_da1[10:10 + len(expected)], expected)

    def test_da2_does_not_include_da1_extra_patches(self):
        """Test that DA2 does NOT include the DA1-extra patches."""
        mtk = self._make_mtk_instance()
        # Create data containing a DA1-only pattern
        pattern = bytes.fromhex("040007C0")
        data = b"\x00" * 10 + pattern + b"\x00" * 10

        result_da2 = mtk.patch_preloader_security_da2(data)
        # DA2 should NOT patch this, so original data should remain
        self.assertEqual(result_da2[10:10 + len(pattern)], pattern)
        mtk.warning.assert_called_once()  # No patches matched

    def test_da1_and_da2_share_common_patches(self):
        """Test that both DA1 and DA2 apply common patches."""
        mtk = self._make_mtk_instance()
        # Create data with a common patch pattern
        pattern = bytes.fromhex("A3687BB12846")
        data = b"\x00" * 10 + pattern + b"\x00" * 10

        result_da1 = mtk.patch_preloader_security_da1(data)
        mtk_da2 = self._make_mtk_instance()
        result_da2 = mtk_da2.patch_preloader_security_da2(data)

        expected = bytes.fromhex("0123A3602846")
        self.assertEqual(result_da1[10:10 + len(expected)], expected)
        self.assertEqual(result_da2[10:10 + len(expected)], expected)

    def test_returns_bytearray(self):
        """Test that the result is always a bytearray."""
        mtk = self._make_mtk_instance()
        data = b"\x00" * 100
        result = mtk._apply_preloader_patches(data, [])
        self.assertIsInstance(result, bytearray)


class TestClassConstants(unittest.TestCase):
    """Test that class-level patch constants are properly defined."""

    def test_common_patches_defined(self):
        self.assertIsInstance(Mtk._COMMON_PATCHES, list)
        self.assertGreater(len(Mtk._COMMON_PATCHES), 0)

    def test_da1_extra_patches_defined(self):
        self.assertIsInstance(Mtk._DA1_EXTRA_PATCHES, list)
        self.assertGreater(len(Mtk._DA1_EXTRA_PATCHES), 0)

    def test_patches_are_tuples_of_three(self):
        for p in Mtk._COMMON_PATCHES + Mtk._DA1_EXTRA_PATCHES:
            self.assertEqual(len(p), 3, f"Patch {p[2]} should be a 3-tuple")

    def test_da1_extra_patches_not_in_common(self):
        """DA1 extra patches should be separate from common patches."""
        common_names = {p[2] for p in Mtk._COMMON_PATCHES}
        extra_names = {p[2] for p in Mtk._DA1_EXTRA_PATCHES}
        self.assertTrue(common_names.isdisjoint(extra_names))


if __name__ == '__main__':
    unittest.main()
