import subprocess

ps_cmd = 'Get-ItemProperty -Path "HKLM:\\SYSTEM\\CurrentControlSet\\Enum\\USB\\VID_04E8&PID_685D*\\*" -ErrorAction SilentlyContinue | Select-Object FriendlyName, PortName, AttachedTo'
res = subprocess.check_output(['powershell', '-NoProfile', '-Command', ps_cmd]).decode('utf-8', errors='ignore')
print(res)

ps_modem = 'Get-CimInstance -ClassName Win32_PnPEntity | Where-Object { $_.DeviceID -match "685D" } | Select-Object Name, DeviceID, Status'
print(subprocess.check_output(['powershell', '-NoProfile', '-Command', ps_modem]).decode('utf-8', errors='ignore'))

