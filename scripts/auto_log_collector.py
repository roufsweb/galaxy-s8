#!/usr/bin/env python3
"""
auto_log_collector.py — High-Priority Autonomous Crash & Forensic Telemetry Collector
Monitors USB ADB and network interfaces continuously for the Samsung Galaxy S8 (SM-G950N).
The split-second the device connects, it autonomously dumps:
1. /proc/last_kmsg (Critical Kernel Panic & Reset Reason)
2. /sys/fs/pstore/* (Persistent RAM oops logs)
3. dmesg & logcat
4. All /data/linux/*.log and Ubuntu /var/log/
5. Battery, PMIC MAX77865, and Fuel Gauge registers
6. Thermal zone sensors
7. Autonomous Telegram notification with forensic crash analysis
"""

import os
import sys
import time
import subprocess
import datetime
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
LOGS_DIR = WORKSPACE / "logs"

def run_cmd(cmd, timeout=10):
    try:
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return res.returncode, res.stdout.strip(), res.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", "TIMEOUT"
    except Exception as e:
        return -1, "", str(e)

def notify_telegram(message, photo=None):
    try:
        script = WORKSPACE / "scripts" / "send_telegram.py"
        if photo and Path(photo).exists():
            subprocess.run([sys.executable, str(script), "--photo", str(photo), message], timeout=20)
        else:
            subprocess.run([sys.executable, str(script), message], timeout=20)
    except Exception as e:
        print(f"[!] Telegram notify error: {e}", file=sys.stderr)

def check_adb_device():
    code, out, _ = run_cmd("adb devices")
    if code == 0:
        for line in out.splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 2 and parts[1] in ("device", "recovery"):
                return parts[0], parts[1]
    return None, None

def collect_telemetry(serial, mode):
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    target_dir = LOGS_DIR / f"crash_investigation_{ts}"
    target_dir.mkdir(parents=True, exist_ok=True)
    print(f"[+] Device detected: {serial} ({mode})! Dumping forensics to {target_dir}...")

    # 1. /proc/last_kmsg (HIGHEST PRIORITY)
    print("[*] Grabbing /proc/last_kmsg...")
    code, out, err = run_cmd(f"adb -s {serial} shell cat /proc/last_kmsg")
    last_kmsg_path = target_dir / "last_kmsg.txt"
    if code == 0 and out and "No such file" not in out:
        last_kmsg_path.write_text(out, encoding="utf-8", errors="replace")
        print(f"[+] /proc/last_kmsg captured ({len(out)} bytes)")
    else:
        last_kmsg_path.write_text(f"NOT_FOUND_OR_EMPTY\nError: {err}\nOutput: {out}", encoding="utf-8")
        print("[-] /proc/last_kmsg was empty or wiped.")

    # 2. pstore ramoops
    print("[*] Grabbing /sys/fs/pstore/*...")
    run_cmd(f"adb -s {serial} pull /sys/fs/pstore/ {target_dir}/pstore")

    # 3. Live dmesg
    print("[*] Grabbing live dmesg...")
    code, out, _ = run_cmd(f"adb -s {serial} shell dmesg")
    (target_dir / "dmesg.txt").write_text(out, encoding="utf-8", errors="replace")

    # 4. Logcat
    print("[*] Grabbing logcat...")
    code, out, _ = run_cmd(f"adb -s {serial} shell logcat -d -v time")
    (target_dir / "logcat.txt").write_text(out, encoding="utf-8", errors="replace")

    # 5. Battery & Power Supply registers
    print("[*] Grabbing power supply registers...")
    code, out, _ = run_cmd(f"adb -s {serial} shell \"for f in /sys/class/power_supply/battery/* /sys/class/power_supply/max77865-charger/*; do if [ -f \\$f ]; then echo \\$f:; cat \\$f 2>/dev/null; fi; done\"")
    (target_dir / "power_supply_dump.txt").write_text(out, encoding="utf-8", errors="replace")

    # 6. Thermal zones
    print("[*] Grabbing thermal zones...")
    code, out, _ = run_cmd(f"adb -s {serial} shell \"for f in /sys/devices/virtual/thermal/thermal_zone*/temp /sys/devices/virtual/thermal/thermal_zone*/type; do if [ -f \\$f ]; then echo \\$f:; cat \\$f 2>/dev/null; fi; done\"")
    (target_dir / "thermal_dump.txt").write_text(out, encoding="utf-8", errors="replace")

    # 7. Process list & System info
    print("[*] Grabbing system stats...")
    code, out, _ = run_cmd(f"adb -s {serial} shell \"uname -a; uptime; free -m 2>/dev/null; df -h 2>/dev/null; ps aux 2>/dev/null || ps\"")
    (target_dir / "system_state.txt").write_text(out, encoding="utf-8", errors="replace")

    # 8. Userland logs from /data/linux and /mnt/ubuntu
    print("[*] Pulling /data/linux logs...")
    run_cmd(f"adb -s {serial} pull /data/linux/ {target_dir}/data_linux")

    # Analyze last_kmsg for panic signature
    kmsg_content = last_kmsg_path.read_text(encoding="utf-8", errors="replace")
    panic_lines = []
    for line in kmsg_content.splitlines():
        lower = line.lower()
        if any(w in lower for w in ["panic", "oops", "null pointer", "watchdog", "kernel bug", "reboot:", "power off", "thermal"]):
            panic_lines.append(line.strip())

    summary_msg = f"[FORENSIC ALERT] Galaxy S8 Reconnected!\nTarget: {serial} ({mode})\nDump Dir: {target_dir.name}\n"
    if panic_lines:
        summary_msg += "CRASH HINTS FOUND in last_kmsg:\n" + "\n".join(panic_lines[-5:])
    else:
        summary_msg += "last_kmsg: No explicit panic signature found or RAM console was wiped."

    print(f"\n================ SUMMARY ================\n{summary_msg}\n=========================================\n")
    notify_telegram(summary_msg)
    return target_dir

def main():
    print("[*] ========================================================")
    print("[*] Galaxy S8 Autonomous Forensic Log Collector Online")
    print("[*] Listening on ADB & USB for device connection...")
    print("[*] Press Ctrl+C to stop.")
    print("[*] ========================================================")

    while True:
        serial, mode = check_adb_device()
        if serial:
            collect_telemetry(serial, mode)
            print("[+] Log capture completed. Continuing to monitor...")
            # Wait 30 seconds before re-checking to avoid spamming dumps
            time.sleep(30)
        time.sleep(1)

if __name__ == "__main__":
    main()

