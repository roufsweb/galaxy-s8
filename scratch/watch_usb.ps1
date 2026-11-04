$watcher = New-Object System.Management.ManagementEventWatcher
$query = New-Object System.Management.WqlEventQuery
$query.EventClassName = "__InstanceCreationEvent"
$query.WithinInterval = New-Object System.TimeSpan(0,0,1)
$query.QueryString = "Select * from __InstanceCreationEvent within 1 where TargetInstance isa 'Win32_PnPEntity'"
$watcher.Query = $query

Write-Host "Listening for USB plug events... (Timeout 60s)"
$startTime = Get-Date
while (((Get-Date) - $startTime).TotalSeconds -lt 60) {
    try {
        $event = $watcher.WaitForNextEvent()
        $target = $event.TargetInstance
        if ($target.Name -match "Samsung|Android|Modem|Serial|CDC|Composite|Unknown|Gadget" -or $target.DeviceID -match "04E8") {
            Write-Host "DEVICE DETECTED: $($target.Name) -> $($target.DeviceID)"
            break
        }
    } catch {
        break
    }
}

