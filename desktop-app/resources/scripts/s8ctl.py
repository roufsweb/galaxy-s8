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
import sys
import time
import subprocess
import json

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
    # 1. Bring all 8 cores online
    for i in range(1, 8):
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

def cpu_normal():
    print("[*] Switching CPU to Balanced Dynamic Scaling (Interactive Governor)...")
    for i in range(1, 8):
        write_sysfs(f"/sys/devices/system/cpu/cpu{i}/online", "1")
    write_sysfs("/sys/devices/system/cpu/cpu0/cpufreq/scaling_min_freq", "455000")
    write_sysfs("/sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq", "1690000")
    write_sysfs("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor", "interactive")
    write_sysfs("/sys/devices/system/cpu/cpu4/cpufreq/scaling_min_freq", "741000")
    write_sysfs("/sys/devices/system/cpu/cpu4/cpufreq/scaling_max_freq", "2314000")
    write_sysfs("/sys/devices/system/cpu/cpu4/cpufreq/scaling_governor", "interactive")
    print("[+] Dynamic frequency scaling active (455MHz - 2.314GHz).")

def cpu_powersave():
    print("[*] Engaging Battery Power-Saver Profile...")
    # Cap Little to 832 MHz, Big to 741 MHz and park 2 big cores
    write_sysfs("/sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq", "832000")
    write_sysfs("/sys/devices/system/cpu/cpu4/cpufreq/scaling_max_freq", "741000")
    write_sysfs("/sys/devices/system/cpu/cpu6/online", "0")
    write_sysfs("/sys/devices/system/cpu/cpu7/online", "0")
    print("[+] Power-saver active: Cores 6-7 parked, frequencies capped.")

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
    write_sysfs("/sys/class/power_supply/battery/batt_tune_input_charge_current", "1500")
    write_sysfs("/sys/class/power_supply/battery/batt_tune_fast_charge_current", "1500")
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
    typec_drole = read_sysfs("/sys/class/typec/port0/data_role", "unknown")
    usb_mode = read_sysfs("/sys/class/host_notify/usb_otg/mode", "unknown")

    sd_status = "NOT DETECTED (Slot empty)"
    if os.path.exists("/dev/block/mmcblk0"):
        if os.path.ismount("/media/sdcard"):
            try:
                usage = shutil.disk_usage("/media/sdcard")
                total_gb = usage.total / (1024**3)
                free_gb = usage.free / (1024**3)
                sd_status = f"MOUNTED ({total_gb:.1f}G total, {free_gb:.1f}G available) @ /media/sdcard"
            except Exception:
                sd_status = "MOUNTED @ /media/sdcard"
        else:
            sd_status = "DETECTED (/dev/block/mmcblk0, not mounted)"

    print("=================================================================")
    print("  Samsung Galaxy S8 Native Ubuntu Linux Platform [roufsweb]")
    print("=================================================================")
    print(f"  CPU (Exynos 8895) : 4xA53 @ {c0_freq} MHz | 4xM2 @ {c4_freq} MHz")
    print(f"  SoC Temperature   : {tz0:.1f} C")
    print(f"  GPU (Mali-G71)    : {gpu_clk} MHz (Load: {gpu_load}%)")
    print(f"  Battery (MAX77865): {cap}% ({status}, Health: {health}) | {vnow:.3f}V | {inow} mA | {btemp:.1f} C")
    print(f"  MicroSD Card      : {sd_status}")
    print(f"  USB-C DisplayPort : Monitor={dp_mon}")
    print(f"  USB Type-C Role   : {typec_drole} (OTG: {usb_mode})")
    print(f"  Bluetooth 5.0     : {bt_state} (Broadcom BCM4361)")
    print("=================================================================")

def typec_status():
    ptype = read_sysfs("/sys/class/typec/port0/port_type")
    drole = read_sysfs("/sys/class/typec/port0/data_role")
    prole = read_sysfs("/sys/class/typec/port0/power_role")
    omode = read_sysfs("/sys/class/host_notify/usb_otg/mode")
    cstate = read_sysfs("/sys/class/sec/ccic/state")
    partner = "ATTACHED" if os.path.exists("/sys/class/typec/port0/port0-partner") else "NONE"
    print("=== USB Type-C Port 0 Hardware Status ===")
    print(f"  Partner Connected : {partner}")
    print(f"  Port Type         : {ptype}")
    print(f"  Data Role         : {drole}")
    print(f"  Power Role        : {prole}")
    print(f"  USB OTG Mode      : {omode}")
    print(f"  CCIC State        : {cstate}")

