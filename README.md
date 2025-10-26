Lordnine Automation Scaffold
===========================

This repo contains a scaffold for building Python automation flows for the MMORPG Lordnine using on-screen image recognition and input synthesis.

Quick Start
-----------

- Place template images under `l9/assets/` (e.g., `l9/assets/ui/minimap/minimap.png`).
- Adjust thresholds, keybinds, and timings in `l9/config.yaml`.
- Run the example demo flow in dry-run mode:

  `python scripts/run_flow.py --dry-run`

GUI Launcher
------------

- Start/stop via a simple GUI:

  `python scripts/gui.py`

- Select the flow (module:Class), choose a config, and toggle dry-run. Logs stream into the window. Stop cleanly via the Stop button.
- Run as Administrator (batch):

  `scripts\run_gui_admin.bat`

  This batch file elevates privileges via UAC and launches `python scripts/gui.py` from the repo root.

Example Flow: Buy Potions
-------------------------

Implement the “refill potions when empty” flow using `BuyPotionsFlow`.

Required assets (place PNGs under these paths):
- `l9/assets/ui/hud/potion_empty.png`
- `l9/assets/ui/town/town_marker.png`
- `l9/assets/npc/general_merchant_icon.png`
- `l9/assets/shop/auto_purchase_button.png`
- `l9/assets/shop/confirm_button.png`
- `l9/assets/shop/close_button.png` (optional)

Run (dry-run first):
- CLI: `python scripts/run_flow.py --flow l9.flows.buy_potions:BuyPotionsFlow --dry-run`
- GUI: set Flow to `l9.flows.buy_potions:BuyPotionsFlow` and Start with Dry-run checked.

Notes:
- The auto-purchase button doubles as the “shop open” indicator; no separate shop frame image required.
- After auto-purchase, the flow waits for and clicks the confirmation OK button, then closes the shop (close button if available, otherwise presses Esc).
- Configure the return-to-town key in `l9/config.yaml` under `keybinds.return_to_town` (default `r`).
- Fine-tune detection thresholds in `l9/config.yaml` and use ROI anchors for performance.

Dependencies
------------

The code is written to work with optional imports. For full functionality, install:

- `opencv-python`
- `numpy`
- `mss`
- `pyautogui`
- `keyboard` (optional, for a panic hotkey)
- `pyyaml` (optional, to load `config.yaml`)
- `pydirectinput` (optional, DirectInput-style input for some games)

Build EXEs (Windows)
--------------------

Package GUI and runner into standalone `.exe` files using PyInstaller.

Prereqs:
- Python 3.10 (64-bit) and a virtualenv
- Install deps above and `pyinstaller`

Build:
- Open PowerShell in the repo root and run:

  `powershell -ExecutionPolicy Bypass -File scripts/build_exe.ps1 -Clean`

Run as Administrator
--------------------

Some games ignore or block inputs from non-elevated processes. You have two options:

- Relaunch GUI elevated at runtime: When you click Start (real run), the GUI will offer to relaunch itself as Administrator. Accept to improve input reliability.
- Build a UAC-elevated GUI EXE: add `-Admin` to the build script so the GUI always requests elevation on launch:

  `powershell -ExecutionPolicy Bypass -File scripts/build_exe.ps1 -Clean -Admin`

Outputs:
- `dist/LordnineGUI/LordnineGUI.exe` (windowed)
- `dist/LordnineRunner/LordnineRunner.exe` (console)
- The build script also copies `LordnineRunner.exe` next to `LordnineGUI.exe` so the GUI can launch it when “Start” is pressed.

Notes:
- If `keyboard` requires admin for global key checks, run the EXE with appropriate permissions or disable the panic key.
- If you update `l9/assets` or `l9/config.yaml`, rebuild to bake new defaults, or point the GUI to an external config.

Flow Development
----------------

Flows are state machines under `l9/flows/`. Implement a class `Flow`-compatible with constructor `(vision, actions, cfg, dry_run)` and a `run()` method. Use `Vision.detect()` and `Flow.wait_for()` to gate transitions, and `Actions` to click/press keys. See `l9/flows/example/demo.py` as a minimal example.

Safety
------

- Always test in `--dry-run` first.
- A panic hotkey can be configured via `keybinds.panic_key` in `l9/config.yaml` (requires `keyboard`).
- Ensure use complies with the game’s Terms of Service and local laws.
- Optional window guard: set `window.title` (substring), and enable `window.require_foreground`/`require_maximized` to block inputs unless the game is active; set `window.auto_focus` to try focusing the window first (Windows-only).

Calibration Notes
-----------------

- Use the `rois` section in `l9/config.yaml` to restrict search regions and improve performance.
- Start matching thresholds between 0.80–0.90; adjust per template via `threshold_overrides`.
- Provide 1x-scale PNG templates, cropped tightly around the UI element.
