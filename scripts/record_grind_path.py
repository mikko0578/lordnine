from __future__ import annotations

import argparse
import json
import os
import sys
import time

# Ensure repo root on sys.path
REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from l9.config_loader import load_config


def path_file(cfg: dict) -> str:
    g = cfg.get("grind", {}) or {}
    # Prefer legacy explicit area_id if provided, else derive from active spot
    area_id = str(g.get("area_id") or f"spot{int(g.get('active_spot_id', 1))}")
    root = os.path.join("l9", "data", "grind_paths")
    os.makedirs(root, exist_ok=True)
    return os.path.join(root, f"{area_id}.json")


def record(cfg: dict, out_path: str) -> int:
    try:
        import keyboard  # type: ignore
    except ModuleNotFoundError:
        print("[ERROR] The 'keyboard' module is required. Install with: python -m pip install keyboard")
        return 2
    try:
        import mouse  # type: ignore
    except ModuleNotFoundError:
        mouse = None  # type: ignore
    g = (cfg.get("grind", {}) or {})
    stop_key = str(g.get("record_stop_key", "f12"))
    # Keys to record (configurable)
    default_keys = ["w", "a", "s", "d"]
    cfg_keys = g.get("record_keys") if isinstance(g.get("record_keys"), list) else None
    rec_keys = [str(k).lower() for k in (cfg_keys or default_keys)]
    print("\n=== Grind Path Recorder ===")
    print("- Focus the game window")
    print("- Teleport to your grind area")
    print(f"- Walk to the spot using: {', '.join(rec_keys).upper()}")
    if mouse is not None:
        print("- Mouse clicks will also be recorded")
    else:
        print("- Mouse clicks recorded via Windows fallback; or install 'mouse' for full hooks")
    print(f"- Press {stop_key} to finish recording\n")

    allowed = set(rec_keys)
    start = time.perf_counter()
    events = []

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
        # WinAPI polling fallback for mouse clicks (no deps)
        last_l = 0
        last_r = 0
        def _cursor_pos() -> tuple[int, int] | None:
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
    print(f"Saved path to {out_path} ({len(events)} events; {n_clicks} clicks, {n_keys} key events)")
    return 0


def _roi_region(cfg: dict, roi_name: str | None) -> tuple[int, int, int, int] | None:
    if not roi_name:
        return None
    try:
        import mss  # type: ignore
    except ModuleNotFoundError:
        mss = None  # type: ignore
    try:
        frac = (cfg.get("rois", {}) or {}).get(roi_name)
        mon_idx = int(cfg.get("monitor_index", 1))
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


