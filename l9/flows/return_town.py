from __future__ import annotations

import logging
import time

from .base import Flow
from ..actions.window import WindowManager


logger = logging.getLogger(__name__)


class ReturnTownFlow(Flow):
    """Return to town by pressing the configured key and confirming arrival.

    - Focuses the game window using WindowManager
    - Presses `keybinds.return_to_town`
    - Waits a minimum teleport time
    - Confirms arrival by detecting the merchant icon template
    """

    T_MERCHANT_ICON = "l9/assets/npc/general_merchant_icon.png"

    def run(self) -> None:
        # Focus window
        try:
            wm = WindowManager(self.cfg)
            ok = wm.ensure_focus()
            logger.info("Window focus %s (fg=%r)", "OK" if ok else "FAILED", wm.get_foreground_title())
        except Exception as e:
            logger.warning("Window focus attempt failed: %s", e)

        # Press return-to-town key
        key = str(self.cfg.get("keybinds", {}).get("return_to_town", "r"))
        try:
            # Use single press to avoid repeats
            self.a.press_once(key)
        except Exception:
            # Fallback to standard press
            self.a.press(key)

        # Allow teleport animation/loading to complete
        min_wait = float(self.cfg.get("timings", {}).get("teleport_min_wait_s", 3.5))
        time.sleep(max(0.0, min_wait))

        # Confirm arrival in town via merchant icon
        town_timeout = float(self.cfg.get("timings", {}).get("return_town_timeout_s", 20.0))
        det = self.wait_for(self.T_MERCHANT_ICON, timeout_s=town_timeout)
        if det or self.dry:
            logger.info("ReturnTownFlow: Arrived in town")
            return
        logger.error("ReturnTownFlow: Timeout waiting for town indicator")
        return

