from __future__ import annotations

import logging
from enum import Enum, auto

from ..base import Flow, State


logger = logging.getLogger(__name__)


class DemoState(Enum):
    START = auto()
    WAIT_MINIMAP = auto()
    DONE = auto()


class DemoFlow(Flow):
    """Example flow that waits for a minimap anchor and exits."""

    def run(self) -> None:
        state: DemoState = DemoState.START
        while state is not DemoState.DONE:
            if state is DemoState.START:
                logger.info("DemoFlow starting")
                state = DemoState.WAIT_MINIMAP
            elif state is DemoState.WAIT_MINIMAP:
                det = self.wait_for("l9/assets/ui/minimap/minimap.png", roi_name="minimap_anchor")
                if det:
                    logger.info("Minimap detected; demo complete")
                    state = DemoState.DONE
                else:
                    logger.warning("Minimap not found within timeout; demo ending")
                    state = DemoState.DONE

