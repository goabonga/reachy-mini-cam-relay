"""Tests for ``reachy_mini_cam_relay.cli.Session``."""

import threading

from reachy_mini_cam_relay.cli import Session


def test_initial_state_is_disconnected() -> None:
    s = Session()
    assert s.media is None


def test_set_then_clear_returns_previous_value() -> None:
    s = Session()
    sentinel = object()
    s.set(sentinel)  # type: ignore[arg-type]
    assert s.media is sentinel
    cleared = s.clear()
    assert cleared is sentinel
    assert s.media is None


def test_clear_when_empty_returns_none() -> None:
    s = Session()
    assert s.clear() is None


def test_set_replaces_previous_value() -> None:
    s = Session()
    s.set("first")  # type: ignore[arg-type]
    s.set("second")  # type: ignore[arg-type]
    assert s.media == "second"


def test_concurrent_set_and_clear_never_returns_corrupted_state() -> None:
    """Hammer set/clear from many threads — invariant: media is either None or
    one of the values that was actually set, never partial / mixed."""
    s = Session()
    valid = {"a", "b", "c", "d"}
    seen_invalid = []

    def writer(value: str) -> None:
        for _ in range(500):
            s.set(value)  # type: ignore[arg-type]

    def reader() -> None:
        for _ in range(500):
            cur = s.media
            if cur is not None and cur not in valid:
                seen_invalid.append(cur)

    def clearer() -> None:
        for _ in range(500):
            popped = s.clear()
            if popped is not None and popped not in valid:
                seen_invalid.append(popped)

    threads = [
        threading.Thread(target=writer, args=(v,)) for v in valid
    ] + [threading.Thread(target=reader)] + [threading.Thread(target=clearer)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert seen_invalid == []
