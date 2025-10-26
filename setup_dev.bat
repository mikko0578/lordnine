@echo off
echo 🛠️  Lordnine Development Setup
echo ==============================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python not found. Please install Python 3.8+ and add it to PATH.
    pause
    exit /b 1
)

echo ✅ Python found

REM Install development dependencies
echo 📦 Installing development dependencies...
pip install -r requirements-dev.txt

if errorlevel 1 (
    echo ❌ Failed to install dependencies
    pause
    exit /b 1
)

echo ✅ Dependencies installed

REM Check build status
echo.
echo 📊 Current build status:
python scripts/build_automation.py --status

echo.
echo 🎯 Development setup complete!
echo.
echo Available commands:
echo   start_auto_build.bat     - Start auto-builder (watches for changes)
echo   scripts/dev_build.bat    - Quick development build
echo   scripts/build_exe.ps1    - Full build with clean
echo.
echo To start auto-building, run: start_auto_build.bat
echo.
pause