def set_typec_role(role):
    if role in ["host", "otg"]:
        print("[*] Switching USB Type-C to HOST mode (DFP + 5V VBUS Booster)...")
        write_sysfs("/sys/class/host_notify/usb_otg/booster", "ON")
        write_sysfs("/sys/class/host_notify/usb_otg/mode", "HOST")
        write_sysfs("/sys/class/typec/port0/data_role", "host")
        write_sysfs("/sys/class/typec/port0/port_type", "source")
        write_sysfs("/sys/class/sec/ccic/role_swap", "1")
        print("[+] USB Host (XHCI) + 5V VBUS activated. Connected keyboard, mouse, and USB devices enabled.")
    elif role in ["device", "pc", "slave"]:
        print("[*] Switching USB Type-C to DEVICE mode (UFP / PC ADB)...")
        write_sysfs("/sys/class/host_notify/usb_otg/booster", "OFF")
        write_sysfs("/sys/class/host_notify/usb_otg/mode", "NONE")
        write_sysfs("/sys/class/typec/port0/data_role", "device")
        write_sysfs("/sys/class/typec/port0/port_type", "dual")
        print("[+] USB Device mode restored for PC ADB connection.")
    else:
        typec_status()

def dock_status():
    hdmi = read_sysfs("/sys/class/switch/hdmi/state", "0")
    mon = read_sysfs("/sys/class/dp_sec/monitor_info", "None").replace("\n", " ")
    omode = read_sysfs("/sys/class/host_notify/usb_otg/mode")
    drole = read_sysfs("/sys/class/typec/port0/data_role")
    booster = read_sysfs("/sys/class/host_notify/usb_otg/booster", "OFF")
    print("=== USB-C Multi-Function Dock & Display Status ===")
    print(f"  DisplayPort HPD   : {'CONNECTED (State 1)' if hdmi == '1' else 'DISCONNECTED (State 0)'}")
    print(f"  Monitor Info      : {mon}")
    print(f"  USB Data Role     : {drole} (OTG: {omode}, 5V Booster: {booster})")
    inputs = []
    if os.path.exists("/dev/input"):
        for ev in sorted(os.listdir("/dev/input")):
            if ev.startswith("event"):
                try:
                    with open(f"/sys/class/input/{ev}/device/name", "r") as f:
                        name = f.read().strip()
                        if not any(k in name.lower() for k in ["ssp", "hrm", "hall", "gpio"]):
                            inputs.append(f"{ev}: {name}")
                except Exception:
                    pass
    print(f"  Active USB Inputs : {len(inputs)} detected")
    for inp in inputs:
        print(f"    * {inp}")

