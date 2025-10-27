@echo off
setlocal ENABLEDELAYEDEXPANSION

rem Change CWD to repo root (folder above this script)
set "SCRIPT_DIR=%~dp0"
pushd "%SCRIPT_DIR%.." >nul

rem Pick Python launcher (prefer 'py', fallback to 'python')
set "PY_CMD="
where py >nul 2>&1 && set "PY_CMD=py"
if not defined PY_CMD where python >nul 2>&1 && set "PY_CMD=python"
if not defined PY_CMD (
  echo [ERROR] Python not found in PATH. Please install Python or add it to PATH.
  pause
  exit /b 1
)

rem Check for Administrator privileges: 'net session' requires admin
net session >nul 2>&1
if errorlevel 1 (
  echo Requesting Administrator privileges...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%PY_CMD%' -ArgumentList '""scripts/gui.py""' -WorkingDirectory '$(Get-Location)' -Verb RunAs"
  goto :eof
) else (
  "%PY_CMD%" -u scripts\gui.py
)

:eof
popd >nul
endlocal

