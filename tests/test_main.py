"""End-to-end tests for ``cli.main`` driven entirely by mocks.

These tests exercise the orchestration glue — argparse, connection bootstrap,
audio worker spawn, the video loop and shutdown — without touching pyvirtualcam,
PulseAudio, GStreamer or the network. The point is to lock the wiring against
regressions; runtime behaviour against a real Reachy is integration test territory.
"""

import threading
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from reachy_mini_cam_relay import cli


@pytest.fixture
def fake_frame() -> np.ndarray:
    return np.zeros((720, 1280, 3), dtype=np.uint8)


def _argv(extra: list[str] | None = None) -> list[str]:
    base = ["reachy-mini-cam-relay", "--reachy-host", "192.0.2.1"]
    return base + (extra or [])


def test_main_requires_reachy_host(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["reachy-mini-cam-relay"])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 2  # argparse usage error


def test_main_returns_0_when_initial_connect_aborts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys.argv", _argv())
    monkeypatch.setattr(cli, "_connect_with_backoff", lambda *_args, **_kw: None)

    assert cli.main() == 0


def test_main_returns_0_when_first_frame_never_arrives(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys.argv", _argv())

    media = MagicMock()
    # Simulate get_frame raising — main breaks out and returns 0.
    media.get_frame.side_effect = RuntimeError("pipeline died")
    monkeypatch.setattr(cli, "_connect_with_backoff", lambda *_args, **_kw: media)

    assert cli.main() == 0
    media.close.assert_called()  # cleanup path ran


def test_main_returns_0_when_stop_event_set_before_first_frame(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys.argv", _argv())

    # Stop the world: the very first call to get_frame returns None and the
    # signal handler sets stop_event so the wait loop exits.
    stop_holder = {}

    def fake_connect(*_args, **_kw) -> MagicMock:
        media = MagicMock()
        media.get_frame.side_effect = lambda: stop_holder["evt"].set() or None
        return media

    monkeypatch.setattr(cli, "_connect_with_backoff", fake_connect)

    real_event = threading.Event
    monkeypatch.setattr(
        cli.threading,
        "Event",
        lambda: stop_holder.setdefault("evt", real_event()),
    )

    assert cli.main() == 0


def test_main_happy_path_runs_video_loop_until_stopped(
    monkeypatch: pytest.MonkeyPatch, fake_frame: np.ndarray
) -> None:
    """Connect succeeds, video loop pumps a few frames, then SIGINT-equivalent
    stops it. Audio is disabled to keep this test focused on the video path
    (the worker loops have their own dedicated tests)."""
    monkeypatch.setattr("sys.argv", _argv(["--fps", "60", "--no-mic", "--no-speakers"]))

    media = MagicMock()
    media.get_frame.return_value = fake_frame

    monkeypatch.setattr(cli, "_connect_with_backoff", lambda *_a, **_kw: media)
    monkeypatch.setattr(cli, "_pactl_sinks", lambda: set())
    monkeypatch.setattr(cli.shutil, "which", lambda _name: None)

    sent_frames = {"n": 0}
    stop_after = 3
    fake_cam = MagicMock()
    fake_cam.device = "/dev/video10"

    def cam_send(_frame: np.ndarray) -> None:
        sent_frames["n"] += 1

    fake_cam.send.side_effect = cam_send

    captured: dict[str, threading.Event] = {}
    real_event_cls = threading.Event

    def event_factory() -> threading.Event:
        evt = real_event_cls()
        captured["stop_event"] = evt
        return evt

    monkeypatch.setattr(cli.threading, "Event", event_factory)

    def cam_sleep_until_next_frame() -> None:
        if sent_frames["n"] >= stop_after:
            captured["stop_event"].set()

    fake_cam.sleep_until_next_frame.side_effect = cam_sleep_until_next_frame

    fake_camera_cm = MagicMock()
    fake_camera_cm.__enter__.return_value = fake_cam
    fake_camera_cm.__exit__.return_value = None

    with patch.object(cli.pyvirtualcam, "Camera", return_value=fake_camera_cm):
        rc = cli.main()

    assert rc == 0
    assert sent_frames["n"] >= stop_after
    fake_camera_cm.__enter__.assert_called_once()
    fake_camera_cm.__exit__.assert_called_once()


def test_main_spawns_and_terminates_audio_subprocesses(
    monkeypatch: pytest.MonkeyPatch, fake_frame: np.ndarray
) -> None:
    """When the virtual mic + speakers sinks exist, main() must spawn pacat and
    parec, then on shutdown close stdin, terminate and wait on each. We mock
    the worker loops to no-ops and exit the video loop by raising from
    cam.sleep_until_next_frame so the test doesn't depend on patching
    threading.Event (which has subtle interactions with daemon threads)."""
    monkeypatch.setattr("sys.argv", _argv())
    monkeypatch.setattr(cli, "_mic_loop", lambda *_a, **_kw: None)
    monkeypatch.setattr(cli, "_speakers_loop", lambda *_a, **_kw: None)

    media = MagicMock()
    media.get_frame.return_value = fake_frame
    monkeypatch.setattr(cli, "_connect_with_backoff", lambda *_a, **_kw: media)
    monkeypatch.setattr(cli, "_pactl_sinks", lambda: {cli.MIC_SINK, cli.SPEAKERS_SINK})
    monkeypatch.setattr(cli.shutil, "which", lambda name: f"/usr/bin/{name}")

    spawned: list[MagicMock] = []

    def fake_popen(*_a: object, **_kw: object) -> MagicMock:
        proc = MagicMock()
        proc.stdin = MagicMock()
        proc.stdout = MagicMock()
        spawned.append(proc)
        return proc

    monkeypatch.setattr(cli.subprocess, "Popen", fake_popen)

    class _StopVideo(Exception):
        pass

    fake_cam = MagicMock()
    fake_cam.device = "/dev/video10"
    fake_cam.sleep_until_next_frame.side_effect = _StopVideo()

    fake_camera_cm = MagicMock()
    fake_camera_cm.__enter__.return_value = fake_cam
    fake_camera_cm.__exit__.return_value = None

    with patch.object(cli.pyvirtualcam, "Camera", return_value=fake_camera_cm):
        with pytest.raises(_StopVideo):
            cli.main()

    # Both subprocesses must be terminated, regardless of how the loop exited.
    assert len(spawned) == 2
    for proc in spawned:
        proc.terminate.assert_called()
        proc.wait.assert_called()


def test_main_kills_proc_when_terminate_times_out(
    monkeypatch: pytest.MonkeyPatch, fake_frame: np.ndarray
) -> None:
    """If ``proc.wait(timeout=2)`` raises ``TimeoutExpired``, fallback to ``kill``."""
    import subprocess as _sp

    monkeypatch.setattr("sys.argv", _argv())
    monkeypatch.setattr(cli, "_mic_loop", lambda *_a, **_kw: None)
    monkeypatch.setattr(cli, "_speakers_loop", lambda *_a, **_kw: None)

    media = MagicMock()
    media.get_frame.return_value = fake_frame
    monkeypatch.setattr(cli, "_connect_with_backoff", lambda *_a, **_kw: media)
    monkeypatch.setattr(cli, "_pactl_sinks", lambda: {cli.MIC_SINK, cli.SPEAKERS_SINK})
    monkeypatch.setattr(cli.shutil, "which", lambda name: f"/usr/bin/{name}")

    spawned: list[MagicMock] = []

    def fake_popen(*_a: object, **_kw: object) -> MagicMock:
        proc = MagicMock()
        proc.stdin = MagicMock()
        proc.stdout = MagicMock()
        proc.wait.side_effect = _sp.TimeoutExpired(cmd="x", timeout=2)
        spawned.append(proc)
        return proc

    monkeypatch.setattr(cli.subprocess, "Popen", fake_popen)

    class _StopVideo(Exception):
        pass

    fake_cam = MagicMock()
    fake_cam.device = "/dev/video10"
    fake_cam.sleep_until_next_frame.side_effect = _StopVideo()

    fake_camera_cm = MagicMock()
    fake_camera_cm.__enter__.return_value = fake_cam
    fake_camera_cm.__exit__.return_value = None

    with patch.object(cli.pyvirtualcam, "Camera", return_value=fake_camera_cm):
        with pytest.raises(_StopVideo):
            cli.main()

    for proc in spawned:
        proc.kill.assert_called()


def test_main_warns_and_continues_when_audio_sinks_missing(
    monkeypatch: pytest.MonkeyPatch,
    fake_frame: np.ndarray,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """No virtual mic/speakers sinks → both warnings printed, no Popen calls."""
    monkeypatch.setattr("sys.argv", _argv())

    media = MagicMock()
    media.get_frame.return_value = fake_frame
    monkeypatch.setattr(cli, "_connect_with_backoff", lambda *_a, **_kw: media)
    monkeypatch.setattr(cli, "_pactl_sinks", lambda: set())  # no sinks
    monkeypatch.setattr(cli.shutil, "which", lambda name: f"/usr/bin/{name}")

    popen_called = {"n": 0}

    def fake_popen(*_args: object, **_kw: object) -> MagicMock:
        popen_called["n"] += 1
        return MagicMock()

    monkeypatch.setattr(cli.subprocess, "Popen", fake_popen)

    # Stop loop after one frame.
    captured: dict[str, threading.Event] = {}
    real_event_cls = threading.Event

    def event_factory() -> threading.Event:
        evt = real_event_cls()
        captured["stop_event"] = evt
        return evt

    monkeypatch.setattr(cli.threading, "Event", event_factory)

    fake_cam = MagicMock()
    fake_cam.device = "/dev/video10"
    fake_cam.sleep_until_next_frame.side_effect = lambda: captured[
        "stop_event"
    ].set()
    fake_camera_cm = MagicMock()
    fake_camera_cm.__enter__.return_value = fake_cam
    fake_camera_cm.__exit__.return_value = None

    with patch.object(cli.pyvirtualcam, "Camera", return_value=fake_camera_cm):
        rc = cli.main()

    assert rc == 0
    assert popen_called["n"] == 0  # no audio subprocess spawned
    err = capsys.readouterr().err
    assert "mic sink" in err
    assert "speakers sink" in err


def test_main_skips_frame_with_unexpected_resolution(
    monkeypatch: pytest.MonkeyPatch,
    fake_frame: np.ndarray,
) -> None:
    """If the daemon ever returns a frame whose shape != the v4l2 device's,
    that frame must be dropped (not crash on cam.send)."""
    monkeypatch.setattr("sys.argv", _argv(["--no-mic", "--no-speakers"]))

    bad_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    frames_iter = iter([fake_frame, bad_frame, fake_frame])

    media = MagicMock()
    media.get_frame.side_effect = lambda: next(frames_iter, None)
    monkeypatch.setattr(cli, "_connect_with_backoff", lambda *_a, **_kw: media)
    monkeypatch.setattr(cli, "_pactl_sinks", lambda: set())
    monkeypatch.setattr(cli.shutil, "which", lambda _name: None)

    captured: dict[str, threading.Event] = {}
    real_event_cls = threading.Event

    def event_factory() -> threading.Event:
        evt = real_event_cls()
        captured["stop_event"] = evt
        return evt

    monkeypatch.setattr(cli.threading, "Event", event_factory)

    sent = {"frames": []}
    fake_cam = MagicMock()
    fake_cam.device = "/dev/video10"
    fake_cam.send.side_effect = lambda f: sent["frames"].append(f.shape)

    iterations = {"n": 0}

    def stop_after_a_few() -> None:
        iterations["n"] += 1
        if iterations["n"] >= 4:
            captured["stop_event"].set()

    fake_cam.sleep_until_next_frame.side_effect = stop_after_a_few
    fake_camera_cm = MagicMock()
    fake_camera_cm.__enter__.return_value = fake_cam
    fake_camera_cm.__exit__.return_value = None

    with patch.object(cli.pyvirtualcam, "Camera", return_value=fake_camera_cm):
        cli.main()

    # We never sent the (480, 640, 3) frame — only the matching-resolution ones.
    assert all(shape == fake_frame.shape for shape in sent["frames"])


def test_main_reconnects_after_no_frame_timeout(
    monkeypatch: pytest.MonkeyPatch, fake_frame: np.ndarray
) -> None:
    """Connection drops mid-stream: get_frame returns None for >timeout, the
    main loop closes the session, and ``_connect_with_backoff`` is called
    again to recover."""
    monkeypatch.setattr("sys.argv", _argv(["--no-mic", "--no-speakers"]))
    monkeypatch.setattr(cli, "NO_FRAME_TIMEOUT_S", 0.0)  # any None triggers retry
    monkeypatch.setattr(cli, "_pactl_sinks", lambda: set())
    monkeypatch.setattr(cli.shutil, "which", lambda _name: None)

    media_a = MagicMock(name="media_a")
    media_a.get_frame.side_effect = [fake_frame, None, None]
    media_b = MagicMock(name="media_b")
    media_b.get_frame.return_value = fake_frame

    connect_calls: list[MagicMock] = []

    def fake_connect(*_args: object, **_kw: object) -> MagicMock:
        next_media = media_b if connect_calls else media_a
        connect_calls.append(next_media)
        return next_media

    monkeypatch.setattr(cli, "_connect_with_backoff", fake_connect)

    captured: dict[str, threading.Event] = {}
    real_event_cls = threading.Event

    def event_factory() -> threading.Event:
        evt = real_event_cls()
        captured["stop_event"] = evt
        return evt

    monkeypatch.setattr(cli.threading, "Event", event_factory)

    fake_cam = MagicMock()
    fake_cam.device = "/dev/video10"
    iterations = {"n": 0}

    def stop_when_recovered() -> None:
        iterations["n"] += 1
        if iterations["n"] >= 5:
            captured["stop_event"].set()

    fake_cam.sleep_until_next_frame.side_effect = stop_when_recovered
    fake_camera_cm = MagicMock()
    fake_camera_cm.__enter__.return_value = fake_cam
    fake_camera_cm.__exit__.return_value = None

    with patch.object(cli.pyvirtualcam, "Camera", return_value=fake_camera_cm):
        cli.main()

    # Two connection attempts: the initial one + the reconnect after timeout.
    assert len(connect_calls) >= 2
    media_a.close.assert_called()  # first session was cleaned up


def test_main_treats_get_frame_exception_as_missing_frame(
    monkeypatch: pytest.MonkeyPatch, fake_frame: np.ndarray
) -> None:
    """``get_frame`` raising mid-stream must be caught: frame becomes None and
    the no-frame handling path runs (reuse last_frame, eventually reconnect)."""
    monkeypatch.setattr("sys.argv", _argv(["--no-mic", "--no-speakers"]))
    monkeypatch.setattr(cli, "NO_FRAME_TIMEOUT_S", 0.0)
    monkeypatch.setattr(cli, "_pactl_sinks", lambda: set())
    monkeypatch.setattr(cli.shutil, "which", lambda _name: None)

    media_a = MagicMock(name="media_a")
    media_a.get_frame.side_effect = [fake_frame, RuntimeError("pipeline broke")]
    media_b = MagicMock(name="media_b")
    media_b.get_frame.return_value = fake_frame

    connect_calls: list[MagicMock] = []

    def fake_connect(*_args: object, **_kw: object) -> MagicMock:
        next_media = media_b if connect_calls else media_a
        connect_calls.append(next_media)
        return next_media

    monkeypatch.setattr(cli, "_connect_with_backoff", fake_connect)

    class _StopVideo(Exception):
        pass

    fake_cam = MagicMock()
    fake_cam.device = "/dev/video10"
    iterations = {"n": 0}

    def stop_after_recovery() -> None:
        iterations["n"] += 1
        if iterations["n"] >= 4:
            raise _StopVideo()

    fake_cam.sleep_until_next_frame.side_effect = stop_after_recovery
    fake_camera_cm = MagicMock()
    fake_camera_cm.__enter__.return_value = fake_cam
    fake_camera_cm.__exit__.return_value = None

    with patch.object(cli.pyvirtualcam, "Camera", return_value=fake_camera_cm):
        with pytest.raises(_StopVideo):
            cli.main()

    assert len(connect_calls) >= 2  # the get_frame exception triggered a reconnect


def test_main_swallows_exception_from_proc_stdin_close(
    monkeypatch: pytest.MonkeyPatch, fake_frame: np.ndarray
) -> None:
    """If ``proc.stdin.close()`` itself raises during cleanup, it must be
    caught so the rest of the shutdown can proceed (terminate, wait, kill)."""
    monkeypatch.setattr("sys.argv", _argv())
    monkeypatch.setattr(cli, "_mic_loop", lambda *_a, **_kw: None)
    monkeypatch.setattr(cli, "_speakers_loop", lambda *_a, **_kw: None)

    media = MagicMock()
    media.get_frame.return_value = fake_frame
    monkeypatch.setattr(cli, "_connect_with_backoff", lambda *_a, **_kw: media)
    monkeypatch.setattr(cli, "_pactl_sinks", lambda: {cli.MIC_SINK, cli.SPEAKERS_SINK})
    monkeypatch.setattr(cli.shutil, "which", lambda name: f"/usr/bin/{name}")

    def fake_popen(*_a: object, **_kw: object) -> MagicMock:
        proc = MagicMock()
        proc.stdin = MagicMock()
        proc.stdin.close.side_effect = OSError("already closed by peer")
        proc.stdout = MagicMock()
        return proc

    monkeypatch.setattr(cli.subprocess, "Popen", fake_popen)

    class _StopVideo(Exception):
        pass

    fake_cam = MagicMock()
    fake_cam.device = "/dev/video10"
    fake_cam.sleep_until_next_frame.side_effect = _StopVideo()

    fake_camera_cm = MagicMock()
    fake_camera_cm.__enter__.return_value = fake_cam
    fake_camera_cm.__exit__.return_value = None

    with patch.object(cli.pyvirtualcam, "Camera", return_value=fake_camera_cm):
        # The OSError from stdin.close() must NOT propagate — only _StopVideo
        # (raised by sleep_until_next_frame) should escape.
        with pytest.raises(_StopVideo):
            cli.main()


def test_main_signal_handler_announces_shutdown_only_once(
    monkeypatch: pytest.MonkeyPatch, fake_frame: np.ndarray
) -> None:
    """SIGINT/SIGTERM may fire multiple times during shutdown — the user-facing
    ``shutting down…`` notice must only print once."""
    monkeypatch.setattr("sys.argv", _argv(["--no-mic", "--no-speakers"]))

    captured_handler: dict[str, object] = {}

    def fake_signal_signal(signum: int, handler: object) -> None:
        captured_handler[f"sig_{signum}"] = handler

    monkeypatch.setattr(cli.signal, "signal", fake_signal_signal)

    media = MagicMock()
    media.get_frame.return_value = fake_frame
    monkeypatch.setattr(cli, "_connect_with_backoff", lambda *_a, **_kw: media)
    monkeypatch.setattr(cli, "_pactl_sinks", lambda: set())
    monkeypatch.setattr(cli.shutil, "which", lambda _name: None)

    captured: dict[str, threading.Event] = {}
    real_event_cls = threading.Event

    def event_factory() -> threading.Event:
        evt = real_event_cls()
        captured["stop_event"] = evt
        return evt

    monkeypatch.setattr(cli.threading, "Event", event_factory)

    fake_cam = MagicMock()
    fake_cam.device = "/dev/video10"

    def fire_signals_then_stop() -> None:
        # Re-fire the handler twice to verify single-print behaviour.
        handler = captured_handler["sig_2"]  # SIGINT = 2
        assert callable(handler)
        handler(2, None)  # type: ignore[operator]
        handler(2, None)  # type: ignore[operator]

    fake_cam.sleep_until_next_frame.side_effect = fire_signals_then_stop
    fake_camera_cm = MagicMock()
    fake_camera_cm.__enter__.return_value = fake_cam
    fake_camera_cm.__exit__.return_value = None

    with patch.object(cli.pyvirtualcam, "Camera", return_value=fake_camera_cm):
        cli.main()

    # The shutdown handler was wired for both SIGINT and SIGTERM.
    assert "sig_2" in captured_handler
    assert "sig_15" in captured_handler
