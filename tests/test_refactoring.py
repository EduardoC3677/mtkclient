#!/usr/bin/env python3
"""Tests for the refactored mtk_api_base module and mtk_class patch consolidation.

These tests run in subprocesses to avoid stdout buffer detachment caused
by the LogBase metaclass and colorama initialization.
"""
import subprocess
import pathlib
import sys
import unittest


def _run_snippet(code: str) -> subprocess.CompletedProcess:
    """Run a Python snippet in a subprocess and return the result."""
    return subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True,
        cwd=str(pathlib.Path(__file__).resolve().parent.parent)
    )


class TestMtkApiBase(unittest.TestCase):
    """Verify that mtk_api_base exports the shared init and connect functions."""

    def test_module_has_init(self):
        r = _run_snippet("import sys; sys.path.insert(0,'.'); from mtk_api_base import init; print('OK')")
        self.assertIn("OK", r.stdout, r.stderr)

    def test_module_has_connect(self):
        r = _run_snippet("import sys; sys.path.insert(0,'.'); from mtk_api_base import connect; print('OK')")
        self.assertIn("OK", r.stdout, r.stderr)

    def test_mtk_api_reexports(self):
        r = _run_snippet(
            "import sys; sys.path.insert(0,'.');"
            "import mtk_api, mtk_api_base;"
            "assert mtk_api.init is mtk_api_base.init;"
            "assert mtk_api.connect is mtk_api_base.connect;"
            "print('OK')"
        )
        self.assertIn("OK", r.stdout, r.stderr)

    def test_mtk_iot_api_reexports(self):
        r = _run_snippet(
            "import sys; sys.path.insert(0,'.');"
            "import mtk_iot_api, mtk_api_base;"
            "assert mtk_iot_api.init is mtk_api_base.init;"
            "assert mtk_iot_api.connect is mtk_api_base.connect;"
            "print('OK')"
        )
        self.assertIn("OK", r.stdout, r.stderr)


class TestPatchConsolidation(unittest.TestCase):
    """Verify the unified _apply_patches logic in Mtk class."""

    def test_base_patches_count(self):
        r = _run_snippet(
            "from mtkclient.Library.mtk_class import Mtk;"
            "assert len(Mtk._BASE_PATCHES) == 8;"
            "print('OK')"
        )
        self.assertIn("OK", r.stdout, r.stderr)

    def test_hash_check_patches_count(self):
        r = _run_snippet(
            "from mtkclient.Library.mtk_class import Mtk;"
            "assert len(Mtk._HASH_CHECK_PATCHES) == 3;"
            "print('OK')"
        )
        self.assertIn("OK", r.stdout, r.stderr)

    def test_da1_uses_all_11_patches(self):
        r = _run_snippet(
            "from mtkclient.Library.mtk_class import Mtk;"
            "assert len(Mtk._BASE_PATCHES + Mtk._HASH_CHECK_PATCHES) == 11;"
            "print('OK')"
        )
        self.assertIn("OK", r.stdout, r.stderr)

    def test_apply_patches_hex_pattern(self):
        r = _run_snippet("""
from mtkclient.Library.mtk_class import Mtk
class FakeMtk:
    _apply_patches = Mtk._apply_patches
    def info(self, msg): pass
    def warning(self, msg): pass
fake = FakeMtk()
pattern = bytes.fromhex("10B50C680268")
data = b"\\x00" * 16 + pattern + b"\\x00" * 16
patches = [("10B50C680268", "10B5012010BD", "ram blacklist")]
result = fake._apply_patches(data, patches)
expected = bytes.fromhex("10B5012010BD")
assert result[16:16 + len(expected)] == expected, f"Got {result[16:16+len(expected)].hex()}"
print('OK')
""")
        self.assertIn("OK", r.stdout, r.stderr)

    def test_apply_patches_no_match_warns(self):
        r = _run_snippet("""
from mtkclient.Library.mtk_class import Mtk
warnings = []
class FakeMtk:
    _apply_patches = Mtk._apply_patches
    def info(self, msg): pass
    def warning(self, msg): warnings.append(msg)
fake = FakeMtk()
data = b"\\x00" * 64
patches = [("DEADBEEF", "00000000", "nonexistent")]
fake._apply_patches(data, patches)
assert len(warnings) == 1
assert "Failed to patch" in warnings[0]
print('OK')
""")
        self.assertIn("OK", r.stdout, r.stderr)


class TestSplitByN(unittest.TestCase):
    """Verify split_by_n was moved to utils.py."""

    def test_split_by_n_in_utils(self):
        r = _run_snippet(
            "from mtkclient.Library.utils import split_by_n;"
            "assert callable(split_by_n);"
            "print('OK')"
        )
        self.assertIn("OK", r.stdout, r.stderr)

    def test_split_by_n_basic(self):
        r = _run_snippet(
            "from mtkclient.Library.utils import split_by_n;"
            "result = list(split_by_n([1,2,3,4,5], 2));"
            "assert result == [[1,2],[3,4],[5]], result;"
            "print('OK')"
        )
        self.assertIn("OK", r.stdout, r.stderr)

    def test_split_by_n_exact(self):
        r = _run_snippet(
            "from mtkclient.Library.utils import split_by_n;"
            "result = list(split_by_n('abcdef', 3));"
            "assert result == ['abc','def'], result;"
            "print('OK')"
        )
        self.assertIn("OK", r.stdout, r.stderr)

    def test_split_by_n_empty(self):
        r = _run_snippet(
            "from mtkclient.Library.utils import split_by_n;"
            "result = list(split_by_n([], 3));"
            "assert result == [], result;"
            "print('OK')"
        )
        self.assertIn("OK", r.stdout, r.stderr)

    def test_split_by_n_not_in_mtk_class(self):
        r = _run_snippet(
            "import types;"
            "import mtkclient.Library.mtk_class as mc;"
            "has = hasattr(mc, 'split_by_n') and isinstance(getattr(mc, 'split_by_n', None), types.FunctionType);"
            "assert not has, 'split_by_n should not be a module-level function in mtk_class';"
            "print('OK')"
        )
        self.assertIn("OK", r.stdout, r.stderr)


if __name__ == "__main__":
    unittest.main()