def dock_activate():
    print("[*] Engaging USB-C Multi-Function Hub & Display Alt-Mode...")
    write_sysfs("/sys/class/host_notify/usb_otg/booster", "ON")
    write_sysfs("/sys/class/host_notify/usb_otg/mode", "HOST")
    write_sysfs("/sys/class/typec/port0/data_role", "host")
    write_sysfs("/sys/class/typec/port0/port_type", "source")
    write_sysfs("/sys/class/sec/ccic/role_swap", "1")
    time.sleep(0.1)

    print("[*] Aligning SBU switch (normal orientation) and training 2-lane DP link...")
    write_sysfs("/sys/class/dp_sec/dp_sbu_sw_sel", "0 0")
    write_sysfs("/sys/class/dp_sec/link", "22")
    time.sleep(0.3)

    if read_sysfs("/sys/class/switch/hdmi/state", "0") == "0":
        print("[*] Polarity inverted: trying flipped orientation...")
        write_sysfs("/sys/class/dp_sec/dp_sbu_sw_sel", "1 0")
        write_sysfs("/sys/class/dp_sec/link", "22")
        time.sleep(0.3)

    if read_sysfs("/sys/class/switch/hdmi/state", "0") == "0":
        print("[*] Multiport 2-lane fell through: trying 4-lane link training...")
        write_sysfs("/sys/class/dp_sec/dp_sbu_sw_sel", "0 0")
        write_sysfs("/sys/class/dp_sec/link", "24")
        time.sleep(0.3)
        if read_sysfs("/sys/class/switch/hdmi/state", "0") == "0":
            write_sysfs("/sys/class/dp_sec/dp_sbu_sw_sel", "1 0")
            write_sysfs("/sys/class/dp_sec/link", "24")
            time.sleep(0.3)

    hdmi_final = read_sysfs("/sys/class/switch/hdmi/state", "0")
    if hdmi_final == "1":
        print("[+] DisplayPort link established (1080p60 active)!")
        vibrate(150)
        time.sleep(0.1)
        vibrate(150)
        # Ensure exynos_dp_bridge is running
        try:
            subprocess.check_output(["pgrep", "-x", "exynos_dp_bridge"])
        except subprocess.CalledProcessError:
            if os.path.exists("/usr/local/bin/exynos_dp_bridge"):
                subprocess.Popen(["/usr/local/bin/exynos_dp_bridge"],
                                 stdout=open("/var/log/exynos_dp_bridge.log", "a"),
                                 stderr=subprocess.STDOUT)
    else:
        print("[!] DisplayPort monitor not detected yet. USB Host mode remains active.")
    dock_status()

def dock_deactivate():
    print("[*] Disconnecting DisplayPort & releasing dock...")
    write_sysfs("/sys/class/dp_sec/link", "0")
    write_sysfs("/sys/class/dp_sec/dp_test", "1,0")
    write_sysfs("/sys/class/host_notify/usb_otg/booster", "OFF")
    write_sysfs("/sys/class/host_notify/usb_otg/mode", "NONE")
    write_sysfs("/sys/class/typec/port0/data_role", "device")
    write_sysfs("/sys/class/typec/port0/port_type", "dual")
    print("[+] DisplayPort deactivated; returned to default PC device mode.")


