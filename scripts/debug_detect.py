from __future__ import annotations

import argparse
import os
import sys
import logging

# Ensure repo root on sys.path when running as a script
REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from l9.config_loader import load_config
from l9.vision.match import Vision


def setup_logging(level: str = "INFO"):
    logging.basicConfig(level=getattr(logging, level, logging.INFO), format="%(asctime)s %(levelname)s %(name)s | %(message)s")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Debug a single template detection and save overlay on miss")
    p.add_argument("--config", default="l9/config.yaml")
    p.add_argument("--template", required=True, help="Path to template (relative to repo root or absolute)")
    p.add_argument("--roi", default=None, help="ROI name from config (e.g., hud_anchor)")
    p.add_argument("--threshold", type=float, default=None)
    args = p.parse_args(argv)

    cfg = load_config(args.config)
    setup_logging(cfg.get("debug", {}).get("log_level", "INFO"))
    v = Vision(cfg, dry_run=False)

    templ_path = args.template
    if not os.path.isabs(templ_path):
        templ_path = os.path.join(REPO_ROOT, templ_path)
    logging.info("Detecting template=%s roi=%s", templ_path, args.roi)
    det = v.detect(templ_path, roi_name=args.roi, threshold=args.threshold)
    if det:
        logging.info("FOUND: score=%.3f x=%d y=%d w=%d h=%d scale=%.2f", det.score, det.x, det.y, det.w, det.h, det.scale)
        return 0
    else:
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
