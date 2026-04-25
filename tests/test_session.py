"""Tests for ``reachy_mini_cam_relay.cli.Session`` (head-tracking variant — also
carries a ``reachy`` reference alongside the media handle)."""

import threading

from reachy_mini_cam_relay.cli import Session


def test_initial_state_is_disconnected() -> None:
    s = Session()
    assert s.media is None
    assert s.reachy is None


def test_set_then_clear_returns_previous_pair() -> None:
    s = Session()
    media_sentinel = object()
    reachy_sentinel = object()
    s.set(media_sentinel, reachy_sentinel)  # type: ignore[arg-type]
    assert s.media is media_sentinel
    assert s.reachy is reachy_sentinel
    cleared_media, cleared_reachy = s.clear()
    assert cleared_media is media_sentinel
    assert cleared_reachy is reachy_sentinel
    assert s.media is None
    assert s.reachy is None


def test_clear_when_empty_returns_none_pair() -> None:
    s = Session()
    assert s.clear() == (None, None)


def test_set_replaces_previous_value() -> None:
    s = Session()
    s.set("first-media", "first-reachy")  # type: ignore[arg-type]
    s.set("second-media", "second-reachy")  # type: ignore[arg-type]
    assert s.media == "second-media"
    assert s.reachy == "second-reachy"


def test_concurrent_set_and_clear_never_returns_corrupted_state() -> None:
    """Hammer set/clear from many threads — invariant: media and reachy stay
    consistent (paired, never mixed across set() calls)."""
    s = Session()
    pairs = {("a", "A"), ("b", "B"), ("c", "C"), ("d", "D")}
    seen_invalid = []

    def writer(value: tuple[str, str]) -> None:
        for _ in range(500):
            s.set(value[0], value[1])  # type: ignore[arg-type]

    def reader() -> None:
        for _ in range(500):
            m, r = s.media, s.reachy
            if m is not None and (m, r) not in pairs:
                seen_invalid.append((m, r))

    def clearer() -> None:
        for _ in range(500):
            popped = s.clear()
            if popped[0] is not None and popped not in pairs:
                seen_invalid.append(popped)

    threads = [
        threading.Thread(target=writer, args=(p,)) for p in pairs
    ] + [threading.Thread(target=reader)] + [threading.Thread(target=clearer)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert seen_invalid == []
