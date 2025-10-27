#!/usr/bin/env python3
"""
Comprehensive build automation for Lordnine.
Handles different build modes and provides status monitoring.
"""

import os
import sys
import time
import subprocess
import argparse
from pathlib import Path
from datetime import datetime

REPO_ROOT = Path(__file__).parent.parent

class BuildAutomation:
    def __init__(self):
        self.build_script = REPO_ROOT / 'scripts' / 'build_exe.ps1'
        self.dist_dir = REPO_ROOT / 'dist'
        self.gui_exe = self.dist_dir / 'LordnineGUI' / 'LordnineGUI.exe'
        self.runner_exe = self.dist_dir / 'LordnineRunner' / 'LordnineRunner.exe'
        
    def check_dependencies(self):
        """Check if required tools are available."""
        print("🔍 Checking dependencies...")
        
        # Check Python
        try:
            result = subprocess.run(['python', '--version'], capture_output=True, text=True)
            if result.returncode == 0:
                print(f"✅ Python: {result.stdout.strip()}")
            else:
                print("❌ Python not found")
                return False
        except FileNotFoundError:
            print("❌ Python not found")
            return False
        
        # Check PyInstaller
        try:
            result = subprocess.run(['pyinstaller', '--version'], capture_output=True, text=True)
            if result.returncode == 0:
                print(f"✅ PyInstaller: {result.stdout.strip()}")
            else:
                print("❌ PyInstaller not found")
                return False
        except FileNotFoundError:
            print("❌ PyInstaller not found")
            return False
        
        # Check PowerShell
        try:
            result = subprocess.run(['powershell', '-Command', '$PSVersionTable.PSVersion'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                print("✅ PowerShell available")
            else:
                print("❌ PowerShell not found")
                return False
        except FileNotFoundError:
            print("❌ PowerShell not found")
            return False
        
        return True
    
    def get_build_info(self):
        """Get information about current build state."""
        info = {
            'gui_exists': self.gui_exe.exists(),
            'runner_exists': self.runner_exe.exists(),
            'gui_size': self.gui_exe.stat().st_size if self.gui_exe.exists() else 0,
            'runner_size': self.runner_exe.stat().st_size if self.runner_exe.exists() else 0,
            'gui_modified': datetime.fromtimestamp(self.gui_exe.stat().st_mtime) if self.gui_exe.exists() else None,
            'runner_modified': datetime.fromtimestamp(self.runner_exe.stat().st_mtime) if self.runner_exe.exists() else None,
        }
        return info
    
    def print_build_status(self):
        """Print current build status."""
        info = self.get_build_info()
        
        print("\n📊 Build Status:")
        print("=" * 40)
        
        if info['gui_exists']:
            size_mb = info['gui_size'] / (1024 * 1024)
            modified = info['gui_modified'].strftime("%Y-%m-%d %H:%M:%S") if info['gui_modified'] else "Unknown"
            print(f"✅ GUI: {size_mb:.1f} MB (modified: {modified})")
        else:
            print("❌ GUI: Not built")
        
        if info['runner_exists']:
            size_mb = info['runner_size'] / (1024 * 1024)
            modified = info['runner_modified'].strftime("%Y-%m-%d %H:%M:%S") if info['runner_modified'] else "Unknown"
            print(f"✅ Runner: {size_mb:.1f} MB (modified: {modified})")
        else:
            print("❌ Runner: Not built")
    
    def build(self, clean=False, admin=False):
        """Run the build process."""
        if not self.build_script.exists():
            print(f"❌ Build script not found: {self.build_script}")
            return False
        
        print(f"\n🚀 Starting {'clean ' if clean else ''}build...")
        start_time = time.time()
        
        # Prepare command
        cmd = [
            'powershell', '-ExecutionPolicy', 'Bypass',
            '-File', str(self.build_script)
        ]
        
        if clean:
            cmd.append('-Clean')
        if admin:
            cmd.append('-Admin')
        
        try:
            # Run build
            result = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True)
            
            duration = time.time() - start_time
            
            if result.returncode == 0:
                print(f"✅ Build completed successfully in {duration:.1f}s")
                self.print_build_status()
                return True
            else:
                print(f"❌ Build failed after {duration:.1f}s")
                print("Error output:")
                print(result.stderr)
                return False
                
        except Exception as e:
            print(f"❌ Build error: {e}")
            return False
    
    def watch_and_build(self):
        """Start watching for changes and auto-building."""
        print("👀 Starting file watcher...")
        print("Press Ctrl+C to stop")
        
        try:
            # Import watchdog here to avoid import error if not installed
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler
            
            from scripts.auto_build import BuildHandler
            
            event_handler = BuildHandler()
            observer = Observer()
            observer.schedule(event_handler, str(REPO_ROOT), recursive=True)
            
            observer.start()
            
            while True:
                time.sleep(1)
                
        except ImportError:
            print("❌ Watchdog not installed. Install with: pip install watchdog")
            return False
        except KeyboardInterrupt:
            print("\n🛑 Stopping watcher...")
            observer.stop()
            observer.join()
            print("✅ Watcher stopped")
            return True

def main():
    parser = argparse.ArgumentParser(description='Lordnine Build Automation')
    parser.add_argument('--clean', action='store_true', help='Clean build (remove previous artifacts)')
    parser.add_argument('--admin', action='store_true', help='Build with UAC elevation')
    parser.add_argument('--watch', action='store_true', help='Watch for changes and auto-build')
    parser.add_argument('--status', action='store_true', help='Show build status only')
    parser.add_argument('--check', action='store_true', help='Check dependencies only')
    
    args = parser.parse_args()
    
    automation = BuildAutomation()
    
    if args.check:
        return 0 if automation.check_dependencies() else 1
    
    if args.status:
        automation.print_build_status()
        return 0
    
    if args.watch:
        return 0 if automation.watch_and_build() else 1
    
    # Default: run build
    if not automation.check_dependencies():
        return 1
    
    success = automation.build(clean=args.clean, admin=args.admin)
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())