def record_auto_gates(cfg: dict, out_path: str) -> int:
    """Record path segments separated by auto-detected OK/confirm gates.

    Behavior:
    - User walks (keys from grind.record_keys). We record down/up with timestamps.
    - When keys idle for a short time, try to detect an OK/confirm button.
      If found, click it, wait for loading (teleport wait + bag icon), then
      finalize current segment and start a new one. Repeat until F12 is pressed.
    - Writes version 3 JSON with segments.
    """
    try:
        import keyboard  # type: ignore
    except ModuleNotFoundError:
        print("[ERROR] The 'keyboard' module is required. Install with: python -m pip install keyboard")
        return 2
    try:
        import pyautogui as pag  # type: ignore
    except ModuleNotFoundError:
        pag = None  # type: ignore
    g = (cfg.get("grind", {}) or {})
    dcfg = (cfg.get("dungeon", {}) or {})
    stop_key = str(g.get("record_stop_key", "f12"))
    # Keys & timings
    default_keys = ["w", "a", "s", "d", "e", "z"]
    cfg_keys = g.get("record_keys") if isinstance(g.get("record_keys"), list) else None
    rec_keys = [str(k).lower() for k in (cfg_keys or default_keys)]
    allowed = set(rec_keys)
    idle_ms = 600  # idle threshold before gate detect
    # Gate detection
    ok_templates = []
    # Prefer a flat list if provided
    if isinstance(dcfg.get("ok_templates"), list):
        ok_templates = [str(x) for x in dcfg.get("ok_templates")]
    # Or collect from gates[*].confirm_templates
    if not ok_templates and isinstance(dcfg.get("gates"), list):
        for gate in dcfg.get("gates"):
            if isinstance(gate, dict) and isinstance(gate.get("confirm_templates"), list):
                ok_templates.extend([str(x) for x in gate.get("confirm_templates")])
    ok_templates = [t for t in ok_templates if t]
    # Fallback default: known path if present
    default_ok = os.path.join("l9", "assets", "dungeon", "ok.png")
    if not ok_templates and os.path.exists(default_ok):
        ok_templates = [default_ok]
    ok_roi = str(dcfg.get("confirm_roi", "center_ui")) if dcfg.get("confirm_roi") is not None else "center_ui"
    ok_region = _roi_region(cfg, ok_roi)
    ok_timeout_s = float(dcfg.get("confirm_timeout_s", cfg.get("timings", {}).get("confirm_timeout_s", 8.0)))
    conf = float(g.get("pyauto_threshold", 0.9))
    # HUD bag icon
    bag_tpl = str(g.get("bag_icon_template", os.path.join("l9", "assets", "ui", "hud", "bag_icon.png")))
    bag_timeout_s = float(g.get("bag_icon_timeout_s", 12.0))
    bag_roi_name = str(g.get("bag_icon_roi", "hud_anchor")) if g.get("bag_icon_roi") is not None else "hud_anchor"
    bag_region = _roi_region(cfg, bag_roi_name)

    print("\n=== Grind Path Recorder (Auto-Gates) ===")
    print("- Focus the game window")
    print("- Walk to a dungeon entrance using: " + ", ".join([k.upper() for k in rec_keys]))
    print("- When you stop, I will try to click OK and wait for loading")
    print(f"- Press {stop_key.upper()} to finish. Supports multiple entrances in sequence.\n")

    start_seg = time.perf_counter()
    segments: list[dict] = []
    events: list[dict] = []
    pressed: set[str] = set()
    last_activity = time.perf_counter()
    gate_counter = 0

    def push_segment():
        nonlocal events
        if events:
            segments.append({"id": f"segment{len(segments)+1}", "events": list(events)})
            events.clear()

    def on_key(e):
        nonlocal last_activity
        try:
            name = (e.name or "").lower()
            if name in allowed and e.event_type in ("down", "up"):
                t = time.perf_counter() - start_seg
                events.append({"t": t, "type": e.event_type, "key": name})
                last_activity = time.perf_counter()
                if e.event_type == "down":
                    pressed.add(name)
                else:
                    pressed.discard(name)
        except Exception:
            pass

    keyboard.hook(on_key)

    def try_click_ok() -> bool:
        # Quick scan: check templates once; if visible, click
        if not pag or not ok_templates:
            return False
        for t in ok_templates:
            try:
                box = pag.locateOnScreen(t, confidence=conf, region=ok_region) if ok_region else pag.locateOnScreen(t, confidence=conf)
            except Exception:
                box = None
            if box:
                cx = box.left + box.width // 2
                cy = box.top + box.height // 2
                try:
                    pag.click(x=cx, y=cy)
                except Exception:
                    pass
                return True
        return False

    def wait_loading():
        # base teleport wait
        wait_s = float(cfg.get("timings", {}).get("teleport_min_wait_s", 3.5))
        time.sleep(wait_s)
        # randomized post wait
        import random as _rnd
        lo = float(cfg.get("timings", {}).get("teleport_post_wait_min_s", 2.0))
        hi = float(cfg.get("timings", {}).get("teleport_post_wait_max_s", 3.0))
        if hi < lo:
            hi = lo
        time.sleep(_rnd.uniform(lo, hi))
        # bag icon gate
        if not pag:
            return
        end = time.time() + max(0.0, bag_timeout_s)
        while time.time() < end:
            try:
                box = pag.locateOnScreen(bag_tpl, confidence=conf, region=bag_region) if bag_region else pag.locateOnScreen(bag_tpl, confidence=conf)
                if box:
                    return
            except Exception:
                pass
            time.sleep(0.2)

    try:
        while True:
            if keyboard.is_pressed(stop_key):
                push_segment()
                break
            # If idle and previously active, try a gate
            idle_for = (time.perf_counter() - last_activity) * 1000.0
            if not pressed and idle_for >= idle_ms:
                # Attempt gate detection/click
                clicked = try_click_ok()
                if clicked:
                    gate_counter += 1
                    push_segment()
                    # reset segment timer
                    start_seg = time.perf_counter()
                    wait_loading()
                    last_activity = time.perf_counter()
                    continue
            time.sleep(0.01)
    finally:
        try:
            keyboard.unhook(on_key)
        except Exception:
            pass

    if not segments:
        print("No segments recorded.")
        return 1
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"version": 3, "segments": segments}, f, indent=2)
    n_clicks = sum(1 for s in segments for e in s.get("events", []) if e.get("type") == "mclick")
    n_keys = sum(1 for s in segments for e in s.get("events", []) if e.get("type") in ("down", "up", "kdown", "kup"))
    print(f"Saved auto-gated path to {out_path} ({len(segments)} segments; {n_keys} key events)")
    return 0
