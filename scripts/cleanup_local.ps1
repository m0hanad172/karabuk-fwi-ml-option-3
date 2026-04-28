# =====================================================================
# Karabuk FWI - local cleanup helper (PowerShell)
# =====================================================================
# Removes ONLY safe, easily-regenerated artefacts from your working
# tree. Designed to be re-runnable, dry-run by default, and
# explicitly aware of the post-restructure layout.
#
# What it WILL remove (only when -Apply is passed):
#   - __pycache__ / *.pyc / *.pyo              (recursively, anywhere)
#   - .pytest_cache / .ruff_cache / .mypy_cache
#   - .tmp       (repo-local pytest/smoke temp files)
#   - frontend/.next   (Next.js build cache)
#   - Pre-restructure leftover root folders if they contain ONLY
#     cache files (src/, configs/, tests/, notebooks/).
#     Any folder with a non-cache file is left untouched.
#   - Empty pre-restructure root folders when they contain no useful
#     files. Database backup files are reported for manual review but
#     are never deleted by this helper.
#
# What it will NEVER remove:
#   - backend/outputs/karabuk_fwi.db        (active SQLite DB)
#   - backend/data/notifications/alerts.jsonl
#   - backend/data/notifications/*.jpg
#   - SQLite backup files (*.db.bak, *.sqlite.bak, *.empty.bak)
#   - .venv  /  venv
#   - frontend/node_modules
#   - any *.joblib / *.pt / *.json under backend/models/
#   - any *.csv under backend/data/processed or backend/data/oof
#
# Usage (from project root):
#   powershell -ExecutionPolicy Bypass -File scripts\cleanup_local.ps1
#       (dry-run - lists what WOULD be removed, changes nothing)
#   powershell -ExecutionPolicy Bypass -File scripts\cleanup_local.ps1 -Apply
#       (actually deletes)
#
# Dry-run is the default to keep accidents impossible.
# =====================================================================

[CmdletBinding()]
param(
    [switch]$Apply
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

if (-not $Apply) {
    Write-Host "[dry-run] Listing what would be removed. Pass -Apply to delete." -ForegroundColor Yellow
} else {
    Write-Host "WARNING: -Apply deletes only the safe cache/build items listed below." -ForegroundColor Yellow
    Write-Host "Protected runtime DBs, alert JSONL/JPG evidence, venvs, node_modules, and DB backups are never deleted." -ForegroundColor Yellow
}
Write-Host "Repo root: $repoRoot"
Write-Host ""

$totalBytes = 0
$removed   = 0
$skipped   = 0

function Format-Size([long]$bytes) {
    if ($bytes -lt 1024)         { return "$bytes B" }
    elseif ($bytes -lt 1MB)      { return ("{0:N1} KB" -f ($bytes / 1KB)) }
    elseif ($bytes -lt 1GB)      { return ("{0:N1} MB" -f ($bytes / 1MB)) }
    else                         { return ("{0:N1} GB" -f ($bytes / 1GB)) }
}

function Get-DirSize($path) {
    try {
        return (Get-ChildItem -LiteralPath $path -Recurse -Force -ErrorAction SilentlyContinue |
                Measure-Object -Property Length -Sum).Sum
    } catch { return 0 }
}

function Remove-Path($path, $reason) {
    if (-not (Test-Path -LiteralPath $path)) { return }
    $isDir = (Get-Item -LiteralPath $path).PSIsContainer
    $size  = if ($isDir) { Get-DirSize $path } else { (Get-Item -LiteralPath $path).Length }
    if ($null -eq $size) { $size = 0 }
    $script:totalBytes += $size
    Write-Host ("  {0,-9}  {1,-12}  {2}" -f (Format-Size $size), $reason, $path)
    if ($Apply) {
        try {
            Remove-Item -LiteralPath $path -Recurse -Force -ErrorAction Stop
            $script:removed++
        } catch {
            Write-Host "    [error] $($_.Exception.Message)" -ForegroundColor Red
        }
    }
}

# ---------------------------------------------------------------------
# 1. Caches anywhere in the tree (Python + frontend).
# ---------------------------------------------------------------------
Write-Host "Caches:" -ForegroundColor Cyan
@(
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache"
) | ForEach-Object {
    $name = $_
    Get-ChildItem -Path $repoRoot -Recurse -Force -Directory -Filter $name -ErrorAction SilentlyContinue |
        Where-Object {
            # Don't traverse into .venv / node_modules - they're not ours.
            $_.FullName -notmatch "\\\.venv\\" -and $_.FullName -notmatch "\\node_modules\\"
        } |
        ForEach-Object { Remove-Path $_.FullName "(cache)" }
}

# Stray .pyc / .pyo files in case they're outside __pycache__.
Get-ChildItem -Path $repoRoot -Recurse -Force -File -Include "*.pyc","*.pyo" -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -notmatch "\\\.venv\\" } |
    ForEach-Object { Remove-Path $_.FullName "(cache)" }

