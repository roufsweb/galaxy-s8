#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
s8ctl - Samsung Galaxy S8 (SM-G950N, Exynos 8895) Native Hardware Control Suite
Controls every hardware subsystem on the Galaxy S8:
  - 8-Core CPU (4x M2 @ 2.314 GHz + 4x A53 @ 1.69 GHz) Power Profiles & Boost
  - ARM Mali-G71 MP20 GPU DVFS & Booster Mode
  - Broadcom BCM4361 Wi-Fi (2.4 GHz & 5 GHz Scanning, Connection, GUI & Tray)
  - Broadcom BCM4361 Bluetooth 5.0 (/dev/ttySAC1 + rfkill0)
  - Rear Camera Flashlight / Torch (/sys/class/leds/torch-sec1/brightness)
  - Haptic Vibration Motor (/sys/class/timed_output/vibrator/enable)
  - MAX77865 PMIC Smart Fast Charging (1500mA input & fast charge)
  - USB-C DisplayPort / HDMI 1.2 Hotplug Daemon (exynos_dp_bridge)
  - Audio Subsystem (Cirrus Logic CS47L92, MAX98506 Speaker, DisplayPort Audio)
"""
import os
import shutil
import sys
import time
import subprocess

S8CTL_VERSION = "1.0.3"


def read_sysfs(path, default="N/A"):
    try:
        with open(path, "r") as f:
            return f.read().strip()
    except Exception:
        return default

def write_sysfs(path, val):
    try:
        with open(path, "w") as f:
            f.write(str(val))
        return True
    except Exception as e:
        print(f"[!] Failed to write {val} to {path}: {e}")
        return False

# ==============================================================================
# CPU & GPU POWER / BOOST MANAGEMENT
# ==============================================================================
def cpu_status():
    print("=== Exynos 8895 Octa-Core CPU Status ===")
    for i in range(8):
        cluster = "LITTLE (A53)" if i < 4 else "BIG (M2)"
        on = read_sysfs(f"/sys/devices/system/cpu/cpu{i}/online", "1" if i == 0 else "0")
        if on == "1":
            cur = int(read_sysfs(f"/sys/devices/system/cpu/cpu{i}/cpufreq/scaling_cur_freq", "0")) // 1000
            gov = read_sysfs(f"/sys/devices/system/cpu/cpu{i}/cpufreq/scaling_governor", "unknown")
            print(f"  CPU{i} [{cluster:<12}]: ONLINE  |  {cur:>4} MHz  |  Governor: {gov}")
        else:
            print(f"  CPU{i} [{cluster:<12}]: OFFLINE (Parked)")

def cpu_boost():
    print("[*] Engaging Full Octa-Core High-Performance BOOST Mode...")
    # 1. Bring all 8 cores online (only write if currently offline to avoid Exynos cpuhp EPERM)
    for i in range(1, 8):
        if read_sysfs(f"/sys/devices/system/cpu/cpu{i}/online", "1") != "1":
            write_sysfs(f"/sys/devices/system/cpu/cpu{i}/online", "1")
    # 2. Set performance governor & max frequency
    # Little cluster (0-3) -> 1.69 GHz
    write_sysfs("/sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq", "1690000")
    write_sysfs("/sys/devices/system/cpu/cpu0/cpufreq/scaling_min_freq", "1690000")
    write_sysfs("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor", "performance")
    # Big cluster (4-7) -> 2.314 GHz
    write_sysfs("/sys/devices/system/cpu/cpu4/cpufreq/scaling_max_freq", "2314000")
    write_sysfs("/sys/devices/system/cpu/cpu4/cpufreq/scaling_min_freq", "2314000")
    write_sysfs("/sys/devices/system/cpu/cpu4/cpufreq/scaling_governor", "performance")
    print("[+] All 4x M2 cores locked at 2.314 GHz, 4x A53 cores locked at 1.690 GHz!")

def _apply_interactive_tuning():
    """Apply cool-idle Exynos 8895 interactive governor parameters."""
    tunables = {
        "/sys/devices/system/cpu/cpu0/cpufreq/interactive/hispeed_freq": "832000",
        "/sys/devices/system/cpu/cpu0/cpufreq/interactive/go_hispeed_load": "90",
        "/sys/devices/system/cpu/cpu0/cpufreq/interactive/target_loads": "75 832000:88 1053000:95 1456000:98",
        "/sys/devices/system/cpu/cpu0/cpufreq/interactive/above_hispeed_delay": "20000 1053000:40000 1456000:80000",
        "/sys/devices/system/cpu/cpu0/cpufreq/interactive/timer_rate": "30000",
        "/sys/devices/system/cpu/cpu4/cpufreq/interactive/hispeed_freq": "1066000",
        "/sys/devices/system/cpu/cpu4/cpufreq/interactive/go_hispeed_load": "90",
        "/sys/devices/system/cpu/cpu4/cpufreq/interactive/target_loads": "80 1066000:90 1469000:96 1937000:99",
        "/sys/devices/system/cpu/cpu4/cpufreq/interactive/above_hispeed_delay": "20000 1469000:50000 1937000:100000",
        "/sys/devices/system/cpu/cpu4/cpufreq/interactive/timer_rate": "30000",
    }
    for path, val in tunables.items():
        if os.path.exists(path):
            write_sysfs(path, val)

def cpu_normal():
    print("[*] Switching CPU to Cool Balanced Dynamic Scaling (Interactive Governor)...")
    for i in range(1, 8):
        if read_sysfs(f"/sys/devices/system/cpu/cpu{i}/online", "1") != "1":
            write_sysfs(f"/sys/devices/system/cpu/cpu{i}/online", "1")
    write_sysfs("/sys/devices/system/cpu/cpu0/cpufreq/scaling_min_freq", "455000")
    write_sysfs("/sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq", "1690000")
    write_sysfs("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor", "interactive")
    write_sysfs("/sys/devices/system/cpu/cpu4/cpufreq/scaling_min_freq", "741000")
    write_sysfs("/sys/devices/system/cpu/cpu4/cpufreq/scaling_max_freq", "2314000")
    write_sysfs("/sys/devices/system/cpu/cpu4/cpufreq/scaling_governor", "interactive")
    _apply_interactive_tuning()
    print("[+] Balanced dynamic scaling active (455MHz - 2.314GHz, cool-idle tuned).")

def cpu_powersave():
    print("[*] Engaging Battery Power-Saver / Cool-Idle Profile...")
    write_sysfs("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor", "interactive")
    write_sysfs("/sys/devices/system/cpu/cpu4/cpufreq/scaling_governor", "interactive")
    _apply_interactive_tuning()
    # Cap Little to 949 MHz, Big to 1066 MHz and park 2 big cores
    write_sysfs("/sys/devices/system/cpu/cpu0/cpufreq/scaling_min_freq", "455000")
    write_sysfs("/sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq", "949000")
    write_sysfs("/sys/devices/system/cpu/cpu4/cpufreq/scaling_min_freq", "741000")
    write_sysfs("/sys/devices/system/cpu/cpu4/cpufreq/scaling_max_freq", "1066000")
    write_sysfs("/sys/devices/system/cpu/cpu6/online", "0")
    write_sysfs("/sys/devices/system/cpu/cpu7/online", "0")
    print("[+] Power-saver active: Cores 6-7 parked, A53<=949MHz, M2<=1.06GHz.")

def gpu_boost():
    write_sysfs("/sys/devices/platform/13900000.mali/dvfs_governor", "Booster")
    write_sysfs("/sys/devices/platform/13900000.mali/dvfs_min_lock", "546000")
    print("[+] ARM Mali-G71 MP20 GPU Boosted: Governor=Booster, Clock=546 MHz")

def gpu_normal():
    write_sysfs("/sys/devices/platform/13900000.mali/dvfs_min_lock", "-1")
    write_sysfs("/sys/devices/platform/13900000.mali/dvfs_governor", "Interactive")
    print("[+] ARM Mali-G71 MP20 GPU reset to Interactive DVFS (260 - 546 MHz)")

# ==============================================================================
# WI-FI MANAGEMENT (2.4 GHz & 5 GHz)
# ==============================================================================
def wifi_status():
    import s8_wifi
    s = s8_wifi.get_wifi_status()
    print("=== Broadcom BCM4361 Wi-Fi Status ===")
    if s["connected"]:
        print(f"  Connected to : {s['ssid']}")
        print(f"  IP Address   : {s['ip']}")
        print(f"  Frequency    : {s['freq']} MHz ({s['band']})")
        print(f"  Signal Level : {s['signal']} dBm")
        print(f"  Security     : {s['security']}")
    else:
        print("  Status       : DISCONNECTED")

def wifi_scan():
    import s8_wifi
    print("[*] Scanning 2.4 GHz & 5 GHz networks...")
    nets = s8_wifi.scan_networks()
    print(f"=== Detected {len(nets)} Networks ===")
    for n in nets:
        active = " [*CONNECTED*]" if n["connected"] else ""
        print(f"  [{n['band']:>7}] {n['ssid']:<24} {n['signal']:>4} dBm  ({n['security']}){active}")

def wifi_connect(ssid, password=None):
    import s8_wifi
    print(f"[*] Associating with '{ssid}'...")
    ok, msg = s8_wifi.connect_network(ssid, password)
    if ok:
        print(f"[+] Success: {msg}")
        vibrate(150)
    else:
        print(f"[!] Failed: {msg}")

def wifi_disconnect():
    import s8_wifi
    s8_wifi.disconnect_wifi()
    print("[+] Wi-Fi disconnected.")

# ==============================================================================
# AUDIO ROUTING & TESTING
# ==============================================================================
def amixer_set(ctl, val):
    subprocess.run(["amixer", "-c", "0", "cset", f"name='{ctl}'", str(val)],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def set_audio_route(mode="speaker"):
    amixer_set("ABOX Sampling Rate Mixer", "48000")
    amixer_set("ABOX Sampling Rate Out1", "48000")

    if mode == "speaker":
        amixer_set("ABOX SPUS IN0", "RDMA")
        amixer_set("ABOX SPUS OUT0", "SIFS1")
        amixer_set("ABOX SIFS1", "SPUS OUT0")
        amixer_set("ABOX UAIF SPK4", "SIFS1")
        amixer_set("SPK out", "Enable")
        amixer_set("SPK Enable Switch", "Enable")
        amixer_set("Speaker Gain", "25")
        print("[+] Audio routed to Galaxy S8 Bottom Speaker (MAX98506 + ABOX UAIF4)")
    elif mode in ("mic", "record"):
        amixer_set("ABOX NSRC0", "UAIF0")
        amixer_set("ABOX SPUM ASRC1", "Off")
        amixer_set("ABOX SIFM0", "WDMA")
        amixer_set("DMIC1 Switch", "1")
        amixer_set("LHPF1 Input 1", "IN3L")
        amixer_set("ASRC1IN1L Input 1", "LHPF1")
        amixer_set("AIF1TX1 Input 1", "ASRC1IN1L")
        amixer_set("AIF1TX2 Input 1", "ASRC1IN1L")
        amixer_set("IN3L Digital Volume", "140")
        print("[+] Audio capture routed to Galaxy S8 Digital Mic 1 (DMIC1 + CS47L92 -> hw:0,9)")
    elif mode in ("headphone", "headset", "3.5mm"):
        amixer_set("ABOX SPUS OUT0", "SIFS0")
        amixer_set("ABOX UAIF SPK0", "SIFS0")
        amixer_set("HPOUT2 Digital Switch", "1")
        amixer_set("HPOUT2 DRE Switch", "1")
        amixer_set("HPOUT2 EDRE Switch", "1")
        amixer_set("HPOUT2L Input 1", "AIF1RX1")
        amixer_set("HPOUT2R Input 1", "AIF1RX2")
        print("[+] Audio routed to 3.5mm Hi-Fi Headphone DAC (Cirrus Logic CS47L92)")
    elif mode in ("hdmi", "dp"):
        print("[+] Audio routed to USB-C DisplayPort / HDMI Audio (ALSA hw:0,22 / pcmC0D22p)")

def audio_test():
    print("[*] Playing verified 440 Hz acoustic chime via ALSA default...")
    set_audio_route("speaker")
    cmd = "aplay /tmp/test_sine.wav >/dev/null 2>&1"
    subprocess.run(cmd, shell=True)

# ==============================================================================
# HARDWARE PERIPHERALS: BLUETOOTH, TORCH, HAPTICS, CHARGER
# ==============================================================================
def set_bluetooth(state="on"):
    if state == "on":
        write_sysfs("/sys/class/rfkill/rfkill0/state", "1")
        os.makedirs("/etc/firmware", exist_ok=True)
        os.makedirs("/lib/firmware/brcm", exist_ok=True)
        for src in ("/vendor/firmware/bcm4361B0_semco.hcd", "/system/vendor/firmware/bcm4361B0_semco.hcd"):
            if os.path.exists(src):
                for dst in ("/etc/firmware/BCM4361B0.hcd", "/lib/firmware/brcm/BCM4361B0.hcd"):
                    if not os.path.exists(dst):
                        try:
                            os.symlink(src, dst)
                        except Exception:
                            pass
                break
        print("[+] Broadcom BCM4361 Bluetooth 5.0 radio unblocked (/dev/ttySAC1 + rfkill0)")
    else:
        write_sysfs("/sys/class/rfkill/rfkill0/state", "0")
        print("[+] Bluetooth radio blocked.")

def set_torch(level):
    level = max(0, min(5, int(level)))
    write_sysfs("/sys/class/leds/torch-sec1/brightness", level)
    print(f"[+] Rear Flashlight / Torch set to level {level}/5")

def vibrate(ms=150):
    write_sysfs("/sys/class/timed_output/vibrator/enable", int(ms))
    print(f"[+] Haptic pulse: {ms} ms")

def boost_battery():
    write_sysfs("/sys/class/power_supply/max77865-charger/data", "0xBD 0x6C")
    write_sysfs("/sys/class/power_supply/max77865-charger/data", "0xC3 0x61")
    write_sysfs("/sys/class/power_supply/max77865-charger/data", "0xC0 0x3C")
    write_sysfs("/sys/class/power_supply/max77865-charger/data", "0xB9 0x9E")
    write_sysfs("/sys/class/power_supply/max77865-charger/data", "0xB7 0x05")
    for tune in ("/sys/class/power_supply/battery/batt_tune_input_charge_current", "/sys/class/power_supply/battery/batt_tune_fast_charge_current"):
        try:
            with open(tune, "w") as f:
                f.write("1500")
        except Exception:
            pass
    print("[+] MAX77865 PMIC Charger unlocked (1500mA input & fast charge)")

def get_status():
    cap = read_sysfs("/sys/class/power_supply/battery/capacity")
    status = read_sysfs("/sys/class/power_supply/battery/status")
    health = read_sysfs("/sys/class/power_supply/battery/health")
    vnow = int(read_sysfs("/sys/class/power_supply/battery/voltage_now", "0")) / 1e6
    inow = read_sysfs("/sys/class/power_supply/battery/current_now", "0")
    btemp = int(read_sysfs("/sys/class/power_supply/battery/temp", "0")) / 10.0

    c0_freq = int(read_sysfs("/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq", "0")) // 1000
    c4_freq = int(read_sysfs("/sys/devices/system/cpu/cpu4/cpufreq/scaling_cur_freq", "0")) // 1000
    tz0 = int(read_sysfs("/sys/class/thermal/thermal_zone0/temp", "0")) / 1000.0
    gpu_clk = read_sysfs("/sys/devices/platform/13900000.mali/clock", "N/A")
    gpu_load = read_sysfs("/sys/devices/platform/13900000.mali/utilization", "0")

    dp_mon = read_sysfs("/sys/class/dp_sec/monitor_info", "Disconnected").replace("\n", " ")
    bt_state = "ON" if read_sysfs("/sys/class/rfkill/rfkill0/state", "0") == "1" else "OFF"

    sd_status = "NOT DETECTED (Slot empty)"
    if os.path.exists("/dev/mmcblk0") or os.path.exists("/dev/block/mmcblk0"):
        if os.path.ismount("/media/sdcard"):
            try:
                usage = shutil.disk_usage("/media/sdcard")
                total_gb = usage.total / (1024**3)
                free_gb = usage.free / (1024**3)
                sd_status = f"MOUNTED ({total_gb:.1f}G total, {free_gb:.1f}G available) @ /media/sdcard"
            except Exception:
                sd_status = "MOUNTED @ /media/sdcard"
        else:
            sd_status = "DETECTED (/dev/mmcblk0, not mounted)"

    print("=================================================================")
    print(f"  Samsung Galaxy S8 Native Linux Platform [s8ctl v{S8CTL_VERSION}]")
    print("=================================================================")
    print(f"  CPU (Exynos 8895) : 4xA53 @ {c0_freq} MHz | 4xM2 @ {c4_freq} MHz")
    print(f"  SoC Temperature   : {tz0:.1f} C")
    print(f"  GPU (Mali-G71)    : {gpu_clk} MHz (Load: {gpu_load}%)")
    print(f"  Battery (MAX77865): {cap}% ({status}, Health: {health}) | {vnow:.3f}V | {inow} mA | {btemp:.1f} C")
    print(f"  MicroSD Card      : {sd_status}")
    print(f"  USB-C DisplayPort : Monitor={dp_mon}")
    print(f"  Bluetooth 5.0     : {bt_state} (Broadcom BCM4361)")
    print("=================================================================")

def main():
    if len(sys.argv) < 2 or sys.argv[1] == "status":
        get_status()
        return

    cmd = sys.argv[1].lower()
    if cmd == "cpu":
        sub = sys.argv[2].lower() if len(sys.argv) > 2 else "status"
        if sub == "boost":
            cpu_boost()
        elif sub in ("normal", "balanced", "cool"):
            cpu_normal()
        elif sub == "powersave":
            cpu_powersave()
        else:
            cpu_status()
    elif cmd == "gpu":
        sub = sys.argv[2].lower() if len(sys.argv) > 2 else "boost"
        if sub == "boost":
            gpu_boost()
        else:
            gpu_normal()
    elif cmd == "wifi":
        sub = sys.argv[2].lower() if len(sys.argv) > 2 else "status"
        if sub == "scan":
            wifi_scan()
        elif sub == "connect":
            ssid = sys.argv[3] if len(sys.argv) > 3 else ""
            pwd = sys.argv[4] if len(sys.argv) > 4 else None
            if ssid:
                wifi_connect(ssid, pwd)
            else:
                print("Usage: s8ctl wifi connect <SSID> [password]")
        elif sub == "disconnect":
            wifi_disconnect()
        elif sub == "gui":
            subprocess.Popen(["/usr/local/bin/s8-wifi-gui"], env=dict(os.environ, DISPLAY=":1"))
        else:
            wifi_status()
    elif cmd == "torch":
        val = sys.argv[2].lower() if len(sys.argv) > 2 else "1"
        if val == "on":
            set_torch(3)
        elif val == "off":
            set_torch(0)
        else:
            set_torch(int(val))
    elif cmd == "vibrate":
        ms = int(sys.argv[2]) if len(sys.argv) > 2 else 150
        vibrate(ms)
    elif cmd == "battery":
        sub = sys.argv[2].lower() if len(sys.argv) > 2 else "status"
        if sub == "boost":
            boost_battery()
        get_status()
    elif cmd == "audio":
        sub = sys.argv[2].lower() if len(sys.argv) > 2 else "speaker"
        if sub == "test":
            audio_test()
        else:
            set_audio_route(sub)
    elif cmd == "bt":
        sub = sys.argv[2].lower() if len(sys.argv) > 2 else "on"
        set_bluetooth(sub)
    elif cmd == "sdcard":
        sd_dev = "/dev/mmcblk0" if os.path.exists("/dev/mmcblk0") else "/dev/block/mmcblk0"
        if os.path.exists(sd_dev):
            print("=== MicroSD Storage Hardware Info ===")
            subprocess.run(["blkid", sd_dev])
            subprocess.run(["df", "-h", "/media/sdcard"])
            print("\n--- Root Contents (/media/sdcard) ---")
            subprocess.run(["ls", "-lh", "/media/sdcard"])
        else:
            print("[!] MicroSD slot is empty.")
    elif cmd in ("display", "screen", "orientation"):
        sub = sys.argv[2].lower() if len(sys.argv) > 2 else "status"
        if sub in ("landscape", "normal", "0"):
            with open("/tmp/s8_dp_orientation", "w") as f:
                f.write("0\n")
            print("[+] Display orientation switched to: LANDSCAPE (0 deg, 1920x1080 16:9)")
        elif sub in ("portrait", "90"):
            with open("/tmp/s8_dp_orientation", "w") as f:
                f.write("90\n")
            print("[+] Display orientation switched to: PORTRAIT (90 deg, 1080x1920 upright)")
        elif sub in ("inverted-landscape", "180"):
            with open("/tmp/s8_dp_orientation", "w") as f:
                f.write("180\n")
            print("[+] Display orientation switched to: INVERTED LANDSCAPE (180 deg)")
        elif sub in ("inverted-portrait", "270"):
            with open("/tmp/s8_dp_orientation", "w") as f:
                f.write("270\n")
            print("[+] Display orientation switched to: INVERTED PORTRAIT (270 deg)")
        else:
            cur_rot = read_sysfs("/tmp/s8_dp_orientation", "0")
            mode_name = "PORTRAIT (90 deg)" if cur_rot == "90" else "LANDSCAPE (0 deg)"
            print("=== USB-C DisplayPort Orientation ===")
            print(f"  Current Rotation : {mode_name}")
            print(f"  Available Modes  : landscape (0), portrait (90), inverted-landscape (180), inverted-portrait (270)")
            print(f"  Usage            : s8ctl display [landscape | portrait]")
    elif cmd in ("version", "--version", "-v"):
        ap_ver = read_sysfs("/etc/s8-ap-version", "3.0.0")
        kver = os.uname().release
        print(f"s8ctl v{S8CTL_VERSION} (galaxy-s8-hw v{S8CTL_VERSION}, AP v{ap_ver}, Kernel {kver})")
    else:
        get_status()

if __name__ == "__main__":
    main()
