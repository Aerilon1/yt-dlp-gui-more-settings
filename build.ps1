# Build yt-dlp-gui.exe (one-folder) into dist/, zip a portable release, optionally deploy.
# Run from the repo root: .\build.ps1
# Requires: Python 3.9+, pip
#
# Uses a dedicated venv so PyInstaller does not scan your global Python (torch, etc.),
# which otherwise produces huge builds and hundreds of bogus "missing DLL" warnings.
#
# User config, cookies, and download history are never bundled or copied by this script --
# they live under %APPDATA%\yt-dlp-gui and are created there automatically on first run.
#
# Examples:
#   .\build.ps1                          # build + portable zip only
#   .\build.ps1 -InstallDir "C:\Program Files\yt-dlp-gui"   # also copy to install folder

param(
    [string]$InstallDir = "",
    [string]$ZipPath = ""
)

$ErrorActionPreference = "Stop"
$RepoRoot = $PSScriptRoot
$VenvDir = Join-Path $RepoRoot ".venv-build"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$DistDir = Join-Path $RepoRoot "dist"
$BuildOutput = Join-Path $DistDir "yt-dlp-gui"

if (-not $ZipPath) {
    $ZipPath = Join-Path $RepoRoot "yt-dlp-gui-win64.zip"
}

Set-Location $RepoRoot

if (-not (Test-Path $VenvPython)) {
    Write-Host "Creating isolated build venv at $VenvDir ..." -ForegroundColor Cyan
    python -m venv $VenvDir
}

Write-Host "Installing build dependencies into venv..." -ForegroundColor Cyan
& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install -r (Join-Path $RepoRoot "requirements.txt")
& $VenvPython -m pip install "pyinstaller>=6.0"

Write-Host "Building exe (one-folder)..." -ForegroundColor Cyan
$env:QT_API = "PySide6"
& $VenvPython -m PyInstaller --clean --noconfirm `
    --distpath $DistDir `
    --workpath (Join-Path $RepoRoot "build\pyinstaller") `
    (Join-Path $RepoRoot "build\yt-dlp-gui.spec")

$BuiltExe = Join-Path $BuildOutput "yt-dlp-gui.exe"
if (-not (Test-Path $BuiltExe)) {
    Write-Host "Build failed: exe not found." -ForegroundColor Red
    exit 1
}

# Portable ZIP matching upstream naming: yt-dlp-gui-win64.zip containing yt-dlp-gui/
Write-Host "Creating portable zip: $ZipPath ..." -ForegroundColor Cyan
if (Test-Path $ZipPath) {
    Remove-Item $ZipPath -Force
}
Compress-Archive -Path $BuildOutput -DestinationPath $ZipPath -CompressionLevel Optimal

if ($InstallDir) {
    Write-Host "Deploying to $InstallDir ..." -ForegroundColor Cyan
    New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
    Get-ChildItem -Path $BuildOutput -Force | ForEach-Object {
        $dest = Join-Path $InstallDir $_.Name
        if ($_.PSIsContainer) {
            if (Test-Path $dest) { Remove-Item $dest -Recurse -Force }
            Copy-Item $_.FullName -Destination $dest -Recurse -Force
        } else {
            Copy-Item $_.FullName -Destination $dest -Force
        }
    }
    Write-Host "Installed. Run: $InstallDir\yt-dlp-gui.exe" -ForegroundColor Green
}

$zipSizeMb = [math]::Round((Get-Item $ZipPath).Length / 1MB, 1)
Write-Host "Done. Portable release: $ZipPath ($zipSizeMb MB)" -ForegroundColor Green
Write-Host "Extract the zip, then run yt-dlp-gui\yt-dlp-gui.exe (ffmpeg + yt-dlp must be on PATH)." -ForegroundColor DarkGray
Write-Host "User config, cookies, and history live under %APPDATA%\yt-dlp-gui." -ForegroundColor DarkGray
