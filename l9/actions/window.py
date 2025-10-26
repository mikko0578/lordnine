from __future__ import annotations

import logging
import sys
from typing import Optional


logger = logging.getLogger(__name__)


class WindowManager:
    """Minimal Windows-only window foreground/maximize helper via ctypes.

    Falls back to no-ops on non-Windows platforms.
    """

    def __init__(self, cfg: dict) -> None:
        self.cfg = cfg
        self.title_sub = str(cfg.get("window", {}).get("title", "") or "")
        self.require_foreground = bool(cfg.get("window", {}).get("require_foreground", False))
        self.require_maximized = bool(cfg.get("window", {}).get("require_maximized", False))
        self.auto_focus = bool(cfg.get("window", {}).get("auto_focus", False))
        self.force_monitor_index = cfg.get("window", {}).get("force_to_monitor_index", None)
        self._is_windows = sys.platform.startswith("win32") or sys.platform.startswith("cygwin")
        if not self._is_windows and (self.require_foreground or self.require_maximized):
            logger.warning("Window guards requested but unsupported on this platform; proceeding without enforcement")

        # Lazy import ctypes bits to avoid issues on non-Windows
        if self._is_windows:
            import ctypes
            from ctypes import wintypes

            self.ctypes = ctypes
            self.wintypes = wintypes
            self.user32 = ctypes.windll.user32
            self.kernel32 = ctypes.windll.kernel32

            # Configure prototypes
            self.user32.GetForegroundWindow.restype = wintypes.HWND
            self.user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
            self.user32.GetWindowTextLengthW.restype = wintypes.INT
            self.user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, wintypes.INT]
            self.user32.GetWindowTextW.restype = wintypes.INT
            self.user32.IsWindowVisible.argtypes = [wintypes.HWND]
            self.user32.IsWindowVisible.restype = wintypes.BOOL

            # EnumWindows callback type
            self.EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
            self.user32.EnumWindows.argtypes = [self.EnumWindowsProc, wintypes.LPARAM]
            self.user32.EnumWindows.restype = wintypes.BOOL
            self.user32.SetForegroundWindow.argtypes = [wintypes.HWND]
            self.user32.SetForegroundWindow.restype = wintypes.BOOL
            self.user32.ShowWindow.argtypes = [wintypes.HWND, wintypes.INT]
            self.user32.ShowWindow.restype = wintypes.BOOL
            self.user32.MoveWindow.argtypes = [wintypes.HWND, wintypes.INT, wintypes.INT, wintypes.INT, wintypes.INT, wintypes.BOOL]
            self.user32.MoveWindow.restype = wintypes.BOOL
            self.user32.IsZoomed.argtypes = [wintypes.HWND]
            self.user32.IsZoomed.restype = wintypes.BOOL
            self.user32.BringWindowToTop.argtypes = [wintypes.HWND]
            self.user32.BringWindowToTop.restype = wintypes.BOOL
            self.user32.SetActiveWindow.argtypes = [wintypes.HWND]
            self.user32.SetActiveWindow.restype = wintypes.HWND
            self.user32.SetFocus.argtypes = [wintypes.HWND]
            self.user32.SetFocus.restype = wintypes.HWND

            # WINDOWPLACEMENT
            class POINT(ctypes.Structure):
                _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]

            class RECT(ctypes.Structure):
                _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG), ("right", wintypes.LONG), ("bottom", wintypes.LONG)]

            class WINDOWPLACEMENT(ctypes.Structure):
                _fields_ = [
                    ("length", wintypes.UINT),
                    ("flags", wintypes.UINT),
                    ("showCmd", wintypes.UINT),
                    ("ptMinPosition", POINT),
                    ("ptMaxPosition", POINT),
                    ("rcNormalPosition", RECT),
                ]

            self.WINDOWPLACEMENT = WINDOWPLACEMENT
            self.POINT = POINT
            self.RECT = RECT
            self.user32.GetWindowPlacement.argtypes = [wintypes.HWND, self.ctypes.POINTER(WINDOWPLACEMENT)]
            self.user32.GetWindowPlacement.restype = wintypes.BOOL
            # Now that RECT is defined, set GetWindowRect prototype
            self.user32.GetWindowRect.argtypes = [wintypes.HWND, self.ctypes.POINTER(RECT)]
            self.user32.GetWindowRect.restype = wintypes.BOOL

            # Constants
            self.SW_RESTORE = 9
            self.SW_SHOWMAXIMIZED = 3

    def _get_title(self, hwnd) -> str:
        if not self._is_windows:
            return ""
        length = self.user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return ""
        buf = self.ctypes.create_unicode_buffer(length + 1)
        self.user32.GetWindowTextW(hwnd, buf, length + 1)
        return buf.value

    def get_foreground_title(self) -> str:
        if not self._is_windows:
            return ""
        hwnd = self.user32.GetForegroundWindow()
        return self._get_title(hwnd)

    def _is_maximized(self, hwnd) -> bool:
        if not self._is_windows:
            return False
        try:
            return bool(self.user32.IsZoomed(hwnd))
        except Exception:
            return False

    def _find_window_by_substring(self, substr: str):
        if not self._is_windows:
            return None
        substr_low = substr.lower()
        hwnd_match = None

        @self.EnumWindowsProc
        def enum_proc(hwnd, lparam):  # type: ignore[misc]
            nonlocal hwnd_match
            if not self.user32.IsWindowVisible(hwnd):
                return True
            title = self._get_title(hwnd)
            if substr_low and substr_low in title.lower():
                hwnd_match = hwnd
                return False  # stop enumeration
            return True

        self.user32.EnumWindows(enum_proc, 0)
        return hwnd_match

    def is_expected_foreground(self) -> bool:
        if not (self.require_foreground or self.require_maximized):
            return True
        if not self._is_windows:
            return True
        title = self.get_foreground_title()
        if self.title_sub and self.title_sub.lower() not in title.lower():
            return False
        if self.require_maximized:
            hwnd = self.user32.GetForegroundWindow()
            if not self._is_maximized(hwnd):
                return False
        return True

    def ensure_focus(self) -> bool:
        if not (self.require_foreground or self.require_maximized):
            return True
        if self.is_expected_foreground():
            return True
        if not self.auto_focus or not self._is_windows or not self.title_sub:
            return False
        hwnd = self._find_window_by_substring(self.title_sub)
        if not hwnd:
            return False
        # Optionally relocate to a specific monitor
        try:
            idx = self.force_monitor_index
            if idx:
                try:
                    import mss  # type: ignore
                except ModuleNotFoundError:
                    mss = None  # type: ignore
                if mss is not None:
                    with mss.mss() as s:
                        mons = s.monitors
                        i = int(idx)
                        i = max(1, min(i, len(mons) - 1))
                        mon = mons[i]
                        # Restore and move to monitor's top-left with monitor size
                        self.user32.ShowWindow(hwnd, self.SW_RESTORE)
                        self.user32.MoveWindow(hwnd, int(mon['left']), int(mon['top']), int(mon['width']), int(mon['height']), True)
                else:
                    logger.warning("force_to_monitor_index set but 'mss' not installed; skipping relocate")
        except Exception as e:
            logger.warning("Failed to move window to monitor %s: %s", self.force_monitor_index, e)

        # Try restore and foreground; maximize if requested
        # Best-effort sequence to bypass focus restrictions
        # 1) Allow set-foreground from any process (if available)
        try:
            self.user32.AllowSetForegroundWindow(-1)
        except Exception:
            pass
        # 2) Restore window
        self.user32.ShowWindow(hwnd, self.SW_RESTORE)
        # 3) Press and release ALT to enable foreground switch
        VK_MENU = 0x12
        KEYEVENTF_KEYUP = 0x0002
        try:
            self.user32.keybd_event(VK_MENU, 0, 0, 0)
        except Exception:
            pass
        # 4) Set foreground
        self.user32.SetForegroundWindow(hwnd)
        # Additional activations
        try:
            self.user32.BringWindowToTop(hwnd)
            self.user32.SetActiveWindow(hwnd)
            self.user32.SetFocus(hwnd)
        except Exception:
            pass
        try:
            self.user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)
        except Exception:
            pass
        if self.require_maximized:
            self.user32.ShowWindow(hwnd, self.SW_SHOWMAXIMIZED)
        return self.is_expected_foreground()
