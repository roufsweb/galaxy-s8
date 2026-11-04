$startTime = Get-Date
Write-Host "Monitoring phone USB reboot status for 35 seconds..."

for ($i = 0; $i -lt 35; $i++) {
    Start-Sleep -Seconds 1
    $elapsed = [int]((Get-Date) - $startTime).TotalSeconds
    
    # Check Samsung USB devices
    $samsung = Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue | Where-Object { 
        $_.InstanceId -match "04E8" -or $_.FriendlyName -match "Samsung|Android|Gadget" 
    }
    
    # Check COM Ports
    $ports = Get-CimInstance -ClassName Win32_SerialPort -ErrorAction SilentlyContinue | Select-Object -ExpandProperty DeviceID
    
    # Check ADB
    $adbOut = (adb devices 2>$null | Where-Object { $_ -match "\t" }) -join "; "
    
    # Check network adapters
    $net = Get-NetAdapter -Physical:$false -ErrorAction SilentlyContinue | Where-Object { 
        $_.InterfaceDescription -match "NDIS|RNDIS|Ethernet|Gadget" 
    } | Select-Object -ExpandProperty Name
    
    $samsungNames = ($samsung | ForEach-Object { "$($_.FriendlyName) [$($_.Status)]" }) -join ", "
    if ($samsungNames -or $ports -or $adbOut -or $net) {
        Write-Host "T+${elapsed}s: USB=[$samsungNames] COM=[$ports] ADB=[$adbOut] NET=[$net]"
    }
}

