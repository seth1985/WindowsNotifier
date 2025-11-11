$min = [version]"26100.2170"

$cv = Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion'
$current = [version]("{0}.{1}" -f $cv.CurrentBuildNumber, $cv.UBR)

if ($current -lt $min) {
    Write-Output "Build below minimum. Exit 1."
    exit 1   # trigger notification
} else {
    Write-Output "Build meets requirement. Exit 0."
    exit 0   # keep waiting
}
