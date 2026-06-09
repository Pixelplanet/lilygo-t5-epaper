# flash.ps1 - One-shot firmware flasher for the LilyGo T5 4.7" Plus (Windows).
#
#   .\flash.ps1 -Port COM7
#
# COM7 is usually the ROM/download port. If unsure, see README "Find the ports".
# This erases the chip and writes firmware-epd.bin at offset 0x0.
param(
    [Parameter(Mandatory = $true)][string]$Port,
    [string]$Firmware = "$PSScriptRoot\firmware-epd.bin"
)

if (-not (Test-Path $Firmware)) {
    Write-Error "Firmware not found: $Firmware"
    exit 1
}

Write-Host "Killing any lingering python (frees the COM port)..." -ForegroundColor Cyan
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 2

Write-Host "Erasing flash on $Port ..." -ForegroundColor Cyan
python -m esptool --chip esp32s3 --port $Port erase_flash
if ($LASTEXITCODE -ne 0) { Write-Error "erase_flash failed"; exit 1 }

Write-Host "Writing $Firmware to $Port ..." -ForegroundColor Cyan
python -m esptool --chip esp32s3 --port $Port --baud 460800 write_flash 0x0 $Firmware
if ($LASTEXITCODE -ne 0) { Write-Error "write_flash failed"; exit 1 }

Write-Host "Done. Tap RST on the board, then deploy the app with deploy.ps1." -ForegroundColor Green
