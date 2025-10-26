@echo off
title Lordnine Auto-Builder
echo.
echo 🔍 Lordnine Auto-Builder
echo ========================
echo.
echo This will monitor your code for changes and automatically
echo rebuild the executables whenever you make modifications.
echo.
echo Press Ctrl+C to stop the auto-builder
echo.

REM Start the auto-builder
python scripts/build_automation.py --watch

echo.
echo Auto-builder stopped.
pause




