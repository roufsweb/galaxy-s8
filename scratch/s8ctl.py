#!/usr/bin/python3
"""
s8ctl — Samsung Galaxy S8 (SM-G950N, Exynos 8895) Native Hardware Control Suite
Controls every hardware subsystem on the Galaxy S8:
  - Front RGBW Notification LED (/sys/class/leds/led_{r,g,b,w}/brightness)
  - Rear Camera Flashlight / Torch (/sys/class/leds/torch-sec1/brightness)
  - Haptic Vibration Motor (/sys/class/timed_output/vibrator/enable)
  - MAX77865 PMIC Smart Battery Charger (/sys/class/power_supply/max77865-charger/data)
  - USB-C DisplayPort / HDMI 1.2 (/sys/class/dp_sec/forced_resolution & exynos_dp_bridge)
  - Audio Routing (MAX98506 Internal Speaker, CS47L92 3.5mm Hi-Fi DAC, USB-C DP Audio)
  - Bluetooth 5.0 (Broadcom BCM4361 /dev/ttySAC1 + rfkill0)
  - Mali-G71 MP20 GPU & 8-Core Exynos 8895 CPU / Thermal / Sensor Telemetry
"""
import os
import sys
import time
import subprocess

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

def amixer_set(ctl, val):
    subprocess.run(["amixer", "-c", "0", "cset", f"name='{ctl}'", str(val)],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def set_audio_route(mode="speaker"):
    # Common ABOX initialization from /system/etc/mixer_paths.xml
    amixer_set("ABOX Sampling Rate Mixer", "48000")
    amixer_set("ABOX Sampling Rate Out1", "48000")
    amixer_set("ABOX SPUS ASRC0", "On")
    amixer_set("ABOX SPUS ASRC7", "On")

    if mode == "speaker":
        amixer_set("SPK Enable Switch", "Enable")
        amixer_set("ABOX ERAP info DSM On", "1")
        amixer_set("ABOX NSRC3", "UAIF4")
        amixer_set("ABOX SPUS OUT0", "SIFS1")
        amixer_set("ABOX SPUS OUT7", "SIFS1")
        amixer_set("ABOX SIFS1", "SPUS OUT0")
        amixer_set("ABOX UAIF SPK4", "SIFS1")
        print("[+] Audio routed to Galaxy S8 Internal Bottom Speaker (MAX98506 + ABOX UAIF4)")
    elif mode in ("headphone", "headset", "3.5mm"):
        amixer_set("ABOX SPUS OUT0", "SIFS0")
        amixer_set("ABOX UAIF SPK0", "SIFS0")
        amixer_set("HPOUT2 Digital Switch", "1")
        amixer_set("HPOUT2 DRE Switch", "1")
        amixer_set("HPOUT2 EDRE Switch", "1")
        amixer_set("HPOUT2L Input 1", "AIF1RX1")
        amixer_set("HPOUT2R Input 1", "AIF1RX2")
        print("[+] Audio routed to 3.5mm Hi-Fi Headphone DAC (Cirrus Logic CS47L92 HPOUT2)")
    elif mode in ("hdmi", "dp"):
        print("[+] Audio routed to USB-C DisplayPort / HDMI Audio (ALSA hw:0,22 / pcmC0D22p)")

def set_bluetooth(state="on"):
    if state == "on":
        write_sysfs("/sys/class/rfkill/rfkill0/state", "1")
        os.makedirs("/etc/firmware", exist_ok=True)
        os.makedirs("/lib/firmware/brcm", exist_ok=True)
        for src in ("/vendor/firmware/bcm4361B0_semco.hcd", "/system/vendor/firmware/bcm4361B0_semco.hcd"):
            if os.path.exists(src):
                for dst in ("/etc/firmware/BCM4361B0.hcd", "/lib/firmware/brcm/BCM4361B0.hcd", "/lib/firmware/brcm/BCM.hcd"):
                    if not os.path.exists(dst):
                        try:
                            os.symlink(src, dst)
                        except Exception:
                            pass
                break
        subprocess.Popen(["btattach", "-B", "/dev/ttySAC1", "-P", "bcm", "-S", "3000000"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.Popen(["/usr/libexec/bluetooth/bluetoothd"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("[+] Broadcom BCM4361 Bluetooth 5.0 powered ON (/dev/ttySAC1 + rfkill0)")
    else:
        write_sysfs("/sys/class/rfkill/rfkill0/state", "0")
        print("[+] Bluetooth powered OFF")

def set_led(r, g, b, w=0):
    write_sysfs("/sys/class/leds/led_r/brightness", r)
    write_sysfs("/sys/class/leds/led_g/brightness", g)
    write_sysfs("/sys/class/leds/led_b/brightness", b)
    write_sysfs("/sys/class/leds/led_w/brightness", w)
    print(f"[+] Front RGBW LED set to R={r}, G={g}, B={b}, W={w}")

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
    write_sysfs("/sys/class/power_supply/max77865-charger/data", "0xB7 0x05")
    write_sysfs("/sys/class/power_supply/battery/batt_tune_input_charge_current", "1200")
    write_sysfs("/sys/class/power_supply/battery/batt_tune_fast_charge_current", "1800")
    print("[+] MAX77865 PMIC Charger unlocked (4.3V UVLO fix + 1200mA input)")

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

    dp_res = read_sysfs("/sys/class/dp_sec/forced_resolution", "auto")
    dp_mon = read_sysfs("/sys/class/dp_sec/monitor_info", "Disconnected").replace("\n", " ")
    baro = read_sysfs("/sys/class/sensors/barometer_sensor/name", "BMP280/LPS25H")
    hrm = read_sysfs("/sys/class/sensors/hrm_sensor/name", "MAX86902")
    gyro = read_sysfs("/sys/class/sensors/gyro_sensor/name", "LSM6DSL")
    bt_state = "ON" if read_sysfs("/sys/class/rfkill/rfkill0/state", "0") == "1" else "OFF"

    print("=================================================================")
    print("  Samsung Galaxy S8 (SM-G950N) Native Ubuntu Hardware Telemetry")
    print("=================================================================")
    print(f"  CPU (Exynos 8895) : LITTLE 4xA53 @ {c0_freq} MHz | BIG 4xM2 @ {c4_freq} MHz")
    print(f"  SoC Temperature   : {tz0:.1f} C")
    print(f"  GPU (Mali-G71)    : {gpu_clk} MHz (Load: {gpu_load}%)")
    print(f"  Battery (MAX77865): {cap}% ({status}, Health: {health}) | {vnow:.3f}V | {inow} mA | {btemp:.1f} C")
    print(f"  USB-C DisplayPort : Mode={dp_res} | Monitor={dp_mon}")
    print(f"  Bluetooth 5.0     : {bt_state} (Broadcom BCM4361 /dev/ttySAC1)")
    print(f"  Onboard Sensors   : IMU={gyro} | Barometer={baro} | Heart-Rate={hrm}")
    print("=================================================================")

def main():
    if len(sys.argv) < 2 or sys.argv[1] == "status":
        get_status()
        return

    cmd = sys.argv[1].lower()
    if cmd == "led":
        colors = {
            "red": (255, 0, 0),
            "green": (0, 120, 0),
            "blue": (0, 0, 255),
            "cyan": (0, 180, 255),
            "purple": (180, 0, 255),
            "yellow": (255, 180, 0),
            "white": (255, 255, 255),
            "off": (0, 0, 0),
        }
        if len(sys.argv) == 3 and sys.argv[2].lower() in colors:
            r, g, b = colors[sys.argv[2].lower()]
            set_led(r, g, b)
        elif len(sys.argv) >= 5:
            set_led(int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]))
        else:
            print("Usage: s8ctl led <red|green|blue|cyan|purple|yellow|white|off> OR s8ctl led <R> <G> <B>")
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
        set_audio_route(sub)
    elif cmd == "bt":
        sub = sys.argv[2].lower() if len(sys.argv) > 2 else "on"
        set_bluetooth(sub)
    elif cmd == "dp":
        sub = sys.argv[2].lower() if len(sys.argv) > 2 else "1080p"
        if sub == "1080p":
            write_sysfs("/sys/class/dp_sec/forced_resolution", "16")
            print("[+] USB-C DisplayPort forced_resolution set to 16 (1920x1080p@60Hz)")
        elif sub == "4k":
            write_sysfs("/sys/class/dp_sec/forced_resolution", "31")
            print("[+] USB-C DisplayPort forced_resolution set to 31 (3840x2160p@60Hz)")
        subprocess.Popen(["/usr/local/bin/exynos_dp_bridge"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("[+] Started exynos_dp_bridge (/dev/ion -> /dev/graphics/fb2)")
    else:
        get_status()

if __name__ == "__main__":
    main()
