#!/bin/sh
# Universal POSIX /bin/sh + Python3 dispatcher for s8ctl (v1.0.3)
# Runs full Python3 s8ctl when python3 is installed (Ubuntu, Debian, Kali, HAOS, SteamOS),
# and falls back to native POSIX /bin/sh on minimal distros (OpenWrt, Alpine Minirootfs).
export PATH=/run/s8:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

if command -v python3 >/dev/null 2>&1 && [ -f /usr/local/libexec/s8ctl.py ]; then
    exec python3 /usr/local/libexec/s8ctl.py "$@"
fi

S8CTL_VERSION="1.0.3"

read_sys() {
    if [ -r "$1" ]; then
        cat "$1" 2>/dev/null | tr -d '\n'
    else
        printf "%s" "${2:-N/A}"
    fi
}

show_status() {
    cap=$(read_sys /sys/class/power_supply/battery/capacity 0)
    stat=$(read_sys /sys/class/power_supply/battery/status Unknown)
    hlth=$(read_sys /sys/class/power_supply/battery/health Good)
    vraw=$(read_sys /sys/class/power_supply/battery/voltage_now 0)
    vnow=$((vraw / 1000))
    inow=$(read_sys /sys/class/power_supply/battery/current_now 0)
    traw=$(read_sys /sys/class/power_supply/battery/temp 0)
    btemp=$((traw / 10))
    c0=$(( $(read_sys /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq 0) / 1000 ))
    c4=$(( $(read_sys /sys/devices/system/cpu/cpu4/cpufreq/scaling_cur_freq 0) / 1000 ))
    tz=$(( $(read_sys /sys/class/thermal/thermal_zone0/temp 0) / 1000 ))
    gclk=$(read_sys /sys/devices/platform/13900000.mali/clock N/A)
    gload=$(read_sys /sys/devices/platform/13900000.mali/utilization 0)
    dpmon=$(read_sys /sys/class/dp_sec/monitor_info Disconnected)
    bt="OFF"
    [ "$(read_sys /sys/class/rfkill/rfkill0/state 0)" = "1" ] && bt="ON"
    sd="NOT DETECTED"
    if [ -b /dev/mmcblk0 ] || [ -b /dev/block/mmcblk0 ]; then
        if mountpoint -q /media/sdcard 2>/dev/null; then
            sd="MOUNTED @ /media/sdcard"
        else
            sd="DETECTED (/dev/mmcblk0)"
        fi
    fi
    echo "================================================================="
    echo "  Samsung Galaxy S8 Native Linux Platform [s8ctl v${S8CTL_VERSION} POSIX]"
    echo "================================================================="
    echo "  CPU (Exynos 8895) : 4xA53 @ ${c0} MHz | 4xM2 @ ${c4} MHz"
    echo "  SoC Temperature   : ${tz} C"
    echo "  GPU (Mali-G71)    : ${gclk} MHz (Load: ${gload}%)"
    echo "  Battery (MAX77865): ${cap}% (${stat}, Health: ${hlth}) | ${vnow} mV | ${inow} mA | ${btemp} C"
    echo "  MicroSD Card      : ${sd}"
    echo "  USB-C DisplayPort : Monitor=${dpmon}"
    echo "  Bluetooth 5.0     : ${bt} (Broadcom BCM4361)"
    echo "================================================================="
}

CMD="${1:-status}"
SUB="${2:-}"

