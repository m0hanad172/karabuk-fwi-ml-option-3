# =====================================================================
# Karabuk FWI - start frontend in Local Hardware Mode
# =====================================================================
# Boots the Next.js dashboard on http://localhost:3000. Talks to the
# backend at NEXT_PUBLIC_API_URL (default http://localhost:8000) -
# start the backend first (scripts\start_backend.ps1) for a working
# Run FWI / Detection Alerts experience.
#
# Usage (from project root):
#   powershell -ExecutionPolicy Bypass -File scripts\start_frontend.ps1
# =====================================================================

[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location (Join-Path $repoRoot "frontend")

if (-not (Test-Path -LiteralPath "node_modules")) {
    Write-Host "node_modules missing - running npm install..." -ForegroundColor Yellow
    npm install
}

$busy = Get-NetTCPConnection -LocalPort 3000 -State Listen -ErrorAction SilentlyContinue
if ($busy) {
    Write-Host "[warn] port 3000 already in use - run scripts\check_ports.ps1 first." -ForegroundColor Yellow
}

Write-Host "Starting Karabuk FWI frontend on http://localhost:3000" -ForegroundColor Green
Write-Host "  Backend expected at: $($env:NEXT_PUBLIC_API_URL ?? 'http://localhost:8000')"
Write-Host ""
npm run dev
