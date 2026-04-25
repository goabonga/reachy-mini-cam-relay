"""Visual servoing using the Reachy Mini SDK's ``look_at_image`` — absolute target
each tick, no integrator wind-up. Pattern borrowed from pollen-robotics'
``reachy_mini_conversation_app`` head-tracking worker."""

import math
import os
import sys
import threading
import time
import urllib.request
from pathlib import Path
from typing import Optional

import numpy as np

DEBUG = os.environ.get("CAM_RELAY_HT_DEBUG") == "1"
DEBUG_EVERY_N_TICKS = 10  # ~2Hz at TICK_HZ=20

# The camera FOV is tighter than the motion model expects — scale the target
# pose down so the robot tracks smoothly without overshooting.
POSE_SCALE = 0.6

FACE_LOST_DELAY_S = 2.0
INTERPOLATION_DURATION_S = 1.0

TICK_HZ = 20.0

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/face_detector/"
    "blaze_face_short_range/float16/1/blaze_face_short_range.tflite"
)
MODEL_CACHE = Path.home() / ".cache" / "reachy-mini-cam-relay" / "blaze_face_short_range.tflite"


class FrameSlot:
    """One-slot thread-safe frame hand-off — the main loop writes, the tracker reads."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._frame: Optional[np.ndarray] = None

    def set(self, frame: np.ndarray) -> None:
        with self._lock:
            self._frame = frame

    def get(self) -> Optional[np.ndarray]:
        with self._lock:
            return self._frame


def _ensure_model() -> str:
    MODEL_CACHE.parent.mkdir(parents=True, exist_ok=True)
    if not MODEL_CACHE.exists():
        urllib.request.urlretrieve(MODEL_URL, MODEL_CACHE)
    return str(MODEL_CACHE)


def _scale_pose(pose: np.ndarray, scale: float) -> np.ndarray:
    from scipy.spatial.transform import Rotation as R

    out = np.eye(4)
    out[:3, 3] = pose[:3, 3] * scale
    euler = R.from_matrix(pose[:3, :3]).as_euler("xyz")
    out[:3, :3] = R.from_euler("xyz", euler * scale).as_matrix()
    return out


def tracking_loop(session, slot: FrameSlot, stop_event: threading.Event) -> None:
    """Run visual-servoing against ``session.reachy``; tolerates the Reachy going
    away and coming back (e.g. network blip) — we re-read ``session.reachy`` each
    tick so reconnection swaps the live instance transparently."""
    import cv2
    import mediapipe as mp
    from mediapipe.tasks.python import BaseOptions
    from mediapipe.tasks.python.vision import (
        FaceDetector,
        FaceDetectorOptions,
        RunningMode,
    )
    from reachy_mini.utils.interpolation import linear_pose_interpolation

    detector = FaceDetector.create_from_options(
        FaceDetectorOptions(
            base_options=BaseOptions(model_asset_path=_ensure_model()),
            running_mode=RunningMode.IMAGE,
            min_detection_confidence=0.5,
        )
    )

    neutral = np.eye(4)
    current_target = np.eye(4)
    last_face_time: Optional[float] = None
    interp_start_time: Optional[float] = None
    interp_start_pose: Optional[np.ndarray] = None
    period = 1.0 / TICK_HZ
    tick = 0

    try:
        while not stop_event.is_set():
            started = time.monotonic()
            tick += 1
            reachy = session.reachy
            frame = slot.get()
            if reachy is None or frame is None:
                time.sleep(period)
                continue

            h, w = frame.shape[:2]
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            result = detector.detect(mp_image)

            if result.detections:
                det = max(
                    result.detections,
                    key=lambda d: d.bounding_box.width * d.bounding_box.height,
                )
                bb = det.bounding_box
                px = int(bb.origin_x + bb.width / 2.0)
                py = int(bb.origin_y + bb.height / 2.0)
                # look_at_image asserts 0 < u < width and 0 < v < height
                px = max(1, min(w - 1, px))
                py = max(1, min(h - 1, py))

                try:
                    target_pose = reachy.look_at_image(
                        px, py, duration=0.0, perform_movement=False
                    )
                except Exception as e:
                    if DEBUG and tick % DEBUG_EVERY_N_TICKS == 0:
                        print(f"[head-track] look_at_image failed: {e}", file=sys.stderr)
                    target_pose = None

                if target_pose is not None:
                    current_target = _scale_pose(target_pose, POSE_SCALE)
                    reachy.set_target(head=current_target)
                    last_face_time = time.time()
                    interp_start_time = None
                    interp_start_pose = None

                    if DEBUG and tick % DEBUG_EVERY_N_TICKS == 0:
                        from scipy.spatial.transform import Rotation as R

                        _, pitch, yaw = R.from_matrix(current_target[:3, :3]).as_euler(
                            "xyz"
                        )
                        print(
                            f"[head-track] face@({px:4d},{py:4d}/{w}x{h})"
                            f" → yaw={math.degrees(yaw):+6.1f}° pitch={math.degrees(pitch):+6.1f}°",
                            file=sys.stderr,
                        )
            else:
                if last_face_time is not None:
                    elapsed_since_lost = time.time() - last_face_time
                    if elapsed_since_lost >= FACE_LOST_DELAY_S:
                        if interp_start_time is None:
                            interp_start_time = time.time()
                            interp_start_pose = current_target.copy()
                        t = min(
                            1.0,
                            (time.time() - interp_start_time) / INTERPOLATION_DURATION_S,
                        )
                        assert interp_start_pose is not None
                        current_target = linear_pose_interpolation(
                            interp_start_pose, neutral, t
                        )
                        reachy.set_target(head=current_target)
                        if t >= 1.0:
                            last_face_time = None
                            interp_start_time = None
                            interp_start_pose = None

                if DEBUG and tick % DEBUG_EVERY_N_TICKS == 0:
                    print("[head-track] no face", file=sys.stderr)

            elapsed = time.monotonic() - started
            if elapsed < period:
                time.sleep(period - elapsed)
    finally:
        reachy = session.reachy
        if reachy is not None:
            try:
                reachy.set_target(head=np.eye(4))
            except Exception:
                pass
        detector.close()
