# deploy.ps1 - Upload the device/ Python tree to the board's flash (Windows).
#
#   .\deploy.ps1 -Port COM5
#
# COM5 is usually the running-app port (native USB-CDC). After flashing the
# firmware and tapping RST, the board re-enumerates as a new COM port - use
# that one here. This copies every file under device/ to the flash root.
param(
    [Parameter(Mandatory = $true)][string]$Port,
    [switch]$Reset
)

$ErrorActionPreference = "Stop"
$dev = "$PSScriptRoot\device"

Write-Host "Killing any lingering python (frees the COM port)..." -ForegroundColor Cyan
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 2

# Create directories first, then copy files into them.
python -m mpremote connect $Port fs mkdir :lib 2>$null
python -m mpremote connect $Port fs mkdir :lib/ui 2>$null
python -m mpremote connect $Port fs mkdir :apps 2>$null

Get-ChildItem $dev -Recurse -File | ForEach-Object {
    $rel = $_.FullName.Substring($dev.Length + 1).Replace('\', '/')
    Write-Host "  -> :$rel" -ForegroundColor DarkGray
    python -m mpremote connect $Port fs cp $_.FullName ":$rel"
}

if ($Reset) {
    Write-Host "Resetting board..." -ForegroundColor Cyan
    python -m mpremote connect $Port reset
}

Write-Host "Deploy complete." -ForegroundColor Green
