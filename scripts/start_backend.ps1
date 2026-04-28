# =====================================================================
# Karabuk FWI - start backend in Local Hardware Mode
# =====================================================================
# Boots the FastAPI backend on http://localhost:8000 with the local
# .venv (auto-created on first run) and BACKEND_ENV=development so
# the uvicorn reload watcher is on. Webcam / PC camera / drone are
# reachable through Windows DSHOW from this process.
#
# Usage (from project root):
#   powershell -ExecutionPolicy Bypass -File scripts\start_backend.ps1
# =====================================================================

[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $venvPython)) {
    Write-Host "No .venv found - creating one..." -ForegroundColor Yellow
    python -m venv .venv
    & $venvPython -m pip install --upgrade pip
    & $venvPython -m pip install -r backend\requirements.txt
}

# Quiet sanity: warn (don't block) if port 8000 is already busy.
$busy = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($busy) {
    Write-Host "[warn] port 8000 already in use - run scripts\check_ports.ps1 first." -ForegroundColor Yellow
}

$env:BACKEND_ENV = "development"
Write-Host "Starting Karabuk FWI backend on http://localhost:8000" -ForegroundColor Green
Write-Host "  API docs:    http://localhost:8000/docs"
Write-Host "  Health:      http://localhost:8000/system/health"
Write-Host ""
& $venvPython "backend\scripts\serve.py"
