from __future__ import annotations

import logging
import time
from enum import Enum, auto
from typing import Optional

from PIL import ImageGrab  # type: ignore
from functools import partial

from .base import Flow
from .buy_potions import BuyPotionsFlow
from .dismantle import DismantleFlow
from .return_town import ReturnTownFlow
from .grind import GrindFlow
from .revive import ReviveFlow


# Ensure multi-monitor capture for pyautogui
ImageGrab.grab = partial(ImageGrab.grab, all_screens=True)
logger = logging.getLogger(__name__)


class LState(Enum):
    START = auto()
    CHECK = auto()
    REFILL = auto()
    GRIND = auto()
    WAIT = auto()
    DONE = auto()
    FAIL = auto()


class GrindRefillLoop(Flow):
    T_POTION_EMPTY = "l9/assets/ui/hud/potion_empty.png"

    def _potion_empty(self) -> bool:
        try:
            import pyautogui as pag  # type: ignore
        except ModuleNotFoundError:
            logger.error("pyautogui not available; cannot check potions")
            return False
        conf = float(self.cfg.get("buy_potions", {}).get("pyauto_threshold", 0.9))
        samples = int(self.cfg.get("buy_potions", {}).get("empty_check_samples", 3))
        min_hits = max(1, int(self.cfg.get("buy_potions", {}).get("empty_check_min_matches", 2)))
        gap = max(0.05, float(self.cfg.get("buy_potions", {}).get("empty_check_interval_ms", 150)) / 1000.0)

        # Compute search region: prefer potion_slot ROI, else hud_anchor, else full monitor
        region = None
        try:
            import mss  # type: ignore
            mon_idx = int(self.cfg.get("monitor_index", 1))
            with mss.mss() as s:
                mons = s.monitors
                i = max(1, min(mon_idx, len(mons) - 1))
                mon = mons[i]
                region = (mon["left"], mon["top"], mon["width"], mon["height"])  # default full monitor
                frac = (self.cfg.get("rois", {}) or {}).get("potion_slot")
                if frac is None:
                    frac = (self.cfg.get("rois", {}) or {}).get("hud_anchor")
                if frac is not None:
                    x1 = int(mon["left"] + frac[0] * mon["width"])
                    y1 = int(mon["top"] + frac[1] * mon["height"])
                    x2 = int(mon["left"] + frac[2] * mon["width"])
                    y2 = int(mon["top"] + frac[3] * mon["height"])
                    region = (x1, y1, x2 - x1, y2 - y1)
        except Exception:
            region = None

        hits = 0
        for _ in range(max(1, samples)):
            try:
                if region is not None:
                    box = pag.locateOnScreen(self.T_POTION_EMPTY, confidence=conf, region=region)
                else:
                    box = pag.locateOnScreen(self.T_POTION_EMPTY, confidence=conf)
                if box is not None:
                    hits += 1
            except Exception:
                pass
            time.sleep(gap)
        return hits >= min_hits

    def run(self) -> None:
        state = LState.START
        reason: Optional[str] = None

        while True:
            if state is LState.START:
                # Loop started
                state = LState.CHECK

            elif state is LState.CHECK:
                # Priority: handle death/revive first if visible
                try:
                    revived = ReviveFlow(self.v, self.a, self.cfg, dry_run=self.dry).run()
                except Exception:
                    revived = False
                if revived:
                    # After revive, immediately check potions and branch
                    time.sleep(0.5)
                    if self._potion_empty():
                        # Potions empty
                        state = LState.REFILL
                    else:
                        state = LState.GRIND
                else:
                    # Normal loop: just check potions
                    empty = self._potion_empty()
                    if empty:
                        # Potions empty
                        state = LState.REFILL
                    else:
                        state = LState.WAIT

            elif state is LState.REFILL:
                # Full sequence when out of potions: return -> dismantle -> buy -> grind
                # Returning to town
                ReturnTownFlow(self.v, self.a, self.cfg, dry_run=self.dry).run()
                # Dismantling items
                DismantleFlow(self.v, self.a, self.cfg, dry_run=self.dry).run()
                # Buying potions
                BuyPotionsFlow(self.v, self.a, self.cfg, dry_run=self.dry).run()
                # After sequence, go to grind
                state = LState.GRIND

            elif state is LState.GRIND:
                # Running grind flow
                GrindFlow(self.v, self.a, self.cfg, dry_run=self.dry).run()
                # After grind step, loop back to check potions
                # Small pause to allow HUD to update
                time.sleep(0.5)
                state = LState.CHECK

            elif state is LState.WAIT:
                # Idle and re-check later; do NOT move to grind map if potions remain
                interval_s = max(0.1, float(self.cfg.get("buy_potions", {}).get("empty_check_interval_ms", 150)) / 1000.0)
                time.sleep(interval_s)
                state = LState.CHECK

            elif state is LState.DONE:
                return

            elif state is LState.FAIL:
                # Loop failed
                return
