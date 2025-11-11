param(
    [switch]$SkipPrune
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$pyinstaller = Join-Path ".venv" "Scripts\pyinstaller.exe"
if (-not (Test-Path $pyinstaller)) {
    throw "PyInstaller executable not found at $pyinstaller. Activate the venv first."
}

& $pyinstaller "packaging/core.spec"
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE."
}

if (-not $SkipPrune) {
& ".\scripts\prune_dist.ps1" -TargetDir "dist\windows_notifier_core"
}
Write-Host "Core build completed."
