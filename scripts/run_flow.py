from __future__ import annotations

import argparse
import importlib
import logging
import os
import sys

# Ensure repo root on sys.path when running as a script
import os
import sys

REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from l9.config_loader import load_config
from l9.vision.match import Vision
from l9.actions.input import Actions


def setup_logging(level: str) -> None:
    lvl = getattr(logging, level.upper(), logging.WARNING)  # Default to WARNING for stealth
    logging.basicConfig(
        level=lvl,
        format="%(asctime)s %(levelname)s %(name)s | %(message)s",
    )


def load_flow(flow_path: str):
    if ":" in flow_path:
        mod_name, cls_name = flow_path.split(":", 1)
    else:
        mod_name, cls_name = flow_path, "Flow"
    mod = importlib.import_module(mod_name)
    cls = getattr(mod, cls_name)
    return cls


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Lordnine automation runner")
    p.add_argument("--flow", default="l9.flows.example.demo:DemoFlow", help="module:Class of the flow to run")
    p.add_argument("--config", default="l9/config.yaml")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)

    cfg = load_config(args.config)
    setup_logging(cfg.get("debug", {}).get("log_level", "INFO"))

    try:
        vision = Vision(cfg, dry_run=args.dry_run)
        actions = Actions(cfg, dry_run=args.dry_run)
        FlowCls = load_flow(args.flow)
        flow = FlowCls(vision, actions, cfg, dry_run=args.dry_run)
        flow.run()
        return 0
    except KeyboardInterrupt:
        # Runner interrupted; exiting cleanly
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
