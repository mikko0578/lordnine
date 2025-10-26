from __future__ import annotations

import logging
import os

from .base import Flow
from .grind import GrindFlow


logger = logging.getLogger(__name__)


class TestPathFlow(Flow):
    """Replay the recorded grind path only (single or multi‑segment).

    Uses GrindFlow's path resolution and replay logic. Does not open the map
    or teleport; simply replays the recorded events from the current position.
    """

    def run(self) -> None:  # type: ignore[override]
        gf = GrindFlow(self.v, self.a, self.cfg, dry_run=self.dry)
        path_file = gf._path_file()
        if not os.path.exists(path_file):
            logger.error("Recorded path not found: %s", path_file)
            return
        logger.info("Testing recorded path: %s", path_file)
        gf._replay_path(path_file)
        logger.info("Test path replay done")

