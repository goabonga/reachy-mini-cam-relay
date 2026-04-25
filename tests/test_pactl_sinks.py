"""Tests for ``cli._pactl_sinks`` parsing logic."""

import subprocess

import pytest

from reachy_mini_cam_relay import cli


def test_returns_empty_when_pactl_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli.shutil, "which", lambda _name: None)
    assert cli._pactl_sinks() == set()


def test_returns_empty_when_pactl_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli.shutil, "which", lambda _name: "/usr/bin/pactl")

    def boom(*_a: object, **_kw: object) -> str:
        raise subprocess.CalledProcessError(1, ["pactl"])

    monkeypatch.setattr(cli.subprocess, "check_output", boom)
    assert cli._pactl_sinks() == set()


def test_parses_sink_names(monkeypatch: pytest.MonkeyPatch) -> None:
    output = (
        "0\talsa_output.pci-0000_00_1f.3.analog-stereo\tmodule-alsa-card\ts16le 2ch 48000Hz\tSUSPENDED\n"
        "1\treachy_sink\tmodule-null-sink.c\tfloat32le 2ch 16000Hz\tIDLE\n"
        "2\treachy_speakers\tmodule-null-sink.c\tfloat32le 2ch 16000Hz\tIDLE\n"
    )
    monkeypatch.setattr(cli.shutil, "which", lambda _name: "/usr/bin/pactl")
    monkeypatch.setattr(
        cli.subprocess, "check_output", lambda *_a, **_kw: output
    )
    assert cli._pactl_sinks() == {
        "alsa_output.pci-0000_00_1f.3.analog-stereo",
        "reachy_sink",
        "reachy_speakers",
    }


def test_skips_lines_without_tabs(monkeypatch: pytest.MonkeyPatch) -> None:
    output = "header without tab\n0\treachy_sink\tmodule\tspecs\tSTATE\n\n"
    monkeypatch.setattr(cli.shutil, "which", lambda _name: "/usr/bin/pactl")
    monkeypatch.setattr(cli.subprocess, "check_output", lambda *_a, **_kw: output)
    assert cli._pactl_sinks() == {"reachy_sink"}
