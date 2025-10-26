from __future__ import annotations

import copy
import logging
import os
from typing import Any, Dict


DEFAULT_CONFIG: Dict[str, Any] = {
    "monitor_index": 1,
    "dpi_scale": 1.0,
    "multi_screen": False,  # Enable multi-screen detection
    "screen": {"width": None, "height": None},
    "window": {
        "title": "",
        "require_foreground": False,
        "require_maximized": False,
        "auto_focus": False,
        "force_to_monitor_index": 1,
        "click_to_focus": False,
    },
    "keybinds": {
        "interact": "e",
        "confirm": "enter",
        "open_shop": "i",
        "close_ui": "esc",
        "move_up": "w",
        "move_left": "a",
        "move_down": "s",
        "move_right": "d",
        "panic_key": "shift+escape",
    },
    "match": {
        "method": "TM_CCOEFF_NORMED",
        "use_color": False,
        "multi_scale": True,
        "scales": [0.70, 0.80, 0.90, 1.0, 1.10, 1.20, 1.30],
        "default_threshold": 0.85,
        "nms_iou": 0.3,
        "max_results": 5,
    },
    "threshold_overrides": {},
    "buy_potions": {
        "empty_check_samples": 5,
        "empty_check_min_matches": 4,
        "empty_check_interval_ms": 150,
        "use_pyautogui_locate": True,
        "pyauto_threshold": 0.9,
        "pyauto_fullscreen": True,
        "color": {
            "red_ratio_has": 0.06,
            "red_ratio_empty": 0.02,
            "sat_thresh": 60,
            "val_thresh": 50,
        },
    },
    "revive": {
        "pyauto_threshold": 0.9,
        "revive_button": "l9/assets/revive/revive_button.png",
        "stat_reclaim_button": "l9/assets/revive/stat_reclaim.png",
        "retrieve_button": "l9/assets/revive/retrieve.png",
        "revive_timeout_s": 2.0,
        "reclaim_timeout_s": 3.0,
        "retrieve_timeout_s": 3.0,
    },
    "input": {
        "prefer_direct": False,   # Prefer pydirectinput if available
        "hold_ms": 80,            # Key hold duration per press
        "press_repeats": 1,       # Number of times to press a key
        "repeat_interval_ms": 70, # Delay between repeats
        "mouse_hold_ms": 60,
        "mouse_move_duration_ms": 0, # Smooth pre-click move duration (0 = instant)
        # Optional per-click randomization range (overrides fixed duration if both set)
        "mouse_move_duration_ms_min": None,
        "mouse_move_duration_ms_max": None,
        "use_wm_messages": False, # Also send WM_* mouse messages to window
        "fire_all_click_backends": False, # Fire all click backends sequentially
        "wiggle_before_click": False,     # Send a tiny relative move before clicking
        "click_repeats": 1,               # Number of click repeats per call
        "click_interval_ms": 80,          # Delay between repeated clicks
    },
    "timings": {
        "wait_min_ms": 60,
        "wait_max_ms": 120,
        "default_timeout_s": 5.0,
        "detection_timeout_s": 3.0,
        "action_retry_count": 3,
        "action_retry_backoff_s": 0.5,
        "pathing_wait_s": 6.0,
        "shop_open_timeout_s": 12.0,
        "return_town_timeout_s": 20.0,
        "teleport_min_wait_s": 3.5,
        # Randomized post-teleport wait window (seconds)
        "teleport_post_wait_min_s": 2.0,
        "teleport_post_wait_max_s": 3.0,
        "confirm_timeout_s": 8.0,
        "close_wait_s": 2.0,
        "post_store_delay_s": 1.0,
    "grind_action_min_s": 1.0,
        # Optional human-like post-action pause (random per action)
        "random_action_pause": False,
        "action_pause_min_ms": 1000,
        "action_pause_max_ms": 3000,
    },
    "grind": {
        "active_spot_id": 1,
        "spots": [
            {
                "id": 1,
                "name": "Spot 1",
                "region_template": "l9/assets/grind/spots/spot1/region.png",
                "area_template": "l9/assets/grind/spots/spot1/area.png",
                "teleporter_template": "l9/assets/grind/spots/spot1/teleporter.png",
                "fast_travel_template": "l9/assets/grind/spots/spot1/fast_travel.png",
                "confirm_template": "l9/assets/grind/spots/spot1/confirm.png",
            },
            {
                "id": 2,
                "name": "Spot 2",
                "region_template": "l9/assets/grind/spots/spot2/region.png",
                "area_template": "l9/assets/grind/spots/spot2/area.png",
                "teleporter_template": "l9/assets/grind/spots/spot2/teleporter.png",
                "fast_travel_template": "l9/assets/grind/spots/spot2/fast_travel.png",
                "confirm_template": "l9/assets/grind/spots/spot2/confirm.png",
            },
            {
                "id": 3,
                "name": "Spot 3",
                "region_template": "l9/assets/grind/spots/spot3/region.png",
                "area_template": "l9/assets/grind/spots/spot3/area.png",
                "teleporter_template": "l9/assets/grind/spots/spot3/teleporter.png",
                "fast_travel_template": "l9/assets/grind/spots/spot3/fast_travel.png",
                "confirm_template": "l9/assets/grind/spots/spot3/confirm.png",
            },
        ],
        "pyauto_threshold": 0.9,
        "record_stop_key": "f12",
        # Loading completion indicator (HUD bag icon)
        "bag_icon_template": "l9/assets/ui/hud/bag_icon.png",
        "bag_icon_timeout_s": 12.0,
        # ROI name to search for bag icon (defaults to hud_anchor if None)
        "bag_icon_roi": "hud_anchor",
    },
    "rois": {
        "minimap_anchor": [0.80, 0.00, 1.00, 0.20],
        "hud_anchor": [0.00, 0.80, 1.00, 1.00],
        # Death/revive UI often appears around center; adjust as needed.
        # Format: [x1, y1, x2, y2] in normalized screen coords.
        "revive_ui": [0.25, 0.20, 0.75, 0.85],
        # Optional precise ROI for potion slot (x1,y1,x2,y2 normalized). If not set, falls back to hud_anchor.
        # "potion_slot": [0.92, 0.82, 0.98, 0.96],
    },
    "debug": {
        "enabled": False,  # Disabled for stealth
        "screenshot_on_failure": False,  # Disabled for stealth
        "dir": "./debug",
        "log_level": "WARNING",  # Reduced logging for stealth
        "screenshot_format": "png",
    },
    "stealth": {
        "enabled": True,
        "disable_logging": True,
        "minimal_console_output": True,
        "randomize_timings": True,
        "human_like_delays": True,
    },
}


def deep_update(base: Dict[str, Any], update: Dict[str, Any]) -> Dict[str, Any]:
    for k, v in update.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            base[k] = deep_update(base[k], v)
        else:
            base[k] = v
    return base


def load_config(path: str = "l9/config.yaml") -> Dict[str, Any]:
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    if not os.path.exists(path):
        logging.getLogger(__name__).info("Config file not found at %s; using defaults", path)
        return cfg

    try:
        import yaml  # type: ignore

        with open(path, "r", encoding="utf-8") as f:
            user_cfg = yaml.safe_load(f) or {}
        if not isinstance(user_cfg, dict):
            logging.getLogger(__name__).warning("Invalid config format; using defaults")
            return cfg
        return deep_update(cfg, user_cfg)
    except ModuleNotFoundError:
        logging.getLogger(__name__).warning(
            "PyYAML not installed; using default config. To load %s, install pyyaml.", path,
        )
        return cfg
