L9 AI Context and Guidelines

Purpose
- Single source of truth for any AI assistant working on this repository. Read this first to understand the app’s architecture, flows, assets, config, and conventions.

High-Level Overview
- App: Lordnine automation tools (Windows-focused), using on-screen image recognition and input synthesis to automate in-game actions.
- Core parts:
  - Launcher GUI: scripts/gui.py
  - Flows (state machines): l9/flows/*.py
  - Vision utilities: l9/vision/*
  - Input and window focus: l9/actions/*
  - Config: l9/config.yaml (merged with defaults from l9/config_loader.py)
  - Assets (templates): l9/assets/**
  - Runner: scripts/run_flow.py

Current Behavior – End-to-End Flow
- Launcher runs one flow: l9.flows.grind_refill_loop:GrindRefillLoop
  - Wait until potions are empty (idle loop; no movement when potions exist)
  - When empty, perform REFILL sequence:
    1) ReturnTownFlow: focus window, press return-to-town, verify merchant icon
    2) DismantleFlow: open inventory once, open dismantle, quick add, dismantle, close inventory
    3) BuyPotionsFlow: navigate to merchant, open shop, auto-purchase, confirm, verify HUD shows potions
    4) GrindFlow: open map once, select area, teleporter, fast-travel (+optional confirm), replay path to spot, start auto-battle
  - Loop back to potion check; wait if potions exist; repeat when empty

Important Design Decisions
- Single orchestration point: GrindRefillLoop owns the entire loop (no pre-sequence from GUI).
- No chained flows inside Dismantle: DismantleFlow ends without calling BuyPotionsFlow internally.
- Stable potion checks:
  - Use ROI (potion_slot or hud_anchor) and sample multiple frames to avoid false positives.
  - BuyPotionsFlow VERIFY waits up to confirm_timeout_s for HUD to show potions have returned.
- Input determinism:
  - press_once is used for toggles like opening map/inventory to avoid repeated presses (press_repeats in config is ignored for press_once).
- Debug screenshots: controlled by config; when `debug.screenshot_on_failure: true`, failures can save images to `./debug`.

Launcher GUI Snapshot
- File: scripts/gui.py:249
  - Buttons: Upload Images, Record Path, Settings, Start, Stop
  - Starts GrindRefillLoop in a background thread; logs stream into GUI
  - Elevates to admin on Windows before running (for reliable input)

Flows (Key Files)
- GrindRefillLoop: l9/flows/grind_refill_loop.py:29
  - States: START → CHECK → (REFILL | WAIT) → GRIND → CHECK
  - CHECK: if empty → REFILL; else → WAIT (idle sleep, then re-check)
  - REFILL: ReturnTown → Dismantle → Buy → then GRIND
  - GRIND: executes GrindFlow; then loops back to CHECK

- ReturnTownFlow: l9/flows/return_town.py:14
  - Focus window (WindowManager.ensure_focus)
  - Press keybinds.return_to_town (press_once)
  - Wait timings.teleport_min_wait_s
  - Verify merchant icon (l9/assets/npc/general_merchant_icon.png)

- DismantleFlow: l9/flows/dismantle.py:19
  - OPEN_INV: press_once inventory key; then locate and click dismantle icon
  - QUICK_ADD → DISMANTLE → close inventory (click close or press_once inventory)
  - Does not call other flows; returns DONE

- BuyPotionsFlow: l9/flows/buy_potions.py:31
  - CHECK_POTIONS: if status != EMPTY → DONE (skip); else continue
  - If already in town (merchant icon found) → skip ReturnTown and go to NAVIGATE_MERCHANT
  - OPEN_SHOP: waits for auto-purchase button
  - AUTO_PURCHASE: click purchase; wait for confirm; click confirm
  - VERIFY: waits up to timings.confirm_timeout_s for _potion_status_stable() to be HAS
  - DONE: returns control to loop

- GrindFlow: l9/flows/grind.py
  - OPEN_MAP: press_once map, then pause >= 1s
  - SELECT_REGION: click region template first (l9/assets/grind/region.png), pause >= 1s
  - SELECT_AREA: click area, pause >= 1s
  - SELECT_TELEPORTER: click teleporter, pause >= 1s
  - FAST_TRAVEL: click fast travel; if confirm appears, click; pause >= 1s either way
  - WAIT_TELEPORT: sleep timings.teleport_min_wait_s; then 2–3s randomized post-teleport delay
  - WAIT_HUD: wait for HUD bag icon (configurable template/ROI/timeout)
  - MOVE_TO_SPOT: replay recorded path (configurable keys + mouse clicks) from l9/data/grind_paths/{area_or_spot}.json
  - START_BATTLE: press_once autobattle; pause >= 1s; DONE
  - Note: per-action pause is controlled by timings.grind_action_min_s (min 1.0s)

Vision & Input
- Vision matching: l9/vision/match.py
  - Uses cv2.TM_CCOEFF_NORMED by default; multi-scale; NMS; grayscale by default
  - Uses ROI support derived from fractions in config
  - On miss: logs debug info; optional screenshot saving when enabled in config
- Screen capture: l9/vision/capture.py
  - MSS with monitor index; tracks last_origin (for click mapping)
- Input synthesis: l9/actions/input.py
  - press_once(key): single down/up ignoring press_repeats
  - press(key): respects input.press_repeats
  - click(x, y): multiple backends (pydirectinput, pyautogui, WinAPI, optional WM messages)
  - Window focus check before input via WindowManager.ensure_focus()

Assets (templates)
- Paths under l9/assets/**
  - UI/HUD: l9/assets/ui/hud/potion_empty.png
  - Town marker & merchant: l9/assets/npc/general_merchant_icon.png
  - Shop UI: l9/assets/shop/auto_purchase_button.png, confirm_button.png, close_button.png
  - Grind: l9/assets/grind/region.png, area.png, teleporter.png, fast_travel.png, confirm.png
  - Dismantle: l9/assets/dismantle/icon.png, quick_add.png, dismantle_has.png, dismantle_none.png, close_inventory.png
  - Ensure present or upload via GUI → Upload Images

Config
- User config: l9/config.yaml merged with defaults: l9/config_loader.py:DEFAULT_CONFIG
- Key sections:
  - window: title, require_foreground, require_maximized, auto_focus, click_to_focus
  - keybinds: inventory, map, return_to_town, autobattle, etc.
  - match: method, default_threshold, scales, nms_iou
  - buy_potions: pyauto_threshold, empty_check_* sampling, pyauto_fullscreen
  - timings: detection/confirm timeouts, teleport wait, post-store delay, grind_action_min_s
  - rois: potion_slot (recommended), hud_anchor, minimap_anchor

Safety & ToS
- Only run where permitted and compliant with game ToS and local laws.
- Prefer Admin on Windows (UAC prompt); focus target window before sending inputs.
- Panic key can be configured (keybinds.panic_key) via actions/safety (not shown above).

Run & Build
- Local run GUI: python scripts/gui.py
- Run a specific flow (headless):
  - python scripts/run_flow.py --flow l9.flows.grind_refill_loop:GrindRefillLoop --config l9/config.yaml

Common Gotchas & Fixes
- Repeating keypresses: use Actions.press_once for toggles (map/inventory/autobattle).
- Buy verify flakiness: VERIFY now waits up to confirm_timeout_s for status == HAS.
- Duplicate return/dismantle/buy: DismantleFlow no longer calls BuyPotionsFlow; orchestration lives in GrindRefillLoop.
- Unwanted early grind: When potions exist, GrindRefillLoop idles in WAIT and does not move.
- Debug screenshots: disabled; do not expect files in ./debug.

AI Contribution Guidelines
- Keep changes minimal and scoped to requested behavior; avoid wide refactors.
- Centralize tunables in l9/config.yaml or l9/config_loader.py defaults.
- Favor Windows compatibility; avoid OS-specific assumptions.
- Do not add dependencies without approval.
- Ensure flows are explicit state machines; add states with clear entry/exit and error handling.
- When adding assets or ROIs, list exact filenames and expected locations.

Quick Cross-References (by file:line)
- scripts/gui.py:289 — Launches GrindRefillLoop only
- l9/flows/grind_refill_loop.py:90 — CHECK → (REFILL | WAIT)
- l9/flows/grind_refill_loop.py:95 — REFILL sequence then GRIND
- l9/flows/dismantle.py:140 — NEXT → DONE (no chained buy)
- l9/flows/buy_potions.py:164 — CHECK_POTIONS skips if not empty; VERIFY waits for HAS
- l9/flows/grind.py:128 — press_once map; 1s pauses between actions
- l9/vision/match.py:173 — On miss: log only, no screenshot

How To Use This File
- When opening a new chat or using a new assistant, point it to L9_AI_CONTEXT.md to ingest the app’s semantics and constraints before making changes.
Recent Updates (2025-09-08)
- Revive handling
  - New flow: l9/flows/revive.py detects a death screen and clicks Revive. If present, also clicks Stat Reclaim → Retrieve. Uses ROI `rois.revive_ui` and per-template thresholds.
  - Integrated into l9/flows/grind_refill_loop.py with priority: revive first, then check potions to decide REFILL vs GRIND.
  - Assets expected: l9/assets/revive/revive_button.png, l9/assets/revive/stat_reclaim.png, l9/assets/revive/retrieve.png.

- Grind flow robustness
  - Post-teleport wait randomized 2–3s (config: timings.teleport_post_wait_min_s, teleport_post_wait_max_s).
  - New HUD readiness check: wait for bag icon before moving (config: grind.bag_icon_template, bag_icon_timeout_s, bag_icon_roi).
  - Multi-spot support: three spots with per-spot templates under l9/assets/grind/spots/spot{1..3}/; active spot selected in GUI. Path files default to l9/data/grind_paths/spot{n}.json.

- GUI improvements (scripts/gui.py)
  - New “Manage Spots” dialog: rename Spot 1–3, upload spot-specific templates, record a path per spot.
  - Spot selector dropdown on the main toolbar.
  - Upload Assets now includes HUD “Bag Icon” and Revive templates.

- Build & packaging
  - PyInstaller specs (lordnine_gui.spec, lordnine_runner.spec) updated with hidden imports to bundle dynamic modules and include l9/assets/** and l9/config.yaml.
  - Build script scripts/build_exe.ps1 verifies common Python modules and builds both GUI and Runner; GUI can be UAC-elevated via -Admin.

- Input quality (earlier update)
  - Mouse glides to click targets using a smooth move with optional per-click random duration (input.mouse_move_duration_ms_min/max) and optional human-like pauses after actions (timings.random_action_pause).

Recent Updates (2025-09-10)
- Path recording improvements
  - Recorder now captures configurable keys (`grind.record_keys`) rather than only WASD; defaults remain W/A/S/D.
  - Mouse clicks are recorded. Prefers optional `mouse` module; on Windows, a WinAPI fallback captures left/right clicks without extra deps.
  - Saved path format version bumped to 2, including `mclick` events with `x/y/button` plus key `down/up` entries.
  - Playback replays both keys and clicks via `Actions.click`, and ensures any pressed keys are released at the end.

- GUI fix & messaging
  - Fixed UnboundLocalError in Manage Spots → Record Path.
  - Recording prompts show which keys are recorded and note mouse click capture with Windows fallback.

- Config additions
  - `grind.record_keys`: list of lowercase key names to capture; example default includes: w, a, s, d, e, z.
