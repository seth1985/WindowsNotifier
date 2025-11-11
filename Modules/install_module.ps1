param(
    [string]$ModuleFolder = "",
    [string]$ModulesRoot = "$env:LOCALAPPDATA\Windows Notifier\Modules"
)

$modulesBase = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not (Test-Path $modulesBase)) {
    throw "Unable to determine modules base directory."
}

$moduleDirs = @()
if ([string]::IsNullOrWhiteSpace($ModuleFolder)) {
    $moduleDirs = Get-ChildItem -Path $modulesBase -Directory
    if (-not $moduleDirs) {
        Write-Warning "No module directories found under $modulesBase."
        exit 0
    }
} else {
    $resolved = Join-Path $modulesBase $ModuleFolder
    if (-not (Test-Path $resolved)) {
        throw "Module folder '$resolved' not found."
    }
    $moduleDirs = ,(Get-Item $resolved)
}

New-Item -ItemType Directory -Path $ModulesRoot -Force | Out-Null

foreach ($moduleDir in $moduleDirs) {
    $moduleName = $moduleDir.Name
    $destination = Join-Path $ModulesRoot $moduleName

    Write-Output "Installing module '$moduleName' into '$ModulesRoot'."

    if (Test-Path $destination) {
        Write-Output "Removing existing module folder at $destination."
        Remove-Item $destination -Recurse -Force
    }

    Copy-Item $moduleDir.FullName -Destination $destination -Recurse -Force

    $manifestPath = Join-Path $destination 'manifest.json'
    if (-not (Test-Path $manifestPath)) {
        Write-Warning "Manifest file not found for '$moduleName' at $manifestPath. Skipping registry entry."
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

    Write-Output "Module '$moduleName' copied. Registry entry created at $registryKey."
}
