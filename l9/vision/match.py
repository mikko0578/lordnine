from __future__ import annotations

import logging
import math
import os
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


try:
    import cv2  # type: ignore
    import numpy as np  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    cv2 = None
    np = None

from .capture import ScreenCapture, ROI

logger = logging.getLogger(__name__)


def _cv2_method(name: str) -> int:
    if cv2 is None:
        raise RuntimeError("OpenCV is required for template matching.")
    name = name.strip().upper()
    if not name.startswith("TM_"):
        name = "TM_" + name
    if not hasattr(cv2, name):
        raise ValueError(f"Unknown OpenCV match method: {name}")
    return getattr(cv2, name)


def non_max_suppression(rects: List[Tuple[int, int, int, int]], scores: List[float], iou_thresh: float) -> List[int]:
    if np is None:
        raise RuntimeError("numpy is required for non-max suppression")
    if not rects:
        return []
    boxes = np.array(rects, dtype=np.float32)
    scores_np = np.array(scores, dtype=np.float32)
    x1, y1, x2, y2 = boxes[:, 0], boxes[:, 1], boxes[:, 0] + boxes[:, 2], boxes[:, 1] + boxes[:, 3]
    areas = (x2 - x1 + 1) * (y2 - y1 + 1)
    order = scores_np.argsort()[::-1]
    keep = []
    while order.size > 0:
        i = order[0]
        keep.append(int(i))
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        w = np.maximum(0.0, xx2 - xx1 + 1)
        h = np.maximum(0.0, yy2 - yy1 + 1)
        inter = w * h
        iou = inter / (areas[i] + areas[order[1:]] - inter)
        inds = np.where(iou <= iou_thresh)[0]
        order = order[inds + 1]
    return keep


@dataclass
class Detection:
    x: int
    y: int
    w: int
    h: int
    score: float
    scale: float


class Vision:
    def __init__(self, cfg: Dict, dry_run: bool = False) -> None:
        self.cfg = cfg
        self.capture = ScreenCapture(
            monitor_index=cfg.get("monitor_index", 1),
            dpi_scale=cfg.get("dpi_scale", 1.0),
            debug_dir=cfg.get("debug", {}).get("dir", "./debug"),
            multi_screen=cfg.get("multi_screen", False),
        )
        self.dry_run = dry_run
        os.makedirs(self.cfg.get("debug", {}).get("dir", "./debug"), exist_ok=True)

    def _roi_from_frac(self, frac: Optional[List[float]]) -> Optional[ROI]:
        if frac is None:
            return None
        # Without knowing screen size ahead, grab one frame to compute ROI
        frame = self.capture.grab()
        H, W = frame.shape[:2]
        x1 = int(frac[0] * W)
        y1 = int(frac[1] * H)
        x2 = int(frac[2] * W)
        y2 = int(frac[3] * H)
        return ROI(x1, y1, x2 - x1, y2 - y1)

    def grab_roi_image(self, roi_name: str):
        frac = (self.cfg.get("rois", {}) or {}).get(roi_name)
        roi = self._roi_from_frac(frac) if frac else None
        return self.capture.grab(roi)

    def _load_image(self, path: str):
        if cv2 is None:
            raise RuntimeError("OpenCV is required to load images.")
        if not os.path.exists(path):
            raise FileNotFoundError(f"Template not found: {path}")
        img = cv2.imread(path, cv2.IMREAD_COLOR)
        if img is None:
            raise RuntimeError(f"Failed to read image: {path}")
        return img

    def detect(
        self,
        template_path: str,
        roi_name: Optional[str] = None,
        threshold: Optional[float] = None,
        return_all: bool = False,
    ) -> Optional[Detection] | List[Detection]:
        if self.dry_run:
            logger.info("[dry] detect template=%s roi=%s", template_path, roi_name)
            return None if not return_all else []

        method = _cv2_method(self.cfg.get("match", {}).get("method", "TM_CCOEFF_NORMED"))
        use_color = bool(self.cfg.get("match", {}).get("use_color", False))
        multi_scale = bool(self.cfg.get("match", {}).get("multi_scale", True))
        scales = list(self.cfg.get("match", {}).get("scales", [1.0]))
        # Per-template threshold override (exact path or basename)
        thr_map = self.cfg.get("threshold_overrides", {}) or {}
        base = os.path.basename(template_path)
        thr = (
            threshold
            or float(thr_map.get(template_path, thr_map.get(base, self.cfg.get("match", {}).get("default_threshold", 0.85))))
        )
        nms_iou = float(self.cfg.get("match", {}).get("nms_iou", 0.3))
        max_results = int(self.cfg.get("match", {}).get("max_results", 5))

        roi = None
        if roi_name:
            frac = self.cfg.get("rois", {}).get(roi_name)
            roi = self._roi_from_frac(frac) if frac else None

        frame = self.capture.grab(roi)
        templ = self._load_image(template_path)

        if not use_color:
            frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            templ_gray = cv2.cvtColor(templ, cv2.COLOR_BGR2GRAY)
        else:
            frame_gray = frame
            templ_gray = templ

        detections: List[Detection] = []
        best: Optional[Detection] = None
        search_scales = scales if multi_scale else [1.0]
        for s in search_scales:
            if not math.isclose(s, 1.0, rel_tol=1e-6):
                t = cv2.resize(templ_gray, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
            else:
                t = templ_gray
            if t.shape[0] >= frame_gray.shape[0] or t.shape[1] >= frame_gray.shape[1]:
                continue
            res = cv2.matchTemplate(frame_gray, t, method)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
            if method in (cv2.TM_SQDIFF, cv2.TM_SQDIFF_NORMED):
                score = 1.0 - float(min_val)
                loc = min_loc
            else:
                score = float(max_val)
                loc = max_loc
            cand = Detection(x=int(loc[0]), y=int(loc[1]), w=t.shape[1], h=t.shape[0], score=score, scale=s)
            if best is None or cand.score > best.score:
                best = cand
            if score >= thr:
                detections.append(cand)

        if not detections:
            # Detection missed - no logging for stealth
            return [] if return_all else None

        if len(detections) > 1:
            rects = [(d.x, d.y, d.w, d.h) for d in detections]
            scores = [d.score for d in detections]
            keep = non_max_suppression(rects, scores, nms_iou)
            detections = [detections[i] for i in keep][:max_results]

        detections.sort(key=lambda d: d.score, reverse=True)
        return detections if return_all else detections[0]
