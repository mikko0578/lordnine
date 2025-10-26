from __future__ import annotations

import os
import sys

# Ensure repo root on sys.path when running as a script
REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


BUY_POTIONS_ASSETS = [
    "l9/assets/ui/hud/potion_empty.png",
    "l9/assets/npc/general_merchant_icon.png",
    "l9/assets/shop/auto_purchase_button.png",
    "l9/assets/shop/confirm_button.png",
    # Optional
    "l9/assets/shop/close_button.png",
]


def main() -> int:
    print("Checking BuyPotionsFlow assets...\n")
    missing = []
    for p in BUY_POTIONS_ASSETS:
        abs_path = os.path.join(REPO_ROOT, p)
        exists = os.path.exists(abs_path)
        status = "OK" if exists else "MISSING"
        print(f"{status:8} {p}")
        if not exists:
            missing.append(p)
    print("\nSummary:")
    if not missing:
        print("All required assets present.")
        return 0
    else:
        print(f"Missing {len(missing)} file(s). Optional ones can be skipped.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
