from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
import traceback

# Ensure repo root on sys.path
REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from l9.config_loader import load_config


def to_abs_region(cfg: dict, roi_name: str | None) -> tuple[int, int, int, int] | None:
    try:
        import mss  # type: ignore
    except ModuleNotFoundError:
        print("mss not installed; cannot compute absolute ROI", file=sys.stderr)
        return None
    mon_idx = int(cfg.get("monitor_index", 1))
    with mss.mss() as s:
        mons = s.monitors
        i = max(1, min(mon_idx, len(mons) - 1))
        mon = mons[i]
        if not roi_name:
            return mon["left"], mon["top"], mon["width"], mon["height"]
        frac = (cfg.get("rois", {}) or {}).get(roi_name)
        if not frac:
            return mon["left"], mon["top"], mon["width"], mon["height"]
        x1 = int(mon["left"] + frac[0] * mon["width"])
        y1 = int(mon["top"] + frac[1] * mon["height"])
        x2 = int(mon["left"] + frac[2] * mon["width"])
        y2 = int(mon["top"] + frac[3] * mon["height"])
        return (x1, y1, x2 - x1, y2 - y1)


def guess_potion_region(cfg: dict) -> tuple[int, int, int, int] | None:
    # If potion_slot ROI exists, use it
    region = to_abs_region(cfg, "potion_slot")
    if region and (cfg.get("rois", {}) or {}).get("potion_slot"):
        return region

    # Else try to locate potion_has or potion_empty templates inside hud_anchor
    try:
        import pyautogui as pag  # type: ignore
        import mss  # type: ignore
    except ModuleNotFoundError:
        return to_abs_region(cfg, "hud_anchor")
    mon_idx = int(cfg.get("monitor_index", 1))
    with mss.mss() as s:
        mons = s.monitors
        i = max(1, min(mon_idx, len(mons) - 1))
        mon = mons[i]
        region = to_abs_region(cfg, "hud_anchor")
        conf = float((cfg.get("buy_potions", {}) or {}).get("pyauto_threshold", 0.9))
        for templ in (
            os.path.join(REPO_ROOT, "l9/assets/ui/hud/potion_has.png"),
            os.path.join(REPO_ROOT, "l9/assets/ui/hud/potion_empty.png"),
        ):
            try:
                box = pag.locateOnScreen(templ, confidence=conf, region=region)
                if box:
                    return (box.left, box.top, box.width, box.height)
            except Exception:
                pass
    return region


def save_region_screenshot(cfg: dict, region: tuple[int, int, int, int]) -> str | None:
    try:
        import mss  # type: ignore
        import numpy as np  # type: ignore
        import cv2  # type: ignore
    except ModuleNotFoundError:
        print("opencv-python, numpy, and mss required to save screenshot", file=sys.stderr)
        return None
    left, top, width, height = region
    with mss.mss() as s:
        img = s.grab({"left": left, "top": top, "width": width, "height": height})
        frame = np.asarray(img)[:, :, :3]
    ts = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    outdir = cfg.get("debug", {}).get("dir", "./debug")
    os.makedirs(outdir, exist_ok=True)
    out = os.path.join(outdir, f"potion_roi_{ts}.png")
    cv2.imwrite(out, frame)
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Screenshot the potion ROI or best guess")
    p.add_argument("--config", default="l9/config.yaml")
    args = p.parse_args(argv)
    cfg = load_config(args.config)
    region = guess_potion_region(cfg)
    if not region:
        print("Could not determine region")
        return 1
    path = save_region_screenshot(cfg, region)
    if not path:
        return 2
    # Also print a suggested normalized ROI
    try:
        import mss  # type: ignore
        mon_idx = int(cfg.get("monitor_index", 1))
        with mss.mss() as s:
            mons = s.monitors
            i = max(1, min(mon_idx, len(mons) - 1))
            mon = mons[i]
            x, y, w, h = region
            fx1 = (x - mon["left"]) / mon["width"]
            fy1 = (y - mon["top"]) / mon["height"]
            fx2 = (x + w - mon["left"]) / mon["width"]
            fy2 = (y + h - mon["top"]) / mon["height"]
            print(f"Saved: {path}")
            print(
                "Suggested rois.potion_slot:",
                f"[{fx1:.4f}, {fy1:.4f}, {fx2:.4f}, {fy2:.4f}]",
            )
    except Exception:
        print(f"Saved: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

