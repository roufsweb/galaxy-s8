while ($true) {
    $dev = Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -match "USB\\VID_04E8" }
    if ($dev) {
        Write-Host "FOUND SAMSUNG USB: $($dev.FriendlyName) [$($dev.InstanceId)]"
        break
    }
    Start-Sleep -Seconds 1
}
