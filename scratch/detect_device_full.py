import subprocess

def run_ps(cmd):
    try:
        return subprocess.check_output(['powershell', '-NoProfile', '-Command', cmd], timeout=8).decode('utf-8', errors='ignore').strip()
    except Exception as e:
        return f'Error: {e}'

print('=== 1. ADB DEVICES ===')
try:
    print(subprocess.check_output(['adb', 'devices'], timeout=5).decode('utf-8', errors='ignore').strip())
except Exception as e:
    print(f'ADB Error: {e}')

print('\n=== 2. SAMSUNG USB DEVICES (VID 04E8) ===')
ps_devs = 'Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -like "*04E8*" } | Format-Table -AutoSize FriendlyName, Class, InstanceId, Status'
print(run_ps(ps_devs))

print('\n=== 3. ALL USB COMPOSITE & SERIAL DEVICES ===')
ps_usb = 'Get-PnpDevice -PresentOnly | Where-Object { $_.Class -match "Ports|Modem|USB" } | Format-Table -AutoSize FriendlyName, Class, InstanceId, Status'
print(run_ps(ps_usb))

