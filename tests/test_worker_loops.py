"""Tests for the mic and speakers background worker loops (head-tracking variant)."""

import threading
from unittest.mock import MagicMock

import numpy as np
import pytest

from reachy_mini_cam_relay import cli


def _make_proc(stdin: MagicMock | None = None, stdout: MagicMock | None = None) -> MagicMock:
    proc = MagicMock()
    proc.stdin = stdin
    proc.stdout = stdout
    return proc


def test_mic_loop_pushes_silence_when_session_has_no_media(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = cli.Session()  # media is None — disconnected state
    stdin = MagicMock()

    stop = threading.Event()

    def stop_then_succeed(_payload: bytes) -> None:
        stop.set()

    stdin.write.side_effect = stop_then_succeed
    monkeypatch.setattr(stop, "wait", lambda _delay: True)

    cli._mic_loop(session, _make_proc(stdin=stdin), stop)

    stdin.write.assert_called_once()
    written = stdin.write.call_args[0][0]
    assert written == cli.SILENCE_CHUNK.tobytes()


def test_mic_loop_forwards_real_samples(monkeypatch: pytest.MonkeyPatch) -> None:
    session = cli.Session()
    media = MagicMock()
    samples = np.ones((cli.AUDIO_CHUNK_SAMPLES, cli.AUDIO_CHANNELS), dtype=np.float32)
    media.get_audio_sample.return_value = samples
    session.set(media, None)

    stdin = MagicMock()
    stop = threading.Event()

    def stop_then_succeed(_payload: bytes) -> None:
        stop.set()

    stdin.write.side_effect = stop_then_succeed

    cli._mic_loop(session, _make_proc(stdin=stdin), stop)

    stdin.write.assert_called_once_with(samples.tobytes())


def test_mic_loop_returns_on_broken_pipe() -> None:
    session = cli.Session()
    stdin = MagicMock()
    stdin.write.side_effect = BrokenPipeError()
    stop = threading.Event()

    cli._mic_loop(session, _make_proc(stdin=stdin), stop)


def test_speakers_loop_returns_on_eof() -> None:
    session = cli.Session()
    media = MagicMock()
    session.set(media, None)

    stdout = MagicMock()
    stdout.read.return_value = b""

    cli._speakers_loop(session, _make_proc(stdout=stdout), threading.Event())

    media.push_audio_sample.assert_not_called()


def test_speakers_loop_drops_audio_when_disconnected() -> None:
    session = cli.Session()  # disconnected
    stdout = MagicMock()
    payload = np.ones(
        (cli.AUDIO_CHUNK_SAMPLES, cli.AUDIO_CHANNELS), dtype=np.float32
    ).tobytes()
    stdout.read.side_effect = [payload, b""]

    cli._speakers_loop(session, _make_proc(stdout=stdout), threading.Event())


def test_speakers_loop_forwards_to_media_when_connected() -> None:
    session = cli.Session()
    media = MagicMock()
    session.set(media, None)

    stdout = MagicMock()
    payload = np.full(
        (cli.AUDIO_CHUNK_SAMPLES, cli.AUDIO_CHANNELS), 0.5, dtype=np.float32
    ).tobytes()
    stdout.read.side_effect = [payload, b""]

    cli._speakers_loop(session, _make_proc(stdout=stdout), threading.Event())

    media.push_audio_sample.assert_called_once()
    pushed = media.push_audio_sample.call_args[0][0]
    assert pushed.shape == (cli.AUDIO_CHUNK_SAMPLES, cli.AUDIO_CHANNELS)
    assert pushed.dtype == np.float32


def test_speakers_loop_swallows_push_errors() -> None:
    session = cli.Session()
    media = MagicMock()
    media.push_audio_sample.side_effect = RuntimeError("transient gst error")
    session.set(media, None)

    stdout = MagicMock()
    payload = np.zeros(
        (cli.AUDIO_CHUNK_SAMPLES, cli.AUDIO_CHANNELS), dtype=np.float32
    ).tobytes()
    stdout.read.side_effect = [payload, b""]

    cli._speakers_loop(session, _make_proc(stdout=stdout), threading.Event())
    media.push_audio_sample.assert_called_once()


def test_mic_loop_silence_then_continue_when_wait_returns_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Silence path: stdin.write succeeds, wait returns False (not stopped),
    loop continues; on the next iteration the stop_event short-circuits.
    Exercises the `continue` branch after the silence write."""
    session = cli.Session()  # disconnected
    stdin = MagicMock()
    stop = threading.Event()

    wait_calls = {"n": 0}

    def fake_wait(_delay: float) -> bool:
        wait_calls["n"] += 1
        # First wait: not stopped → loop continues. Second wait: stop signalled.
        if wait_calls["n"] >= 2:
            return True
        stop.set()  # set BEFORE returning so the next is_set() check exits
        return False

    monkeypatch.setattr(stop, "wait", fake_wait)

    cli._mic_loop(session, _make_proc(stdin=stdin), stop)

    assert stdin.write.call_count == 1
    assert wait_calls["n"] == 1


def test_mic_loop_skips_when_get_audio_sample_raises() -> None:
    session = cli.Session()
    media = MagicMock()
    session.set(media, None)

    stop = threading.Event()
    iteration_count = {"n": 0}

    def wrapped_get_audio_sample() -> object:
        iteration_count["n"] += 1
        if iteration_count["n"] >= 3:
            stop.set()
        if iteration_count["n"] == 1:
            raise RuntimeError("transient")
        return None  # exercises the `samples is None: continue` branch

    media.get_audio_sample.side_effect = wrapped_get_audio_sample

    stdin = MagicMock()
    cli._mic_loop(session, _make_proc(stdin=stdin), stop)

    # No stdin.write because both branches (exception + None) skip the write.
    stdin.write.assert_not_called()


def test_mic_loop_returns_on_broken_pipe_during_sample_write() -> None:
    """Connected state: media yields samples but stdin.write fails — must return."""
    session = cli.Session()
    media = MagicMock()
    samples = np.ones((cli.AUDIO_CHUNK_SAMPLES, cli.AUDIO_CHANNELS), dtype=np.float32)
    media.get_audio_sample.return_value = samples
    session.set(media, None)

    stdin = MagicMock()
    stdin.write.side_effect = BrokenPipeError()

    cli._mic_loop(session, _make_proc(stdin=stdin), threading.Event())

    stdin.write.assert_called_once()
