"""Tests for the mic and speakers background worker loops."""

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

    # Stop the loop after the first silence write so the test terminates.
    stop = threading.Event()

    def stop_then_succeed(_payload: bytes) -> None:
        stop.set()

    stdin.write.side_effect = stop_then_succeed
    # No real sleep please — make stop_event.wait return immediately as if signalled.
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
    session.set(media)

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
    # No assertion needed — the test passes if the loop returns rather than spinning.


def test_speakers_loop_returns_on_eof() -> None:
    session = cli.Session()
    media = MagicMock()
    session.set(media)

    stdout = MagicMock()
    stdout.read.return_value = b""  # EOF on parec

    cli._speakers_loop(session, _make_proc(stdout=stdout), threading.Event())

    media.push_audio_sample.assert_not_called()


def test_speakers_loop_drops_audio_when_disconnected() -> None:
    session = cli.Session()  # disconnected
    stdout = MagicMock()
    payload = np.ones(
        (cli.AUDIO_CHUNK_SAMPLES, cli.AUDIO_CHANNELS), dtype=np.float32
    ).tobytes()
    # First read returns audio, second returns EOF to terminate the loop.
    stdout.read.side_effect = [payload, b""]

    # We want to assert the loop does NOT try to push to media since session is empty.
    cli._speakers_loop(session, _make_proc(stdout=stdout), threading.Event())
    # Reaching here without exception means it correctly skipped the push call.


def test_speakers_loop_forwards_to_media_when_connected() -> None:
    session = cli.Session()
    media = MagicMock()
    session.set(media)

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
    session.set(media)

    stdout = MagicMock()
    payload = np.zeros(
        (cli.AUDIO_CHUNK_SAMPLES, cli.AUDIO_CHANNELS), dtype=np.float32
    ).tobytes()
    stdout.read.side_effect = [payload, b""]

    cli._speakers_loop(session, _make_proc(stdout=stdout), threading.Event())
    media.push_audio_sample.assert_called_once()
