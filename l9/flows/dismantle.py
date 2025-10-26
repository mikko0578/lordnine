from __future__ import annotations

import logging
import time
from enum import Enum, auto
from typing import Optional

from PIL import ImageGrab  # type: ignore
from functools import partial

from .base import Flow
from .buy_potions import BuyPotionsFlow


# Enable multi-monitor capture for pyautogui
ImageGrab.grab = partial(ImageGrab.grab, all_screens=True)
logger = logging.getLogger(__name__)


class DState(Enum):
    START = auto()
    OPEN_INV = auto()
    OPEN_DISMANTLE = auto()
    QUICK_ADD = auto()
    DISMANTLE = auto()
    CLOSE_INV = auto()
    NEXT = auto()
    DONE = auto()
    FAIL = auto()


class DismantleFlow(Flow):
    T_ICON = "l9/assets/dismantle/icon.png"
    T_QUICK_ADD = "l9/assets/dismantle/quick_add.png"
    T_DISMANTLE_HAS = "l9/assets/dismantle/dismantle_has.png"
    T_DISMANTLE_NONE = "l9/assets/dismantle/dismantle_none.png"
    T_CLOSE_INV = "l9/assets/dismantle/close_inventory.png"

    def _find(self, template: str, timeout_s: float) -> Optional[object]:
        try:
            import pyautogui as pag  # type: ignore
        except ModuleNotFoundError:
            logger.error("pyautogui not installed; cannot locate %s", template)
            return None
        conf = float(self.cfg.get("grind", {}).get("pyauto_threshold", 0.9))
        end = time.time() + max(0.0, timeout_s)
        while time.time() < end:
            try:
                box = pag.locateOnScreen(template, confidence=conf)
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

    def _click_center_foreground(self):
        if self.dry:
            return
        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            class RECT(ctypes.Structure):
                _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG), ("right", wintypes.LONG), ("bottom", wintypes.LONG)]
            r = RECT()
            if user32.GetWindowRect(hwnd, ctypes.byref(r)):
                cx = int((r.left + r.right) / 2)
                cy = int((r.top + r.bottom) / 2)
                self.a.click(cx, cy)
        except Exception:
            pass

    def _click_at_cursor(self):
        """Click exactly where the mouse cursor currently is.

        Tries pyautogui.position() first; falls back to WinAPI GetCursorPos.
        """
        if self.dry:
            return
        # Try pyautogui for cursor position
        try:
            import pyautogui as pag  # type: ignore
            pos = pag.position()
            if pos:
                self.a.click(int(pos.x), int(pos.y))
                return
        except Exception:
            pass
        # Fallback: WinAPI
        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32
            class POINT(ctypes.Structure):
                _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]
            p = POINT()
            if user32.GetCursorPos(ctypes.byref(p)):
                self.a.click(int(p.x), int(p.y))
        except Exception:
            pass

    def run(self) -> None:
        state = DState.START
        reason: Optional[str] = None

        while True:
            if state is DState.START:
                logger.info("Dismantle start")
                state = DState.OPEN_INV

            elif state is DState.OPEN_INV:
                # Press inventory exactly once to avoid toggling issues
                self.a.press_once(str(self.cfg.get("keybinds", {}).get("inventory", "i")))
                time.sleep(0.3)
                state = DState.OPEN_DISMANTLE

            elif state is DState.OPEN_DISMANTLE:
                box = self._find(self.T_ICON, timeout_s=8.0)
                if not box and not self.dry:
                    reason = "dismantle icon not found"
                    state = DState.FAIL
                    continue
                self._click_box(box)
                time.sleep(0.2)
                state = DState.QUICK_ADD

            elif state is DState.QUICK_ADD:
                box = self._find(self.T_QUICK_ADD, timeout_s=8.0)
                if box:
                    self._click_box(box)
                time.sleep(0.2)
                state = DState.DISMANTLE

            elif state is DState.DISMANTLE:
                # Try the actionable dismantle button first
                box = self._find(self.T_DISMANTLE_HAS, timeout_s=3.0)
                if not box:
                    # If none available, click the 'none' state button anyway to progress
                    box = self._find(self.T_DISMANTLE_NONE, timeout_s=2.0)
                if box:
                    self._click_box(box)
                # Click anywhere (center) to dismiss result
                time.sleep(2)
                # Replace center click with a click at current cursor position
                self._click_at_cursor()
                time.sleep(2)
                state = DState.CLOSE_INV

            elif state is DState.CLOSE_INV:
                # Prefer clicking close, otherwise toggle inventory key
                box = self._find(self.T_CLOSE_INV, timeout_s=2.0)
                if box:
                    self._click_box(box)
                else:
                    self.a.press_once(str(self.cfg.get("keybinds", {}).get("inventory", "i")))
                time.sleep(float(self.cfg.get("timings", {}).get("post_store_delay_s", 1.0)))
                state = DState.NEXT

            elif state is DState.NEXT:
                # Dismantle sequence complete; outer controller decides next step
                state = DState.DONE

            elif state is DState.DONE:
                logger.info("Dismantle done")
                return

            elif state is DState.FAIL:
                logger.error("Dismantle failed: %s", reason or "unknown")
                return
