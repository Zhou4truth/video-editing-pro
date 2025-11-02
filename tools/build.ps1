Param(
    [switch]$SkipInstaller
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Write-Host "Video Editor MVP build script (placeholder)." -ForegroundColor Cyan
Write-Host "This script will be expanded to download ffmpeg, run PyInstaller, and invoke Inno Setup."

if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment..."
    python -m venv .venv
}

Write-Host "Activating virtual environment and installing requirements..."
& .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

Write-Host "TODO: Add PyInstaller + Inno Setup steps."