# ==============================================================================
# HARDWARE SENSORS & SYSTEM TELEMETRY
# ==============================================================================
def get_sensors_snapshot():
    thermals = {}
    for i in range(6):
        t_type = read_sysfs(f"/sys/class/thermal/thermal_zone{i}/type")
        t_val = read_sysfs(f"/sys/class/thermal/thermal_zone{i}/temp")
        if t_type != "N/A" and t_val != "N/A":
            try:
                thermals[t_type] = round(float(t_val) / 1000.0, 1)
            except Exception:
                thermals[t_type] = t_val

    calib = {}
    ap_t = read_sysfs("/sys/devices/virtual/sec/sec-ap-thermistor/temperature")
    ap_adc = read_sysfs("/sys/devices/virtual/sec/sec-ap-thermistor/temp_adc")
    if ap_t != "N/A":
        try:
            calib["ap_board_celsius"] = round(float(ap_t) / 10.0, 1)
            calib["ap_board_raw_adc"] = int(ap_adc)
        except Exception:
            pass

    pa_t = read_sysfs("/sys/devices/virtual/sec/sec-pa-thermistor/temperature")
    pa_adc = read_sysfs("/sys/devices/virtual/sec/sec-pa-thermistor/temp_adc")
    if pa_t != "N/A":
        try:
            calib["rf_pa_celsius"] = round(float(pa_t) / 10.0, 1)
            calib["rf_pa_raw_adc"] = int(pa_adc)
        except Exception:
            pass

    adc_channels = {
        0: ("ap_temp_ntc", "AP SoC Board Thermistor"),
        1: ("bat_temp_ntc", "Battery Pack NTC Thermistor"),
        3: ("chg_temp_ntc", "Charger IC NTC Thermistor"),
        4: ("wpc_temp_ntc", "Wireless Charger / VBUS Sense"),
        8: ("audio_sense", "Audio Jack / Accessory Sense"),
        10: ("pa_temp_ntc", "Power Amplifier Thermistor"),
        11: ("bat_sense_volt", "Battery Pack Sense Line")
    }
    adc_readings = {}
    for ch, (k, desc) in adc_channels.items():
        raw = read_sysfs(f"/sys/bus/iio/devices/iio:device0/in_voltage{ch}_raw")
        if raw != "N/A":
            try:
                cnt = int(raw)
                mv = round((cnt / 4095.0) * 1800.0, 1)
                adc_readings[k] = {"channel": ch, "description": desc, "raw": cnt, "mv": mv}
            except Exception:
                pass

    bat_v = int(read_sysfs("/sys/class/power_supply/battery/voltage_now", "0")) // 1000
    bat_c = int(read_sysfs("/sys/class/power_supply/battery/current_now", "0"))
    bat_cap = int(read_sysfs("/sys/class/power_supply/battery/capacity", "0"))
    bat_st = read_sysfs("/sys/class/power_supply/battery/status")
    bat_hl = read_sysfs("/sys/class/power_supply/battery/health")

    hrm_id = read_sysfs("/sys/class/sensors/hrm_sensor/device_id")
    hrm_ver = read_sysfs("/sys/class/sensors/hrm_sensor/hrm_version")
    hrm_ppg = read_sysfs("/sys/class/sensors/hrm_sensor/curr_adc")

    mcu_name = read_sysfs("/sys/class/sensors/ssp_sensor/mcu_name")
    mcu_rev = read_sysfs("/sys/class/sensors/ssp_sensor/mcu_rev")
    mcu_pwr = read_sysfs("/sys/class/sec/sensorhub/mcu_power")
    ssp_enable = read_sysfs("/sys/class/sensors/ssp_sensor/enable")

    return {
        "timestamp": time.time(),
        "timestamp_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "device": "Samsung Galaxy S8 (SM-G950N)",
        "platform": "Exynos 8895",
        "thermals": thermals,
        "calibrated_thermistors": calib,
        "adc_channels": adc_readings,
        "battery": {
            "voltage_mv": bat_v,
            "current_ma": bat_c,
            "capacity_pct": bat_cap,
            "status": bat_st,
            "health": bat_hl
        },
        "hrm": {
            "device": "Maxim MAX86907E",
            "device_id": hrm_id,
            "version": hrm_ver,
            "ppg": hrm_ppg
        },
        "sensorhub": {
            "mcu": mcu_name,
            "revision": mcu_rev,
            "regulator_pwr": mcu_pwr == "1",
            "enable_mask": ssp_enable
        }
    }

def sensors_status():
    snap = get_sensors_snapshot()
    print("=================================================================")
    print("  Samsung Galaxy S8 (Exynos 8895) Live Hardware Sensors")
    print("=================================================================")
    th = snap.get("thermals", {})
    print(" [1] Silicon Thermal Zones (Exynos 8895 TMU):")
    print(f"     M2 High-Performance Big Cores : {th.get('mngs-thermal', 'N/A')} °C")
    print(f"     A53 High-Efficiency Little Cores: {th.get('APOLLO', 'N/A')} °C")
    print(f"     Mali-G71 MP20 GPU Cores       : {th.get('GPU', 'N/A')} °C")
    print(f"     Image Signal Processor (ISP)  : {th.get('ISP', 'N/A')} °C")
    print(f"     Motherboard Ambient (ac)      : {th.get('ac', 'N/A')} °C")

    cal = snap.get("calibrated_thermistors", {})
    if cal:
        print("\n [2] Calibrated NTC Thermistors (Sub-Degree Precision):")
        if "ap_board_celsius" in cal:
            print(f"     AP Board Surface Thermistor   : {cal['ap_board_celsius']} °C (Raw ADC: {cal.get('ap_board_raw_adc')})")
        if "rf_pa_celsius" in cal:
            print(f"     RF Power Amplifier Thermistor : {cal['rf_pa_celsius']} °C (Raw ADC: {cal.get('rf_pa_raw_adc')})")

    adc = snap.get("adc_channels", {})
    if adc:
        print("\n [3] Hardware ADC Channels (12-Bit / 15b70000.adc):")
        for k, v in adc.items():
            print(f"     CH{v['channel']:<2} [{v['description']:<30}]: {v['raw']:>4} counts | {v['mv']:>6.1f} mV")

    b = snap.get("battery", {})
    print("\n [4] Power & MAX77865 PMIC Battery Fuel Gauge:")
    print(f"     State of Charge : {b.get('capacity_pct')}% ({b.get('status')}) | Health: {b.get('health')}")
    print(f"     Terminal Voltage: {b.get('voltage_mv')} mV ({b.get('voltage_mv', 0)/1000.0:.3f} V)")
    print(f"     Real-Time Flow  : {b.get('current_ma')} mA")

    hrm = snap.get("hrm", {})
    print("\n [5] Optical Heart Rate & SpO2 PPG (Maxim MAX86907E):")
    print(f"     Hardware Chip   : {hrm.get('device')} (ID: {hrm.get('device_id')}, Rev: {hrm.get('version')})")
    print(f"     Optical PPG Raw : {hrm.get('ppg')}")

    sh = snap.get("sensorhub", {})
    print("\n [6] Broadcom Sensorhub MCU (BCM4774):")
    print(f"     MCU Chip Model  : {sh.get('mcu')} (Firmware: {sh.get('revision')})")
    pwr_str = "ENABLED (1.8V Active)" if sh.get('regulator_pwr') else "STANDBY"
    print(f"     VDD_MCU_1P8 Reg : {pwr_str} | Mask: {sh.get('enable_mask')}")
    print("=================================================================")

