from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Optional, Tuple


try:
    import mss  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - optional at runtime
    mss = None

try:
    import numpy as np  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    np = None

try:
    import cv2  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    cv2 = None


logger = logging.getLogger(__name__)


@dataclass
class ROI:
    x: int
    y: int
    w: int
    h: int


class ScreenCapture:
    def __init__(self, monitor_index: int = 1, dpi_scale: float = 1.0, debug_dir: str = "./debug", multi_screen: bool = False) -> None:
        self.monitor_index = monitor_index
        self.dpi_scale = dpi_scale
        self.debug_dir = debug_dir
        self.multi_screen = multi_screen
        self.last_origin: Tuple[int, int] = (0, 0)  # absolute screen origin (left, top) of last grab
        os.makedirs(self.debug_dir, exist_ok=True)

        if mss is None:
            # Silent failure for stealth
            pass

    def grab(self, roi: Optional[ROI] = None):
        if mss is None or np is None:
            raise RuntimeError("Screen capture requires 'mss' and 'numpy' to be installed.")
        with mss.mss() as sct:
            monitors = sct.monitors
            
            if self.multi_screen:
                # Use all monitors combined (monitor 0 is all monitors)
                idx = 0
            else:
                # Use specific monitor
                idx = max(1, min(self.monitor_index, len(monitors) - 1))
            
            mon = monitors[idx]
            bbox = {
                "left": mon["left"],
                "top": mon["top"],
                "width": mon["width"],
                "height": mon["height"],
            }
            if roi is not None:
                bbox = {
                    "left": mon["left"] + roi.x,
                    "top": mon["top"] + roi.y,
                    "width": roi.w,
                    "height": roi.h,
                }
            # Remember absolute origin for click mapping
            self.last_origin = (int(bbox["left"]), int(bbox["top"]))
            img = sct.grab(bbox)
            frame = np.asarray(img)
            # mss returns BGRA; drop alpha and ensure BGR for cv2
            frame = frame[:, :, :3]
            return frame

    def save(self, image, path: str) -> None:
        if cv2 is None:
            raise RuntimeError("Saving screenshots requires 'opencv-python' to be installed.")
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        cv2.imwrite(path, image)
