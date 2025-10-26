from __future__ import annotations

import json
import logging
import os
import time
import random
from enum import Enum, auto
from typing import Optional, List, Dict, Any

from PIL import ImageGrab  # type: ignore
from functools import partial

from .base import Flow


ImageGrab.grab = partial(ImageGrab.grab, all_screens=True)  # enable multi-monitor capture for pyautogui
logger = logging.getLogger(__name__)


class GState(Enum):
    START = auto()
    OPEN_MAP = auto()
    SELECT_REGION = auto()
    SELECT_AREA = auto()
    SELECT_TELEPORTER = auto()
    FAST_TRAVEL = auto()
    WAIT_TELEPORT = auto()
    WAIT_HUD = auto()
    MOVE_TO_SPOT = auto()
    START_BATTLE = auto()
    DONE = auto()
    FAIL = auto()


class GrindFlow(Flow):
    T_REGION = "l9/assets/grind/region.png"
    T_AREA = "l9/assets/grind/area.png"
    T_TELE = "l9/assets/grind/teleporter.png"
    T_FAST = "l9/assets/grind/fast_travel.png"
    T_CONFIRM = "l9/assets/grind/confirm.png"
    T_BAG = "l9/assets/ui/hud/bag_icon.png"

    def _pause(self) -> None:
        # Ensure at least 1 second between actions (configurable via timings.grind_action_min_s)
        min_s = float(self.cfg.get("timings", {}).get("grind_action_min_s", 1.0))
        if min_s < 1.0:
            min_s = 1.0
        time.sleep(min_s)

    def _active_spot(self) -> Optional[dict]:
        g = self.cfg.get("grind", {}) or {}
        spots = g.get("spots") or []
        active_id = int(g.get("active_spot_id", 1))
        for s in spots:
            try:
                if int(s.get("id")) == active_id:
                    return s
            except Exception:
                continue
        return None

    def _spot_templ(self, key: str, fallback: str) -> str:
        spot = self._active_spot()
        if spot and isinstance(spot.get(key), str) and spot.get(key):
            return str(spot.get(key))
        # backwards compatibility: read from grind.<key>
        return str((self.cfg.get("grind", {}) or {}).get(key, fallback))

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

    def _roi_region(self, roi_name: Optional[str]) -> Optional[tuple[int, int, int, int]]:
        if not roi_name:
            return None
        try:
            import mss  # type: ignore
        except ModuleNotFoundError:
            mss = None  # type: ignore
        try:
            frac = (self.cfg.get("rois", {}) or {}).get(roi_name)
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

    def _wait_bag_icon(self, timeout_s: float) -> bool:
        try:
            import pyautogui as pag  # type: ignore
        except ModuleNotFoundError:
            logger.error("pyautogui not available; skipping bag icon wait")
            return True
        g = self.cfg.get("grind", {}) or {}
        t_path = str(g.get("bag_icon_template", self.T_BAG))
        try:
            import os
            if not os.path.exists(t_path):
                logger.info("Bag icon template missing; skipping wait: %s", t_path)
                return True
        except Exception:
            pass
        conf = float(g.get("pyauto_threshold", 0.9))
        roi_name = str(g.get("bag_icon_roi", "hud_anchor")) if g.get("bag_icon_roi") is not None else None
        region = self._roi_region(roi_name)
        end = time.time() + max(0.0, timeout_s)
        while time.time() < end:
            try:
                box = pag.locateOnScreen(t_path, confidence=conf, region=region) if region else pag.locateOnScreen(t_path, confidence=conf)
                if box:
                    return True
            except Exception:
                pass
            time.sleep(0.15)
        logger.warning("Bag icon not detected within %.1fs; continuing", timeout_s)
        return False

    def _click_box(self, box) -> None:
        if not box or self.dry:
            return
        cx = box.left + box.width // 2
        cy = box.top + box.height // 2
        self.a.click(cx, cy)

    def _path_file(self) -> str:
        # Prefer spot-based path naming, fallback to legacy area_id
        g = self.cfg.get("grind", {}) or {}
        area_id = str(g.get("area_id") or f"spot{int(g.get('active_spot_id', 1))}")
        root = os.path.join("l9", "data", "grind_paths")
        os.makedirs(root, exist_ok=True)
        return os.path.join(root, f"{area_id}.json")

    def _record_path(self, out_path: str) -> None:
        try:
            import keyboard  # type: ignore
        except ModuleNotFoundError:
            logger.error("keyboard module not installed; cannot record path")
            return
        try:
            import mouse  # type: ignore
        except ModuleNotFoundError:
            mouse = None  # type: ignore
        gcfg = self.cfg.get("grind", {}) or {}
        stop_key = str(gcfg.get("record_stop_key", "f12"))
        logger.info(
            "Recording path: WASD keypresses and mouse clicks%s. Press %s to stop.",
            " (mouse requires 'mouse' module)" if mouse is None else "",
            stop_key,
        )
        # Keys to record: configurable, defaults to movement + a few common
        default_keys = ["w", "a", "s", "d"]
        cfg_keys = gcfg.get("record_keys") if isinstance(gcfg.get("record_keys"), list) else None
        rec_keys = [str(k).lower() for k in (cfg_keys or default_keys)]
        allowed = set(rec_keys)
        start = time.perf_counter()
        events: List[Dict[str, Any]] = []

        def on_key(e):
            try:
                name = (e.name or "").lower()
                if name in allowed and e.event_type in ("down", "up"):
                    t = time.perf_counter() - start
                    events.append({"t": t, "type": e.event_type, "key": name})
            except Exception:
                pass

        def on_mouse_click(e=None):  # type: ignore[no-redef]
            if mouse is None:
                return
            try:
                x, y = mouse.get_position()  # type: ignore[attr-defined]
                btn = None
                try:
                    btn = getattr(e, "button", None)
                except Exception:
                    btn = None
                if not btn:
                    btn = "left"
                t = time.perf_counter() - start
                events.append({"t": t, "type": "mclick", "button": str(btn), "x": int(x), "y": int(y)})
            except Exception:
                pass

        keyboard.hook(on_key)
        mouse_hook = None
        try:
            if mouse is not None:
                try:
                    if hasattr(mouse, "on_click"):
                        mouse_hook = mouse.on_click(on_mouse_click)  # type: ignore[attr-defined]
                    else:
                        def _mouse_any(ev):
                            try:
                                if getattr(ev, "event_type", "") == "down":
                                    on_mouse_click(ev)
                            except Exception:
                                pass
                        mouse_hook = mouse.hook(_mouse_any)  # type: ignore[attr-defined]
                except Exception:
                    mouse_hook = None
            # WinAPI polling fallback for clicks when 'mouse' module unavailable
            last_l = 0
            last_r = 0
            def _cursor_pos():
                try:
                    import pyautogui as pag  # type: ignore
                    p = pag.position()
                    return int(p.x), int(p.y)
                except Exception:
                    pass
                try:
                    import ctypes
                    from ctypes import wintypes
                    class POINT(ctypes.Structure):
                        _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]
                    pt = POINT()
                    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
                    return int(pt.x), int(pt.y)
                except Exception:
                    return None
            def _poll_clicks_win():
                nonlocal last_l, last_r
                try:
                    import ctypes
                    user32 = ctypes.windll.user32
                    VK_LBUTTON = 0x01
                    VK_RBUTTON = 0x02
                    def down(vk):
                        return (user32.GetAsyncKeyState(vk) & 0x8000) != 0
                    l = 1 if down(VK_LBUTTON) else 0
                    r = 1 if down(VK_RBUTTON) else 0
                    if l and not last_l:
                        pos = _cursor_pos()
                        if pos:
                            t = time.perf_counter() - start
                            events.append({"t": t, "type": "mclick", "button": "left", "x": pos[0], "y": pos[1]})
                    if r and not last_r:
                        pos = _cursor_pos()
                        if pos:
                            t = time.perf_counter() - start
                            events.append({"t": t, "type": "mclick", "button": "right", "x": pos[0], "y": pos[1]})
                    last_l, last_r = l, r
                except Exception:
                    pass
            while True:
                if keyboard.is_pressed(stop_key):
                    break
                if mouse is None:
                    _poll_clicks_win()
                time.sleep(0.01)
        finally:
            try:
                keyboard.unhook(on_key)
            except Exception:
                pass
            if mouse is not None and mouse_hook is not None:
                try:
                    if hasattr(mouse, "unhook"):
                        mouse.unhook(mouse_hook)  # type: ignore[attr-defined]
                except Exception:
                    pass
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump({"version": 2, "events": events}, f, indent=2)
        n_clicks = sum(1 for e in events if e.get("type") == "mclick")
        n_keys = sum(1 for e in events if e.get("type") in ("down", "up", "kdown", "kup"))
        logger.info("Saved path to %s (%d events; %d clicks, %d key events)", out_path, len(events), n_clicks, n_keys)

    def _replay_path(self, path_file: str) -> None:
        try:
            with open(path_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            logger.error("Failed to load path %s: %s", path_file, e)
            return
        # Choose backend
        prefer_direct = bool(self.cfg.get("input", {}).get("prefer_direct", False))
        try:
            import pydirectinput as pdi  # type: ignore
        except ModuleNotFoundError:
            pdi = None
        try:
            import pyautogui as pag  # type: ignore
        except ModuleNotFoundError:
            pag = None

        def kd(k):
            if prefer_direct and pdi is not None:
                pdi.keyDown(k)
            elif pag is not None:
                pag.keyDown(k)

        def ku(k):
            if prefer_direct and pdi is not None:
                pdi.keyUp(k)
            elif pag is not None:
                pag.keyUp(k)

        def replay_events(events):
            logger.info("Replaying path (%d events)", len(events))
            base = time.perf_counter()
            idx = 0
            pressed: set[str] = set()
            while idx < len(events):
                e = events[idx]
                target = base + float(e.get("t", 0.0))
                now = time.perf_counter()
                if target > now:
                    time.sleep(target - now)
                typ = e.get("type")
                if typ in ("down", "kdown"):
                    k = str(e.get("key", ""))
                    if k:
                        kd(k)
                        pressed.add(k)
                elif typ in ("up", "kup"):
                    k = str(e.get("key", ""))
                    if k:
                        ku(k)
                        pressed.discard(k)
                elif typ == "mclick":
                    try:
                        x = int(e.get("x"))
                        y = int(e.get("y"))
                        btn = str(e.get("button", "left"))
                        if not self.dry:
                            self.a.click(x, y, button=btn)
                    except Exception:
                        pass
                idx += 1
            for k in list(pressed):
                try:
                    ku(k)
                except Exception:
                    pass

        def _enter_gate(gate_index: int) -> None:
            dcfg = (self.cfg.get("dungeon", {}) or {})
            gates = dcfg.get("gates") or []
            gate = gates[gate_index] if gate_index < len(gates) else {}
            templates = gate.get("confirm_templates") if isinstance(gate.get("confirm_templates"), list) else []
            roi_name = gate.get("confirm_roi") or "center_ui"
            timeout_s = float(gate.get("confirm_timeout_s", self.cfg.get("timings", {}).get("confirm_timeout_s", 8.0)))
            fallback_keys = gate.get("fallback_keys") if isinstance(gate.get("fallback_keys"), list) else None
            if fallback_keys is None:
                # default fallback: interact, maybe z, and confirm
                fb = [str(self.cfg.get("keybinds", {}).get("interact", "e")), "z", str(self.cfg.get("keybinds", {}).get("confirm", "enter"))]
                fallback_keys = fb
            region = self._roi_region(roi_name)
            found = False
            if templates:
                conf = float(self.cfg.get("grind", {}).get("pyauto_threshold", 0.9))
                end = time.time() + max(0.0, timeout_s)
                while time.time() < end and not found:
                    try:
                        import pyautogui as _pag  # type: ignore
                    except ModuleNotFoundError:
                        break
                    for tpath in templates:
                        try:
                            box = _pag.locateOnScreen(tpath, confidence=conf, region=region) if region else _pag.locateOnScreen(tpath, confidence=conf)
                            if box:
                                if not self.dry:
                                    cx = box.left + box.width // 2
                                    cy = box.top + box.height // 2
                                    self.a.click(cx, cy)
                                found = True
                                break
                        except Exception:
                            pass
                    if not found:
                        time.sleep(0.15)
            if not found:
                # Fallback: press keys with small pauses
                for _ in range(3):
                    for k in fallback_keys:
                        self.a.press_once(str(k))
                        time.sleep(0.1)
            # After entering, wait for teleport/load and HUD readiness
            wait_s = float(self.cfg.get("timings", {}).get("teleport_min_wait_s", 3.5))
            time.sleep(wait_s)
            post_min = float(self.cfg.get("timings", {}).get("teleport_post_wait_min_s", 2.0))
            post_max = float(self.cfg.get("timings", {}).get("teleport_post_wait_max_s", 3.0))
            if post_max < post_min:
                post_max = post_min
            time.sleep(random.uniform(post_min, post_max))
            timeout = float((self.cfg.get("grind", {}) or {}).get("bag_icon_timeout_s", 12.0))
            self._wait_bag_icon(timeout)

        # If version 3 with segments, iterate with gates; else replay single events
        if isinstance(data, dict) and isinstance(data.get("segments"), list):
            segments = data.get("segments")
            for i, seg in enumerate(segments):
                evs = seg.get("events", [])
                replay_events(evs)
                if i < len(segments) - 1:
                    _enter_gate(i)
        else:
            events = data.get("events", [])
            replay_events(events)

    def run(self) -> None:
        state = GState.START
        reason: Optional[str] = None

        while True:
            if state is GState.START:
                logger.info("GrindFlow start")
                state = GState.OPEN_MAP

            elif state is GState.OPEN_MAP:
                # Open map with a single keypress (avoid repeats)
                self.a.press_once(str(self.cfg.get("keybinds", {}).get("map", "m")))
                self._pause()
                state = GState.SELECT_REGION

            elif state is GState.SELECT_REGION:
                # Optional step: click the broader region before selecting area
                box = self._find(self._spot_templ("region_template", self.T_REGION), timeout_s=8.0)
                if not box and not self.dry:
                    reason = "region not found"
                    state = GState.FAIL
                    continue
                self._click_box(box)
                self._pause()
                state = GState.SELECT_AREA

            elif state is GState.SELECT_AREA:
                box = self._find(self._spot_templ("area_template", self.T_AREA), timeout_s=8.0)
                if not box and not self.dry:
                    reason = "area not found"
                    state = GState.FAIL
                    continue
                self._click_box(box)
                self._pause()
                state = GState.SELECT_TELEPORTER

            elif state is GState.SELECT_TELEPORTER:
                box = self._find(self._spot_templ("teleporter_template", self.T_TELE), timeout_s=8.0)
                if not box and not self.dry:
                    reason = "teleporter not found"
                    state = GState.FAIL
                    continue
                self._click_box(box)
                self._pause()
                state = GState.FAST_TRAVEL

            elif state is GState.FAST_TRAVEL:
                box = self._find(self._spot_templ("fast_travel_template", self.T_FAST), timeout_s=8.0)
                if not box and not self.dry:
                    reason = "fast travel not found"
                    state = GState.FAIL
                    continue
                self._click_box(box)
                # Optional confirm dialog
                cbox = self._find(self._spot_templ("confirm_template", self.T_CONFIRM), timeout_s=4.0)
                if cbox and not self.dry:
                    self._click_box(cbox)
                    self._pause()
                else:
                    self._pause()
                state = GState.WAIT_TELEPORT

            elif state is GState.WAIT_TELEPORT:
                wait_s = float(self.cfg.get("timings", {}).get("teleport_min_wait_s", 3.5))
                time.sleep(wait_s)
                # Add randomized human-like delay after teleport completes
                post_min = float(self.cfg.get("timings", {}).get("teleport_post_wait_min_s", 2.0))
                post_max = float(self.cfg.get("timings", {}).get("teleport_post_wait_max_s", 3.0))
                if post_max < post_min:
                    post_max = post_min
                time.sleep(random.uniform(post_min, post_max))
                state = GState.WAIT_HUD

            elif state is GState.WAIT_HUD:
                # Wait until loading is done and HUD is back by checking the bag icon
                timeout = float((self.cfg.get("grind", {}) or {}).get("bag_icon_timeout_s", 12.0))
                self._wait_bag_icon(timeout)
                state = GState.MOVE_TO_SPOT

            elif state is GState.MOVE_TO_SPOT:
                path_file = self._path_file()
                if os.path.exists(path_file):
                    logger.info("Replaying recorded path: %s", path_file)
                    self._replay_path(path_file)
                else:
                    logger.info("Path not found; starting recording: %s", path_file)
                    self._record_path(path_file)
                state = GState.START_BATTLE

            elif state is GState.START_BATTLE:
                self.a.press(str(self.cfg.get("keybinds", {}).get("autobattle", "g")))
                self._pause()
                logger.info("Auto battle started")
                state = GState.DONE

            elif state is GState.DONE:
                logger.info("GrindFlow done")
                return

            elif state is GState.FAIL:
                logger.error("GrindFlow failed: %s", reason or "unknown")
                return
