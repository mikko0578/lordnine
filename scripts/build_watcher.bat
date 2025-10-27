@echo off
echo 🔍 Lordnine Auto-Builder
echo ========================
echo.
echo Starting auto-build watcher...
echo Press Ctrl+C to stop
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Error: Python not found in PATH
    echo Please install Python and add it to your PATH
    pause
    exit /b 1
)

REM Check if watchdog is installed
python -c "import watchdog" >nul 2>&1
if errorlevel 1 (
    echo 📦 Installing watchdog package...
    pip install watchdog
    if errorlevel 1 (
        echo ❌ Failed to install watchdog
        pause
        exit /b 1
    )
)

REM Start the auto-builder
python scripts/auto_build.py

pause




