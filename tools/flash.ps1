<#
    flash.ps1 - Erase the ESP32-S3 and write mainline MicroPython.

    IMPORTANT: use the SPIRAM_OCT (Octal PSRAM) build for the N16R8 module, or
    the 8 MB PSRAM will not map and the board will boot-loop.
    Download: https://micropython.org/download/ESP32_GENERIC_S3/  (variant: SPIRAM_OCT)

    Usage:
        ./tools/flash.ps1 -Port COM5 -Firmware .\firmware\ESP32_GENERIC_S3-SPIRAM_OCT.bin
#>
param(
    [Parameter(Mandatory = $true)][string]$Port,
    [Parameter(Mandatory = $true)][string]$Firmware
)

if (-not (Test-Path $Firmware)) { throw "Firmware not found: $Firmware" }

Write-Host "Erasing flash on $Port ..." -ForegroundColor Cyan
python -m esptool --chip esp32s3 --port $Port erase_flash
if ($LASTEXITCODE -ne 0) { throw "erase_flash failed" }

Write-Host "Writing $Firmware at 0x0 ..." -ForegroundColor Cyan
python -m esptool --chip esp32s3 --port $Port --baud 921600 write_flash -z 0x0 $Firmware
if ($LASTEXITCODE -ne 0) { throw "write_flash failed" }

Write-Host "Done. Now upload the app:  ./tools/deploy.ps1 -Port $Port" -ForegroundColor Green
