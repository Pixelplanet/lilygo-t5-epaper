<#
    deploy.ps1 - Upload the contents of src/ to the board flash root via mpremote.

    Usage:
        ./tools/deploy.ps1 -Port COM5
#>
param(
    [Parameter(Mandatory = $true)][string]$Port
)

$src = Join-Path $PSScriptRoot "..\src"
$src = (Resolve-Path $src).Path

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
    foreach ($d in $dirs)  { $a += @('fs', 'mkdir', ":$d", '+') }
    foreach ($f in $files) {
        Write-Host "  + $f"
        $a += @('fs', 'cp', "$f", ":$f", '+')
    }
    if ($a[-1] -eq '+') { $a = $a[0..($a.Length - 2)] }

    # mkdir on an existing dir is non-fatal; ignore its specific failure but
    # surface genuine copy errors.
    python -m mpremote @a
    if ($LASTEXITCODE -ne 0) { throw "mpremote deploy failed (exit $LASTEXITCODE)" }
}
finally { Pop-Location }

Write-Host "Done. Reset the board or run:  python -m mpremote connect $Port run src/main.py" -ForegroundColor Green
