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

try:
    import mss
except ModuleNotFoundError:
    mss = None


def get_monitor_info():
    """Get monitor information for dropdown selection, filtered to 1920x1080 monitors only."""
    if mss is None:
        return [{"index": 1, "name": "Monitor 1", "resolution": "1920x1080"}]
    
    try:
        with mss.mss() as s:
            monitors = s.monitors
            monitor_list = []
            for i, mon in enumerate(monitors):
                if i == 0:  # Skip monitor 0 (all monitors combined)
                    continue
                width = mon['width']
                height = mon['height']
                # Only include 1920x1080 monitors
                if width == 1920 and height == 1080:
                    monitor_list.append({
                        "index": i,
                        "name": f"Monitor {i}",
                        "resolution": f"{width}x{height}"
                    })
            return monitor_list
    except Exception:
        return [{"index": 1, "name": "Monitor 1", "resolution": "1920x1080"}]


def has_multiple_1920x1080_monitors():
    """Check if system has multiple 1920x1080 monitors."""
    if mss is None:
        return False
    try:
        with mss.mss() as s:
            monitors = s.monitors
            count = 0
            for i, mon in enumerate(monitors):
                if i == 0:  # Skip monitor 0
                    continue
                if mon['width'] == 1920 and mon['height'] == 1080:
                    count += 1
            return count > 1
    except Exception:
        return False

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
        self.root.title("Lordnine Automation")
        self.root.configure(bg='#f5f5f5')
        self.proc: subprocess.Popen | None = None
        self.log_queue: queue.Queue[str] = queue.Queue()
        self.reader_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

        # Internal config path reference
        self.cfg_path = repo_path("l9", "config.yaml")

        # Main container
        main_frame = tk.Frame(root, bg='#f5f5f5')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Header Section
        header_frame = tk.Frame(main_frame, bg='#f5f5f5')
        header_frame.pack(fill=tk.X, pady=(0, 20))

        # Title
        title_label = tk.Label(header_frame, text="LORDNINE", 
                              font=("Roboto", 12, "bold"), fg='#333333', bg='#f5f5f5')
        title_label.pack(side=tk.LEFT)

        # Status buttons in header
        status_frame = tk.Frame(header_frame, bg='#f5f5f5')
        status_frame.pack(side=tk.RIGHT)

        self.running_btn = tk.Button(status_frame, text="Running", 
                                   font=("Roboto", 8, "bold"), fg='white',
                                   relief=tk.FLAT, padx=10, pady=3, state=tk.DISABLED)
        self.running_btn.pack(side=tk.LEFT, padx=(0, 5))

        self.admin_btn = tk.Button(status_frame, text="Admin", 
                                 font=("Roboto", 8), fg='#666666',
                                 relief=tk.FLAT, padx=10, pady=3, state=tk.DISABLED)
        self.admin_btn.pack(side=tk.LEFT)

        # Main Control Section
        control_frame = tk.Frame(main_frame, bg='#f5f5f5')
        control_frame.pack(fill=tk.X, pady=(0, 20))

        # Start/Stop buttons
        button_frame = tk.Frame(control_frame, bg='#f5f5f5')
        button_frame.pack(fill=tk.X, pady=(0, 15))

        # Start button (large, primary)
        self.start_btn = tk.Button(button_frame, text="▶ Start", 
                                 font=("Roboto", 14, "bold"), fg='white', bg='#28a745',
                                 relief=tk.FLAT, command=self.start)
        self.start_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

        # Stop button (smaller, secondary)
        self.stop_btn = tk.Button(button_frame, text="⏹ Stop", 
                                font=("Roboto", 12), fg='#ffc107', bg='white',
                                relief=tk.FLAT, command=self.stop, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Feature buttons row
        feature_frame = tk.Frame(control_frame, bg='#f5f5f5')
        feature_frame.pack(fill=tk.X, pady=(0, 15))

        # Upload button
        self.upload_btn = tk.Button(feature_frame, text="↑ Upload", 
                                  font=("Roboto", 10), fg='#666666', bg='#e0e0e0',
                                  relief=tk.FLAT, command=self.open_upload_assets)
        self.upload_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

        # Spots button
        self.manage_spots_btn = tk.Button(feature_frame, text="📍 Spots", 
                                        font=("Roboto", 10), fg='#666666', bg='#e0e0e0',
                                        relief=tk.FLAT, command=self.open_manage_spots)
        self.manage_spots_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

        # Settings button
        self.settings_btn = tk.Button(feature_frame, text="⚙ Settings", 
                                    font=("Roboto", 10), fg='#666666', bg='#e0e0e0',
                                    relief=tk.FLAT, command=self.open_key_settings)
        self.settings_btn.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Configuration row
        config_frame = tk.Frame(control_frame, bg='#f5f5f5')
        config_frame.pack(fill=tk.X)

        # Spot selection (same line)
        spot_row_frame = tk.Frame(config_frame, bg='#f5f5f5')
        spot_row_frame.pack(fill=tk.X, pady=(0, 10))

        spot_label = tk.Label(spot_row_frame, text="Spot:", font=("Roboto", 10), fg='#333333', bg='#f5f5f5')
        spot_label.pack(side=tk.LEFT, padx=(0, 8))

        self.spot_var = tk.StringVar()
        self.spot_combo = ttk.Combobox(spot_row_frame, textvariable=self.spot_var, state="readonly",
                                     font=("Roboto", 10))
        self.spot_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._init_spot_combo()
        self.spot_combo.bind("<<ComboboxSelected>>", self._on_spot_selected)

        # Monitor selection (initially hidden, shown when multiple monitors detected)
        self.monitor_row_frame = tk.Frame(config_frame, bg='#f5f5f5')
        # Don't pack initially - will be shown/hidden dynamically

        monitor_label = tk.Label(self.monitor_row_frame, text="Monitor:", font=("Roboto", 10), fg='#333333', bg='#f5f5f5')
        monitor_label.pack(side=tk.LEFT, padx=(0, 8))

        self.monitor_var = tk.StringVar()
        self.monitor_combo = ttk.Combobox(self.monitor_row_frame, textvariable=self.monitor_var, state="readonly",
                                        font=("Roboto", 10))
        self.monitor_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.monitor_combo.bind("<<ComboboxSelected>>", self._on_monitor_selected)
        
        # Second row for Monitor Detection and Assets Ready
        second_row_frame = tk.Frame(config_frame, bg='#f5f5f5')
        second_row_frame.pack(fill=tk.X)

        # Monitor Detection button
        self.monitor_detection_btn = tk.Button(second_row_frame, text="Detect Monitor", 
                                             font=("Roboto", 10), fg='#666666', bg='#e0e0e0',
                                             relief=tk.FLAT, command=self._detect_monitors,
                                             padx=10, pady=3)
        self.monitor_detection_btn.pack(side=tk.LEFT, padx=(0, 20))
        

        # Asset status indicator
        self.asset_status_label = tk.Label(second_row_frame, text="", font=("Roboto", 10, "bold"), fg='#28a745', bg='#f5f5f5')
        self.asset_status_label.pack(side=tk.RIGHT)
        self._update_asset_status()

        # Console Output Section
        console_frame = tk.Frame(main_frame, bg='#f5f5f5')
        console_frame.pack(fill=tk.BOTH, expand=True)

        # Separator line
        separator = tk.Frame(console_frame, height=1, bg='#cccccc')
        separator.pack(fill=tk.X, pady=(0, 10))

        # Console title
        console_title = tk.Label(console_frame, text="Console Output", 
                               font=("Roboto", 12, "bold"), fg='#333333', bg='#f5f5f5')
        console_title.pack(anchor=tk.W, pady=(0, 10))

        # Log display
        self.log = scrolledtext.ScrolledText(console_frame, height=15, state=tk.DISABLED,
                                           font=("Consolas", 9), bg='white', fg='#333333',
                                           relief=tk.FLAT, bd=0)
        self.log.pack(fill=tk.BOTH, expand=True)

        # Close handler and log polling
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.after(100, self._poll_log_queue)

        # Safety & ToS reminder removed

        # Initialize monitor detection on startup (silent) - after all UI elements are created
        self._detect_monitors(show_log=False)

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

    def _on_monitor_selected(self, event=None):
        """Handle monitor selection change."""
        monitors = get_monitor_info()
        try:
            idx = int(self.monitor_combo.current())
            selected_monitor = monitors[idx]["index"]
            
            # Update config with new monitor selection
            cfg = self._load_cfg_raw()
            cfg["monitor_index"] = selected_monitor
            
            # Also set force_to_monitor_index to move the game window to selected monitor
            if "window" not in cfg:
                cfg["window"] = {}
            cfg["window"]["force_to_monitor_index"] = selected_monitor
            
            if self._save_cfg(cfg):
                self._append_log(f"Monitor selection changed to Monitor {selected_monitor} (1920x1080)\n")
                self._append_log(f"Config updated: monitor_index={selected_monitor}, force_to_monitor_index={selected_monitor}\n")
                self._append_log("Click 'Start' to apply the new monitor setting.\n")
        except Exception as e:
            self._append_log(f"Error changing monitor: {e}\n")

    def _check_and_show_monitor_dropdown(self):
        """Check if monitor dropdown should be shown and initialize it."""
        try:
            monitors = get_monitor_info()
            if monitors:
                self._show_monitor_dropdown(monitors)
            else:
                self._hide_monitor_dropdown()
        except Exception as e:
            self._hide_monitor_dropdown()

    def _show_monitor_dropdown(self, monitors):
        """Show the monitor dropdown and populate it."""
        # Pack the frame to make it visible above the detect monitor button
        self.monitor_row_frame.pack(fill=tk.X, pady=(0, 10), before=self.monitor_detection_btn.master)
        
        # Initialize the dropdown with monitors
        monitor_names = [f"{mon['name']} ({mon['resolution']})" for mon in monitors]
        self.monitor_combo["values"] = monitor_names
        
        # Load current monitor setting from config
        cfg = self._load_cfg()
        current_monitor = int(cfg.get("monitor_index", 1))
        
        # Check if current monitor is still available in detected monitors
        current_monitor_available = any(mon["index"] == current_monitor for mon in monitors)
        
        if current_monitor_available:
            # Use current monitor if it's still available
            monitor_idx = 0
            for i, mon in enumerate(monitors):
                if mon["index"] == current_monitor:
                    monitor_idx = i
                    break
        else:
            # Use first available monitor if current one is not available
            monitor_idx = 0
            current_monitor = monitors[0]["index"]
        
        self.monitor_combo.current(monitor_idx)
        self.monitor_var.set(monitor_names[monitor_idx])
        
        # Only update config on startup detection, not on manual detection
        # This allows user to change selection without immediately applying it
        if not hasattr(self, '_startup_detection_complete'):
            # This is startup detection - update config with first monitor
            cfg_raw = self._load_cfg_raw()
            cfg_raw["monitor_index"] = current_monitor
            
            # Set force_to_monitor_index to match monitor_index
            if "window" not in cfg_raw:
                cfg_raw["window"] = {}
            cfg_raw["window"]["force_to_monitor_index"] = current_monitor
            
            self._save_cfg(cfg_raw)
            
            # Log the config update with debug info
            if hasattr(self, '_append_log'):
                monitor_info = f"Monitor {current_monitor} ({monitors[0]['resolution']})"
                self._append_log(f"Startup: Set config to {monitor_info} (first 1920x1080 monitor)\n")
                self._append_log(f"Debug: monitor_index={current_monitor}, force_to_monitor_index={current_monitor}\n")
                monitor_list = [f'Monitor {m["index"]}' for m in monitors]
                self._append_log(f"Debug: Available monitors: {monitor_list}\n")
            
            self._startup_detection_complete = True

    def _hide_monitor_dropdown(self):
        """Hide the monitor dropdown."""
        self.monitor_row_frame.pack_forget()

    def _detect_monitors(self, show_log=True):
        """Detect monitors and update status."""
        try:
            if show_log:
                self._append_log("Detecting monitors...\n")
            monitors = get_monitor_info()
            
            if monitors:
                monitor_count = len(monitors)
                monitor_names = [mon['name'] for mon in monitors]
                if show_log:
                    self._append_log(f"Found {monitor_count} 1920x1080 monitor(s): {', '.join(monitor_names)}\n")
                
                # Always show dropdown with available monitors
                self._show_monitor_dropdown(monitors)
                if show_log:
                    if monitor_count == 1:
                        self._append_log("Monitor dropdown available with 1 monitor.\n")
                    else:
                        self._append_log("Monitor selection dropdown is now available.\n")
                
                # Update button text to show detection result
                self.monitor_detection_btn.config(text=f"Detect Monitor (✓ {monitor_count})")
            else:
                if show_log:
                    self._append_log("No 1920x1080 monitors detected.\n")
                self._hide_monitor_dropdown()
                self.monitor_detection_btn.config(text="Detect Monitor (✗ None)")
            
        except Exception as e:
            if show_log:
                self._append_log(f"Error detecting monitors: {e}\n")
            self._hide_monitor_dropdown()
            self.monitor_detection_btn.config(text="Detect Monitor (✗ Error)")

    def _update_monitor_detection_status(self):
        """Update monitor detection status indicator."""
        try:
            monitors = get_monitor_info()
            if monitors:
                monitor_count = len(monitors)
                if monitor_count == 1:
                    self.monitor_detection_btn.config(text=f"Detect Monitor (✓ {monitor_count})")
                else:
                    self.monitor_detection_btn.config(text=f"Detect Monitor (✓ {monitor_count})")
            else:
                self.monitor_detection_btn.config(text="Detect Monitor (✗ None)")
            
        except Exception as e:
            self.monitor_detection_btn.config(text="Detect Monitor (✗ Error)")

    def _update_asset_status(self):
        """Update the asset status indicator on the main GUI."""
        try:
            asset_status = self._check_assets_status()
            total_assets = len(asset_status)
            existing_assets = sum(1 for info in asset_status.values() if info['exists'])
            
            if existing_assets == total_assets:
                status_text = "✅ Assets Ready"
                color = "#28a745"  # Green
            elif existing_assets > total_assets // 2:
                status_text = f"⚠️ {existing_assets}/{total_assets} Assets"
                color = "#ffc107"  # Orange
            else:
                status_text = f"❌ {existing_assets}/{total_assets} Assets"
                color = "#dc3545"  # Red
                
            self.asset_status_label.config(text=status_text, fg=color)
        except Exception:
            self.asset_status_label.config(text="❓ Assets Unknown", fg="#6c757d")


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

    def _apply_current_monitor_selection(self):
        """Apply the current monitor selection from dropdown to config."""
        try:
            self._append_log("Debug: Applying current monitor selection...\n")
            if hasattr(self, 'monitor_combo') and hasattr(self, 'monitor_var'):
                monitors = get_monitor_info()
                if monitors:
                    # Get the currently selected monitor from dropdown
                    current_selection = self.monitor_var.get()
                    monitor_names = [f"{mon['name']} ({mon['resolution']})" for mon in monitors]
                    
                    self._append_log(f"Debug: Current selection='{current_selection}', Available={monitor_names}\n")
                    
                    if current_selection in monitor_names:
                        selected_idx = monitor_names.index(current_selection)
                        selected_monitor = monitors[selected_idx]["index"]
                        
                        # Update config with selected monitor
                        cfg = self._load_cfg_raw()
                        cfg["monitor_index"] = selected_monitor
                        
                        if "window" not in cfg:
                            cfg["window"] = {}
                        cfg["window"]["force_to_monitor_index"] = selected_monitor
                        
                        self._save_cfg(cfg)
                        self._append_log(f"Applied Monitor {selected_monitor} for automation (force + image recognition)\n")
                        self._append_log(f"Debug: monitor_index={selected_monitor}, force_to_monitor_index={selected_monitor}\n")
                        monitor_list = [f'Monitor {m["index"]}' for m in monitors]
                        self._append_log(f"Debug: Available monitors: {monitor_list}\n")
                    else:
                        self._append_log(f"Debug: Current selection not found in available monitors\n")
                else:
                    self._append_log("Debug: No monitors available for selection\n")
            else:
                self._append_log("Debug: Monitor combo or var not available\n")
        except Exception as e:
            self._append_log(f"Error applying monitor selection: {e}\n")

    def start(self):
        if self.proc and self.proc.poll() is None:
            messagebox.showwarning("Already running", "Automation is already running.")
            return
        
        # Apply current monitor selection before starting
        self._apply_current_monitor_selection()
        
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
                self.admin_btn.config(text="Admin", fg='white', bg='#333333')

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
        self.start_btn.configure(state=tk.DISABLED)
        self.stop_btn.configure(state=tk.NORMAL)
        self.running_btn.config(text="Running", fg='white', bg='#333333')

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
                self.root.after(0, lambda: self.running_btn.config(text="Idle", fg='#666666', bg='#e0e0e0'))
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
        win.geometry("500x300")
        win.resizable(False, False)
        win.state('normal')
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
        win.geometry("600x400")
        win.resizable(False, False)
        win.state('normal')
        
        # Check asset status
        asset_status = self._check_assets_status()
        
        # Show summary
        total_assets = len(asset_status)
        existing_assets = sum(1 for info in asset_status.values() if info['exists'])
        
        summary_label = tk.Label(win, text=f"Assets: {existing_assets}/{total_assets} present", 
                                font=("Roboto", 10, "bold"))
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
        win.geometry("700x500")
        win.resizable(False, False)
        win.state('normal')
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
                # Also refresh monitor combo if it exists
                if hasattr(self, 'monitor_combo'):
                    self._init_monitor_combo()
                win.destroy()

        tk.Button(win, text="Save", command=save_and_close).grid(row=row, column=0, columnspan=4, pady=(8,6))

    def stop(self):
        # signal any waiting loops to stop
        self._stop_event.set()
        if not self.proc or self.proc.poll() is not None:
            self.start_btn.configure(state=tk.NORMAL)
            self.stop_btn.configure(state=tk.DISABLED)
            self.running_btn.config(text="Idle", fg='#666666', bg='#e0e0e0')
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
        self.start_btn.configure(state=tk.NORMAL)
        self.stop_btn.configure(state=tk.DISABLED)
        self.running_btn.config(text="Idle", fg='#666666', bg='#e0e0e0')

    def on_close(self):
        if self.proc and self.proc.poll() is None:
            if not messagebox.askyesno("Quit", "Automation is running. Stop and exit?"):
                return
            self.stop()
        self.root.destroy()


def main():
    root = tk.Tk()
    LauncherGUI(root)
    root.minsize(440, 450)  # Match the design width
    root.geometry("440x500")  # Set exact width to match design
    root.resizable(False, False)  # Prevent resizing and maximization
    root.state('normal')  # Ensure window is not maximized
    root.mainloop()


if __name__ == "__main__":
    main()
