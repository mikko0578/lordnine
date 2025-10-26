from __future__ import annotations

import logging
import time
import os
from enum import Enum, auto
from typing import Optional

from .base import Flow
from ..vision.color import red_ratio_bgr

from PIL import ImageGrab
from functools import partial
ImageGrab.grab = partial(ImageGrab.grab, all_screens=True)


logger = logging.getLogger(__name__)


class BuyState(Enum):
    START = auto()
    CHECK_POTIONS = auto()
    RETURN_TOWN = auto()
    NAVIGATE_MERCHANT = auto()
    OPEN_SHOP = auto()
    AUTO_PURCHASE = auto()
    VERIFY = auto()
    DONE = auto()
    FAIL = auto()


class BuyPotionsFlow(Flow):
    """
    Flow: Refill potions when empty.

    Steps:
    1) Detect potion-empty indicator on HUD. If not empty, exit.
    2) If not already in town, press return-to-town key (R) and wait for town indicator.
       If already in town (merchant icon visible), skip return.
    3) Click general merchant icon to auto-path and wait for shop UI.
    4) Click auto-purchase and confirm.
    5) Verify potion indicator shows available.

    Required assets (place under l9/assets/...):
      - ui/hud/potion_empty.png            # indicator that you're out of potions
      - npc/general_merchant_icon.png      # town-only icon; used as town marker and to auto-path
      - shop/auto_purchase_button.png      # serves as both shop-open indicator and purchase action
      - shop/confirm_button.png            # confirmation dialog OK button (required)
      - shop/close_button.png              # optional close (X) button
    """

    # Asset paths (relative to repo root)
    T_POTION_EMPTY = "l9/assets/ui/hud/potion_empty.png"
    T_MERCHANT_ICON = "l9/assets/npc/general_merchant_icon.png"
    T_AUTO_PURCHASE = "l9/assets/shop/auto_purchase_button.png"
    T_CONFIRM = "l9/assets/shop/confirm_button.png"
    T_CLOSE = "l9/assets/shop/close_button.png"
    T_POTION_HAS = "l9/assets/ui/hud/potion_has.png"

    def _center(self, det):
        # Compute center click point, adjusting for ROI offset if used.
        if det is None:
            return None
        cx = det.x + det.w // 2
        cy = det.y + det.h // 2
        # Add absolute origin of last capture (monitor + ROI offset)
        try:
            ox, oy = getattr(self.v.capture, "last_origin", (0, 0))
        except Exception:
            ox, oy = (0, 0)
        return cx + ox, cy + oy

    def _click_template(self, template: str, roi_name: Optional[str] = None, threshold: Optional[float] = None, timeout: Optional[float] = None) -> bool:
        if self.dry:
            logger.info("[dry] click_template %s roi=%s", template, roi_name)
            return True
        det = self.wait_for(template, roi_name=roi_name, threshold=threshold, timeout_s=timeout)
        if not det:
            return False
        pt = self._center(det)
        if not pt:
            return False
        self.a.click(pt[0], pt[1])
        return True

    def _potion_status_stable(self) -> str:
        """Return 'EMPTY', 'HAS', or 'UNKNOWN' after sampling multiple frames.

        Uses both empty/has templates if available to reduce false triggers.
        """
        samples = int(self.cfg.get("buy_potions", {}).get("empty_check_samples", 5))
        min_hits = int(self.cfg.get("buy_potions", {}).get("empty_check_min_matches", 4))
        gap = max(0.0, float(self.cfg.get("buy_potions", {}).get("empty_check_interval_ms", 150)) / 1000.0)
        empty_hits = 0
        has_hits = 0
        has_tpl_exists = os.path.exists(self.T_POTION_HAS)
        for _ in range(max(1, samples)):
            try:
                det_empty = self._exists_template(self.T_POTION_EMPTY, roi_name="potion_slot")
            except Exception:
                det_empty = None
            if det_empty:
                empty_hits += 1

            det_has = None
            if has_tpl_exists:
                try:
                    det_has = self._exists_template(self.T_POTION_HAS, roi_name="potion_slot")
                except Exception:
                    det_has = None
                if det_has:
                    has_hits += 1
            time.sleep(gap)

        # Potion status check completed
        if empty_hits >= min_hits and empty_hits >= has_hits:
            return "EMPTY"
        if has_hits >= min_hits and has_hits > empty_hits:
            return "HAS"
        # No color fallback: if inconclusive, report unknown to avoid false positives
        return "UNKNOWN"

    def _exists_template(self, template_path: str, roi_name: Optional[str] = None) -> bool:
        """Check for template via pyautogui.locateOnScreen if enabled, else Vision.detect."""
        # Use pyautogui.locateOnScreen exclusively for potion checks
        try:
            import pyautogui as pag  # type: ignore
        except ModuleNotFoundError:
            logger.warning("pyautogui not available for template check: %s", template_path)
            return False

        try:
            # If fullscreen search requested, let pyautogui pick its own region (primary monitor)
            if bool(self.cfg.get("buy_potions", {}).get("pyauto_fullscreen", False)):
                conf = float(self.cfg.get("buy_potions", {}).get("pyauto_threshold", 0.9))
                box = pag.locateOnScreen(template_path, confidence=conf)
                return box is not None
            # Else compute region from monitor + ROI fractions
            import mss  # type: ignore
            mon_idx = int(self.cfg.get("monitor_index", 1))
            with mss.mss() as s:
                mons = s.monitors
                i = max(1, min(mon_idx, len(mons) - 1))
                mon = mons[i]
                region = (mon["left"], mon["top"], mon["width"], mon["height"])
                frac = (self.cfg.get("rois", {}) or {}).get(roi_name) if roi_name else None
                if frac:
                    x1 = int(mon["left"] + frac[0] * mon["width"])
                    y1 = int(mon["top"] + frac[1] * mon["height"])
                    x2 = int(mon["left"] + frac[2] * mon["width"])
                    y2 = int(mon["top"] + frac[3] * mon["height"])
                    region = (x1, y1, x2 - x1, y2 - y1)
                conf = float(self.cfg.get("buy_potions", {}).get("pyauto_threshold", 0.9))
                box = pag.locateOnScreen(template_path, confidence=conf, region=region)
                return box is not None
        except Exception as e:
            logger.warning("pyautogui locate failed for %s: %s", template_path, e)
            return False

    def run(self) -> None:
        state: BuyState = BuyState.START
        reason: Optional[str] = None

        while True:
            if state is BuyState.START:
                # Buy potions flow started
                state = BuyState.CHECK_POTIONS

            elif state is BuyState.CHECK_POTIONS:
                # Dry-run: exercise the flow without gating on emptiness
                if self.dry:
                    logger.info("[dry] assuming potions empty; skipping return-to-town for dry-run")
                    state = BuyState.NAVIGATE_MERCHANT
                    continue
                # Quick, stable check: if NOT empty, skip this flow (avoid blocking)
                status = self._potion_status_stable()
                if status != "EMPTY":
                    # Potions available, skipping refill
                    state = BuyState.DONE
                    continue
                # Potions empty
                # If already in town (merchant icon visible), skip return
                try:
                    in_town = self._exists_template(self.T_MERCHANT_ICON)
                except Exception:
                    in_town = False
                if in_town or self.dry:
                    # Already in town, skipping return
                    state = BuyState.NAVIGATE_MERCHANT
                else:
                    state = BuyState.RETURN_TOWN

            elif state is BuyState.RETURN_TOWN:
                key = str(self.cfg.get("keybinds", {}).get("return_to_town", "r"))
                self.a.press(key)
                # Allow time for teleport animation/loading
                min_wait = float(self.cfg.get("timings", {}).get("teleport_min_wait_s", 3.5))
                time.sleep(max(0.0, min_wait))
                # Use merchant icon as a town-only indicator
                town_timeout = float(self.cfg.get("timings", {}).get("return_town_timeout_s", 20.0))
                det_town = self.wait_for(self.T_MERCHANT_ICON, timeout_s=town_timeout)
                if det_town or self.dry:
                    # Arrived in town
                    state = BuyState.NAVIGATE_MERCHANT
                else:
                    reason = "Timeout returning to town"
                    state = BuyState.FAIL

            elif state is BuyState.NAVIGATE_MERCHANT:
                clicked = self._click_template(self.T_MERCHANT_ICON)  # full screen search by default
                if not clicked and not self.dry:
                    reason = "Merchant icon not found"
                    state = BuyState.FAIL
                else:
                    # Allow time for auto-pathing to walk to the merchant
                    path_wait = float(self.cfg.get("timings", {}).get("pathing_wait_s", 6.0))
                    time.sleep(path_wait)
                    state = BuyState.OPEN_SHOP

            elif state is BuyState.OPEN_SHOP:
                # Consider the shop open when the auto purchase button is visible
                shop_timeout = float(self.cfg.get("timings", {}).get("shop_open_timeout_s", 12.0))
                det_btn = self.wait_for(self.T_AUTO_PURCHASE, timeout_s=shop_timeout)
                if det_btn or self.dry:
                    state = BuyState.AUTO_PURCHASE
                else:
                    # If the button didn't appear yet, give pathing some time and retry once.
                    time.sleep(2.0)
                    det_btn = self.wait_for(self.T_AUTO_PURCHASE, timeout_s=3.0)
                    if det_btn or self.dry:
                        state = BuyState.AUTO_PURCHASE
                    else:
                        reason = "Auto purchase button not detected"
                        state = BuyState.FAIL

            elif state is BuyState.AUTO_PURCHASE:
                if not self._click_template(self.T_AUTO_PURCHASE):
                    if self.dry:
                        logger.info("[dry] auto purchase clicked")
                    else:
                        reason = "Auto-purchase button not found"
                        state = BuyState.FAIL
                        continue
                # Required confirm: wait then click OK
                confirm_timeout = float(self.cfg.get("timings", {}).get("confirm_timeout_s", 8.0))
                det_confirm = self.wait_for(self.T_CONFIRM, timeout_s=confirm_timeout)
                if det_confirm or self.dry:
                    if not self.dry:
                        pt = self._center(det_confirm)
                        if pt:
                            self.a.click(pt[0], pt[1])
                    # Purchase confirmed
                else:
                    reason = "Confirm dialog not detected"
                    state = BuyState.FAIL
                    continue
                # Post-confirm delay
                time.sleep(float(self.cfg.get("timings", {}).get("post_store_delay_s", 1.0)))
                # Close shop via close button or Esc fallback
                close_wait = float(self.cfg.get("timings", {}).get("close_wait_s", 2.0))
                clicked_close = self._click_template(self.T_CLOSE, timeout=close_wait)
                if not clicked_close and not self.dry:
                    self.a.press(str(self.cfg.get("keybinds", {}).get("close_ui", "esc")))
                # Post-close delay
                time.sleep(float(self.cfg.get("timings", {}).get("post_store_delay_s", 1.0)))
                state = BuyState.VERIFY

            elif state is BuyState.VERIFY:
                if self.dry:
                    logger.info("[dry] assuming potions refilled")
                    state = BuyState.DONE
                else:
                    # Allow HUD to settle, then wait up to a timeout for status to flip to HAS
                    time.sleep(float(self.cfg.get("timings", {}).get("post_store_delay_s", 1.0)))
                    deadline = time.time() + float(self.cfg.get("timings", {}).get("confirm_timeout_s", 8.0))
                    ok = False
                    while time.time() < deadline:
                        status = self._potion_status_stable()
                        if status == "HAS":
                            ok = True
                            break
                        # UNKNOWN or EMPTY: keep waiting briefly
                        time.sleep(0.3)
                    if ok:
                        # Refill succeeded
                        state = BuyState.DONE
                    else:
                        reason = "potion still empty"
                        state = BuyState.FAIL

            elif state is BuyState.DONE:
                # Buy potions flow completed
                return

            elif state is BuyState.FAIL:
                # Buy potions flow failed
                return
