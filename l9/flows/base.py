from __future__ import annotations

import enum
import logging
import time
from typing import Callable, Optional

from ..actions.input import Actions
from ..actions.safety import Safety
from ..vision.match import Vision, Detection


logger = logging.getLogger(__name__)


class State(enum.Enum):
    START = 0
    DONE = 1


class Flow:
    def __init__(self, vision: Vision, actions: Actions, cfg: dict, dry_run: bool = False) -> None:
        self.v = vision
        self.a = actions
        self.cfg = cfg
        self.dry = dry_run
        self.safety = Safety(cfg)

    def wait_for(
        self,
        template_path: str,
        roi_name: Optional[str] = None,
        timeout_s: Optional[float] = None,
        threshold: Optional[float] = None,
        poll_s: float = 0.2,
    ) -> Optional[Detection]:
        deadline = time.time() + (timeout_s or float(self.cfg.get("timings", {}).get("detection_timeout_s", 3.0)))
        while time.time() < deadline:
            with self.safety.guard():
                det = self.v.detect(template_path, roi_name=roi_name, threshold=threshold)
                if det:
                    logger.info("detect ok template=%s score=%.3f x=%d y=%d w=%d h=%d", template_path, det.score, det.x, det.y, det.w, det.h)
                    return det
                time.sleep(poll_s)
        return None

    def run(self) -> None:
        raise NotImplementedError

