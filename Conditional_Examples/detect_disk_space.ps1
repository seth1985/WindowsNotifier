# ===== CONFIG =====
$MinGB = 250     # Minimum GB required
# ==================

# Convert to bytes
$MinBytes = $MinGB * 1GB

# Get physical disks with partitions
$Drives = Get-PSDrive -PSProvider FileSystem

$LowSpace = $false

foreach ($Drive in $Drives) {
    if ($Drive.Free -lt $MinBytes) {
        $LowSpace = $true
    }
}

if ($LowSpace) {
    Write-Host ("Drive {0} is below minimum: {1:N2} GB free" -f $Drive.Name, ($Drive.Free / 1GB))
    exit 1    # Fails requirement
} else {
    Write-Output "Build meets requirement. Exit 0."
    exit 0    # Meets requirement
}
