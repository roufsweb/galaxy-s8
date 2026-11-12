#!/bin/bash
# s8-hardware-init.sh -- Samsung Galaxy S8 (SM-G950N, Exynos 8895) Boot Hardware Provisioner
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

# 1. Enforce Exynos V4L2 FIMC-IS2 panic guard & Hardware Disconnect Fault-Tolerance (Rule 29)
echo 0 > /proc/sys/kernel/panic_on_oops 2>/dev/null || true
echo 5 > /proc/sys/kernel/panic 2>/dev/null || true
rm -f /dev/video[1-9][0-9]* /dev/v4l-subdev* 2>/dev/null || true

# 2. Android-compatible /dev/graphics/fb* and /dev/block/* symlinks + GPU/ION permissions
mkdir -p /dev/graphics /dev/block
for fb in /dev/fb*; do
    name="$(basename "$fb")"
    if [ -c "$fb" ] && [ ! -L "$fb" ] && [ ! -c "/dev/graphics/$name" ]; then
        ln -sf "$fb" "/dev/graphics/$name"
    fi
done
if [ ! -c /dev/graphics/fb2 ]; then
    rm -f /dev/graphics/fb2 2>/dev/null || true
    mknod /dev/graphics/fb2 c 29 2 2>/dev/null || true
fi
chmod 660 /dev/graphics/fb* 2>/dev/null || true
for blk in /dev/sd* /dev/mmcblk*; do
    [ -b "$blk" ] && ln -sf "$blk" "/dev/block/$(basename "$blk")"
done
chmod 666 /dev/ion /dev/mali0 2>/dev/null || true

# 3. Provision vendor Wi-Fi, Bluetooth & Audio DSP firmware cleanly (Rule 16 compliant: sourced locally from device)
mkdir -p /vendor/etc/wifi /vendor/firmware /etc/firmware /lib/firmware/brcm
provision_vendor_fw() {
    local cache_wifi="/mnt/android_data/linux/vendor_fw/wifi"
    local cache_fw="/mnt/android_data/linux/vendor_fw/firmware"
    if [ ! -f /vendor/etc/wifi/bcmdhd_clm.blob ] && [ -f "$cache_wifi/bcmdhd_clm.blob" ]; then
        cp -n "$cache_wifi/"* /vendor/etc/wifi/ 2>/dev/null || true
    fi
    if [ ! -f /etc/firmware/calliope_dram.bin ] && [ -d "$cache_fw" ]; then
        cp -n "$cache_fw/"* /etc/firmware/ 2>/dev/null || true
        cp -n "$cache_fw/"* /vendor/firmware/ 2>/dev/null || true
    fi
    if [ ! -f /vendor/etc/wifi/bcmdhd_clm.blob ] && [ -b /dev/sda17 ]; then
        mkdir -p /tmp/.s8_ro_sys
        if mount -o ro /dev/sda17 /tmp/.s8_ro_sys 2>/dev/null; then
            for wdir in /tmp/.s8_ro_sys/system/vendor/etc/wifi /tmp/.s8_ro_sys/vendor/etc/wifi; do
                [ -d "$wdir" ] && cp -n "$wdir/"* /vendor/etc/wifi/ 2>/dev/null || true
            done
            for fdir in /tmp/.s8_ro_sys/system/vendor/firmware /tmp/.s8_ro_sys/vendor/firmware; do
                if [ -d "$fdir" ]; then
                    cp -n "$fdir/"bcm* /etc/firmware/ 2>/dev/null || true
                    cp -n "$fdir/"bcm* /vendor/firmware/ 2>/dev/null || true
                fi
            done
            umount /tmp/.s8_ro_sys 2>/dev/null || true
        fi
        rmdir /tmp/.s8_ro_sys 2>/dev/null || true
    fi
    # Standardize BCM4361 Bluetooth firmware symlink
    for src in /vendor/firmware/bcm4361B0_semco.hcd /etc/firmware/bcm4361B0_semco.hcd /vendor/firmware/bcm4361B0_murata.hcd /etc/firmware/bcm4361B0_murata.hcd; do
        if [ -f "$src" ]; then
            [ -e /etc/firmware/BCM4361B0.hcd ] || ln -sf "$src" /etc/firmware/BCM4361B0.hcd
            [ -e /lib/firmware/brcm/BCM4361B0.hcd ] || ln -sf "$src" /lib/firmware/brcm/BCM4361B0.hcd
            break
        fi
    done
}
provision_vendor_fw

