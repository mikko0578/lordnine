@echo off
echo 🚀 Lordnine Development Build
echo =============================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Error: Python not found in PATH
    pause
    exit /b 1
)

REM Run quick build
echo Starting quick build...
python scripts/quick_build.py

if errorlevel 1 (
    echo.
    echo ❌ Quick build failed. Trying full clean build...
    python scripts/quick_build.py --clean
)

echo.
echo ✅ Build process completed
pause