def record_multi(cfg: dict, out_path: str) -> int:
    try:
        import keyboard  # type: ignore
    except ModuleNotFoundError:
        print("[ERROR] The 'keyboard' module is required. Install with: python -m pip install keyboard")
        return 2
    try:
        import mouse  # type: ignore
    except ModuleNotFoundError:
        mouse = None  # type: ignore
    g = (cfg.get("grind", {}) or {})
    stop_key = str(g.get("record_stop_key", "f12"))
    split_key = str(g.get("record_split_key", "f9")).lower()
    # Keys to record (configurable)
    default_keys = ["w", "a", "s", "d"]
    cfg_keys = g.get("record_keys") if isinstance(g.get("record_keys"), list) else None
    rec_keys = [str(k).lower() for k in (cfg_keys or default_keys)]
    allowed = set(rec_keys)
    print("\n=== Grind Path Recorder (Multi-Segment) ===")
    print("- Focus the game window")
    print("- Walk/click a segment using: " + ", ".join([k.upper() for k in rec_keys]))
    print(f"- Press {split_key.upper()} to start a new segment; press {stop_key.upper()} to finish\n")
    if mouse is not None:
        print("- Mouse clicks will also be recorded")
    else:
        print("- Mouse clicks recorded via Windows fallback; or install 'mouse' for full hooks")

    start = time.perf_counter()
    segments = []  # list of dicts: {id, events}
    current_events = []

    def on_key(e):
        try:
            name = (e.name or "").lower()
            if name == split_key and e.event_type == "down":
                if current_events:
                    segments.append({"id": f"segment{len(segments)+1}", "events": list(current_events)})
                    current_events.clear()
                    print(f"[split] Started new segment (total: {len(segments)})")
                return
            if name in allowed and e.event_type in ("down", "up"):
                t = time.perf_counter() - start
                current_events.append({"t": t, "type": e.event_type, "key": name})
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
            current_events.append({"t": t, "type": "mclick", "button": str(btn), "x": int(x), "y": int(y)})
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
        # WinAPI polling fallback for mouse clicks (no deps)
        last_l = 0
        last_r = 0
        def _cursor_pos() -> tuple[int, int] | None:
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
                        current_events.append({"t": t, "type": "mclick", "button": "left", "x": pos[0], "y": pos[1]})
                if r and not last_r:
                    pos = _cursor_pos()
                    if pos:
                        t = time.perf_counter() - start
                        current_events.append({"t": t, "type": "mclick", "button": "right", "x": pos[0], "y": pos[1]})
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

    if current_events:
        segments.append({"id": f"segment{len(segments)+1}", "events": list(current_events)})

    if not segments:
        print("No segments recorded.")
        return 1

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"version": 3, "segments": segments}, f, indent=2)
    n_clicks = sum(1 for s in segments for e in s.get("events", []) if e.get("type") == "mclick")
    n_keys = sum(1 for s in segments for e in s.get("events", []) if e.get("type") in ("down", "up", "kdown", "kup"))
    print(f"Saved multi-segment path to {out_path} ({len(segments)} segments; {n_clicks} clicks, {n_keys} key events)")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Record path for Grind flow")
    p.add_argument("--config", default="l9/config.yaml")
    p.add_argument("--multi", action="store_true", help="Record multi-segment path (use split key)")
    p.add_argument("--auto-gates", action="store_true", help="Auto-detect OK at idle, wait load, split segments")
    args = p.parse_args(argv)
    cfg = load_config(args.config)
    out = path_file(cfg)
    if args.auto_gates:
        return record_auto_gates(cfg, out)
    if args.multi:
        return record_multi(cfg, out)
    return record(cfg, out)


if __name__ == "__main__":
    raise SystemExit(main())
