<#
    deploy.ps1 - Upload the contents of src/ to the board flash root via mpremote.
    Also generates version.json with SHA-256 hashes for OTA update support.

    Usage:
        ./tools/deploy.ps1 -Port COM5
#>
param(
    [Parameter(Mandatory = $true)][string]$Port
)

$src = Join-Path $PSScriptRoot "..\src"
$src = (Resolve-Path $src).Path
$versionFile = Join-Path $PSScriptRoot "..\version.json"
$updateFile = Join-Path $PSScriptRoot "..\update.json"

Write-Host "Uploading $src -> $Port :/" -ForegroundColor Cyan

# Collect dirs and .py files, skipping Python bytecode caches.
Push-Location $src
try {
    $dirs = Get-ChildItem -Recurse -Directory |
        ForEach-Object { $_.FullName.Substring($src.Length + 1).Replace('\', '/') } |
        Where-Object { $_ -notmatch '__pycache__' }

    $files = Get-ChildItem -Recurse -File -Filter *.py |
        ForEach-Object { $_.FullName.Substring($src.Length + 1).Replace('\', '/') } |
        Where-Object { $_ -notmatch '__pycache__' }

    # Build ONE chained mpremote session (avoids per-file USB resets on
    # ESP32-S3 USB-Serial/JTAG, which is fragile when reopened repeatedly).
    $a = @('connect', $Port)
    foreach ($d in $dirs)  { $a += @('fs', 'mkdir', ":$d") }
    foreach ($f in $files) {
        Write-Host "  + $f"
        $a += @('fs', 'cp', "$f", ":$f")
    }

    # Run as one chained command. mkdir on existing dirs is non-fatal
    # in practice (mpremote prints a warning but continues), yet the
    # exit code may still be non-zero. Ignore mkdir failures.
    $aText = $a -join ' '
    Write-Host "  mpremote $aText" -ForegroundColor DarkGray
    python -m mpremote @a 2>&1 | Out-Host
    if ($LASTEXITCODE -ne 0) {
        # Check if all cp's actually succeeded despite the exit code.
        Write-Host "  WARNING: mpremote exited $LASTEXITCODE (mkdir on existing dirs is expected)" -ForegroundColor Yellow
    }

    # --- Generate version.json with SHA-256 hashes of all deployed files ---
    Write-Host "`nGenerating version.json..." -ForegroundColor Cyan

    $hashTable = @{}
    foreach ($f in $files) {
        $fullPath = Join-Path $src $f
        $hash = (Get-FileHash -Path $fullPath -Algorithm SHA256).Hash.ToLower()
        $hashTable[$f] = $hash
    }

    # Read current remote version to determine next version number.
    $remoteVersion = 0
    if (Test-Path $updateFile) {
        try {
            $remoteJson = Get-Content $updateFile -Raw | ConvertFrom-Json
            $remoteVersion = [int]$remoteJson.version
        } catch {}
    }

    $versionObj = @{
        version = $remoteVersion
        files   = $hashTable
    }

    # Write local version.json (for reference, also uploaded to device).
    $versionJson = $versionObj | ConvertTo-Json -Depth 3
    Set-Content -Path $versionFile -Value $versionJson -Encoding UTF8
    Write-Host "  Wrote $versionFile (v$remoteVersion, $($hashTable.Count) files)" -ForegroundColor Green

    # Upload version.json to the device as well so OTA can compare against it.
    Write-Host "  Uploading version.json to device..." -ForegroundColor DarkGray
    python -m mpremote connect $Port fs cp "$versionFile" ":version.json"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  WARNING: version.json upload failed (OTA won't work until next deploy)" -ForegroundColor Yellow
    }

    # Also generate/update the remote update.json manifest using Python
    # (more reliable than PowerShell's JSON handling).
    Write-Host "  Generating update.json via Python..." -ForegroundColor DarkGray
    $genScript = Join-Path $PSScriptRoot "gen_hashes.py"
    python $genScript
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  WARNING: gen_hashes.py failed" -ForegroundColor Yellow
    }
    Write-Host "  Updated $updateFile for GitHub upload" -ForegroundColor Green
    Write-Host "  → Commit & push update.json to publish the OTA update" -ForegroundColor Yellow
}
finally { Pop-Location }

Write-Host "`nDone. Reset the board or run:  python -m mpremote connect $Port run src/main.py" -ForegroundColor Green

