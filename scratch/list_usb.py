import subprocess

ps_cmd = 'Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -like "*USB*" } | Format-Table -AutoSize FriendlyName, InstanceId, Status'
res = subprocess.check_output(['powershell', '-NoProfile', '-Command', ps_cmd]).decode('utf-8', errors='ignore')
print(res)

