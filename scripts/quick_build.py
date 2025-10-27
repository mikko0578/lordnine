#!/usr/bin/env python3
"""
Quick build script for development - faster than full build.
Only rebuilds when specific files change.
"""

import os
import sys
import subprocess
import time
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent

def quick_build():
    """Run a quick build without cleaning."""
    print("🚀 Quick build starting...")
    start_time = time.time()
    
    try:
        # Run build without clean flag for faster builds
        result = subprocess.run([
            'powershell', '-ExecutionPolicy', 'Bypass', 
            '-File', str(REPO_ROOT / 'scripts' / 'build_exe.ps1')
        ], cwd=REPO_ROOT)
        
        duration = time.time() - start_time
        
        if result.returncode == 0:
            print(f"✅ Quick build completed in {duration:.1f}s")
            return True
        else:
            print(f"❌ Quick build failed after {duration:.1f}s")
            return False
            
    except Exception as e:
        print(f"❌ Build error: {e}")
        return False

def full_build():
    """Run a full clean build."""
    print("🧹 Full clean build starting...")
    start_time = time.time()
    
    try:
        result = subprocess.run([
            'powershell', '-ExecutionPolicy', 'Bypass', 
            '-File', str(REPO_ROOT / 'scripts' / 'build_exe.ps1'),
            '-Clean'
        ], cwd=REPO_ROOT)
        
        duration = time.time() - start_time
        
        if result.returncode == 0:
            print(f"✅ Full build completed in {duration:.1f}s")
            return True
        else:
            print(f"❌ Full build failed after {duration:.1f}s")
            return False
            
    except Exception as e:
        print(f"❌ Build error: {e}")
        return False

def main():
    if len(sys.argv) > 1 and sys.argv[1] == '--clean':
        return 0 if full_build() else 1
    else:
        return 0 if quick_build() else 1

if __name__ == "__main__":
    sys.exit(main())