# 4. Unlock MAX77865 PMIC 1500mA Fast Charge + UVLO skip
if [ -w /sys/class/power_supply/max77865-charger/data ]; then
    echo "0xBD 0x6C" > /sys/class/power_supply/max77865-charger/data 2>/dev/null || true
    echo "0xC3 0x61" > /sys/class/power_supply/max77865-charger/data 2>/dev/null || true
    echo "0xC0 0x3C" > /sys/class/power_supply/max77865-charger/data 2>/dev/null || true
    echo "0xB9 0x9E" > /sys/class/power_supply/max77865-charger/data 2>/dev/null || true
    echo "0xB7 0x05" > /sys/class/power_supply/max77865-charger/data 2>/dev/null || true
fi
echo 1500 > /sys/class/power_supply/battery/batt_tune_input_charge_current 2>/dev/null || true
echo 1500 > /sys/class/power_supply/battery/batt_tune_fast_charge_current 2>/dev/null || true
echo 0 > /sys/class/power_supply/battery/batt_slate_mode 2>/dev/null || true

# 5. IPv4 forwarding & Android data directories
echo 1 > /proc/sys/net/ipv4/ip_forward 2>/dev/null || true
mkdir -p /mnt/android_data/docker /mnt/android_data/linux /mnt/android_data/sdcard /media/sdcard /mnt/sdcard /run/user/0
chmod 700 /run/user/0

# 6. Ensure Android PARANOID_NETWORK aid_* groups apply to all real human users
for u in $(awk -F: '$3>=1000 && $3<65534 {print $1}' /etc/passwd 2>/dev/null); do
    usermod -a -G aid_inet,aid_net_raw,aid_net_admin,aid_net_bt_admin,aid_net_bt,aid_graphics,aid_audio,aid_sdcard_rw "$u" 2>/dev/null || true
done

# 7. Initialize LZ4 ZRAM swap (1.5 GB)
if [ -b /dev/zram0 ] && ! grep -q zram0 /proc/swaps 2>/dev/null; then
    echo lz4 > /sys/block/zram0/comp_algorithm 2>/dev/null || true
    echo 1610612736 > /sys/block/zram0/disksize 2>/dev/null || true
    mkswap /dev/zram0 >/dev/null 2>&1 || true
    swapon -p 100 /dev/zram0 2>/dev/null || true
fi

# 8. Mount MicroSD card if present
if [ -b /dev/mmcblk0 ] || [ -b /dev/block/mmcblk0 ]; then
    MMC_DEV=/dev/mmcblk0
    [ -b /dev/mmcblk0p1 ] && MMC_DEV=/dev/mmcblk0p1
    if ! mountpoint -q /media/sdcard; then
        mount -t vfat -o rw,umask=000,iocharset=utf8 "$MMC_DEV" /media/sdcard 2>/dev/null || mount "$MMC_DEV" /media/sdcard 2>/dev/null || true
    fi
    if mountpoint -q /media/sdcard; then
        mountpoint -q /mnt/sdcard || mount --bind /media/sdcard /mnt/sdcard 2>/dev/null || true
        mountpoint -q /mnt/android_data/sdcard || mount --bind /media/sdcard /mnt/android_data/sdcard 2>/dev/null || true
    fi
fi

