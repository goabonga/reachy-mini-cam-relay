"""Tests for ``cli._close`` — must always be a no-op-or-clean shutdown.

The head-tracking variant takes both a ``media`` and a ``reachy`` handle: when
a ReachyMini instance owns the connection we call its ``__exit__`` (so it both
closes the media manager and disconnects the WebSocket client), otherwise we
just close the standalone ``media``.
"""

from unittest.mock import MagicMock

from reachy_mini_cam_relay import cli


def test_close_none_is_noop() -> None:
    cli._close(None, None)  # must not raise


def test_close_calls_media_close_when_no_reachy() -> None:
    media = MagicMock()
    cli._close(media, None)
    media.close.assert_called_once_with()


def test_close_swallows_exceptions_from_media() -> None:
    media = MagicMock()
    media.close.side_effect = RuntimeError("daemon already disconnected")
    cli._close(media, None)  # must not propagate


def test_close_calls_reachy_exit_and_skips_media() -> None:
    media = MagicMock()
    reachy = MagicMock()
    cli._close(media, reachy)
    reachy.__exit__.assert_called_once_with(None, None, None)
    media.close.assert_not_called()


def test_close_swallows_exceptions_from_reachy() -> None:
    reachy = MagicMock()
    reachy.__exit__.side_effect = RuntimeError("daemon WS already closed")
    cli._close(None, reachy)  # must not propagate
