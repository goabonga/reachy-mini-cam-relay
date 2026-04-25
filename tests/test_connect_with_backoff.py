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

    def flaky(_host: str, _head_track: bool) -> object:
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise RuntimeError("transient network glitch")
        return (f"media-{attempts['n']}", "reachy")

    monkeypatch.setattr(cli, "_connect", flaky)

    stop = threading.Event()
    monkeypatch.setattr(stop, "wait", lambda _delay: False)

    media, reachy = cli._connect_with_backoff("h", False, stop)

    assert media == "media-3"
    assert reachy == "reachy"
    assert attempts["n"] == 3


def test_connect_without_head_track_calls_media_manager(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cover the standalone-MediaManager branch of ``_connect``."""
    captured: dict[str, object] = {}

    class FakeMediaManager:
        def __init__(self, *, backend: object, signalling_host: str) -> None:
            captured["backend"] = backend
            captured["signalling_host"] = signalling_host

    monkeypatch.setattr(cli, "MediaManager", FakeMediaManager)

    media, reachy = cli._connect("the-reachy", False)

    assert isinstance(media, FakeMediaManager)
    assert reachy is None
    assert captured["signalling_host"] == "the-reachy"
    assert captured["backend"] is cli.MediaBackend.WEBRTC


def test_connect_with_head_track_constructs_reachy_mini(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cover the ``head_track=True`` branch — must build a ReachyMini and
    return its media_manager paired with the instance."""
    captured: dict[str, object] = {}

    class FakeReachyMini:
        def __init__(self, *, host: str, connection_mode: str, media_backend: str) -> None:
            captured["host"] = host
            captured["connection_mode"] = connection_mode
            captured["media_backend"] = media_backend
            self.media_manager = "media-from-reachy"

    # ``cli._connect`` does ``from reachy_mini import ReachyMini`` lazily, so
    # we patch the actual module attribute that the import resolves to.
    import reachy_mini

    monkeypatch.setattr(reachy_mini, "ReachyMini", FakeReachyMini)

    media, reachy = cli._connect("the-reachy", True)

    assert media == "media-from-reachy"
    assert isinstance(reachy, FakeReachyMini)
    assert captured == {
        "host": "the-reachy",
        "connection_mode": "network",
        "media_backend": "webrtc",
    }
