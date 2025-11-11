param(
    [Parameter(Mandatory = $true)]
    [string]$TargetDir
)

$ErrorActionPreference = 'Stop'
$resolved = Resolve-Path -LiteralPath $TargetDir
if (-not $resolved) {
    throw "Target directory '$TargetDir' not found."
}
$distRoot = $resolved.ProviderPath
$internal = Join-Path $distRoot "_internal"
if (-not (Test-Path $internal)) {
    throw "Path '$internal' not found. Build output is missing."
}

function Remove-IfExists {
    param([string]$Path)
    if (Test-Path $Path) {
        Remove-Item -LiteralPath $Path -Recurse -Force
    }
}

function Remove-Many {
    param([string]$BasePath, [string[]]$Names)
    foreach ($name in $Names) {
        Remove-IfExists (Join-Path $BasePath $name)
    }
}

Write-Host "Pruning $distRoot ..."

# PySide6 trimming
$pysidePaths = @(
    (Join-Path $internal "PySide6"),
    (Join-Path $internal "QtPlugins")
)

# Directories in PySide6 we never need at runtime
$unusedDirs = @('doc','glue','include','lib','metatypes','qml','QtAsyncio','resources','scripts','support','translations','typesystems','__pycache__')
# Developer tooling we can remove
$unusedExe = @('assistant.exe','balsam.exe','balsamui.exe','designer.exe','linguist.exe','lrelease.exe','lupdate.exe','qmlcachegen.exe','qmlformat.exe','qmlimportscanner.exe','qmllint.exe','qmltyperegistrar.exe','qmltestrunner.exe','qmltime.exe','qt-cmake-private-test.exe','qt-cmake-private-tests.exe','qmltyperegistrar.exe','qmltestrunner.exe')

$pysideKeepDlls = @(
    'Qt6Core.dll',
    'Qt6Gui.dll',
    'Qt6Widgets.dll',
    'Qt6PrintSupport.dll',
    'pyside6.abi3.dll',
    'pyside6qml.abi3.dll',
    'shiboken6.abi3.dll',
    'msvcp140.dll',
    'msvcp140_1.dll',
    'msvcp140_2.dll',
    'msvcp140_codecvt_ids.dll',
    'vcruntime140.dll',
    'python314.dll',
    'python311.dll',
    'python3.dll'
)

$keepPyd = @('QtCore','QtGui','QtWidgets','QtPrintSupport','QtConcurrent','QtAxContainer')
$keepExe = @('rcc.exe','uic.exe')

foreach ($pyside in $pysidePaths) {
    if (-not (Test-Path $pyside)) { continue }

    Remove-Many -BasePath $pyside -Names $unusedDirs
    foreach ($exe in $unusedExe) {
        Remove-IfExists (Join-Path $pyside $exe)
    }

    Get-ChildItem -Path $pyside -Filter *.dll -ErrorAction SilentlyContinue | ForEach-Object {
        if ($pysideKeepDlls -notcontains $_.Name) {
            Remove-Item $_.FullName -Force
        }
    }

    Get-ChildItem -Path $pyside -Filter *.pyd -ErrorAction SilentlyContinue | ForEach-Object {
        if ($keepPyd -notcontains $_.BaseName) {
            Remove-Item $_.FullName -Force
        }
    }
    Get-ChildItem -Path $pyside -Filter *.pyi -ErrorAction SilentlyContinue | ForEach-Object {
        $base = $_.BaseName.Split('.')[0]
        if ($keepPyd -notcontains $base) {
            Remove-Item $_.FullName -Force
        }
    }

    Get-ChildItem -Path $pyside -Filter *.exe -ErrorAction SilentlyContinue | ForEach-Object {
        if ($keepExe -notcontains $_.Name) {
            Remove-Item $_.FullName -Force
        }
    }
}

# Qt plugin cleanup
foreach ($pluginsRel in @('PySide6\plugins','QtPlugins')) {
    $pluginPath = Join-Path $internal $pluginsRel
    if (-not (Test-Path $pluginPath)) { continue }
    Get-ChildItem -Path $pluginPath -Directory | Where-Object { $_.Name -ne 'platforms' } | Remove-Item -Recurse -Force
    $platformDir = Join-Path $pluginPath 'platforms'
    if (Test-Path $platformDir) {
        Get-ChildItem -Path $platformDir -File | Where-Object { $_.Name -ne 'qwindows.dll' } | Remove-Item -Force
    }
}

Write-Host "Pruning complete for $distRoot."