# 9. Configure Broadcom BCM4361 dhd module parameters BEFORE bringing wlan0 up (no _b0 suffix)
if [ -d /sys/module/dhd/parameters ]; then
    printf "/vendor/etc/wifi/bcmdhd_sta.bin" > /sys/module/dhd/parameters/firmware_path 2>/dev/null || true
    printf "/vendor/etc/wifi/nvram.txt" > /sys/module/dhd/parameters/nvram_path 2>/dev/null || true
    printf "/vendor/etc/wifi/bcmdhd_clm.blob" > /sys/module/dhd/parameters/clm_path 2>/dev/null || true
fi
ip link set wlan0 up 2>/dev/null || true
echo "0 0" > /sys/class/dp_sec/dp_sbu_sw_sel 2>/dev/null || true

# 10. Exynos 8895 Cool-Idle Interactive CPU/GPU Tuning + Snapd 4.4.111 Crash-Loop Guard
tune_exynos_governor() {
    for c in 0 4; do
        gov="/sys/devices/system/cpu/cpu${c}/cpufreq/scaling_governor"
        [ -w "$gov" ] && echo interactive > "$gov" 2>/dev/null || true
    done
    if [ -d /sys/devices/system/cpu/cpu0/cpufreq/interactive ]; then
        echo 832000 > /sys/devices/system/cpu/cpu0/cpufreq/interactive/hispeed_freq 2>/dev/null || true
        echo 90 > /sys/devices/system/cpu/cpu0/cpufreq/interactive/go_hispeed_load 2>/dev/null || true
        echo "75 832000:88 1053000:95 1456000:98" > /sys/devices/system/cpu/cpu0/cpufreq/interactive/target_loads 2>/dev/null || true
        echo "20000 1053000:40000 1456000:80000" > /sys/devices/system/cpu/cpu0/cpufreq/interactive/above_hispeed_delay 2>/dev/null || true
        echo 30000 > /sys/devices/system/cpu/cpu0/cpufreq/interactive/timer_rate 2>/dev/null || true
    fi
    if [ -d /sys/devices/system/cpu/cpu4/cpufreq/interactive ]; then
        echo 1066000 > /sys/devices/system/cpu/cpu4/cpufreq/interactive/hispeed_freq 2>/dev/null || true
        echo 90 > /sys/devices/system/cpu/cpu4/cpufreq/interactive/go_hispeed_load 2>/dev/null || true
        echo "80 1066000:90 1469000:96 1937000:99" > /sys/devices/system/cpu/cpu4/cpufreq/interactive/target_loads 2>/dev/null || true
        echo "20000 1469000:50000 1937000:100000" > /sys/devices/system/cpu/cpu4/cpufreq/interactive/above_hispeed_delay 2>/dev/null || true
        echo 30000 > /sys/devices/system/cpu/cpu4/cpufreq/interactive/timer_rate 2>/dev/null || true
    fi
    if [ -w /sys/devices/platform/13900000.mali/dvfs_governor ]; then
        echo -1 > /sys/devices/platform/13900000.mali/dvfs_min_lock 2>/dev/null || true
        echo Interactive > /sys/devices/platform/13900000.mali/dvfs_governor 2>/dev/null || true
    fi
}
tune_exynos_governor

# Prevent snapd 120% CPU crash-rollback seeding loop on 4.4.111 kernels lacking /dev/pts/ptmx & AppArmor
if [ ! -e /dev/pts/ptmx ] && [ -d /run/systemd/system ] && systemctl list-unit-files snapd.service >/dev/null 2>&1; then
    systemctl stop --no-block snapd.seeded.service snapd.service snapd.socket 2>/dev/null || true
fi

# 11. Initialize Calliope ABOX Native ALSA Audio if amixer is available
if [ -x /usr/local/bin/init_audio.sh ] && command -v amixer >/dev/null 2>&1; then
    /usr/local/bin/init_audio.sh >/var/log/s8_init_audio.log 2>&1 || true
fi

# 12. Double haptic pulse on native Linux ready
echo 120 > /sys/class/timed_output/vibrator/enable 2>/dev/null || true
sleep 0.35
echo 120 > /sys/class/timed_output/vibrator/enable 2>/dev/null || true
exit 0

