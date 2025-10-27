param(
    [switch]$Clean,
    [switch]$Admin
)

Write-Host "== Lordnine EXE Builder ==" -ForegroundColor Cyan

function Require-Tool($name) {
    if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
        Write-Error "'$name' not found in PATH. Install it in your environment (e.g., pip install pyinstaller)."
        exit 1
    }
}

Require-Tool pyinstaller

function Require-PyModule($name) {
    $cmd = "import $name"
    $p = python -c "try: $cmd; print('OK'); except Exception as e: print('ERR')"
    if (-not ($LASTEXITCODE -eq 0)) { return $false }
    return $p.Trim() -eq 'OK'
}

# Verify common runtime dependencies are installed before building
$pyMods = @('mss','cv2','numpy','PIL','pyautogui','keyboard','yaml','pydirectinput','tkinter')
$missing = @()
foreach ($m in $pyMods) {
    try {
        python -c "import $m" 2>$null 1>$null
        if (-not ($LASTEXITCODE -eq 0)) { $missing += $m }
    } catch { $missing += $m }
}
if ($missing.Count -gt 0) {
    Write-Host "Missing Python modules: $($missing -join ', ')" -ForegroundColor Yellow
    Write-Host "Install with: python -m pip install mss opencv-python numpy pillow pyautogui keyboard pyyaml pydirectinput" -ForegroundColor Yellow
    # Continue; PyInstaller may still proceed if some are optional, but warn first
}

function Stop-IfRunning($procName) {
    try {
        $procs = Get-Process -Name $procName -ErrorAction SilentlyContinue
        if ($procs) {
            Write-Host "Stopping running process: $procName" -ForegroundColor Yellow
            $procs | Stop-Process -Force -ErrorAction SilentlyContinue
            Start-Sleep -Milliseconds 300
        }
    } catch { }
}

function Remove-Dir-Retry($path, $retries=8) {
    for ($i=0; $i -lt $retries; $i++) {
        if (-not (Test-Path -LiteralPath $path)) { return }
        try {
            Remove-Item -Recurse -Force -ErrorAction Stop -LiteralPath $path
            return
        } catch {
            Start-Sleep -Milliseconds (200 + ($i * 100))
        }
    }
    if (Test-Path -LiteralPath $path) {
        Write-Host "Warning: failed to remove $path after retries" -ForegroundColor Yellow
    }
}

if ($Clean) {
    Write-Host "Cleaning previous build artifacts..." -ForegroundColor Yellow
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue build, dist
}

# Ensure no old EXEs are locking dist directories
Stop-IfRunning 'LordnineGUI'
Stop-IfRunning 'LordnineRunner'
Remove-Dir-Retry ([System.IO.Path]::Combine('dist','LordnineGUI'))
Remove-Dir-Retry ([System.IO.Path]::Combine('dist','LordnineRunner'))

Write-Host "Building Runner (LordnineRunner.exe)..." -ForegroundColor Green
pyinstaller --noconfirm lordnine_runner.spec
if ($LASTEXITCODE -ne 0) { Write-Error "Runner build failed"; exit 1 }

Write-Host "Building GUI (LordnineGUI.exe)..." -ForegroundColor Green
$uac = ""
if ($Admin) { $uac = "--uac-admin" }
pyinstaller --noconfirm $uac lordnine_gui.spec
if ($LASTEXITCODE -ne 0) { Write-Error "GUI build failed"; exit 1 }

$runner = [System.IO.Path]::Combine('dist','LordnineRunner','LordnineRunner.exe')
$guiDir = [System.IO.Path]::Combine('dist','LordnineGUI')
if ((Test-Path -LiteralPath $runner) -and (Test-Path -LiteralPath $guiDir)) {
    Write-Host "Copying Runner next to GUI for convenience..." -ForegroundColor Green
    $dest = [System.IO.Path]::Combine($guiDir, 'LordnineRunner.exe')
    Copy-Item -Force -LiteralPath $runner -Destination $dest
}

Write-Host "Done. Run 'dist/LordnineGUI/LordnineGUI.exe'." -ForegroundColor Cyan
