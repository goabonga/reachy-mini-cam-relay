"""Smoke tests for the audio packing constants."""

import numpy as np

from reachy_mini_cam_relay import cli


def test_silence_chunk_is_stereo_float32() -> None:
    assert cli.SILENCE_CHUNK.shape == (cli.AUDIO_CHUNK_SAMPLES, cli.AUDIO_CHANNELS)
    assert cli.SILENCE_CHUNK.dtype == np.float32


def test_silence_chunk_is_actually_silent() -> None:
    assert not cli.SILENCE_CHUNK.any()


def test_chunk_byte_size_matches_layout() -> None:
    expected = cli.AUDIO_CHUNK_SAMPLES * cli.AUDIO_CHANNELS * 4  # float32 = 4 bytes
    assert cli.AUDIO_CHUNK_BYTES == expected
    assert cli.SILENCE_CHUNK.tobytes().__len__() == cli.AUDIO_CHUNK_BYTES