def sensors_json():
    snap = get_sensors_snapshot()
    print(json.dumps(snap, indent=2))

def sensors_watch():
    print("[*] Starting continuous sensor monitoring (Ctrl+C to exit)...")
    try:
        while True:
            os.system("clear")
            sensors_status()
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\n[+] Monitoring stopped.")

def sensors_hrm_live():
    print("[*] Maxim MAX86907E Optical Heart Rate PPG Stream:")
    print("    Place finger gently over rear heart rate sensor window...")
    base = "/sys/class/sensors/hrm_sensor"
    try:
        for i in range(20):
            ppg = read_sysfs(f"{base}/curr_adc")
            print(f"  [{i+1:02d}/20] PPG: {ppg}")
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    print("[+] HRM sampling finished.")

def sensors_adc_table():
    snap = get_sensors_snapshot()
    adc = snap.get("adc_channels", {})
    print("=== Hardware ADC Channels (15b70000.adc) ===")
    print(f" {'CH':<4} {'Description':<32} {'Counts':<8} {'Voltage (mV)':<12}")
    print("-" * 60)
    for k, v in adc.items():
        print(f" {v['channel']:<4} {v['description']:<32} {v['raw']:<8} {v['mv']:<12.1f}")

def main():
    if len(sys.argv) < 2 or sys.argv[1] == "status":
        get_status()
        return

    cmd = sys.argv[1].lower()
    if cmd == "cpu":
        sub = sys.argv[2].lower() if len(sys.argv) > 2 else "status"
        if sub == "boost":
            cpu_boost()
        elif sub == "normal":
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
    elif cmd == "typec":
        sub = sys.argv[2].lower() if len(sys.argv) > 2 else "status"
        set_typec_role(sub)
    elif cmd == "dock":
        sub = sys.argv[2].lower() if len(sys.argv) > 2 else "status"
        if sub in ["on", "start", "enable"]:
            dock_activate()
        elif sub in ["off", "stop", "disable"]:
            dock_deactivate()
        else:
            dock_status()
    elif cmd == "sensors":
        sub = sys.argv[2].lower() if len(sys.argv) > 2 else "status"
        if sub in ["json", "--json", "-j"]:
            sensors_json()
        elif sub in ["watch", "--watch", "-w", "live"]:
            sensors_watch()
        elif sub in ["hrm", "heart", "pulse"]:
            sensors_hrm_live()
        elif sub in ["adc", "volt"]:
            sensors_adc_table()
        else:
            sensors_status()
    elif cmd == "sdcard":
        if os.path.exists("/dev/block/mmcblk0"):
            print("=== MicroSD Storage Hardware Info ===")
            subprocess.run(["blkid", "/dev/block/mmcblk0"])
            subprocess.run(["df", "-h", "/media/sdcard"])
            print("\n--- Root Contents (/media/sdcard) ---")
            subprocess.run(["ls", "-lh", "/media/sdcard"])
        else:
            print("[!] MicroSD slot is empty.")
    else:
        get_status()

if __name__ == "__main__":
    main()
