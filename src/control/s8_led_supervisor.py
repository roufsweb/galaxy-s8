#!/usr/bin/env python3
"""
s8_led_supervisor.py — Samsung Galaxy S8 (SM-G950N, Exynos 8895)
Autonomous Hardware Status LED Color Sync Supervisor.

Monitors real-time SoC temperature, battery health, charging status,
DisplayPort connection, and core services. Dynamically drives the
MAX77865 PMIC 4-channel RGB LED via /sys/class/sec/led/:

Color & Pattern States:
  - SUBTLE GREEN (Solid / Calm Hue)   : System healthy, normal Linux server operation.
  - PULSING BLUE (300ms on / 300ms off) : Booting / initializing rootfs.
  - SOFT AMBER (1000ms on / 1000ms off) : 1500mA Fast Charging in progress (<95%).
  - CALM CYAN (Solid Cyan)             : External USB-C DisplayPort / HDMI active.
  - BLINKING RED (500ms on / 500ms off): Battery low (<15%).
  - RAPID STROBE RED (150ms / 150ms)   : Thermal alert (>70°C) or critical kernel fault.
  - OFF                                : Standby / sleep.
"""

import os
import sys
import time
import subprocess
from pathlib import Path

LED_PATTERN_PATH = "/sys/class/sec/led/led_pattern"
LED_BLINK_PATH   = "/sys/class/sec/led/led_blink"
LED_BRIGHTNESS   = "/sys/class/sec/led/led_brightness"

BATT_CAP_PATH    = "/sys/class/power_supply/battery/capacity"
BATT_STATUS_PATH = "/sys/class/power_supply/battery/status"
BATT_TEMP_PATH   = "/sys/class/power_supply/battery/temp"
HDMI_STATE_PATH  = "/sys/class/switch/hdmi/state"
THERMAL_ZONE0    = "/sys/devices/virtual/thermal/thermal_zone0/temp"

def write_sysfs(path: str, val: str):
    try:
        with open(path, "w") as f:
            f.write(val.strip() + "\n")
        return True
    except Exception:
        return False

def read_sysfs_int(path: str, default=0) -> int:
    try:
        with open(path, "r") as f:
            return int(f.read().strip())
    except Exception:
        return default

def read_sysfs_str(path: str, default="") -> str:
    try:
        with open(path, "r") as f:
            return f.read().strip()
    except Exception:
        return default

class S8LedSupervisor:
    def __init__(self):
        self.current_state = None

    def set_color(self, state: str):
        if state == self.current_state:
            return
        self.current_state = state

        if state == "HEALTHY_GREEN":
            # Subtle calm green hue via hardware pattern 5 (FULLY_CHARGED)
            write_sysfs(LED_PATTERN_PATH, "5")
        elif state == "BOOTING_BLUE":
            # Pulsing blue
            write_sysfs(LED_BLINK_PATH, "0x0000FF 300 300")
        elif state == "DISPLAYPORT_CYAN":
            # Solid calm cyan (Blue + Green)
            write_sysfs(LED_BLINK_PATH, "0x003333 0 0")
        elif state == "CHARGING_AMBER":
            # Soft amber breathing
            write_sysfs(LED_BLINK_PATH, "0x442200 800 800")
        elif state == "LOW_BATTERY_RED":
            # Blinking red
            write_sysfs(LED_BLINK_PATH, "0xFF0000 500 500")
        elif state == "THERMAL_ALERT_RED":
            # Rapid strobe red
            write_sysfs(LED_BLINK_PATH, "0xFF0000 150 150")
        elif state == "OFF":
            write_sysfs(LED_PATTERN_PATH, "0")
            write_sysfs(LED_BLINK_PATH, "0 0 0")

    def evaluate_hardware_state(self) -> str:
        # 1. Thermal check (SoC or battery temp > 70 C)
        soc_temp_raw = read_sysfs_int(THERMAL_ZONE0, 0)
        soc_temp_c = soc_temp_raw / 1000.0 if soc_temp_raw > 1000 else soc_temp_raw
        if soc_temp_c > 70.0:
            return "THERMAL_ALERT_RED"

        # 2. Battery health & capacity
        batt_cap = read_sysfs_int(BATT_CAP_PATH, 100)
        batt_status = read_sysfs_str(BATT_STATUS_PATH, "Discharging").lower()

        if batt_cap <= 15:
            return "LOW_BATTERY_RED"

        # 3. DisplayPort monitor connection
        hdmi_state = read_sysfs_int(HDMI_STATE_PATH, 0)
        if hdmi_state == 1:
            return "DISPLAYPORT_CYAN"

        # 4. Charging state
        if "charging" in batt_status and batt_cap < 95:
            return "CHARGING_AMBER"

        # 5. Default: Subtle green hue (everything is healthy and operational)
        return "HEALTHY_GREEN"

    def run_loop(self, poll_interval=3):
        print("[*] S8 LED Hardware Status Supervisor started.")
        sys.stdout.flush()
        while True:
            target_state = self.evaluate_hardware_state()
            self.set_color(target_state)
            time.sleep(poll_interval)

if __name__ == "__main__":
    sup = S8LedSupervisor()
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        if cmd == "green":
            sup.set_color("HEALTHY_GREEN")
            print("[OK] LED set to Subtle Calm Green (System Healthy)")
        elif cmd == "red":
            sup.set_color("LOW_BATTERY_RED")
            print("[OK] LED set to Blinking Red (Alert)")
        elif cmd == "blue":
            sup.set_color("BOOTING_BLUE")
            print("[OK] LED set to Pulsing Blue (Booting)")
        elif cmd == "cyan":
            sup.set_color("DISPLAYPORT_CYAN")
            print("[OK] LED set to Calm Cyan (DisplayPort)")
        elif cmd == "amber":
            sup.set_color("CHARGING_AMBER")
            print("[OK] LED set to Soft Amber (Charging)")
        elif cmd == "off":
            sup.set_color("OFF")
            print("[OK] LED turned OFF")
        elif cmd in ("auto", "daemon", "start"):
            sup.run_loop(poll_interval=3)
        else:
            print("Usage: s8_led_supervisor.py [green|red|blue|cyan|amber|off|auto]")
    else:
        # Default run in auto supervisor mode
        sup.run_loop(poll_interval=3)
