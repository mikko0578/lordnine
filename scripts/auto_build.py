#!/usr/bin/env python3
"""
Auto-build script that monitors file changes and rebuilds the Lordnine executables.
Run this script to automatically rebuild whenever source files change.
"""

import os
import sys
import time
import subprocess
import threading
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Add repo root to path
REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

class BuildHandler(FileSystemEventHandler):
    def __init__(self):
        self.last_build = 0
        self.build_cooldown = 5  # Minimum seconds between builds
        self.building = False
        
    def should_build(self, file_path):
        """Check if the changed file should trigger a rebuild."""
        path = Path(file_path)
        
        # Only watch Python files and config files
        if path.suffix not in ['.py', '.yaml', '.yml']:
            return False
            
        # Ignore build artifacts and temporary files
        ignore_dirs = ['build', 'dist', '__pycache__', '.git', 'node_modules']
        if any(part in ignore_dirs for part in path.parts):
            return False
            
        # Ignore specific files
        ignore_files = ['auto_build.py', 'build_exe.ps1']
        if path.name in ignore_files:
            return False
            
        return True
    
    def on_modified(self, event):
        if event.is_directory:
            return
            
        if not self.should_build(event.src_path):
            return
            
        current_time = time.time()
        if current_time - self.last_build < self.build_cooldown:
            return
            
        if self.building:
            return
            
        print(f"\n🔄 File changed: {event.src_path}")
        self.trigger_build()
    
    def trigger_build(self):
        """Trigger a build in a separate thread."""
        if self.building:
            return
            
        self.building = True
        self.last_build = time.time()
        
        def build_thread():
            try:
                print("🚀 Starting auto-build...")
                start_time = time.time()
                
                # Run the build script
                result = subprocess.run([
                    'powershell', '-ExecutionPolicy', 'Bypass', 
                    '-File', str(REPO_ROOT / 'scripts' / 'build_exe.ps1')
                ], capture_output=True, text=True, cwd=REPO_ROOT)
                
                end_time = time.time()
                duration = end_time - start_time
                
                if result.returncode == 0:
                    print(f"✅ Build completed successfully in {duration:.1f}s")
                    print("📁 Executables updated in dist/LordnineGUI/")
                else:
                    print(f"❌ Build failed after {duration:.1f}s")
                    print("Error output:", result.stderr)
                    
            except Exception as e:
                print(f"❌ Build error: {e}")
            finally:
                self.building = False
        
        thread = threading.Thread(target=build_thread, daemon=True)
        thread.start()

def main():
    print("🔍 Lordnine Auto-Builder")
    print("=" * 50)
    print("Monitoring for changes in:")
    print(f"  📁 {REPO_ROOT}")
    print("  📄 Python files (.py)")
    print("  ⚙️  Config files (.yaml, .yml)")
    print("\n🛑 Press Ctrl+C to stop")
    print("=" * 50)
    
    # Check if watchdog is installed
    try:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler
    except ImportError:
        print("❌ Error: 'watchdog' package not installed")
        print("Install with: pip install watchdog")
        return 1
    
    # Check if build script exists
    build_script = REPO_ROOT / 'scripts' / 'build_exe.ps1'
    if not build_script.exists():
        print(f"❌ Error: Build script not found at {build_script}")
        return 1
    
    # Set up file watcher
    event_handler = BuildHandler()
    observer = Observer()
    
    # Watch the entire repo
    observer.schedule(event_handler, str(REPO_ROOT), recursive=True)
    
    try:
        observer.start()
        print("👀 Watching for changes...")
        
        # Keep the script running
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n🛑 Stopping auto-builder...")
        observer.stop()
        
    observer.join()
    print("✅ Auto-builder stopped")
    return 0

if __name__ == "__main__":
    sys.exit(main())




