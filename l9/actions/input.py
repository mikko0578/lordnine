from __future__ import annotations

import logging
import random
import time
import sys
from typing import Iterable, Optional


logger = logging.getLogger(__name__)

try:
    import pyautogui  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    pyautogui = None

try:
    import pydirectinput as pdi  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    pdi = None

try:
    import keyboard as kb  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    kb = None


class Actions:
    def __init__(self, cfg: dict, dry_run: bool = False) -> None:
        self.cfg = cfg
        self.dry = dry_run
        self._set_dpi_aware()
        try:
            from .window import WindowManager
            self._win = WindowManager(cfg)
        except Exception:
            self._win = None  # Fallback if window checks unavailable
        if pyautogui is not None:
            # Stealth optimizations: disable failsafe and pause for faster execution
            pyautogui.PAUSE = 0
            pyautogui.FAILSAFE = False  # Disable failsafe for stealth
        if pdi is not None:
            pdi.PAUSE = 0
            pdi.FAILSAFE = False

    def _set_dpi_aware(self) -> None:
        if sys.platform[:3] != "win":
            return
        try:
            import ctypes
            shcore = ctypes.windll.shcore
            # PROCESS_PER_MONITOR_DPI_AWARE = 2
            shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                import ctypes
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass

    def _sleep_jitter(self) -> None:
        tmin = float(self.cfg.get("timings", {}).get("wait_min_ms", 50)) / 1000.0
        tmax = float(self.cfg.get("timings", {}).get("wait_max_ms", 120)) / 1000.0
        dt = random.uniform(tmin, tmax)
        time.sleep(dt)

    def _action_pause(self) -> None:
        """Optional random pause after an action, for human-like timing.

        Controlled by timings.random_action_pause and min/max in ms.
        """
        tcfg = self.cfg.get("timings", {}) or {}
        if not bool(tcfg.get("random_action_pause", False)):
            return
        try:
            lo_ms = int(tcfg.get("action_pause_min_ms", 1000))
            hi_ms = int(tcfg.get("action_pause_max_ms", 3000))
            if hi_ms < lo_ms:
                hi_ms = lo_ms
            time.sleep(random.uniform(lo_ms, hi_ms) / 1000.0)
        except Exception:
            pass

    def _get_cursor_pos(self) -> Optional[tuple[int, int]]:
        # Try pyautogui first
        try:
            if pyautogui is not None:
                p = pyautogui.position()
                return int(p.x), int(p.y)
        except Exception:
            pass
        # Fallback WinAPI
        try:
            if sys.platform[:3] == "win":
                import ctypes
                from ctypes import wintypes
                user32 = ctypes.windll.user32
                class POINT(ctypes.Structure):
                    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]
                pt = POINT()
                if user32.GetCursorPos(ctypes.byref(pt)):
                    return int(pt.x), int(pt.y)
        except Exception:
            pass
        return None

    def _smooth_move_to(self, x: int, y: int, duration: float) -> None:
        """Move cursor smoothly to (x, y) over duration seconds.

        Prefers pyautogui's tweened move if available; otherwise steps via WinAPI.
        """
        # If no duration requested, do nothing (instant move handled by backend)
        if duration <= 0:
            # best-effort: use backend immediate move
            try:
                if pdi is not None:
                    pdi.moveTo(x, y)
                    return
            except Exception:
                pass
            if pyautogui is not None:
                try:
                    pyautogui.moveTo(x, y)
                except Exception:
                    pass
            else:
                try:
                    if sys.platform[:3] == "win":
                        import ctypes
                        ctypes.windll.user32.SetCursorPos(int(x), int(y))
                except Exception:
                    pass
            return

        # Use pyautogui if present for natural tweening
        if pyautogui is not None:
            try:
                pyautogui.moveTo(x, y, duration=duration)
                return
            except Exception:
                pass

        # Fallback: manual stepping using WinAPI SetCursorPos
        start = self._get_cursor_pos()
        if not start:
            # As a last resort, just jump
            try:
                if pdi is not None:
                    pdi.moveTo(x, y)
                elif pyautogui is not None:
                    pyautogui.moveTo(x, y)
            except Exception:
                pass
            return
        sx, sy = start
        steps = max(5, int(duration / 0.01))  # ~100Hz cap, min 5 steps
        try:
            if sys.platform[:3] == "win":
                import ctypes
                user32 = ctypes.windll.user32
                for i in range(1, steps + 1):
                    t = i / steps
                    nx = int(sx + (x - sx) * t)
                    ny = int(sy + (y - sy) * t)
                    user32.SetCursorPos(nx, ny)
                    time.sleep(duration / steps)
                return
        except Exception:
            pass
        # If all else fails
        try:
            if pdi is not None:
                pdi.moveTo(x, y)
            elif pyautogui is not None:
                pyautogui.moveTo(x, y)
        except Exception:
            pass

    def _window_ok(self) -> bool:
        if self.dry:
            return True
        if not self._win:
            return True
        ok = self._win.ensure_focus()
        if not ok:
            logger.warning("Input blocked: target window not foreground/maximized as required")
            return False
        # Optional click to solidify focus (some games need a click)
        try:
            if bool(self.cfg.get("window", {}).get("click_to_focus", False)):
                # Prefer clicking center of the foreground window rectangle
                import ctypes  # type: ignore
                from ctypes import wintypes  # type: ignore
                user32 = ctypes.windll.user32
                hwnd = user32.GetForegroundWindow()
                class RECT(ctypes.Structure):
                    _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG), ("right", wintypes.LONG), ("bottom", wintypes.LONG)]
                r = RECT()
                ok = user32.GetWindowRect(hwnd, ctypes.byref(r))
                if ok and r.right > r.left and r.bottom > r.top:
                    cx = int((r.left + r.right) / 2)
                    cy = int((r.top + r.bottom) / 2)
                else:
                    # Fallback: click center of configured monitor
                    cx = cy = None
                    try:
                        import mss  # type: ignore
                    except ModuleNotFoundError:
                        mss = None  # type: ignore
                    if mss is not None:
                        with mss.mss() as s:
                            mon_idx = int(self.cfg.get("monitor_index", 1))
                            mons = s.monitors
                            i = max(1, min(mon_idx, len(mons) - 1))
                            mon = mons[i]
                            cx = int(mon["left"] + mon["width"] / 2)
                            cy = int(mon["top"] + mon["height"] / 2)
                if cx is not None and pyautogui is not None:
                    pyautogui.click(x=cx, y=cy)
                    self._sleep_jitter()
        except Exception:
            pass
        return True

    # Windows-only low-level fallback using SendInput with scan codes
    def _send_key_winapi(self, key: str) -> bool:
        if sys.platform[:3] != "win":
            return False

    def _send_mouse_winapi(self, x: int, y: int, button: str = "left", hold_ms: int = 60) -> bool:
        if sys.platform[:3] != "win":
            return False
        try:
            import ctypes
            user32 = ctypes.windll.user32
            # Position cursor
            user32.SetCursorPos(int(x), int(y))
            # mouse_event flags
            if button == "right":
                down, up = 0x0008, 0x0010
            else:
                down, up = 0x0002, 0x0004
            user32.mouse_event(down, 0, 0, 0, 0)
            time.sleep(max(0.01, hold_ms / 1000.0))
            user32.mouse_event(up, 0, 0, 0, 0)
            return True
        except Exception:
            return False

    def _send_mouse_wm(self, x: int, y: int, button: str = "left") -> bool:
        if sys.platform[:3] != "win":
            return False
        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32
            # Resolve target window at point
            pt = wintypes.POINT(x, y)
            hwnd = user32.WindowFromPoint(pt)
            if not hwnd:
                hwnd = user32.GetForegroundWindow()
            # Convert screen to client coords
            class POINT(ctypes.Structure):
                _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]
            p = POINT(x, y)
            user32.ScreenToClient(hwnd, ctypes.byref(p))
            lparam = (p.y << 16) | (p.x & 0xFFFF)
            if button == "right":
                down, up = 0x0204, 0x0205  # WM_RBUTTONDOWN/UP
            else:
                down, up = 0x0201, 0x0202  # WM_LBUTTONDOWN/UP
            user32.SendMessageW(hwnd, down, 1, lparam)
            user32.SendMessageW(hwnd, up, 0, lparam)
            return True
        except Exception:
            return False
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            MAPVK_VK_TO_VSC = 0
            KEYEVENTF_KEYUP = 0x0002
            KEYEVENTF_SCANCODE = 0x0008

            # Resolve virtual key
            vk = None
            special = {
                "enter": 0x0D,
                "esc": 0x1B,
                "escape": 0x1B,
                "space": 0x20,
                "tab": 0x09,
            }
            k = key.lower()
            if len(k) == 1:
                # VkKeyScanW returns virtual-key and shift state in high-order bits
                vk_scan = user32.VkKeyScanW(ord(k))
                if vk_scan == -1:
                    return False
                vk = vk_scan & 0xFF
            else:
                vk = special.get(k)
            if vk is None:
                return False

            sc = user32.MapVirtualKeyW(vk, MAPVK_VK_TO_VSC)

            class KEYBDINPUT(ctypes.Structure):
                _fields_ = [
                    ("wVk", wintypes.WORD),
                    ("wScan", wintypes.WORD),
                    ("dwFlags", wintypes.DWORD),
                    ("time", wintypes.DWORD),
                    ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG)),
                ]

            class MOUSEINPUT(ctypes.Structure):
                _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG))]

            class HARDWAREINPUT(ctypes.Structure):
                _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD), ("wParamH", wintypes.WORD)]

            class INPUT_UNION(ctypes.Union):
                _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("hi", HARDWAREINPUT)]

            class INPUT(ctypes.Structure):
                _fields_ = [("type", wintypes.DWORD), ("union", INPUT_UNION)]

            def make_input(scan, flags):
                ki = KEYBDINPUT(wVk=0, wScan=scan, dwFlags=flags, time=0, dwExtraInfo=None)
                return INPUT(type=1, union=INPUT_UNION(ki=ki))

            sent = False
            if sc != 0:
                inputs = (make_input(sc, KEYEVENTF_SCANCODE), make_input(sc, KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP))
                n = user32.SendInput(len(inputs), (INPUT * len(inputs))(*inputs), ctypes.sizeof(INPUT))
                sent = (n == len(inputs))
            if not sent and len(k) == 1:
                # Unicode fallback
                KEYEVENTF_UNICODE = 0x0004
                def make_unicode_input(ch, flags):
                    ki = KEYBDINPUT(wVk=0, wScan=ord(ch), dwFlags=flags, time=0, dwExtraInfo=None)
                    return INPUT(type=1, union=INPUT_UNION(ki=ki))
                inputs = (make_unicode_input(k, KEYEVENTF_UNICODE), make_unicode_input(k, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP))
                n = user32.SendInput(len(inputs), (INPUT * len(inputs))(*inputs), ctypes.sizeof(INPUT))
                sent = (n == len(inputs))
            return sent
        except Exception:
            return False

    def move(self, x: int, y: int, duration: float = 0.0) -> None:
        if self.dry:
            logger.info("[dry] move to x=%s y=%s dur=%.2f", x, y, duration)
            self._sleep_jitter()
            return
        if not self._window_ok():
            return
        prefer_direct = bool(self.cfg.get("input", {}).get("prefer_direct", False))
        sent = False
        if prefer_direct and pdi is not None:
            try:
                pdi.moveTo(x, y, duration=duration)
                logger.info("move backend=pydirectinput x=%s y=%s", x, y)
                sent = True
            except Exception:
                sent = False
        if not sent and pyautogui is not None:
            try:
                pyautogui.moveTo(x, y, duration=duration)
                logger.info("move backend=pyautogui x=%s y=%s", x, y)
                sent = True
            except Exception:
                sent = False
        if not sent and pdi is not None:
            try:
                pdi.moveTo(x, y, duration=duration)
                logger.info("move backend=pydirectinput-fallback x=%s y=%s", x, y)
            except Exception:
                pass
        # Optionally also send WM_* messages to the window
        if not self.dry and bool(self.cfg.get("input", {}).get("use_wm_messages", False)):
            try:
                self._send_mouse_wm(x, y, button=button)
                logger.info("click backend=wm_message x=%s y=%s btn=%s", x, y, button)
            except Exception:
                pass
        self._sleep_jitter()
        self._action_pause()

    def click(self, x: int, y: int, button: str = "left", clicks: int = 1, interval: float = 0.1) -> None:
        if self.dry:
            logger.info("[dry] click x=%s y=%s button=%s clicks=%s", x, y, button, clicks)
            self._sleep_jitter()
            return
        if not self._window_ok():
            return
        prefer_direct = bool(self.cfg.get("input", {}).get("prefer_direct", False))
        fire_all = bool(self.cfg.get("input", {}).get("fire_all_click_backends", False))
        wiggle = bool(self.cfg.get("input", {}).get("wiggle_before_click", False))
        c_repeats = int(self.cfg.get("input", {}).get("click_repeats", 1))
        c_gap = max(0, float(self.cfg.get("input", {}).get("click_interval_ms", 80)) / 1000.0)
        hold_ms = int(self.cfg.get("input", {}).get("mouse_hold_ms", 60))

        def do_click_once(cx: int, cy: int) -> bool:
            did = False
            # Optional wiggle before click
            if wiggle:
                try:
                    if prefer_direct and pdi is not None:
                        pdi.moveRel(1, 0)
                        pdi.moveRel(-1, 0)
                    elif pyautogui is not None:
                        pyautogui.moveRel(1, 0)
                        pyautogui.moveRel(-1, 0)
                except Exception:
                    pass
            # Optional smooth move duration before the click (supports per-click randomization)
            in_cfg = self.cfg.get("input", {}) or {}
            min_ms = in_cfg.get("mouse_move_duration_ms_min")
            max_ms = in_cfg.get("mouse_move_duration_ms_max")
            move_dur: float
            if min_ms is not None and max_ms is not None:
                try:
                    lo = max(0.0, float(min_ms) / 1000.0)
                    hi = max(lo, float(max_ms) / 1000.0)
                    move_dur = random.uniform(lo, hi)
                except Exception:
                    move_dur = max(0.0, float(in_cfg.get("mouse_move_duration_ms", 0)) / 1000.0)
            else:
                move_dur = max(0.0, float(in_cfg.get("mouse_move_duration_ms", 0)) / 1000.0)
            # Preferred backend: smooth move then DirectInput down/up with hold
            if prefer_direct and pdi is not None:
                try:
                    # Smoothly move the cursor to target if duration > 0
                    self._smooth_move_to(cx, cy, move_dur)
                    pdi.mouseDown(x=cx, y=cy, button=button)
                    time.sleep(max(0.01, hold_ms / 1000.0))
                    pdi.mouseUp(x=cx, y=cy, button=button)
                    logger.info("click backend=pydirectinput x=%s y=%s btn=%s", cx, cy, button)
                    did = True
                except Exception:
                    did = False
            # # PyAutoGUI backend
            # if (fire_all or not did) and pyautogui is not None:
            #     try:
            #         self._smooth_move_to(cx, cy, move_dur)
            #         pyautogui.mouseDown(x=cx, y=cy, button=button)
            #         time.sleep(max(0.01, hold_ms / 1000.0))
            #         pyautogui.mouseUp(x=cx, y=cy, button=button)
            #         logger.info("click backend=pyautogui x=%s y=%s btn=%s", cx, cy, button)
            #         did = True
            #     except Exception:
            #         pass
            # # WinAPI backend
            # if fire_all or not did:
            #     ok = self._send_mouse_winapi(cx, cy, button=button, hold_ms=hold_ms)
            #     if ok:
            #         logger.info("click backend=winapi x=%s y=%s btn=%s", cx, cy, button)
            #         did = True
            #     else:
            #         logger.warning("WinAPI mouse click failed at x=%s y=%s", cx, cy)
            # # Optional WM messages
            # if bool(self.cfg.get("input", {}).get("use_wm_messages", False)):
            #     okm = self._send_mouse_wm(cx, cy, button=button)
            #     if okm:
            #         logger.info("click backend=wm_message x=%s y=%s btn=%s", cx, cy, button)
            #         did = True
            return did

        # Repeat clicks if requested
        last = False
        for i in range(max(1, c_repeats)):
            last = do_click_once(x, y)
            time.sleep(c_gap)
        self._sleep_jitter()
        self._action_pause()

    def press(self, key: str) -> None:
        if self.dry or pyautogui is None:
            logger.info("[dry] press key=%s", key)
            self._sleep_jitter()
            return
        if not self._window_ok():
            return
        # Attempt chain with repeats and optional prefer_direct
        sent = False
        prefer_direct = bool(self.cfg.get("input", {}).get("prefer_direct", False))
        hold_ms = int(self.cfg.get("input", {}).get("hold_ms", 80))
        repeats = int(self.cfg.get("input", {}).get("press_repeats", 1))
        gap = max(0, float(self.cfg.get("input", {}).get("repeat_interval_ms", 70)) / 1000.0)

        def press_once_with(func_down, func_up) -> bool:
            try:
                func_down(key)
                time.sleep(max(0.01, hold_ms / 1000.0))
                func_up(key)
                return True
            except Exception:
                return False

        for _ in range(max(1, repeats)):
            sent = False
            # Preferred DirectInput first
            if prefer_direct and pdi is not None:
                sent = press_once_with(pdi.keyDown, pdi.keyUp)
                if sent:
                    logger.info("press backend=pydirectinput key=%s", key)
            # PyAutoGUI
            if not sent and pyautogui is not None:
                sent = press_once_with(pyautogui.keyDown, pyautogui.keyUp)
                if sent:
                    logger.info("press backend=pyautogui key=%s", key)
            # keyboard module
            if not sent and kb is not None:
                try:
                    kb.press_and_release(key)
                    sent = True
                    logger.info("press backend=keyboard key=%s", key)
                except Exception as e:
                    logger.warning("keyboard press fallback failed: %s", e)
            # WinAPI scancode
            if not sent:
                sent = self._send_key_winapi(key)
                if sent:
                    logger.info("press backend=winapi key=%s", key)
            # DirectInput fallback (if not preferred earlier)
            if not sent and pdi is not None:
                sent = press_once_with(pdi.keyDown, pdi.keyUp)
                if sent:
                    logger.info("press backend=pydirectinput-fallback key=%s", key)
            time.sleep(gap)
        if not sent:
            logger.warning("All key press backends failed for key=%s", key)
        self._sleep_jitter()
        self._action_pause()

    def press_once(self, key: str) -> None:
        """Press a key exactly once, ignoring press_repeats in config.

        Keeps the same backend preference and hold timing as `press`, but forces a
        single down/up sequence. Useful for toggles like opening inventory.
        """
        if self.dry or pyautogui is None:
            logger.info("[dry] press_once key=%s", key)
            self._sleep_jitter()
            return
        if not self._window_ok():
            return
        sent = False
        prefer_direct = bool(self.cfg.get("input", {}).get("prefer_direct", False))
        hold_ms = int(self.cfg.get("input", {}).get("hold_ms", 80))

        def press_once_with(func_down, func_up) -> bool:
            try:
                func_down(key)
                time.sleep(max(0.01, hold_ms / 1000.0))
                func_up(key)
                return True
            except Exception:
                return False

        # Preferred DirectInput first
        if prefer_direct and pdi is not None:
            sent = press_once_with(pdi.keyDown, pdi.keyUp)
            if sent:
                logger.info("press_once backend=pydirectinput key=%s", key)
        # PyAutoGUI
        if not sent and pyautogui is not None:
            sent = press_once_with(pyautogui.keyDown, pyautogui.keyUp)
            if sent:
                logger.info("press_once backend=pyautogui key=%s", key)
        # keyboard module
        if not sent and kb is not None:
            try:
                kb.press_and_release(key)
                sent = True
                logger.info("press_once backend=keyboard key=%s", key)
            except Exception as e:
                logger.warning("keyboard press_once fallback failed: %s", e)
        # WinAPI scancode
        if not sent:
            sent = self._send_key_winapi(key)
            if sent:
                logger.info("press_once backend=winapi key=%s", key)
        # DirectInput fallback (if not preferred earlier)
        if not sent and pdi is not None:
            sent = press_once_with(pdi.keyDown, pdi.keyUp)
            if sent:
                logger.info("press_once backend=pydirectinput-fallback key=%s", key)
        if not sent:
            logger.warning("All key press backends failed for press_once key=%s", key)
        self._sleep_jitter()
        self._action_pause()

    def hotkey(self, *keys: Iterable[str]) -> None:
        if self.dry or pyautogui is None:
            logger.info("[dry] hotkey keys=%s", "+".join(keys))
            self._sleep_jitter()
            return
        if not self._window_ok():
            return
        pyautogui.hotkey(*keys)
        self._sleep_jitter()
        self._action_pause()

    def type_text(self, text: str, interval: Optional[float] = None) -> None:
        if self.dry or pyautogui is None:
            logger.info("[dry] type text=%r", text)
            self._sleep_jitter()
            return
        if not self._window_ok():
            return
        pyautogui.typewrite(text, interval=interval)
        self._sleep_jitter()
