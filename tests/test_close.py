"""Tests for ``cli._close`` — must always be a no-op-or-clean shutdown."""

from unittest.mock import MagicMock

from reachy_mini_cam_relay import cli


def test_close_none_is_noop() -> None:
    cli._close(None)  # must not raise


def test_close_calls_media_close() -> None:
    media = MagicMock()
    cli._close(media)
    media.close.assert_called_once_with()


def test_close_swallows_exceptions_from_media() -> None:
    media = MagicMock()
    media.close.side_effect = RuntimeError("daemon already disconnected")
    cli._close(media)  # must not propagate
