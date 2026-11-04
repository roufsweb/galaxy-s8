import subprocess

ps_cmd = 'Get-PnpDevice -PresentOnly | Where-Object { $_.Status -ne "OK" -or $_.Class -match "Ports|Modem|Android|Samsung" -or $_.InstanceId -match "USB" } | Format-Table -AutoSize FriendlyName, Class, InstanceId, Status'
res = subprocess.check_output(['powershell', '-NoProfile', '-Command', ps_cmd]).decode('utf-8', errors='ignore')
print(res)

