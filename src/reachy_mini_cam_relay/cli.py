import argparse
import shutil
import signal
import subprocess
import sys
import threading
import time
from typing import Optional, Tuple

import numpy as np
import pyvirtualcam
from reachy_mini.media.media_manager import MediaBackend, MediaManager

MIC_SINK = "reachy_sink"
SPEAKERS_SINK = "reachy_speakers"

AUDIO_RATE = 16000
AUDIO_CHANNELS = 2
AUDIO_CHUNK_SAMPLES = 320  # 20ms @ 16kHz
AUDIO_CHUNK_BYTES = AUDIO_CHUNK_SAMPLES * AUDIO_CHANNELS * 4  # float32

NO_FRAME_TIMEOUT_S = 5.0
RECONNECT_BACKOFF_S = (1.0, 2.0, 5.0, 10.0, 30.0, 60.0)

SILENCE_CHUNK = np.zeros((AUDIO_CHUNK_SAMPLES, AUDIO_CHANNELS), dtype=np.float32)


class Session:
    """Current media connection, shared between the main loop and worker threads.

    When ``media`` is None the Reachy is unreachable — workers keep the virtual
    devices alive (black frames, silence) instead of tearing them down.
    """

    def __init__(self) -> None:
        self.media: Optional[MediaManager] = None
        self._lock = threading.Lock()

    def set(self, media: Optional[MediaManager]) -> None:
        with self._lock:
            self.media = media

    def clear(self) -> Optional[MediaManager]:
        with self._lock:
            m = self.media
            self.media = None
        return m


def _pactl_sinks() -> set[str]:
    if shutil.which("pactl") is None:
        return set()
    try:
        out = subprocess.check_output(
            ["pactl", "list", "short", "sinks"], text=True, stderr=subprocess.DEVNULL
        )
    except subprocess.CalledProcessError:
        return set()
    return {line.split("\t")[1] for line in out.splitlines() if "\t" in line}


def _connect(host: str) -> MediaManager:
    return MediaManager(backend=MediaBackend.WEBRTC, signalling_host=host)


def _close(media: Optional[MediaManager]) -> None:
    if media is not None:
        try:
            media.close()
        except Exception:
            pass


def _connect_with_backoff(
    host: str, stop_event: threading.Event
) -> Optional[MediaManager]:
    attempt = 0
    while not stop_event.is_set():
        try:
            media = _connect(host)
            print(f"connected to {host}", file=sys.stderr)
            return media
        except Exception as e:
            delay = RECONNECT_BACKOFF_S[min(attempt, len(RECONNECT_BACKOFF_S) - 1)]
            print(
                f"connection to {host} failed ({e}); retrying in {delay:.0f}s",
                file=sys.stderr,
            )
            if stop_event.wait(delay):
                return None
            attempt += 1
    return None


def _mic_loop(session: Session, proc: subprocess.Popen, stop_event: threading.Event):
    """Pipe Reachy mic audio to pacat; push silence when disconnected."""
    silence_bytes = SILENCE_CHUNK.tobytes()
    silence_period = AUDIO_CHUNK_SAMPLES / AUDIO_RATE
    while not stop_event.is_set():
        media = session.media
        if media is None:
            try:
                proc.stdin.write(silence_bytes)
                proc.stdin.flush()
            except (BrokenPipeError, OSError):
                return
            if stop_event.wait(silence_period):
                return
            continue
        try:
            samples = media.get_audio_sample()
        except Exception:
            continue
        if samples is None:
            continue
        try:
            proc.stdin.write(samples.tobytes())
        except (BrokenPipeError, OSError):
            return


