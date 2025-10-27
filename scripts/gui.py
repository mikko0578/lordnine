from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
from tkinter import ttk
import time
try:
    # Ensure multi-monitor screenshots for potion check
    from PIL import ImageGrab  # type: ignore
    from functools import partial
    ImageGrab.grab = partial(ImageGrab.grab, all_screens=True)
except Exception:
    pass
import shutil

# Ensure repo root on sys.path when running as a script
# Handle both development and executable modes
if getattr(sys, 'frozen', False):
    # Running as executable - assets are in the same directory as the exe
    REPO_ROOT = os.path.dirname(sys.executable)
else:
    # Running as script - go up one level from scripts directory
    REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))

if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from l9.config_loader import load_config
from l9.actions.window import WindowManager


def repo_path(*parts: str) -> str:
    if getattr(sys, 'frozen', False):
        # Running as executable - config is in the same directory as the exe
        here = os.path.dirname(sys.executable)
        return os.path.normpath(os.path.join(here, *parts))
    else:
        # Running as script - go up one level from scripts directory
        here = os.path.dirname(os.path.abspath(__file__))
        return os.path.normpath(os.path.join(here, "..", *parts))


def _is_admin() -> bool:
    try:
        import ctypes  # type: ignore
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _relaunch_as_admin():
    try:
        import ctypes  # type: ignore
        if getattr(sys, "frozen", False):
            exe = sys.executable
            cwd = os.path.dirname(exe)
            ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, None, cwd, 1)
        else:
            exe = sys.executable
            script = os.path.abspath(__file__)
            cwd = os.path.dirname(script)
            ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, f'"{script}"', cwd, 1)
        return True
    except Exception:
        return False


class LauncherGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Lordnine Automation Launcher")
        self.proc: subprocess.Popen | None = None
        self.log_queue: queue.Queue[str] = queue.Queue()
        self.reader_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

        # Controls
        frm = tk.Frame(root, padx=10, pady=10)
        frm.pack(fill=tk.BOTH, expand=True)

        # Internal config path reference
        self.cfg_path = repo_path("l9", "config.yaml")

        # Row 1: Start/Stop buttons (primary controls)
        self.start_btn = tk.Button(frm, text="Start", width=12, command=self.start)
        self.stop_btn = tk.Button(frm, text="Stop", width=12, command=self.stop, state=tk.DISABLED)
        self.start_btn.grid(row=0, column=0, sticky="w", pady=(5, 5))
        self.stop_btn.grid(row=0, column=1, sticky="w", padx=(8, 0), pady=(5, 5))

        # Row 2: Main action buttons
        self.upload_btn = tk.Button(frm, text="Upload Images", width=14, command=self.open_upload_assets)
        self.manage_spots_btn = tk.Button(frm, text="Manage Spots", width=14, command=self.open_manage_spots)
        self.settings_btn = tk.Button(frm, text="Settings", width=12, command=self.open_key_settings)
        self.upload_btn.grid(row=1, column=0, sticky="w", pady=(5, 5))
        self.manage_spots_btn.grid(row=1, column=1, sticky="w", padx=(8, 0), pady=(5, 5))
        self.settings_btn.grid(row=1, column=2, sticky="w", padx=(8, 0), pady=(5, 5))

        # Row 3: Inputs and checkboxes
        # Spot selector
        self.spot_var = tk.StringVar()
        tk.Label(frm, text="Spot:").grid(row=2, column=0, sticky="e", padx=(0, 2), pady=(5, 5))
        self.spot_combo = ttk.Combobox(frm, textvariable=self.spot_var, state="readonly", width=18)
        self.spot_combo.grid(row=2, column=1, sticky="w", pady=(5, 5))
        self._init_spot_combo()
        self.spot_combo.bind("<<ComboboxSelected>>", self._on_spot_selected)
        
        # Multi-screen option
        self.multi_screen_var = tk.BooleanVar()
        self.multi_screen_check = tk.Checkbutton(frm, text="Multi-Screen", variable=self.multi_screen_var, command=self._on_multi_screen_toggle)
        self.multi_screen_check.grid(row=2, column=2, sticky="w", padx=(8, 0), pady=(5, 5))
        self._load_multi_screen_setting()
        
        # Asset status indicator
        self.asset_status_label = tk.Label(frm, text="", font=("Arial", 8))
        self.asset_status_label.grid(row=2, column=3, sticky="w", padx=(8, 0), pady=(5, 5))
        self._update_asset_status()

        # Status row
        self.status_var = tk.StringVar(value="Idle")
        self.admin_var = tk.StringVar(value=("Admin" if _is_admin() else "User"))
        tk.Label(frm, textvariable=self.status_var, anchor="w").grid(row=3, column=0, columnspan=4, sticky="we")
        tk.Label(frm, textvariable=self.admin_var, anchor="e").grid(row=3, column=4, columnspan=2, sticky="e")

        # Logs
        self.log = scrolledtext.ScrolledText(frm, height=12, state=tk.DISABLED)
        self.log.grid(row=4, column=0, columnspan=6, sticky="nsew", pady=(8, 0))

        for c in range(6):
            frm.columnconfigure(c, weight=1)
        frm.rowconfigure(4, weight=1)

        # Close handler and log polling
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.after(100, self._poll_log_queue)

        # Safety & ToS reminder removed

    def _load_cfg(self) -> dict:
        try:
            from l9.config_loader import load_config as _load
            return _load(self.cfg_path)
        except Exception:
            return {}

    def _load_cfg_raw(self) -> dict:
        try:
            import yaml  # type: ignore
            with open(self.cfg_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception:
            return {}

    def _save_cfg(self, cfg: dict) -> bool:
        try:
            import yaml  # type: ignore
        except ModuleNotFoundError:
            messagebox.showerror("Config", "PyYAML not installed. Install with: python -m pip install pyyaml")
            return False
        try:
            with open(self.cfg_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(cfg, f, sort_keys=False)
            return True
        except Exception as e:
            messagebox.showerror("Config", str(e))
            return False

    def _init_spot_combo(self):
        cfg = self._load_cfg()
        g = cfg.get("grind", {}) or {}
        spots = g.get("spots") or []
        names = [str(s.get("name") or f"Spot {s.get('id', i+1)}") for i, s in enumerate(spots)]
        if not names:
            names = ["Spot 1", "Spot 2", "Spot 3"]
        self.spot_combo["values"] = names
        active_id = int(g.get("active_spot_id", 1))
        idx = max(0, min(active_id - 1, len(names) - 1))
        self.spot_combo.current(idx)
        self.spot_var.set(names[idx])

    def _on_spot_selected(self, event=None):
        cfg = self._load_cfg_raw()
        g = cfg.setdefault("grind", {})
        # Map selection index back to spot id positionally (1-based)
        try:
            idx = int(self.spot_combo.current())
        except Exception:
            idx = 0
        g["active_spot_id"] = idx + 1
        if self._save_cfg(cfg):
            # Active spot updated
            pass

    def _on_multi_screen_toggle(self):
        # Update multi-screen setting in config
        cfg = self._load_cfg_raw()
        if not cfg:
            return
        cfg["multi_screen"] = self.multi_screen_var.get()
        self._save_cfg(cfg)

    def _load_multi_screen_setting(self):
        # Load multi-screen setting from config - default to True (always on)
        cfg = self._load_cfg_raw()
        if cfg:
            self.multi_screen_var.set(cfg.get("multi_screen", True))
        else:
            self.multi_screen_var.set(True)

    def _update_asset_status(self):
        """Update the asset status indicator on the main GUI."""
        try:
            asset_status = self._check_assets_status()
            total_assets = len(asset_status)
            existing_assets = sum(1 for info in asset_status.values() if info['exists'])
            
            if existing_assets == total_assets:
                status_text = "✅ Assets Ready"
                color = "green"
            elif existing_assets > total_assets // 2:
                status_text = f"⚠️ {existing_assets}/{total_assets} Assets"
                color = "orange"
            else:
                status_text = f"❌ {existing_assets}/{total_assets} Assets"
                color = "red"
                
            self.asset_status_label.config(text=status_text, fg=color)
        except Exception:
            self.asset_status_label.config(text="❓ Assets Unknown", fg="gray")


    def _append_log(self, text: str):
        self.log.configure(state=tk.NORMAL)
        self.log.insert(tk.END, text)
        self.log.see(tk.END)
        self.log.configure(state=tk.DISABLED)

    def _reader(self, proc: subprocess.Popen):
        try:
            for line in iter(proc.stdout.readline, ""):
                if not line:
                    break
                self.log_queue.put(line)
        except Exception as e:
            self.log_queue.put(f"[reader error] {e}\n")

    def _poll_log_queue(self):
        try:
            while True:
                line = self.log_queue.get_nowait()
                self._append_log(line)
        except queue.Empty:
            pass
        self.root.after(100, self._poll_log_queue)

    def start(self):
        if self.proc and self.proc.poll() is None:
            messagebox.showwarning("Already running", "Automation is already running.")
            return
        cfg = self.cfg_path
        # reset stop flag for new run
        self._stop_event.clear()

        # Elevate to admin on Windows for reliable input
        if os.name == "nt" and not _is_admin():
            # Silent elevation for stealth
            ok = _relaunch_as_admin()
            if not ok:
                messagebox.showerror("Elevation failed", "Could not relaunch with Administrator privileges.")
                return
            self.root.destroy()
            return
        else:
            if os.name == "nt":
                self.admin_var.set("Admin")

        if not os.path.isfile(cfg):
            messagebox.showerror("Config not found", f"Config file not found:\n{cfg}")
            return

        # Preflight: window guard (attempt focus if configured)
        try:
            cfg_obj = load_config(cfg)
            wm = WindowManager(cfg_obj)
            wcfg = cfg_obj.get("window", {}) or {}
            title = wcfg.get("title", "")
            req_fg = bool(wcfg.get("require_foreground", False))
            req_max = bool(wcfg.get("require_maximized", False))
            auto = bool(wcfg.get("auto_focus", False))
            should_run = bool(title) and (req_fg or req_max or auto)
            if should_run:
                self._append_log(
                    f"Window guard: title={title!r} require_fg={req_fg} require_max={req_max} auto_focus={auto}\n"
                )
                ok = wm.ensure_focus()
                fg_title = wm.get_foreground_title()
                if not ok:
                    self._append_log(f"Window guard NOT satisfied. Foreground: {fg_title!r}\n")
                    if req_fg or req_max:
                        messagebox.showerror(
                            "Window guard",
                            "Target window is not foreground/maximized per config.\n\n"
                            f"Foreground now: {fg_title!r}\n"
                            "Adjust window or disable the guard in config, then try again.",
                        )
                        return
                else:
                    self._append_log(f"Window guard OK. Foreground: {fg_title!r}\n")
            else:
                self._append_log("Window guard disabled or no window.title configured; skipping preflight\n")
        except Exception as e:
            self._append_log(f"[warn] Window guard preflight failed: {e}\n")

        # Dependencies check
        missing = []
        for mod in ("mss", "cv2", "numpy", "pyautogui", "yaml"):
            try:
                __import__(mod)
            except Exception:
                missing.append(mod)
        if missing:
            messagebox.showerror(
                "Missing dependencies",
                "Real run requires these modules:\n- " + "\n- ".join(missing) +
                "\n\nInstall with pip, e.g.:\n  python -m pip install mss opencv-python numpy pillow pyautogui keyboard pyyaml",
            )
            return

        # Ensure grind path exists before running sequence
        try:
            cfg_obj = load_config(cfg)
            path = self._grind_path_file(cfg_obj)
            if not os.path.exists(path):
                if messagebox.askyesno(
                    "Grind Path Missing",
                    "No recorded path found for this area.\n\nRecord now? (Press F12 to stop)",
                ):
                    self.record_path()
                else:
                    return
        except Exception:
            pass

        # Optional: verify assets before launch
        try:
            script = repo_path("scripts", "check_assets.py")
            if os.path.isfile(script):
                out = subprocess.check_output([sys.executable, script], text=True, cwd=REPO_ROOT)
                self._append_log(out + ("\n" if not out.endswith("\n") else ""))
        except subprocess.CalledProcessError as e:
            self._append_log(e.output + ("\n" if e.output and not e.output.endswith("\n") else ""))
            messagebox.showwarning("Assets", "Some assets are missing. See log for details.")
            return
        except Exception:
            pass

        # Kick off the fixed sequence on a background thread to avoid blocking the GUI
        self.log.configure(state=tk.NORMAL)
        self.log.delete("1.0", tk.END)
        self.log.configure(state=tk.DISABLED)
        self.status_var.set("Running")
        self.start_btn.configure(state=tk.DISABLED)
        self.stop_btn.configure(state=tk.NORMAL)

        def run_sequence():
            try:
                def build_cmd(flow_str: str) -> list[str]:
                    is_frozen = getattr(sys, "frozen", False)
                    if is_frozen:
                        runner_exe = os.path.join(os.path.dirname(sys.executable), "LordnineRunner.exe")
                        return [runner_exe, "--flow", flow_str, "--config", cfg]
                    else:
                        return [
                            sys.executable,
                            "-u",
                            repo_path("scripts", "run_flow.py"),
                            "--flow",
                            flow_str,
                            "--config",
                            cfg,
                        ]

                # Check potion status first
                def is_potion_empty() -> bool:
                    try:
                        import pyautogui as pag  # type: ignore
                    except ModuleNotFoundError:
                        return False
                    t_path = os.path.join(REPO_ROOT, "l9", "assets", "ui", "hud", "potion_empty.png")
                    conf = float((self._load_cfg().get("buy_potions", {}) or {}).get("pyauto_threshold", 0.9))
                    try:
                        box = pag.locateOnScreen(t_path, confidence=conf)
                        return box is not None
                    except Exception:
                        return False

                # Defer all checks and refill logic to GrindRefillLoop only
                flows = [
                    "l9.flows.grind_refill_loop:GrindRefillLoop",
                ]
                for idx, fstr in enumerate(flows, start=1):
                    self.log_queue.put(f"\n=== Step {idx}/{len(flows)}: {fstr} ===\n")
                    cmd = build_cmd(fstr)
                    self.proc = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        bufsize=1,
                        cwd=REPO_ROOT,
                    )
                    self.reader_thread = threading.Thread(target=self._reader, args=(self.proc,), daemon=True)
                    self.reader_thread.start()
                    rc = self.proc.wait()
                    if rc not in (0, 130):
                        self.log_queue.put(f"Step failed with code {rc}. Aborting.\n")
                        break
            except Exception as e:
                # marshal error to UI thread via log
                self.log_queue.put(f"[error] Launch failed: {e}\n")
            finally:
                # reset controls on UI thread
                self.root.after(0, lambda: self.status_var.set("Idle"))
                self.root.after(0, lambda: self.start_btn.configure(state=tk.NORMAL))
                self.root.after(0, lambda: self.stop_btn.configure(state=tk.DISABLED))

        threading.Thread(target=run_sequence, daemon=True).start()

    # Removed Potion ROI per prior request (placeholder)
    def snapshot_potion_roi(self):
        pass

    def open_key_settings(self):
        try:
            import yaml  # type: ignore
        except ModuleNotFoundError:
            messagebox.showerror("Settings", "PyYAML not installed. Install with: python -m pip install pyyaml")
            return
        try:
            with open(self.cfg_path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
        except Exception:
            cfg = {}
        kb = cfg.get("keybinds", {}) or {}
        inv = tk.StringVar(value=str(kb.get("inventory", "i")))
        mp = tk.StringVar(value=str(kb.get("map", "m")))
        rtn = tk.StringVar(value=str(kb.get("return_to_town", "r")))
        ab = tk.StringVar(value=str(kb.get("autobattle", "g")))

        win = tk.Toplevel(self.root)
        win.title("Settings - Keybinds")
        tk.Label(win, text="Open Inventory").grid(row=0, column=0, sticky="e")
        tk.Entry(win, textvariable=inv, width=10).grid(row=0, column=1, sticky="w")
        tk.Label(win, text="Open Map").grid(row=1, column=0, sticky="e")
        tk.Entry(win, textvariable=mp, width=10).grid(row=1, column=1, sticky="w")
        tk.Label(win, text="Return to Town").grid(row=2, column=0, sticky="e")
        tk.Entry(win, textvariable=rtn, width=10).grid(row=2, column=1, sticky="w")
        tk.Label(win, text="Auto Battle").grid(row=3, column=0, sticky="e")
        tk.Entry(win, textvariable=ab, width=10).grid(row=3, column=1, sticky="w")

        def save_keys():
            cfg.setdefault("keybinds", {})
            cfg["keybinds"]["inventory"] = inv.get().strip() or "i"
            cfg["keybinds"]["map"] = mp.get().strip() or "m"
            cfg["keybinds"]["return_to_town"] = rtn.get().strip() or "r"
            cfg["keybinds"]["autobattle"] = ab.get().strip() or "g"
            try:
                with open(self.cfg_path, "w", encoding="utf-8") as f:
                    yaml.safe_dump(cfg, f, sort_keys=False)
                self._append_log("Keybind settings saved.\n")
                messagebox.showinfo("Settings", "Keybinds updated.")
                win.destroy()
            except Exception as e:
                messagebox.showerror("Settings", str(e))

        tk.Button(win, text="Save", command=save_keys).grid(row=4, column=0, columnspan=2, pady=(8, 4))

    def _check_assets_status(self):
        """Check and return the status of all required assets."""
        assets = [
            ("Potion Empty", "l9/assets/ui/hud/potion_empty.png"),
            ("Bag Icon", "l9/assets/ui/hud/bag_icon.png"),
            ("Merchant Icon", "l9/assets/npc/general_merchant_icon.png"),
            ("Auto Purchase", "l9/assets/shop/auto_purchase_button.png"),
            ("Buy Confirm", "l9/assets/shop/confirm_button.png"),
            ("Shop Close", "l9/assets/shop/close_button.png"),
            ("Grind Region", "l9/assets/grind/region.png"),
            ("Grind Area", "l9/assets/grind/area.png"),
            ("Teleporter", "l9/assets/grind/teleporter.png"),
            ("Fast Travel", "l9/assets/grind/fast_travel.png"),
            ("Fast Travel Confirm", "l9/assets/grind/confirm.png"),
            ("Dismantle Icon", "l9/assets/dismantle/icon.png"),
            ("Quick Add", "l9/assets/dismantle/quick_add.png"),
            ("Dismantle Button", "l9/assets/dismantle/dismantle_has.png"),
            ("Dismantle None", "l9/assets/dismantle/dismantle_none.png"),
            ("Close Inventory", "l9/assets/dismantle/close_inventory.png"),
            ("Revive Button", "l9/assets/revive/revive_button.png"),
            ("Stat Reclaim", "l9/assets/revive/stat_reclaim.png"),
            ("Retrieve", "l9/assets/revive/retrieve.png"),
        ]
        
        status = {}
        for label, rel_path in assets:
            full_path = os.path.join(REPO_ROOT, rel_path)
            status[label] = {
                'path': full_path,
                'exists': os.path.exists(full_path),
                'rel_path': rel_path
            }
        return status

    def open_upload_assets(self):
        win = tk.Toplevel(self.root)
        win.title("Upload Assets")
        
        # Check asset status
        asset_status = self._check_assets_status()
        
        # Show summary
        total_assets = len(asset_status)
        existing_assets = sum(1 for info in asset_status.values() if info['exists'])
        
        summary_label = tk.Label(win, text=f"Assets: {existing_assets}/{total_assets} present", 
                                font=("Arial", 10, "bold"))
        summary_label.grid(row=0, column=0, columnspan=3, pady=(0, 10))
        
        tk.Label(win, text="Asset").grid(row=1, column=0, sticky="w")
        tk.Label(win, text="Status").grid(row=1, column=1, sticky="w")
        tk.Label(win, text="Upload").grid(row=1, column=2, sticky="w")
        
        for r, (label, info) in enumerate(asset_status.items(), start=2):
            tk.Label(win, text=label).grid(row=r, column=0, sticky="w")
            status_var = tk.StringVar()
            status_text = "✅ OK" if info['exists'] else "❌ MISSING"
            status_var.set(status_text)
            status_label = tk.Label(win, textvariable=status_var)
            status_label.grid(row=r, column=1, sticky="w")
            
            # Color code the status
            if info['exists']:
                status_label.config(fg="green")
            else:
                status_label.config(fg="red")

            def make_uploader(target_path=info['path'], sv=status_var, sl=status_label):
                def _upload():
                    p = filedialog.askopenfilename(
                        title=f"Upload for {label}", filetypes=[("PNG", "*.png"), ("All", "*.*")]
                    )
                    if p:
                        os.makedirs(os.path.dirname(target_path), exist_ok=True)
                        try:
                            shutil.copyfile(p, target_path)
                            sv.set("✅ OK")
                            sl.config(fg="green")
                            self._append_log(f"Updated asset: {target_path}\n")
                            # Refresh summary and main status
                            self._refresh_asset_summary(win, summary_label)
                            self._update_asset_status()
                        except Exception as e:
                            messagebox.showerror("Upload", str(e))
                return _upload

            tk.Button(win, text="Choose...", command=make_uploader()).grid(row=r, column=2, sticky="w")

    def _refresh_asset_summary(self, win, summary_label):
        """Refresh the asset summary after an upload."""
        asset_status = self._check_assets_status()
        total_assets = len(asset_status)
        existing_assets = sum(1 for info in asset_status.values() if info['exists'])
        summary_label.config(text=f"Assets: {existing_assets}/{total_assets} present")

    def _grind_path_file(self, cfg_obj: dict) -> str:
        g = (cfg_obj.get("grind", {}) or {})
        try:
            area_id = str(g.get("area_id") or f"spot{int(g.get('active_spot_id', 1))}")
        except Exception:
            area_id = str(g.get("area_id") or "default")
        root = os.path.join(REPO_ROOT, "l9", "data", "grind_paths")
        os.makedirs(root, exist_ok=True)
        return os.path.join(root, f"{area_id}.json")

    def _record_path_direct(self, spot_id: int, auto_gates: bool = False):
        """Record path directly without launching external scripts."""
        try:
            import keyboard  # type: ignore
        except ModuleNotFoundError:
            self._append_log("[ERROR] The 'keyboard' module is required. Install with: python -m pip install keyboard\n")
            return
        
        try:
            import mouse  # type: ignore
        except ModuleNotFoundError:
            mouse = None  # type: ignore
        
        cfg = self._load_cfg()
        gcfg = cfg.get("grind", {}) or {}
        stop_key = str(gcfg.get("record_stop_key", "f12"))
        
        # Keys to record (configurable)
        default_keys = ["w", "a", "s", "d"]
        cfg_keys = gcfg.get("record_keys") if isinstance(gcfg.get("record_keys"), list) else None
        rec_keys = [str(k).lower() for k in (cfg_keys or default_keys)]
        keys_disp = ", ".join([str(k).upper() for k in rec_keys])
        
        if auto_gates:
            self._append_log(f"Recording auto-gated path for Spot {spot_id}: Walk with {keys_disp}. When you stop, I will try to click OK and wait for loading. Press {stop_key} to finish.\n")
        else:
            self._append_log(f"Recording path for Spot {spot_id}: focus the game, walk/click path. Keys recorded: {keys_disp}. Mouse clicks recorded if 'mouse' module present. Press {stop_key} to finish.\n")
        
        # Get output path
        out_path = self._grind_path_file(cfg)
        
        allowed = set(rec_keys)
        start = time.perf_counter()
        events = []
        
        def on_key(e):
            try:
                name = (e.name or "").lower()
                if name in allowed and e.event_type in ("down", "up"):
                    t = time.perf_counter() - start
                    events.append({"t": t, "type": e.event_type, "key": name})
            except Exception:
                pass
        
        def on_mouse_click(e=None):
            if mouse is None:
                return
            try:
                t = time.perf_counter() - start
                events.append({"t": t, "type": "mclick", "x": e.x, "y": e.y, "button": e.button})
            except Exception:
                pass
        
        # Set up hooks
        recording = True
        
        def on_key_with_stop(e):
            # Check for stop key first
            if e.name and e.name.lower() == stop_key.lower() and e.event_type == "down":
                nonlocal recording
                recording = False
                return
            # Otherwise handle normal key recording
            on_key(e)
        
        keyboard.hook(on_key_with_stop)
        mouse_hook = None
        if mouse is not None:
            try:
                mouse_hook = mouse.hook(on_mouse_click)
            except Exception:
                pass
        
        # Wait for stop key
        try:
            while recording:
                time.sleep(0.01)
        except KeyboardInterrupt:
            pass
        finally:
            try:
                keyboard.unhook_all()
            except Exception:
                pass
            if mouse is not None and mouse_hook is not None:
                try:
                    if hasattr(mouse, "unhook"):
                        mouse.unhook(mouse_hook)
                except Exception:
                    pass
        
        # Save the recorded path
        with open(out_path, "w", encoding="utf-8") as f:
            import json
            json.dump({"version": 2, "events": events}, f, indent=2)
        
        n_clicks = sum(1 for e in events if e.get("type") == "mclick")
        n_keys = sum(1 for e in events if e.get("type") in ("down", "up", "kdown", "kup"))
        self._append_log(f"Saved path to {out_path} ({len(events)} events; {n_clicks} clicks, {n_keys} key events)\n")


    def open_manage_spots(self):
        cfg = self._load_cfg_raw()
        g = cfg.setdefault("grind", {})
        spots = g.setdefault("spots", [
            {"id": 1, "name": "Spot 1"},
            {"id": 2, "name": "Spot 2"},
            {"id": 3, "name": "Spot 3"},
        ])

        def target_paths(spot_id: int) -> dict:
            base = os.path.join(REPO_ROOT, "l9", "assets", "grind", "spots", f"spot{spot_id}")
            return {
                "region_template": os.path.join(base, "region.png"),
                "area_template": os.path.join(base, "area.png"),
                "teleporter_template": os.path.join(base, "teleporter.png"),
                "fast_travel_template": os.path.join(base, "fast_travel.png"),
                "confirm_template": os.path.join(base, "confirm.png"),
            }

        win = tk.Toplevel(self.root)
        win.title("Manage Grind Spots")
        tk.Label(win, text="ID").grid(row=0, column=0, sticky="w")
        tk.Label(win, text="Name").grid(row=0, column=1, sticky="w")
        tk.Label(win, text="Templates").grid(row=0, column=2, sticky="w")
        tk.Label(win, text="").grid(row=0, column=3, sticky="w")

        name_vars: list[tk.StringVar] = []

        row = 1
        for s in spots[:3]:
            sid = int(s.get("id", row))
            sname = str(s.get("name", f"Spot {sid}"))
            paths = target_paths(sid)
            # Ensure cfg paths exist in spot definition
            for k, pth in paths.items():
                s.setdefault(k, os.path.relpath(pth, REPO_ROOT).replace("\\", "/"))

            tk.Label(win, text=str(sid)).grid(row=row, column=0, sticky="w")
            nv = tk.StringVar(value=sname)
            name_vars.append(nv)
            tk.Entry(win, textvariable=nv, width=18).grid(row=row, column=1, sticky="w")

            # Uploaders block
            col = 2
            inner = tk.Frame(win)
            inner.grid(row=row, column=col, sticky="w")
            def add_uploader(fname_label: str, key: str, target_file: str, r: int):
                lbl = tk.Label(inner, text=fname_label)
                lbl.grid(row=r, column=0, sticky="w")
                st = tk.StringVar(value=("OK" if os.path.exists(target_file) else "MISSING"))
                tk.Label(inner, textvariable=st, width=8).grid(row=r, column=1, sticky="w")
                def do_upload():
                    p = filedialog.askopenfilename(title=f"Choose {fname_label}", filetypes=[("PNG", "*.png"), ("All", "*.*")])
                    if not p:
                        return
                    try:
                        os.makedirs(os.path.dirname(target_file), exist_ok=True)
                        shutil.copyfile(p, target_file)
                        st.set("OK")
                        self._append_log(f"Updated spot {sid} asset: {target_file}\n")
                    except Exception as e:
                        messagebox.showerror("Upload", str(e))
                tk.Button(inner, text="Choose...", command=do_upload).grid(row=r, column=2, sticky="w", padx=(4, 0))

            add_uploader("Region", "region_template", paths["region_template"], 0)
            add_uploader("Area", "area_template", paths["area_template"], 1)
            add_uploader("Teleporter", "teleporter_template", paths["teleporter_template"], 2)
            add_uploader("Fast Travel", "fast_travel_template", paths["fast_travel_template"], 3)
            add_uploader("Confirm", "confirm_template", paths["confirm_template"], 4)

            def record_for_this_spot(spot_id=sid):
                # Set active spot and save
                g["active_spot_id"] = int(spot_id)
                if not self._save_cfg(cfg):
                    return
                # Start recording directly in this thread
                try:
                    self._record_path_direct(spot_id)
                except Exception as e:
                    messagebox.showerror("Record Path", str(e))

            def record_auto_for_this_spot(spot_id=sid):
                # Set active spot and save
                g["active_spot_id"] = int(spot_id)
                if not self._save_cfg(cfg):
                    return
                try:
                    self._record_path_direct(spot_id, auto_gates=True)
                except Exception as e:
                    messagebox.showerror("Record Path", str(e))

            def test_path_for_this_spot(spot_id=sid):
                # Set active spot and save
                g["active_spot_id"] = int(spot_id)
                if not self._save_cfg(cfg):
                    return
                # Ensure path exists
                try:
                    cfg2 = self._load_cfg()
                    pth = self._grind_path_file(cfg2)
                except Exception as e:
                    messagebox.showerror("Test Path", f"Failed to resolve path file: {e}")
                    return
                if not os.path.exists(pth):
                    messagebox.showwarning("Test Path", f"No recorded path found: {pth}\nRecord one first.")
                    return
                try:
                    self._append_log(f"Testing recorded path: {pth}\n")
                    cmd = [
                        sys.executable,
                        "-u",
                        repo_path("scripts", "run_flow.py"),
                        "--flow",
                        "l9.flows.test_path:TestPathFlow",
                        "--config",
                        self.cfg_path,
                    ]
                    proc = subprocess.Popen(
                        cmd,
                        cwd=REPO_ROOT,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        bufsize=1,
                    )
                    def _reader3():
                        for line in iter(proc.stdout.readline, ""):
                            if not line:
                                break
                            self._append_log(line)
                    t3 = threading.Thread(target=_reader3, daemon=True)
                    t3.start()
                    proc.wait()
                    self._append_log("Test path finished.\n")
                except Exception as e:
                    messagebox.showerror("Test Path", str(e))

            tk.Button(win, text="Record Path", command=record_for_this_spot).grid(row=row, column=3, sticky="w", padx=(8,0))
            tk.Button(win, text="Record Auto", command=record_auto_for_this_spot).grid(row=row, column=4, sticky="w", padx=(8,0))
            tk.Button(win, text="Test Path", command=test_path_for_this_spot).grid(row=row, column=5, sticky="w", padx=(8,0))
            row += 1

        def save_and_close():
            # Persist spot names
            for i, s in enumerate(spots[:3]):
                s["name"] = name_vars[i].get().strip() or f"Spot {int(s.get('id', i+1))}"
            if self._save_cfg(cfg):
                # Spots saved
                self._init_spot_combo()
                win.destroy()

        tk.Button(win, text="Save", command=save_and_close).grid(row=row, column=0, columnspan=4, pady=(8,6))

    def stop(self):
        # signal any waiting loops to stop
        self._stop_event.set()
        if not self.proc or self.proc.poll() is not None:
            self.status_var.set("Idle")
            self.start_btn.configure(state=tk.NORMAL)
            self.stop_btn.configure(state=tk.DISABLED)
            return
        # Stopping automation
        try:
            self.proc.terminate()
        except Exception:
            pass
        try:
            self.proc.wait(timeout=3)
        except Exception:
            try:
                self.proc.kill()
            except Exception:
                pass
        self.status_var.set("Stopped")
        self.start_btn.configure(state=tk.NORMAL)
        self.stop_btn.configure(state=tk.DISABLED)

    def on_close(self):
        if self.proc and self.proc.poll() is None:
            if not messagebox.askyesno("Quit", "Automation is running. Stop and exit?"):
                return
            self.stop()
        self.root.destroy()


def main():
    root = tk.Tk()
    LauncherGUI(root)
    root.minsize(800, 450)  # Slightly larger for better layout
    root.geometry("900x500")  # Set default size
    root.resizable(False, False)  # Prevent resizing and maximization
    root.state('normal')  # Ensure window is not maximized
    root.mainloop()


if __name__ == "__main__":
    main()