# Next.js build cache.
$tmp = Join-Path $repoRoot ".tmp"
if (Test-Path -LiteralPath $tmp) { Remove-Path $tmp "(temp)" }

# Next.js build cache.
$next = Join-Path $repoRoot "frontend\.next"
if (Test-Path -LiteralPath $next) { Remove-Path $next "(next cache)" }
$nextOut = Join-Path $repoRoot "frontend\out"
if (Test-Path -LiteralPath $nextOut) { Remove-Path $nextOut "(next out)" }

# ---------------------------------------------------------------------
# 2. Pre-restructure leftover root folders - only if cache-only.
# ---------------------------------------------------------------------
Write-Host ""
Write-Host "Pre-restructure leftovers (cache-only check):" -ForegroundColor Cyan
@("src","configs","scripts","tests","notebooks") | ForEach-Object {
    $name = $_
    $candidate = Join-Path $repoRoot $name
    if (-not (Test-Path -LiteralPath $candidate)) { return }
    # Skip the *real* scripts/ dir if our cleanup script lives there.
    if ($PSScriptRoot.StartsWith($candidate, [System.StringComparison]::OrdinalIgnoreCase)) {
        Write-Host "  skipping $name (this script lives inside it)" -ForegroundColor DarkGray
        return
    }
    # Check whether every file under it is a cache-only artefact.
    $nonCache = Get-ChildItem -Path $candidate -Recurse -File -Force -ErrorAction SilentlyContinue |
        Where-Object {
            $_.Name -notmatch '\.pyc$' -and
            $_.Name -notmatch '\.pyo$' -and
            $_.Directory.FullName -notmatch '\\__pycache__'
        }
    if ($null -eq $nonCache -or @($nonCache).Count -eq 0) {
        Remove-Path $candidate "(legacy)"
    } else {
        Write-Host ("  skipping $name - contains {0} non-cache file(s)" -f @($nonCache).Count) -ForegroundColor DarkGray
        $script:skipped++
    }
}

# ---------------------------------------------------------------------
# 3. SQLite backups / legacy outputs: report only.
# ---------------------------------------------------------------------
Write-Host ""
Write-Host "SQLite backups / legacy outputs (manual review only):" -ForegroundColor Cyan
$rootOutputs = Join-Path $repoRoot "outputs"
if (Test-Path -LiteralPath $rootOutputs) {
    Write-Host "  skipping $rootOutputs - legacy DB/output data requires manual review" -ForegroundColor DarkGray
    $script:skipped++
}

# Specifically the post-restructure empty-DB safety backup, if present.
$emptyBak = Join-Path $repoRoot "backend\outputs\karabuk_fwi.db.empty.bak"
if (Test-Path -LiteralPath $emptyBak) {
    Write-Host "  skipping $emptyBak - DB backup requires manual review after smoke/dashboard checks" -ForegroundColor DarkGray
    $script:skipped++
}

Write-Host ""
Write-Host ("Total reclaimable: {0}" -f (Format-Size $totalBytes))
if (-not $Apply) {
    Write-Host ""
    Write-Host "Dry-run only. Re-run with -Apply to actually delete." -ForegroundColor Yellow
} else {
    Write-Host ("Removed {0} item(s); skipped {1}." -f $removed, $skipped) -ForegroundColor Green
}
