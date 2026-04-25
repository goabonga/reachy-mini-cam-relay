"""Tests for the reconnection backoff loop (head-tracking variant)."""

import threading

import pytest

from reachy_mini_cam_relay import cli


def test_returns_pair_on_first_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        cli, "_connect", lambda host, head_track: (f"connected:{host}", "reachy")
    )
    stop = threading.Event()

    media, reachy = cli._connect_with_backoff("the-host", False, stop)

    assert media == "connected:the-host"
    assert reachy == "reachy"


def test_returns_none_pair_when_stop_event_set_before_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def must_not_call(_host: str, _head_track: bool) -> object:
        raise AssertionError("connect should not be invoked once stop is set")

    monkeypatch.setattr(cli, "_connect", must_not_call)

    stop = threading.Event()
    stop.set()
    assert cli._connect_with_backoff("h", False, stop) == (None, None)


def test_aborts_on_stop_event_during_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    """Failures should retry, but a stop_event mid-wait must short-circuit."""
    attempts = {"n": 0}

    def always_fails(_host: str, _head_track: bool) -> object:
        attempts["n"] += 1
        raise RuntimeError("nope")

    monkeypatch.setattr(cli, "_connect", always_fails)

    stop = threading.Event()
    monkeypatch.setattr(stop, "wait", lambda _delay: True)

    media, reachy = cli._connect_with_backoff("h", True, stop)

    assert media is None
    assert reachy is None
    assert attempts["n"] == 1


def test_backoff_table_is_monotonic_and_capped() -> None:
    backoff = cli.RECONNECT_BACKOFF_S
    assert backoff[0] >= 1.0
    assert backoff == tuple(sorted(backoff))
    assert backoff[-1] >= 30.0


def test_retries_until_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Exercise the post-failure increment + retry path."""
    attempts = {"n": 0}

    def flaky(_host: str) -> object:
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise RuntimeError("transient network glitch")
        return f"connected-after-{attempts['n']}"

    monkeypatch.setattr(cli, "_connect", flaky)

    stop = threading.Event()
    # Don't actually wait between attempts.
    monkeypatch.setattr(stop, "wait", lambda _delay: False)

    media = cli._connect_with_backoff("h", stop)

    assert media == "connected-after-3"
    assert attempts["n"] == 3


def test_connect_calls_media_manager(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cover the body of ``_connect`` — that it actually constructs a
    ``MediaManager`` with the right arguments."""
    captured = {}

    class FakeMediaManager:
        def __init__(self, *, backend: object, signalling_host: str) -> None:
            captured["backend"] = backend
            captured["signalling_host"] = signalling_host

    monkeypatch.setattr(cli, "MediaManager", FakeMediaManager)

    result = cli._connect("the-reachy")

    assert isinstance(result, FakeMediaManager)
    assert captured["signalling_host"] == "the-reachy"
    assert captured["backend"] is cli.MediaBackend.WEBRTC
