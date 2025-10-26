from __future__ import annotations

import logging
import time

from ..base import Flow
from ...actions.window import WindowManager


logger = logging.getLogger(__name__)


class PressRFlow(Flow):
    """Focus the game window then press the return-to-town key after 2 seconds.

    Uses window guard config to bring the window to foreground (and move to
    configured monitor if enabled), waits 2 seconds, then sends the key from
    `keybinds.return_to_town` (default 'r').
    """

    def run(self) -> None:
        logger.info("PressRFlow start: Ensuring foreground window...")
        wm = WindowManager(self.cfg)
        ok = wm.ensure_focus()
        logger.info("Window focus %s (foreground=%r)", "OK" if ok else "FAILED", wm.get_foreground_title())
        # Wait 2 seconds as requested
        time.sleep(2.0)
        key = str(self.cfg.get("keybinds", {}).get("return_to_town", "r"))
        logger.info("Pressing key: %s", key)
        self.a.press(key)
        logger.info("PressRFlow done")

