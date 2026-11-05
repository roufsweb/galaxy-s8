import subprocess
import time
import sys
import datetime

def log(msg):
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")
    sys.stdout.flush()

log("WATCHER_ACTIVE: Polling for Samsung S8 (ADB or Download Mode)...")

start_time = time.time()
last_state = ""

while time.time() - start_time < 1800:
    # 1. Check ADB
    try:
        adb_out = subprocess.check_output(['adb', 'devices'], timeout=3).decode('utf-8', errors='ignore')
        lines = [line.strip() for line in adb_out.splitlines() if line.strip() and not line.startswith('List of')]
        if lines:
            device_line = lines[0]
            log(f"ADB_ONLINE: {device_line}")
            # Run quick telemetry
            try:
                telemetry = subprocess.check_output([
                    'adb', 'shell',
                    'echo 150 > /sys/class/timed_output/vibrator/enable 2>/dev/null ; '
                    'echo "BATT: $(cat /sys/class/power_supply/battery/capacity 2>/dev/null)% $(cat /sys/class/power_supply/battery/voltage_now 2>/dev/null)uV" ; '
                    'echo "MODE: $(cat /proc/cmdline 2>/dev/null | tr \" \" \"\\n\" | grep -iE \"mode|bootreason\")" ; '
                    'echo "UBUNTU: $(mountpoint -q /mnt/ubuntu && echo mounted || echo unmounted)" ; '
                    'echo "CHARGER: $(cat /sys/class/power_supply/battery/current_now 2>/dev/null)uA"'
                ], timeout=5).decode('utf-8', errors='ignore').strip()
                log(f"TELEMETRY:\n{telemetry}")
            except Exception as e:
                log(f"Telemetry error: {e}")
            break
    except Exception:
        pass

    # 2. Check PnP for Download Mode (VID_04E8 & PID_685D) or other Samsung state
    try:
        ps_cmd = 'Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue | Where-Object { $_.InstanceId -like "*04E8*" } | Select-Object -ExpandProperty InstanceId'
        pnp_out = subprocess.check_output(['powershell', '-NoProfile', '-Command', ps_cmd], timeout=3).decode('utf-8', errors='ignore').strip()
        if pnp_out:
            if "PID_685D" in pnp_out:
                if last_state != "DOWNLOAD_MODE":
                    last_state = "DOWNLOAD_MODE"
                    log(f"DOWNLOAD_MODE_DETECTED (PID_685D on Odin COM port)")
            else:
                if last_state != pnp_out:
                    last_state = pnp_out
                    log(f"SAMSUNG_DEVICE_DETECTED: {pnp_out}")
        else:
            if last_state != "NONE":
                last_state = "NONE"
    except Exception:
        pass

    time.sleep(1.0)

log("WATCHER_FINISHED")
