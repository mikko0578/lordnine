from __future__ import annotations

import logging
from contextlib import contextmanager


logger = logging.getLogger(__name__)

try:
    import keyboard  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    keyboard = None


class Panic(Exception):
    pass


class Safety:
    def __init__(self, cfg: dict) -> None:
        self.cfg = cfg
        self.panic_combo = str(cfg.get("keybinds", {}).get("panic_key", "shift+escape"))
        if keyboard is None:
            logger.warning("keyboard module not installed; panic key disabled")

    def check(self) -> None:
        if keyboard is None:
            return
        try:
            if keyboard.is_pressed(self.panic_combo):
                raise Panic("Panic key pressed")
        except RuntimeError:
            # On some systems this may require elevated privileges; ignore
            pass

    @contextmanager
    def guard(self):
        try:
            self.check()
            yield
            self.check()
        except Panic:
            logger.error("Panic triggered; aborting flow")
            raise

