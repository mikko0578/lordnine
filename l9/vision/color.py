from __future__ import annotations

import logging
from typing import Tuple

try:
    import cv2  # type: ignore
    import numpy as np  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    cv2 = None
    np = None


logger = logging.getLogger(__name__)


def red_ratio_bgr(img_bgr, sat_thresh: int = 60, val_thresh: int = 50) -> float:
    """Return fraction of pixels considered 'red' in BGR image.

    Red mask is defined in HSV as hue near 0/180 with sufficient saturation/value.
    """
    if cv2 is None or np is None:
        raise RuntimeError("opencv-python and numpy are required for color analysis")
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(hsv)
    # Lower and upper red ranges in OpenCV HSV (H:0..179)
    lower_red1 = (0, sat_thresh, val_thresh)
    upper_red1 = (10, 255, 255)
    lower_red2 = (170, sat_thresh, val_thresh)
    upper_red2 = (179, 255, 255)
    mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
    mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
    mask = cv2.bitwise_or(mask1, mask2)
    red_count = int(np.count_nonzero(mask))
    total = int(mask.size)
    return float(red_count) / float(total) if total else 0.0

