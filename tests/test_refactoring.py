#!/usr/bin/env python3
"""Tests for ArgHandler refactoring in mtk_main.py."""
import unittest
from unittest.mock import MagicMock, patch
from types import SimpleNamespace
from mtkclient.Library.mtk_main import ArgHandler


class TestSafeGetArg(unittest.TestCase):
    """Tests for the _safe_get_arg static method."""

    def test_returns_existing_attribute(self):
        args = SimpleNamespace(vid="0x0E8D")
        result = ArgHandler._safe_get_arg(args, "vid")
        self.assertEqual(result, "0x0E8D")

    def test_returns_default_for_missing_attribute(self):
        args = SimpleNamespace()
        result = ArgHandler._safe_get_arg(args, "vid")
        self.assertIsNone(result)

    def test_returns_custom_default_for_missing_attribute(self):
        args = SimpleNamespace()
        result = ArgHandler._safe_get_arg(args, "vid", 42)
        self.assertEqual(result, 42)

    def test_returns_default_for_none_value(self):
        args = SimpleNamespace(vid=None)
        result = ArgHandler._safe_get_arg(args, "vid", "default")
        self.assertEqual(result, "default")

    def test_returns_false_when_value_is_false(self):
        args = SimpleNamespace(stock=False)
        result = ArgHandler._safe_get_arg(args, "stock", True)
        self.assertFalse(result)

    def test_returns_zero_when_value_is_zero(self):
        """Zero is falsy but not None, should be returned."""
        args = SimpleNamespace(gpt_num_part_entries=0)
        result = ArgHandler._safe_get_arg(args, "gpt_num_part_entries", 99)
        self.assertEqual(result, 0)

    def test_returns_empty_string_as_default(self):
        args = SimpleNamespace(name=None)
        result = ArgHandler._safe_get_arg(args, "name", "")
        self.assertEqual(result, "")


class TestArgHandlerInit(unittest.TestCase):
    """Tests for ArgHandler initialization with various arg combinations."""

    def _make_config(self):
        """Create a config-like object that records attribute assignments."""
        config = SimpleNamespace()
        config.loglevel = 20  # logging.INFO
        config.gui = None
        config.chipconfig = SimpleNamespace(
            da_payload_addr=None,
            brom_payload_addr=None,
            watchdog=None,
            uart=None,
            var1=None,
        )
        return config

    def _make_minimal_args(self):
        """Create a minimal args namespace (simulating a command with no optional args)."""
        return SimpleNamespace(cmd="rf")

    @patch('mtkclient.Library.mtk_main.logsetup')
    def test_init_with_minimal_args(self, mock_logsetup):
        """ArgHandler should handle args with no optional attributes."""
        mock_logsetup.return_value = (MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        config = self._make_config()
        args = self._make_minimal_args()

        # Should not raise any exception
        handler = ArgHandler(args, config)
        self.assertIsNotNone(handler)

    @patch('mtkclient.Library.mtk_main.logsetup')
    def test_vid_pid_set_correctly(self, mock_logsetup):
        """ArgHandler should set config.vid and config.pid from args."""
        mock_logsetup.return_value = (MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        config = self._make_config()
        args = SimpleNamespace(cmd="rf", vid="0x0E8D", pid="0x0003")

        ArgHandler(args, config)

        self.assertEqual(config.vid, 0x0E8D)
        self.assertEqual(config.pid, 0x0003)

    @patch('mtkclient.Library.mtk_main.logsetup')
    def test_stock_default_is_false(self, mock_logsetup):
        """ArgHandler should set config.stock to False by default."""
        mock_logsetup.return_value = (MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        config = self._make_config()
        args = SimpleNamespace(cmd="rf")

        ArgHandler(args, config)

        self.assertFalse(config.stock)

    @patch('mtkclient.Library.mtk_main.logsetup')
    def test_reconnect_default_is_true(self, mock_logsetup):
        """ArgHandler should set config.reconnect to True by default."""
        mock_logsetup.return_value = (MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        config = self._make_config()
        args = SimpleNamespace(cmd="rf")

        ArgHandler(args, config)

        self.assertTrue(config.reconnect)

    @patch('mtkclient.Library.mtk_main.logsetup')
    def test_noreconnect_inverts_reconnect(self, mock_logsetup):
        """ArgHandler should set config.reconnect to False when noreconnect is True."""
        mock_logsetup.return_value = (MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        config = self._make_config()
        args = SimpleNamespace(cmd="rf", noreconnect=True)

        ArgHandler(args, config)

        self.assertFalse(config.reconnect)


class TestStage2Constants(unittest.TestCase):
    """Test that stage2 protocol constants are properly defined."""

    def test_constants_exist(self):
        from stage2 import (STAGE2_MAGIC, CMD_WRITE, CMD_JUMP, CMD_READ,
                            CMD_CLEAR_CACHE, CMD_EMMC_READ, CMD_EMMC_SWITCH,
                            CMD_RPMB_READ, CMD_REBOOT, CMD_EMMC_INIT,
                            CMD_EMMC_INIT_ALT, ACK_OK, ACK_EMMC_INIT_OK)
        self.assertEqual(STAGE2_MAGIC, 0xf00dd00d)
        self.assertEqual(CMD_WRITE, 0x4000)
        self.assertEqual(CMD_JUMP, 0x4001)
        self.assertEqual(CMD_READ, 0x4002)
        self.assertEqual(CMD_CLEAR_CACHE, 0x5000)
        self.assertEqual(CMD_EMMC_READ, 0x1000)
        self.assertEqual(CMD_EMMC_SWITCH, 0x1002)
        self.assertEqual(CMD_RPMB_READ, 0x2000)
        self.assertEqual(CMD_REBOOT, 0x3000)
        self.assertEqual(CMD_EMMC_INIT, 0x6000)
        self.assertEqual(CMD_EMMC_INIT_ALT, 0x6001)
        self.assertEqual(ACK_OK, 0xD0D0D0D0)
        self.assertEqual(ACK_EMMC_INIT_OK, 0xD1D1D1D1)


class TestStage2Getint(unittest.TestCase):
    """Test the getint utility function in stage2.py."""

    def test_decimal_string(self):
        from stage2 import getint
        self.assertEqual(getint("42"), 42)

    def test_hex_string(self):
        from stage2 import getint
        self.assertEqual(getint("0xFF"), 255)

    def test_empty_string(self):
        from stage2 import getint
        self.assertIsNone(getint(""))

    def test_invalid_string(self):
        from stage2 import getint
        self.assertEqual(getint("not_a_number"), 0)


if __name__ == '__main__':
    unittest.main()