case "$CMD" in
    status)
        show_status
        ;;
    cpu)
        case "$SUB" in
            boost)
                for i in 1 2 3 4 5 6 7; do echo 1 > "/sys/devices/system/cpu/cpu${i}/online" 2>/dev/null || true; done
                echo 1690000 > /sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq 2>/dev/null || true
                echo 1690000 > /sys/devices/system/cpu/cpu0/cpufreq/scaling_min_freq 2>/dev/null || true
                echo performance > /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>/dev/null || true
                echo 2314000 > /sys/devices/system/cpu/cpu4/cpufreq/scaling_max_freq 2>/dev/null || true
                echo 2314000 > /sys/devices/system/cpu/cpu4/cpufreq/scaling_min_freq 2>/dev/null || true
                echo performance > /sys/devices/system/cpu/cpu4/cpufreq/scaling_governor 2>/dev/null || true
                echo "[+] All 4x M2 cores locked at 2.314 GHz, 4x A53 cores locked at 1.690 GHz!"
                ;;
            normal|balanced|cool)
                for i in 1 2 3 4 5 6 7; do echo 1 > "/sys/devices/system/cpu/cpu${i}/online" 2>/dev/null || true; done
                echo 455000 > /sys/devices/system/cpu/cpu0/cpufreq/scaling_min_freq 2>/dev/null || true
                echo 1690000 > /sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq 2>/dev/null || true
                echo interactive > /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>/dev/null || true
                echo 741000 > /sys/devices/system/cpu/cpu4/cpufreq/scaling_min_freq 2>/dev/null || true
                echo 2314000 > /sys/devices/system/cpu/cpu4/cpufreq/scaling_max_freq 2>/dev/null || true
                echo interactive > /sys/devices/system/cpu/cpu4/cpufreq/scaling_governor 2>/dev/null || true
                echo "[+] Balanced dynamic scaling active (455MHz - 2.314GHz)."
                ;;
            powersave)
                echo interactive > /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>/dev/null || true
                echo interactive > /sys/devices/system/cpu/cpu4/cpufreq/scaling_governor 2>/dev/null || true
                echo 455000 > /sys/devices/system/cpu/cpu0/cpufreq/scaling_min_freq 2>/dev/null || true
                echo 949000 > /sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq 2>/dev/null || true
                echo 741000 > /sys/devices/system/cpu/cpu4/cpufreq/scaling_min_freq 2>/dev/null || true
                echo 1066000 > /sys/devices/system/cpu/cpu4/cpufreq/scaling_max_freq 2>/dev/null || true
                echo 0 > /sys/devices/system/cpu/cpu6/online 2>/dev/null || true
                echo 0 > /sys/devices/system/cpu/cpu7/online 2>/dev/null || true
                echo "[+] Power-saver active: Cores 6-7 parked, A53<=949MHz, M2<=1.06GHz."
                ;;
            *)
                show_status
                ;;
        esac
        ;;
    gpu)
        if [ "${SUB:-boost}" = "boost" ]; then
            echo Booster > /sys/devices/platform/13900000.mali/dvfs_governor 2>/dev/null || true
            echo 546000 > /sys/devices/platform/13900000.mali/dvfs_min_lock 2>/dev/null || true
            echo "[+] ARM Mali-G71 MP20 GPU Boosted: Governor=Booster, Clock=546 MHz"
        else
            echo -1 > /sys/devices/platform/13900000.mali/dvfs_min_lock 2>/dev/null || true
            echo Interactive > /sys/devices/platform/13900000.mali/dvfs_governor 2>/dev/null || true
            echo "[+] ARM Mali-G71 MP20 GPU reset to Interactive DVFS (260 - 546 MHz)"
        fi
        ;;
    torch)
        lvl="${SUB:-1}"
        [ "$lvl" = "on" ] && lvl=3
        [ "$lvl" = "off" ] && lvl=0
        echo "$lvl" > /sys/class/leds/torch-sec1/brightness 2>/dev/null || true
        echo "[+] Rear Flashlight / Torch set to level ${lvl}/5"
        ;;
    vibrate)
        ms="${SUB:-150}"
        echo "$ms" > /sys/class/timed_output/vibrator/enable 2>/dev/null || true
        echo "[+] Haptic pulse: ${ms} ms"
        ;;
    battery)
        if [ "$SUB" = "boost" ]; then
            echo "0xBD 0x6C" > /sys/class/power_supply/max77865-charger/data 2>/dev/null || true
            echo "0xC3 0x61" > /sys/class/power_supply/max77865-charger/data 2>/dev/null || true
            echo "0xC0 0x3C" > /sys/class/power_supply/max77865-charger/data 2>/dev/null || true
            echo "0xB9 0x9E" > /sys/class/power_supply/max77865-charger/data 2>/dev/null || true
            echo "0xB7 0x05" > /sys/class/power_supply/max77865-charger/data 2>/dev/null || true
            echo 1500 > /sys/class/power_supply/battery/batt_tune_input_charge_current 2>/dev/null || true
            echo 1500 > /sys/class/power_supply/battery/batt_tune_fast_charge_current 2>/dev/null || true
            echo "[+] MAX77865 PMIC Charger unlocked (1500mA input & fast charge)"
        fi
        show_status
        ;;
    wifi)
        ip link set wlan0 up 2>/dev/null || true
        if [ "$SUB" = "scan" ]; then
            echo "[*] Scanning 2.4 GHz & 5 GHz networks on wlan0..."
            if command -v iw >/dev/null 2>&1; then
                iw dev wlan0 scan 2>/dev/null | grep -E "SSID:|freq:|signal:" | head -n 30
            elif command -v iwinfo >/dev/null 2>&1; then
                iwinfo wlan0 scan 2>/dev/null | head -n 30
            else
                grep -E "wlan0" /proc/net/wireless /proc/net/dev 2>/dev/null || ip addr show wlan0
            fi
        else
            ip addr show wlan0 2>/dev/null || true
        fi
        ;;
    sdcard)
        echo "=== MicroSD Storage Hardware Info ==="
        df -h /media/sdcard 2>/dev/null || true
        ls -la /media/sdcard 2>/dev/null | head -n 15 || true
        ;;
    bt)
        if [ "${SUB:-on}" = "on" ]; then
            echo 1 > /sys/class/rfkill/rfkill0/state 2>/dev/null || true
            echo "[+] Broadcom BCM4361 Bluetooth 5.0 radio unblocked (/dev/ttySAC1 + rfkill0)"
        else
            echo 0 > /sys/class/rfkill/rfkill0/state 2>/dev/null || true
            echo "[+] Bluetooth radio blocked."
        fi
        ;;
    version|--version|-v)
        ap_ver=$(read_sys /etc/s8-ap-version 3.0.0)
        kver=$(uname -r)
        echo "s8ctl v${S8CTL_VERSION} (galaxy-s8-hw v${S8CTL_VERSION}, AP v${ap_ver}, Kernel ${kver})"
        ;;
    *)
        show_status
        ;;
esac

