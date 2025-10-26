from __future__ import annotations

import logging
import time
import random

from ..base import Flow
from ...actions.window import WindowManager


logger = logging.getLogger(__name__)


class ClickCenterFlow(Flow):
    """Focus the game window, move to its center, and click several times.

    This is a diagnostic flow to verify click delivery. It relies on the
    window guard configuration to bring the target window to the foreground
    (and move to a configured monitor if enabled), then performs a few clicks
    at the center of the foreground window.
    """

    def run(self) -> None:
        wm = WindowManager(self.cfg)
        logger.info("ClickCenterFlow start: Ensuring foreground window...")
        ok = wm.ensure_focus()
        fg = wm.get_foreground_title()
        logger.info("Window focus %s (foreground=%r)", "OK" if ok else "FAILED", fg)

        # Determine window-center in screen coordinates
        cx, cy = self._center_of_foreground_window()
        logger.info("Computed center: x=%s y=%s", cx, cy)

        # Small move then several clicks with slight jitter
        clicks = 3
        gap = 0.15
        jitter = 2
        self.a.move(cx, cy, duration=0.05)
        for i in range(clicks):
            jx = cx + random.randint(-jitter, jitter)
            jy = cy + random.randint(-jitter, jitter)
            logger.info("Click #%d at (%d,%d)", i + 1, jx, jy)
            self.a.click(jx, jy)
            time.sleep(gap)
        logger.info("ClickCenterFlow done")

    def _center_of_foreground_window(self) -> tuple[int, int]:
        # Try foreground window rectangle first
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            class RECT(ctypes.Structure):
                _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG), ("right", wintypes.LONG), ("bottom", wintypes.LONG)]
            r = RECT()
            ok = user32.GetWindowRect(hwnd, ctypes.byref(r))
            if ok and r.right > r.left and r.bottom > r.top:
                cx = int((r.left + r.right) / 2)
                cy = int((r.top + r.bottom) / 2)
                return cx, cy
        except Exception:
            pass

        # Fallback: center of configured monitor
        try:
            import mss  # type: ignore
            mon_idx = int(self.cfg.get("monitor_index", 1))
            with mss.mss() as s:
                mons = s.monitors
                i = max(1, min(mon_idx, len(mons) - 1))
                mon = mons[i]
                cx = int(mon["left"] + mon["width"] / 2)
                cy = int(mon["top"] + mon["height"] / 2)
                return cx, cy
        except Exception:
            pass

        # Last resort: screen center (0,0 origin + 960x540 assumption not used here)
        return 960, 540

