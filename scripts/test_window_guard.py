from __future__ import annotations

import argparse
import logging
import time

from l9.config_loader import load_config
from l9.actions.input import Actions
from l9.actions.window import WindowManager


def setup_logging():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s | %(message)s")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Quick test for window guard without EXE")
    p.add_argument("--config", default="l9/config.yaml")
    p.add_argument("--text", default="hello-window-guard")
    p.add_argument("--key", default="enter")
    p.add_argument("--count", type=int, default=1)
    p.add_argument("--interval", type=float, default=0.2)
    args = p.parse_args(argv)

    setup_logging()
    cfg = load_config(args.config)
    wm = WindowManager(cfg)

    title = cfg.get("window", {}).get("title", "")
    req_fg = cfg.get("window", {}).get("require_foreground", False)
    req_max = cfg.get("window", {}).get("require_maximized", False)
    auto = cfg.get("window", {}).get("auto_focus", False)
    logging.info("window guard | title=%r require_foreground=%s require_maximized=%s auto_focus=%s", title, req_fg, req_max, auto)

    ok = wm.ensure_focus()
    logging.info("ensure_focus -> %s (foreground title: %r)", ok, wm.get_foreground_title())

    actions = Actions(cfg, dry_run=False)
    for i in range(args.count):
        logging.info("typing text #%d", i + 1)
        actions.type_text(args.text, interval=args.interval)
        time.sleep(args.interval)
        if args.key:
            logging.info("pressing key: %s", args.key)
            actions.press(args.key)
            time.sleep(args.interval)

    logging.info("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

