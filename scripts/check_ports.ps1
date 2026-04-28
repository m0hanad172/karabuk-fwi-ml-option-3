# =====================================================================
# Karabuk FWI - port availability check (Local Hardware Mode)
# =====================================================================
# Confirms that ports 8000 (backend) and 3000 (frontend) are free
# before you start the stack. Reports any process holding the port
# so you can stop it.
#
# Usage (from project root):
#   powershell -ExecutionPolicy Bypass -File scripts\check_ports.ps1
# =====================================================================

[CmdletBinding()]
param(
    [int[]]$Ports = @(8000, 3000)
)

$ErrorActionPreference = "Stop"

$conflicts = 0
foreach ($port in $Ports) {
    $owners = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($null -eq $owners -or @($owners).Count -eq 0) {
        Write-Host ("  [OK]   port {0,-5} : free" -f $port) -ForegroundColor Green
        continue
    }
    $conflicts++
    foreach ($conn in $owners) {
        try {
            $proc = Get-Process -Id $conn.OwningProcess -ErrorAction Stop
            $name = $proc.ProcessName
        } catch {
            $name = "unknown"
        }
        Write-Host ("  [BUSY] port {0,-5} : pid {1} ({2})" -f $port, $conn.OwningProcess, $name) -ForegroundColor Yellow
    }
}

Write-Host ""
if ($conflicts -gt 0) {
    Write-Host "Free a busy port with:  Stop-Process -Id <pid>  (or close the app)" -ForegroundColor Yellow
    exit 1
}
Write-Host "All required ports are free." -ForegroundColor Green
exit 0
