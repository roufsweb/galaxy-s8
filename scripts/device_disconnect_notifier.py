#!/usr/bin/env python3
"""
device_disconnect_notifier.py — Continuous USB Disconnect & Reconnect Watchdog
Monitors the Samsung Galaxy S8 (ce10171ab3e9620804) connection in real-time.
Instantly dispatches Telegram alerts when the phone is unplugged, reboots, or re-enumerates.
Consumes EXACTLY 0 LLM tokens (pure local Python network calls).
"""

import os
import sys
import time
import subprocess
from datetime import datetime
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE))

from scripts.send_telegram import send_telegram_message

SERIAL = "ce10171ab3e9620804"
LOG_FILE = WORKSPACE / "scratch" / "device_connection.log"
POLL_INTERVAL = 1.5  # seconds

def get_adb_state():
    # 1. Primary check: adb devices
    try:
        res = subprocess.run(
            ["adb", "devices"],
            capture_output=True,
            text=True,
            timeout=6
        )
        for line in res.stdout.splitlines():
            if SERIAL in line:
                parts = line.strip().split()
                if len(parts) >= 2:
                    return parts[1]
    except Exception:
        pass

    # 2. Secondary check: Windows COM ports or Download Mode PID_685D
    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -like '*04E8*685D*' -or $_.FriendlyName -like '*SAMSUNG Mobile USB Modem*' } | Select-Object -ExpandProperty Status"],
            capture_output=True,
            text=True,
            timeout=4
        )
        if "OK" in res.stdout:
            return "download_mode"
    except Exception:
        pass

    return "disconnected"

def log_event(event_type, details):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    msg = f"[{ts}] [{event_type}] {details}"
    print(msg, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(msg + "\n")

def main():
    print(f"[*] Starting Samsung Galaxy S8 Connection Watchdog (Serial: {SERIAL})...", flush=True)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    last_state = get_adb_state()
    log_event("STARTUP", f"Initial device state: {last_state.upper()}")

    if last_state != "disconnected":
        send_telegram_message(f"[INFO] Connection Watchdog active. Galaxy S8 is currently ONLINE ({last_state.upper()}).")
    else:
        send_telegram_message(f"[ALERT] Connection Watchdog active. Galaxy S8 is currently DISCONNECTED.")

    consecutive_disconnects = 0
    disconnect_alerted = False

    while True:
        try:
            current_state = get_adb_state()

            if current_state == "disconnected":
                consecutive_disconnects += 1
                if consecutive_disconnects >= 2 and not disconnect_alerted:
                    # Debounced disconnect (verified across 3+ seconds)
                    ts = datetime.now().strftime("%H:%M:%S")
                    log_event("DISCONNECT", f"Device severed connection at {ts}")
                    send_telegram_message(f"[ALERT] Samsung Galaxy S8 DISCONNECTED from host PC at {ts}! Monitoring for reboot / re-enumeration...")
                    disconnect_alerted = True
                    last_state = "disconnected"
            else:
                consecutive_disconnects = 0
                if disconnect_alerted or last_state == "disconnected" or current_state != last_state:
                    ts = datetime.now().strftime("%H:%M:%S")
                    log_event("RECONNECT", f"Device re-established connection in {current_state.upper()} mode at {ts}")
                    send_telegram_message(f"[PASS] Samsung Galaxy S8 RECONNECTED at {ts}! Mode: {current_state.upper()} (Serial: {SERIAL}).")
                    disconnect_alerted = False
                    last_state = current_state

            time.sleep(POLL_INTERVAL)
        except KeyboardInterrupt:
            print("\n[*] Stopping Connection Watchdog.")
            break
        except Exception as e:
            time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()
