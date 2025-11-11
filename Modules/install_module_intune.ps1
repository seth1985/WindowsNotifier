param(
    [string]$ModulesRoot = "$env:LOCALAPPDATA\Windows Notifier\Modules"
)

$ErrorActionPreference = 'Stop'
$packageBase = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not (Test-Path $packageBase)) {
    throw "Unable to determine package directory."
}

$moduleDirs = Get-ChildItem -Path $packageBase -Directory | Where-Object {
    Test-Path (Join-Path $_.FullName 'manifest.json')
}

if (-not $moduleDirs) {
    Write-Warning "No module folders found next to this script. Nothing to install."
    exit 0
}

Write-Output "Copying modules into $ModulesRoot ..."
New-Item -ItemType Directory -Path $ModulesRoot -Force | Out-Null

foreach ($moduleDir in $moduleDirs) {
    $moduleName = $moduleDir.Name
    $destination = Join-Path $ModulesRoot $moduleName

    if (Test-Path $destination) {
        Write-Output "Removing existing module at $destination"
        Remove-Item -LiteralPath $destination -Recurse -Force
    }

    Copy-Item -LiteralPath $moduleDir.FullName -Destination $destination -Recurse -Force

    $manifestPath = Join-Path $destination 'manifest.json'
    if (-not (Test-Path $manifestPath)) {
        Write-Warning "Manifest missing for '$moduleName' after copy. Skipping registry updates."
        continue
    }

    $manifest = Get-Content $manifestPath -Raw | ConvertFrom-Json
    $registryKey = "HKCU:\Software\WindowsNotifier\Modules\$moduleName"
    New-Item -Path $registryKey -Force | Out-Null
    Set-ItemProperty -Path $registryKey -Name Status -Value 'Pending'
    if ($manifest.title) {
        Set-ItemProperty -Path $registryKey -Name Title -Value $manifest.title
    }
    if ($manifest.category) {
        Set-ItemProperty -Path $registryKey -Name Category -Value $manifest.category
    }
    if ($manifest.schedule) {
        Set-ItemProperty -Path $registryKey -Name ScheduledAt -Value $manifest.schedule
    } else {
        Remove-ItemProperty -Path $registryKey -Name ScheduledAt -ErrorAction SilentlyContinue
    }

    Write-Output "Module '$moduleName' deployed to $destination and registered."
}

Write-Output "Module deployment complete."