def _speakers_loop(
    session: Session, proc: subprocess.Popen, stop_event: threading.Event
):
    """Pull browser audio from parec; forward to Reachy or drop when disconnected."""
    while not stop_event.is_set():
        data = proc.stdout.read(AUDIO_CHUNK_BYTES)
        if not data:
            return
        media = session.media
        if media is None:
            continue
        samples = np.frombuffer(data, dtype=np.float32).reshape(-1, AUDIO_CHANNELS)
        try:
            media.push_audio_sample(samples)
        except Exception:
            pass


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="reachy-mini-cam-relay",
        description="Relay Reachy Mini camera + mic + speakers over the network via virtual devices, with automatic reconnect.",
    )
    parser.add_argument("--reachy-host", required=True, help="Reachy Mini hostname or IP")
    parser.add_argument("--device", default="/dev/video10", help="v4l2loopback target device")
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--no-mic", action="store_true", help="disable Reachy→browser audio")
    parser.add_argument("--no-speakers", action="store_true", help="disable browser→Reachy audio")
    args = parser.parse_args()

    stop_event = threading.Event()
    shutdown_announced = [False]

    def handle_signal(_signum, _frame):
        if not shutdown_announced[0]:
            shutdown_announced[0] = True
            print("\nshutting down…", file=sys.stderr)
        stop_event.set()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    media = _connect_with_backoff(args.reachy_host, stop_event)
    if media is None:
        return 0

    session = Session()
    session.set(media)

    first = None
    while first is None and not stop_event.is_set():
        try:
            first = media.get_frame()
        except Exception:
            first = None
            break
    if stop_event.is_set() or first is None:
        _close(session.clear())
        return 0

    height, width = first.shape[:2]

    sinks = _pactl_sinks()
    pacat = shutil.which("pacat")
    parec = shutil.which("parec")

    mic_proc: Optional[subprocess.Popen] = None
    spk_proc: Optional[subprocess.Popen] = None
    threads: list[threading.Thread] = []
    try:
        if not args.no_mic:
            if pacat and MIC_SINK in sinks:
                mic_proc = subprocess.Popen(
                    [
                        pacat, "--playback", "--raw",
                        f"--device={MIC_SINK}",
                        "--format=float32le",
                        f"--rate={AUDIO_RATE}",
                        f"--channels={AUDIO_CHANNELS}",
                        "--client-name=reachy-mini-cam-relay",
                    ],
                    stdin=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                )
                t = threading.Thread(
                    target=_mic_loop, args=(session, mic_proc, stop_event), daemon=True
                )
                t.start()
                threads.append(t)
            else:
                print(
                    f"note: mic sink '{MIC_SINK}' not found — run scripts/setup-virtual-audio.sh",
                    file=sys.stderr,
                )

        if not args.no_speakers:
            if parec and SPEAKERS_SINK in sinks:
                spk_proc = subprocess.Popen(
                    [
                        parec, "--raw",
                        f"--device={SPEAKERS_SINK}.monitor",
                        "--format=float32le",
                        f"--rate={AUDIO_RATE}",
                        f"--channels={AUDIO_CHANNELS}",
                        "--latency-msec=20",
                        "--client-name=reachy-mini-cam-relay",
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                )
                t = threading.Thread(
                    target=_speakers_loop, args=(session, spk_proc, stop_event), daemon=True
                )
                t.start()
                threads.append(t)
            else:
                print(
                    f"note: speakers sink '{SPEAKERS_SINK}' not found — run scripts/setup-virtual-audio.sh",
                    file=sys.stderr,
                )

        with pyvirtualcam.Camera(
            width=width,
            height=height,
            fps=args.fps,
            device=args.device,
            fmt=pyvirtualcam.PixelFormat.BGR,
        ) as cam:
            tags = []
            if mic_proc is not None:
                tags.append("mic")
            if spk_proc is not None:
                tags.append("speakers")
            suffix = f" + {' + '.join(tags)}" if tags else ""
            print(
                f"relaying {args.reachy_host} ({width}x{height}@{args.fps}fps{suffix}) -> {cam.device}",
                file=sys.stderr,
            )
            cam.send(first)
            cam.sleep_until_next_frame()

            last_frame = first
            last_frame_time = time.monotonic()

            while not stop_event.is_set():
                current_media = session.media

                if current_media is None:
                    cam.send(last_frame)
                    cam.sleep_until_next_frame()
                    new_media = _connect_with_backoff(args.reachy_host, stop_event)
                    if new_media is not None:
                        session.set(new_media)
                        last_frame_time = time.monotonic()
                    continue

                try:
                    frame = current_media.get_frame()
                except Exception:
                    frame = None

                if frame is None:
                    if time.monotonic() - last_frame_time > NO_FRAME_TIMEOUT_S:
                        print(
                            f"no frames for {NO_FRAME_TIMEOUT_S:.0f}s — reconnecting",
                            file=sys.stderr,
                        )
                        _close(session.clear())
                    cam.send(last_frame)
                    cam.sleep_until_next_frame()
                    continue

                if frame.shape[:2] != (height, width):
                    continue

                last_frame = frame
                last_frame_time = time.monotonic()
                cam.send(frame)
                cam.sleep_until_next_frame()
    finally:
        stop_event.set()
        for t in threads:
            t.join(timeout=2)
        for proc in (mic_proc, spk_proc):
            if proc is None:
                continue
            if proc.stdin:
                try:
                    proc.stdin.close()
                except Exception:
                    pass
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
        _close(session.clear())

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(0)
