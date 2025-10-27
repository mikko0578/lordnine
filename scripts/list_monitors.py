from __future__ import annotations

import os
import sys

try:
    import mss
except ModuleNotFoundError:
    mss = None


def main() -> int:
    if mss is None:
        print("mss not installed. Install with: python -m pip install mss")
        return 1
    with mss.mss() as s:
        mons = s.monitors
        print(f"Found {len(mons)-1} monitor(s) [1-based indexing].")
        for i, mon in enumerate(mons):
            if i == 0:
                label = "[0] (all monitors, not used)"
            else:
                label = f"[{i}]"
            print(
                f"{label} left={mon['left']} top={mon['top']} width={mon['width']} height={mon['height']}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

