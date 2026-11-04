import subprocess
import time
import sys

print("WATCHER_ACTIVE: Polling for Samsung USB device (600s)...")
sys.stdout.flush()

start_time = time.time()
while time.time() - start_time < 600:
    ps_cmd = 'Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue | Where-Object { $_.InstanceId -like "*04E8*" } | Select-Object -ExpandProperty FriendlyName'
    try:
        out = subprocess.check_output(['powershell', '-NoProfile', '-Command', ps_cmd], timeout=3).decode('utf-8', errors='ignore').strip()
        if out:
            print(f"DEVICE_DETECTED: {out}")
            sys.stdout.flush()
            break
    except Exception:
        pass
    time.sleep(0.5)

print("WATCHER_FINISHED")
