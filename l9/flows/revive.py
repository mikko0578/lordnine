from __future__ import annotations

import logging
import time
from enum import Enum, auto
from typing import Optional, Tuple

from PIL import ImageGrab  # type: ignore
from functools import partial

from .base import Flow


# Enable multi-monitor capture for pyautogui consistency
ImageGrab.grab = partial(ImageGrab.grab, all_screens=True)
logger = logging.getLogger(__name__)


class RState(Enum):
    START = auto()
    CHECK_REVIVE = auto()
    CLICK_REVIVE = auto()
    CHECK_RECLAIM = auto()
    CLICK_RECLAIM = auto()
    CHECK_RETRIEVE = auto()
    CLICK_RETRIEVE = auto()
    DONE = auto()
    FAIL = auto()


class ReviveFlow(Flow):
    """Handle death screen: revive, optionally reclaim stats, then return.

    This flow is designed to be quick and safe:
    - If no revive UI is visible, it returns immediately (no-op).
    - If revive is visible, it clicks it, then conditionally handles stat reclaim.

    Returns True if a revive action was performed, False otherwise.
    """

    # Default expected template locations (can be overridden via config)
    T_REVIVE = "l9/assets/revive/revive_button.png"
    T_STAT_RECLAIM = "l9/assets/revive/stat_reclaim.png"
    T_RETRIEVE = "l9/assets/revive/retrieve.png"
    
    # Class variable to track if we've already logged the start message
    _start_logged = False

    def _roi_region(self) -> Optional[Tuple[int, int, int, int]]:
        """Compute absolute pixel region from configured ROI name 'revive_ui'."""
        try:
            import mss  # type: ignore
        except ModuleNotFoundError:
            mss = None  # type: ignore
        try:
            frac = (self.cfg.get("rois", {}) or {}).get("revive_ui")
            mon_idx = int(self.cfg.get("monitor_index", 1))
            if mss is None or not frac:
                return None
            with mss.mss() as s:
                mons = s.monitors
                i = max(1, min(mon_idx, len(mons) - 1))
                mon = mons[i]
                x1 = int(mon["left"] + frac[0] * mon["width"])
                y1 = int(mon["top"] + frac[1] * mon["height"])
                x2 = int(mon["left"] + frac[2] * mon["width"])
                y2 = int(mon["top"] + frac[3] * mon["height"])
                return (x1, y1, x2 - x1, y2 - y1)
        except Exception:
            return None

    def _locate(self, template: str, timeout_s: float) -> Optional[object]:
        try:
            import pyautogui as pag  # type: ignore
        except ModuleNotFoundError:
            logger.error("pyautogui not installed; cannot locate %s", template)
            return None
        conf = float(self.cfg.get("revive", {}).get("pyauto_threshold", 0.9))
        end = time.time() + max(0.0, timeout_s)
        region = self._roi_region()
        while time.time() < end:
            try:
                box = (
                    pag.locateOnScreen(template, confidence=conf, region=region)
                    if region is not None
                    else pag.locateOnScreen(template, confidence=conf)
                )
                if box:
                    return box
            except Exception:
                pass
            time.sleep(0.15)
        return None

    def _click_box(self, box) -> None:
        if not box or self.dry:
            return
        cx = box.left + box.width // 2
        cy = box.top + box.height // 2
        self.a.click(cx, cy)

    def run(self) -> bool:  # type: ignore[override]
        rcfg = self.cfg.get("revive", {}) or {}
        t_revive = str(rcfg.get("revive_button", self.T_REVIVE))
        t_reclaim = str(rcfg.get("stat_reclaim_button", self.T_STAT_RECLAIM))
        t_retrieve = str(rcfg.get("retrieve_button", self.T_RETRIEVE))
        try:
            import os
            if not os.path.exists(t_revive):
                logger.warning("Revive template missing: %s", t_revive)
            if not os.path.exists(t_reclaim):
                logger.info("Stat reclaim template not found (optional): %s", t_reclaim)
            if not os.path.exists(t_retrieve):
                logger.info("Retrieve template not found (optional): %s", t_retrieve)
        except Exception:
            pass

        t_revive_timeout = float(rcfg.get("revive_timeout_s", 2.0))
        t_reclaim_timeout = float(rcfg.get("reclaim_timeout_s", 3.0))
        t_retrieve_timeout = float(rcfg.get("retrieve_timeout_s", 3.0))

        state = RState.START
        reason: Optional[str] = None
        revived = False

        while True:
            if state is RState.START:
                if not ReviveFlow._start_logged:
                    logger.info("Revive check start")
                    ReviveFlow._start_logged = True
                state = RState.CHECK_REVIVE

            elif state is RState.CHECK_REVIVE:
                box = self._locate(t_revive, timeout_s=t_revive_timeout)
                if not box:
                    # No revive UI visible; no-op
                    state = RState.DONE
                    continue
                self._click_box(box)
                revived = True
                time.sleep(0.3)
                state = RState.CHECK_RECLAIM

            elif state is RState.CHECK_RECLAIM:
                # Optional step: if a stat reclaim button exists, click it
                box = self._locate(t_reclaim, timeout_s=t_reclaim_timeout)
                if box:
                    self._click_box(box)
                    time.sleep(0.25)
                    state = RState.CHECK_RETRIEVE
                else:
                    state = RState.DONE

            elif state is RState.CHECK_RETRIEVE:
                # Optional confirm/accept/retrieve
                box = self._locate(t_retrieve, timeout_s=t_retrieve_timeout)
                if box:
                    self._click_box(box)
                    time.sleep(0.25)
                state = RState.DONE

            elif state is RState.DONE:
                if revived:
                    logger.info("Revive flow completed")
                    # Reset the start logged flag so we can log again if needed
                    ReviveFlow._start_logged = False
                return revived

            elif state is RState.FAIL:
                logger.error("Revive flow failed: %s", reason or "unknown")
                return revived
