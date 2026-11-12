#!/usr/bin/env python3
"""
build_universal_ap.py -- Pure Native Linux Galaxy S8 (SM-G950N) AP Image Builder (GEMINI.md Rule 28)

Produces:
  - scratch/boot_s8_universal.img (<= 41,943,040 B; target <= 39,845,888 B)
  - Galaxy_S8_Linux_AP.tar & releases/Galaxy_S8_Linux_AP.tar (Odin AP USTAR package)

Architecture Guarantees (GEMINI.md Rules 1, 2, 3, 13, 17, 18, 19, 23, 28):
  1. 100% Pure Native Linux Boot (Zero Android init, zero init.rc, zero sepolicy, zero Bionic libs):
       - Initramfs `/init` uses static BusyBox + static e2fsck + pure Linux ConfigFS USB Gadget.
       - Stages static runtime into `/run/s8/` (`tmpfs`), mounts `/data/linux/rootfs.img`, moves virtual
         filesystems (`/dev`, `/proc`, `/sys`, `/run`, `/mnt_data`), and hands PID 1 directly to
         native guest `/sbin/init` (`systemd`) via `exec busybox switch_root`.
       - Clean initramfs rescue fallback over USB RNDIS (`192.168.7.2`), CDC ACM (`COMx` `/dev/ttyGS0`),
         SSH (`:22`), RWP (`:7860`), and DisplayPort console if no guest rootfs is installed yet.
  2. Distro-Agnostic USB Transport (ConfigFS `0x1D6B:0x0104` Composite RNDIS + CDC ACM + Windows OS Descriptors):
       - Interface 0/1: `rndis.usb0` -> `192.168.7.2/24` + `udhcpd` (`192.168.7.10..50`) + `s8_usb_agentd` (:7860) + Dropbear SSH.
       - Interface 2/3: `acm.gs0` -> `/dev/ttyGS0` auto-getty root serial console (`USB Serial Device COMx`).
  3. Zero Rogue Loops & Zero Firmware Shadowing:
       - All 9 Calliope DSP audio firmwares embedded in `/etc/firmware/` & staged to `/run/s8/firmware/`
         (registered via `/sys/module/firmware_class/parameters/path` so stock OS rootfs stays untouched).
       - Optional Broadcom BCM4361 Wi-Fi blobs staged to `/run/s8/wifi/` for `/sys/module/dhd/parameters/`.
"""

import lzma
import os
import struct
import sys
import tarfile
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
AP_PREBUILT = WORKSPACE / "packages" / "galaxy-s8-hw" / "prebuilt" / "ap_ramdisk"
SRC_TAR = WORKSPACE / "archive" / "boot_twrp_exact.tar"
DEFAULT_KERNEL = WORKSPACE / "kernel" / "arch" / "arm64" / "boot" / "Image"
STATIC_BB = (
    WORKSPACE / "scratch" / "ramdisk_work" / "bin" / "busybox"
    if (WORKSPACE / "scratch" / "ramdisk_work" / "bin" / "busybox").is_file()
    else AP_PREBUILT / "bin" / "busybox"
)
E2FSCK_STATIC = (
    WORKSPACE / "scratch" / "e2fsck.static"
    if (WORKSPACE / "scratch" / "e2fsck.static").is_file()
    else AP_PREBUILT / "sbin" / "e2fsck.static"
)
BUTTON_DAEMON = (
    WORKSPACE / "scratch" / "s8_button_daemon_static"
    if (WORKSPACE / "scratch" / "s8_button_daemon_static").is_file()
    else (
        WORKSPACE / "scratch" / "s8_button_daemon"
        if (WORKSPACE / "scratch" / "s8_button_daemon").is_file()
        else AP_PREBUILT / "sbin" / "s8_button_daemon"
    )
)
DP_DAEMON = (
    WORKSPACE / "scratch" / "s8_dp_daemon"
    if (WORKSPACE / "scratch" / "s8_dp_daemon").is_file()
    else AP_PREBUILT / "sbin" / "s8_dp_daemon"
)
USB_AGENTD = (
    WORKSPACE / "scratch" / "s8_usb_agentd"
    if (WORKSPACE / "scratch" / "s8_usb_agentd").is_file()
    else AP_PREBUILT / "sbin" / "s8_usb_agentd"
)
DROPBEAR_BIN = (
    WORKSPACE / "desktop-app" / "resources" / "bin" / "s8-dropbear-arm64"
    if (WORKSPACE / "desktop-app" / "resources" / "bin" / "s8-dropbear-arm64").is_file()
    else AP_PREBUILT / "sbin" / "s8-dropbear-arm64"
)
WIFI_FW_DIR = (
    WORKSPACE / "scratch" / "s8_wifi_fw" / "wifi"
    if (WORKSPACE / "scratch" / "s8_wifi_fw" / "wifi").is_dir()
    else AP_PREBUILT / "etc" / "firmware" / "wifi"
)

OUT_BOOT = WORKSPACE / "scratch" / "boot_s8_universal.img"
OUT_ODIN_ROOT = WORKSPACE / "Galaxy_S8_Linux_AP.tar"
OUT_ODIN_RELEASE = WORKSPACE / "releases" / "Galaxy_S8_Linux_AP.tar"
AP_VERSION = "3.0.0"
OUT_ODIN_HISTORY = WORKSPACE / "releases" / "history" / f"Galaxy_S8_Linux_AP_v{AP_VERSION}.tar"


SDA7_HARD_LIMIT = 41_943_040
SAFE_TARGET_CEILING = 39_845_888  # <= 38.00 MiB safe ceiling (< 39 MiB bootloop rule)

ALL_FIRMWARES = [
    "calliope_sram.bin",
    "calliope_dram.bin",
    "calliope_iva.bin",
    "dsm.bin",
    "AP_AUDIO_SLSI.bin",
    "APBargeIn_AUDIO_SLSI.bin",
    "SoundBoosterParam.bin",
    "APBiBF_AUDIO_SLSI.bin",
    "dsm_tune.bin",
]

WIFI_FW_FILES = [
    "bcmdhd_sta.bin_b0",
    "bcmdhd_sta.bin_b2",
    "bcmdhd_clm.blob",
    "nvram.txt",
    "nvram.txt_r02j_b0",
]

BUSYBOX_BIN_APPLETS = [
    "sh", "ash", "cat", "chmod", "chown", "cp", "dd", "df", "dmesg", "echo",
    "grep", "kill", "killall", "ln", "ls", "mkdir", "mknod", "mount", "umount",
    "mountpoint", "mv", "ps", "rm", "rmdir", "sed", "awk", "sleep", "sync",
    "touch", "true", "false", "uname", "basename", "dirname", "id", "env",
    "vi", "head", "tail", "wc", "sort", "uniq", "tr", "cut", "tee", "seq",
]

BUSYBOX_SBIN_APPLETS = [
    "busybox", "switch_root", "chroot", "udhcpd", "udhcpc", "ip", "ifconfig",
    "route", "getty", "losetup", "mkswap", "swapon", "swapoff", "telnetd",
    "httpd", "mdev", "reboot", "poweroff", "halt",
]

S8_UDHCPC_SCRIPT = b"""#!/run/s8/sh
[ -z "$1" ] && exit 1
BB=/run/s8/busybox
[ -x "$BB" ] || BB=/bin/busybox
case "$1" in
    deconfig)
        "$BB" ip addr flush dev "$interface" 2>/dev/null || true
        ;;
    renew|bound)
        "$BB" ip addr flush dev "$interface" 2>/dev/null || true
        "$BB" ip addr add "$ip/${mask:-24}" dev "$interface" 2>/dev/null || "$BB" ifconfig "$interface" "$ip" netmask "${subnet:-255.255.255.0}" up
        if [ -n "$router" ]; then
            for r in $router; do
                "$BB" ip route replace default via "$r" dev "$interface" 2>/dev/null || "$BB" route add default gw "$r" dev "$interface" 2>/dev/null || true
                break
            done
        fi
        if [ -n "$dns" ]; then
            : > /tmp/s8_resolv.conf
            for d in $dns; do
                echo "nameserver $d" >> /tmp/s8_resolv.conf
            done
            if [ -w /etc/resolv.conf ] && [ ! -L /etc/resolv.conf ]; then
                "$BB" cp /tmp/s8_resolv.conf /etc/resolv.conf 2>/dev/null || true
            fi
        fi
        ;;
esac
exit 0
"""

S8_NET_HOTPLUG_SCRIPT = b"""#!/run/s8/sh
# Auto-configure DHCP on any USB-LAN / USB-Ethernet dongle (like a standard Linux SBC)
BB=/run/s8/busybox
[ -x "$BB" ] || BB=/bin/busybox
"$BB" sleep 2
while true; do
    for path in /sys/class/net/*; do
        [ -e "$path" ] || continue
        iface=$("$BB" basename "$path")
        case "$iface" in
            lo|wlan*|swlan*|p2p*|umts*|rndis*|rmnet*|sit*|ip6*|tun*|tap*|veth*|docker*|br-*|dummy*|hassio*)
                continue ;;
        esac
        "$BB" ip link set "$iface" up 2>/dev/null || "$BB" ifconfig "$iface" up 2>/dev/null || true
        carrier=$("$BB" cat "$path/carrier" 2>/dev/null || echo 1)
        if [ "$carrier" = "1" ]; then
            has_ip=$("$BB" ip -4 addr show dev "$iface" 2>/dev/null | "$BB" grep -c 'inet ')
            if [ "${has_ip:-0}" -eq 0 ]; then
                "$BB" udhcpc -n -q -t 4 -T 2 -i "$iface" -s /run/s8/s8_udhcpc.script >/var/log/udhcpc_${iface}.log 2>&1 || true
            fi
        fi
    done
    "$BB" sleep 3
done
"""

S8_SERIAL_SHELL_SCRIPT = b"""#!/run/s8/sh
export PATH=/run/s8:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export TERM=vt100
export HOME=/root
export LANG=C.UTF-8
cd /root 2>/dev/null || cd /
echo ""
echo "=== Galaxy S8 Native Linux Serial Console (ttyGS0) ==="
echo "PID 1: $(cat /proc/1/comm 2>/dev/null || echo unknown) | Kernel: $(uname -r)"
if [ -x /bin/bash ]; then
    exec /bin/bash -l
elif [ -x /bin/ash ]; then
    exec /bin/ash -l
elif [ -x /bin/sh ]; then
    exec /bin/sh -l
fi
exec /run/s8/sh -l
"""

S8_SERIAL_GETTY_SCRIPT = b"""#!/run/s8/sh
BB=/run/s8/busybox
[ -x "$BB" ] || BB=/bin/busybox
while true; do
    if [ ! -c /dev/ttyGS0 ] && [ -r /sys/class/tty/ttyGS0/dev ]; then
        IFS=: read maj min < /sys/class/tty/ttyGS0/dev
        "$BB" mknod -m 660 /dev/ttyGS0 c "$maj" "$min" 2>/dev/null || true
    fi
    if [ -c /dev/ttyGS0 ]; then
        "$BB" getty -n -l /run/s8/s8_serial_shell.sh -L ttyGS0 115200 vt100 >/dev/null 2>&1 || true
    fi
    "$BB" sleep 2
done
"""

S8_POSTBOOT_SCRIPT = b"""#!/run/s8/sh
# Post-boot supervisor executed by systemd (or fallback) once multi-user target starts
BB=/run/s8/busybox
mkdir -p /var/log /run/s8 2>/dev/null || true
if "$BB" ip link show rndis0 >/dev/null 2>&1; then
    "$BB" ip addr replace 192.168.7.2/24 dev rndis0 2>/dev/null || true
    "$BB" ip link set rndis0 up 2>/dev/null || true
fi
if [ -x /mnt/android_data/linux/s8_post_boot.sh ]; then
    /bin/sh /mnt/android_data/linux/s8_post_boot.sh >/var/log/s8_user_post_boot.log 2>&1 || true
fi
exit 0
"""

S8_PID1_BOOT_SCRIPT = b"""#!/run/s8/sh
# Stage-2 PID 1 Handoff inside switched rootfs (executes BEFORE exec /sbin/init -> systemd)
BB=/run/s8/busybox
export PATH=/run/s8:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
exec </dev/null >/run/s8/pid1_boot.log 2>&1
set -x

# 1. Re-enforce V4L2 FIMC-IS2 node guard & graphics permissions before systemd-udevd starts
"$BB" rm -f /dev/video[1-9][0-9]* /dev/v4l-subdev* 2>/dev/null || true
for idx in 0 1 2; do
    [ -c "/dev/graphics/fb${idx}" ] || "$BB" mknod "/dev/graphics/fb${idx}" c 29 "${idx}" 2>/dev/null || true
    [ -c "/dev/graphics/fb${idx}" ] && "$BB" ln -sf "/dev/graphics/fb${idx}" "/dev/fb${idx}" 2>/dev/null || true
done
"$BB" chmod 660 /dev/graphics/fb* 2>/dev/null || true
"$BB" chmod 666 /dev/ion /dev/mali0 /dev/ptmx 2>/dev/null || true

# 2. Keep AP firmware path active without writing into stock guest rootfs (Rule 19)
echo -n "/run/s8/firmware" > /sys/module/firmware_class/parameters/path 2>/dev/null || true
if [ -f /run/s8/wifi/bcmdhd_sta.bin_b0 ]; then
    echo -n "/run/s8/wifi/bcmdhd_sta.bin" > /sys/module/dhd/parameters/firmware_path 2>/dev/null || true
    echo -n "/run/s8/wifi/nvram.txt" > /sys/module/dhd/parameters/nvram_path 2>/dev/null || true
    echo -n "/run/s8/wifi/bcmdhd_clm.blob" > /sys/module/dhd/parameters/clm_path 2>/dev/null || true
fi

# 3. Runtime-only NetworkManager & systemd-networkd guards so rndis0 192.168.7.2/24 stays stable
"$BB" mkdir -p /run/NetworkManager/conf.d /run/systemd/network /run/systemd/system/multi-user.target.wants /var/log
cat <<'NMCONF' > /run/NetworkManager/conf.d/99-s8-rndis.conf
[keyfile]
unmanaged-devices=interface-name:rndis0
NMCONF
cat <<'NETCONF' > /run/systemd/network/10-s8-rndis.network
[Match]
Name=rndis0

[Network]
Address=192.168.7.2/24
KeepConfiguration=yes
NETCONF

cat <<'UNIT' > /run/systemd/system/s8-postboot.service
[Unit]
Description=Galaxy S8 Native Linux Runtime Post-Boot Supervisor
After=network.target

[Service]
Type=oneshot
ExecStart=/run/s8/s8_postboot.sh
StandardOutput=append:/var/log/s8_postboot.log
StandardError=append:/var/log/s8_postboot.log

[Install]
WantedBy=multi-user.target
UNIT
"$BB" ln -sf /run/systemd/system/s8-postboot.service /run/systemd/system/multi-user.target.wants/s8-postboot.service

# Run optional firstboot seed script if present on newly flashed rootfs
if [ -x /opt/s8-seed/s8-firstboot.sh ] && [ ! -f /var/lib/s8-firstboot.done ]; then
    /bin/sh /opt/s8-seed/s8-firstboot.sh </dev/null >/var/log/guest_firstboot.log 2>&1 || true
    "$BB" mkdir -p /var/lib
    "$BB" touch /var/lib/s8-firstboot.done 2>/dev/null || true
fi

# 4. Mark native switch_root active and spawn persistent USB/DP/Button/DHCP/SSH daemons in switched '/'
"$BB" touch /run/s8/switched_root
if "$BB" ip link show rndis0 >/dev/null 2>&1; then
    "$BB" ip addr replace 192.168.7.2/24 dev rndis0 2>/dev/null || true
    "$BB" ip link set rndis0 up 2>/dev/null || true
fi

"$BB" touch /run/s8/udhcpd.leases
cat <<'DHCP' > /run/s8/udhcpd.conf
start 192.168.7.10
end 192.168.7.50
interface rndis0
lease_file /run/s8/udhcpd.leases
pidfile /run/s8/udhcpd.pid
option subnet 255.255.255.0
option lease 43200
DHCP
/run/s8/udhcpd -S /run/s8/udhcpd.conf </dev/null >/var/log/s8_udhcpd.log 2>&1 || true

[ -x /run/s8/s8_usb_agentd ] && /run/s8/s8_usb_agentd </dev/null >/var/log/s8_usb_agentd.log 2>&1 &
[ -x /run/s8/s8_dp_daemon ] && /run/s8/s8_dp_daemon </dev/null >/var/log/s8_dp_daemon.log 2>&1 &
[ -x /run/s8/s8_button_daemon ] && /run/s8/s8_button_daemon </dev/null >/var/log/s8_button_daemon.log 2>&1 &
[ -x /run/s8/s8_net_hotplug.sh ] && /run/s8/s8_net_hotplug.sh </dev/null >/var/log/s8_net_hotplug.log 2>&1 &
[ -x /run/s8/s8_serial_getty.sh ] && /run/s8/s8_serial_getty.sh </dev/null >/var/log/s8_serial_getty.log 2>&1 &

if [ -x /run/s8/s8-dropbear-arm64 ]; then
    "$BB" mkdir -p /run/s8/dropbear /mnt/android_data/linux/dropbear 2>/dev/null || true
    if [ -s /mnt/android_data/linux/dropbear/dropbear_ed25519_host_key ]; then
        "$BB" cp /mnt/android_data/linux/dropbear/dropbear_ed25519_host_key /run/s8/dropbear/ 2>/dev/null || true
    else
        /run/s8/dropbearkey -t ed25519 -f /run/s8/dropbear/dropbear_ed25519_host_key >/dev/null 2>&1 || true
        "$BB" cp /run/s8/dropbear/dropbear_ed25519_host_key /mnt/android_data/linux/dropbear/ 2>/dev/null || true
    fi
    if [ -x /usr/sbin/sshd ]; then
        /run/s8/dropbear -R -r /run/s8/dropbear/dropbear_ed25519_host_key -P /run/s8/dropbear.pid -p 192.168.7.2:2222 </dev/null >/var/log/s8_dropbear.log 2>&1 || true
    else
        /run/s8/dropbear -R -r /run/s8/dropbear/dropbear_ed25519_host_key -P /run/s8/dropbear.pid -p 192.168.7.2:22 </dev/null >/var/log/s8_dropbear.log 2>&1 || true
    fi
fi

# 5. Universal permissions, cgroup hierarchy (for non-systemd/Docker/HAOS/OpenWrt/Alpine) & PID 1 handoff
if [ -f /etc/group ]; then
    "$BB" grep -q ":3003:" /etc/group 2>/dev/null || echo "aid_inet:x:3003:root" >> /etc/group 2>/dev/null || true
    "$BB" grep -q ":3004:" /etc/group 2>/dev/null || echo "aid_net_raw:x:3004:root" >> /etc/group 2>/dev/null || true
    "$BB" grep -q ":3005:" /etc/group 2>/dev/null || echo "aid_net_admin:x:3005:root" >> /etc/group 2>/dev/null || true
    "$BB" grep -q ":1003:" /etc/group 2>/dev/null || echo "aid_graphics:x:1003:root" >> /etc/group 2>/dev/null || true
    "$BB" grep -q ":1005:" /etc/group 2>/dev/null || echo "aid_audio:x:1005:root" >> /etc/group 2>/dev/null || true
fi

INIT_BIN=""
for cand in /sbin/init /init /lib/systemd/systemd /usr/lib/systemd/systemd /etc/preinit /bin/init; do
    if [ -x "$cand" ] || [ -L "$cand" ]; then
        INIT_BIN="$cand"
        break
    fi
done

# Pre-mount cgroup v1 hierarchy if guest init is non-systemd (Alpine OpenRC, OpenWrt procd, custom init)
if [ ! -e /lib/systemd/systemd ] && [ ! -e /usr/lib/systemd/systemd ]; then
    "$BB" mkdir -p /sys/fs/cgroup 2>/dev/null || true
    "$BB" mountpoint -q /sys/fs/cgroup 2>/dev/null || "$BB" mount -t tmpfs -o mode=755 cgroup_root /sys/fs/cgroup 2>/dev/null || true
    for subsys in devices memory cpu cpuacct blkio freezer pids cpuset net_cls perf_event; do
        if "$BB" grep -qw "$subsys" /proc/cgroups 2>/dev/null; then
            "$BB" mkdir -p "/sys/fs/cgroup/$subsys" 2>/dev/null || true
            "$BB" mountpoint -q "/sys/fs/cgroup/$subsys" 2>/dev/null || "$BB" mount -t cgroup -o "$subsys" cgroup "/sys/fs/cgroup/$subsys" 2>/dev/null || true
        fi
    done
    "$BB" mkdir -p /sys/fs/cgroup/systemd 2>/dev/null || true
    "$BB" mountpoint -q /sys/fs/cgroup/systemd 2>/dev/null || "$BB" mount -t cgroup -o none,name=systemd systemd /sys/fs/cgroup/systemd 2>/dev/null || true
fi

if [ -n "$INIT_BIN" ]; then
    echo "Executing real PID 1: $INIT_BIN"
    echo 90 > /sys/class/timed_output/vibrator/enable 2>/dev/null || true
    exec </dev/null >/dev/null 2>&1
    exec "$INIT_BIN"
fi

# Fallback if rootfs had no init
while true; do
    "$BB" sleep 60
done
"""

PURE_LINUX_INIT = b"""#!/bin/sh
# Pure Native Linux AP Initramfs /init (GEMINI.md Rule 28 -- Zero Android /init)
export PATH=/run/s8:/sbin:/bin:/usr/sbin:/usr/bin
exec </dev/null >/dev/null 2>&1

/bin/busybox mkdir -p /proc /sys /dev /tmp /run /mnt_data /media/sdcard /newroot /var/log
/bin/busybox mount -t proc proc /proc 2>/dev/null || true
/bin/busybox mount -t sysfs sysfs /sys 2>/dev/null || true
/bin/busybox mount -t devtmpfs devtmpfs /dev 2>/dev/null || true
/bin/busybox mkdir -p /dev/pts /dev/shm /dev/block /dev/graphics
/bin/busybox mount -t devpts devpts /dev/pts 2>/dev/null || true
/bin/busybox mount -t tmpfs -o mode=1777,nosuid,nodev tmpfs /dev/shm 2>/dev/null || true
/bin/busybox mount -t tmpfs -o rw,nosuid,nodev,mode=755 tmpfs /run 2>/dev/null || true
/bin/busybox mount -t configfs none /sys/kernel/config 2>/dev/null || true
/bin/busybox mkdir -p /run/initramfs /run/s8 /run/s8/firmware /run/s8/wifi /run/s8/dropbear

exec </dev/null >/run/initramfs/init.log 2>&1
set -x

echo "=== Galaxy S8 Pure Native Linux AP Init (Rule 28) ==="
/bin/busybox cat /proc/version || true
/bin/busybox cat /proc/cmdline || true

# Early physical heartbeat (no OLED screen on chassis -> haptics + brief torch)
echo 120 > /sys/class/timed_output/vibrator/enable 2>/dev/null || true
echo 25 > /sys/class/leds/torch-sec1/brightness 2>/dev/null || true
/bin/busybox sleep 0.15
echo 0 > /sys/class/leds/torch-sec1/brightness 2>/dev/null || true

# 1. CRITICAL V4L2 FIMC-IS2 PANIC GUARD & Hardware Disconnect Fault-Tolerance (Rules 2 & 29)
echo 0 > /proc/sys/kernel/panic_on_oops 2>/dev/null || true
echo 5 > /proc/sys/kernel/panic 2>/dev/null || true
/bin/busybox rm -f /dev/video[1-9][0-9]* /dev/v4l-subdev* 2>/dev/null || true
for idx in 0 1 2; do
    if [ ! -c "/dev/graphics/fb${idx}" ]; then
        /bin/busybox rm -f "/dev/graphics/fb${idx}" 2>/dev/null || true
        /bin/busybox mknod "/dev/graphics/fb${idx}" c 29 "${idx}" 2>/dev/null || true
    fi
    if [ -c "/dev/graphics/fb${idx}" ]; then
        /bin/busybox ln -sf "/dev/graphics/fb${idx}" "/dev/fb${idx}" 2>/dev/null || true
    fi
done
/bin/busybox chmod 660 /dev/graphics/fb* 2>/dev/null || true
/bin/busybox chmod 666 /dev/ion /dev/mali0 /dev/ptmx 2>/dev/null || true

# 2. MAX77865 PMIC 1,500mA Fast-Charge & UVLO Unlock (Rule 3)
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

# 3. Cool-idle Exynos 8895 Interactive Governor & LZ4 ZRAM
for c in 0 4; do
    gov="/sys/devices/system/cpu/cpu${c}/cpufreq/scaling_governor"
    [ -w "$gov" ] && echo interactive > "$gov" 2>/dev/null || true
done
[ -b /dev/zram0 ] || /bin/busybox mknod /dev/zram0 b 253 0 2>/dev/null || true
if [ -b /dev/zram0 ] && ! /bin/busybox grep -q zram0 /proc/swaps 2>/dev/null; then
    echo lz4 > /sys/block/zram0/comp_algorithm 2>/dev/null || true
    echo 1610612736 > /sys/block/zram0/disksize 2>/dev/null || true
    /bin/busybox mkswap /dev/zram0 >/dev/null 2>&1 || true
    /bin/busybox swapon -p 100 /dev/zram0 2>/dev/null || true
fi

# 4. Stage static AP binaries & firmwares inside tmpfs /run/s8 (survives switch_root)
/bin/busybox cp /bin/busybox /run/s8/busybox
/bin/busybox chmod 755 /run/s8/busybox
for app in sh ash cat chmod chown cp dd df dmesg echo grep kill killall ln ls mkdir mknod mount umount mountpoint mv ps rm sed awk sleep sync touch udhcpd udhcpc ip ifconfig route getty losetup telnetd basename dirname switch_root; do
    /bin/busybox ln -sf /run/s8/busybox "/run/s8/$app"
done
for b in s8_dp_daemon s8_usb_agentd s8_button_daemon s8_net_hotplug.sh s8_udhcpc.script s8_pid1_boot.sh s8_postboot.sh s8_serial_shell.sh s8_serial_getty.sh s8-dropbear-arm64; do
    if [ -e "/sbin/$b" ]; then
        /bin/busybox cp -a "/sbin/$b" "/run/s8/$b"
        /bin/busybox chmod 755 "/run/s8/$b"
    fi
done
/bin/busybox ln -sf /run/s8/s8-dropbear-arm64 /run/s8/dropbear
/bin/busybox ln -sf /run/s8/s8-dropbear-arm64 /run/s8/dropbearkey
/bin/busybox ln -sf /run/s8/s8-dropbear-arm64 /run/s8/scp

[ -d /etc/firmware ] && /bin/busybox cp -a /etc/firmware/* /run/s8/firmware/ 2>/dev/null || true
[ -d /etc/firmware/wifi ] && /bin/busybox cp -a /etc/firmware/wifi/* /run/s8/wifi/ 2>/dev/null || true
if [ -f /run/s8/wifi/nvram.txt_r02j_b0 ] && [ ! -f /run/s8/wifi/nvram.txt ]; then
    /bin/busybox cp /run/s8/wifi/nvram.txt_r02j_b0 /run/s8/wifi/nvram.txt 2>/dev/null || true
fi
echo -n "/run/s8/firmware" > /sys/module/firmware_class/parameters/path 2>/dev/null || true
if [ -f /run/s8/wifi/bcmdhd_sta.bin_b0 ]; then
    echo -n "/run/s8/wifi/bcmdhd_sta.bin" > /sys/module/dhd/parameters/firmware_path 2>/dev/null || true
    echo -n "/run/s8/wifi/nvram.txt" > /sys/module/dhd/parameters/nvram_path 2>/dev/null || true
    echo -n "/run/s8/wifi/bcmdhd_clm.blob" > /sys/module/dhd/parameters/clm_path 2>/dev/null || true
fi

# 5. Pure Native Linux USB Composite ConfigFS Gadget (RNDIS 192.168.7.2 + CDC ACM COMx)
setup_usb_gadget() {
    G=/sys/kernel/config/usb_gadget/g1
    if [ "$(/bin/busybox cat "$G/UDC" 2>/dev/null)" = "10c00000.dwc3" ] && [ -d "$G/functions/rndis.usb0" ]; then
        return 0
    fi
    echo "" > "$G/UDC" 2>/dev/null || true
    /bin/busybox mkdir -p "$G/strings/0x409" "$G/configs/c.1/strings/0x409" "$G/functions/rndis.usb0" "$G/functions/acm.gs0"
    echo 0x1D6B > "$G/idVendor"
    echo 0x0104 > "$G/idProduct"
    echo 0xEF > "$G/bDeviceClass"
    echo 0x02 > "$G/bDeviceSubClass" 2>/dev/null || true
    echo 0x01 > "$G/bDeviceProtocol" 2>/dev/null || true
    SERIAL=$(/bin/busybox sed -n 's/.*androidboot.serialno=\\([^ ]*\\).*/\\1/p' /proc/cmdline 2>/dev/null)
    [ -z "$SERIAL" ] && SERIAL="ce10171ab3e9620804"
    echo "$SERIAL" > "$G/strings/0x409/serialnumber"
    echo "Samsung" > "$G/strings/0x409/manufacturer"
    echo "Galaxy S8 Native Linux" > "$G/strings/0x409/product"
    echo "RNDIS+ACM" > "$G/configs/c.1/strings/0x409/configuration"
    echo 250 > "$G/configs/c.1/MaxPower" 2>/dev/null || true

    echo 1 > "$G/os_desc/use" 2>/dev/null || true
    echo 0xcd > "$G/os_desc/b_vendor_code" 2>/dev/null || true
    echo "MSFT100" > "$G/os_desc/qw_sign" 2>/dev/null || true
    echo "RNDIS" > "$G/functions/rndis.usb0/os_desc/interface.rndis/compatible_id" 2>/dev/null || true
    echo "5162001" > "$G/functions/rndis.usb0/os_desc/interface.rndis/sub_compatible_id" 2>/dev/null || true
    /bin/busybox ln -sf "$G/configs/c.1" "$G/os_desc/c.1" 2>/dev/null || true

    /bin/busybox ln -sf "$G/functions/rndis.usb0" "$G/configs/c.1/rndis.usb0" 2>/dev/null || true
    /bin/busybox ln -sf "$G/functions/acm.gs0" "$G/configs/c.1/acm.gs0" 2>/dev/null || true
    echo "rndis,acm" > /sys/class/android_usb/android0/functions 2>/dev/null || echo "rndis" > /sys/class/android_usb/android0/functions 2>/dev/null || true
    echo "10c00000.dwc3" > "$G/UDC" 2>/dev/null || true
    echo 1 > /sys/class/android_usb/android0/enable 2>/dev/null || true

    for _w in 1 2 3 4 5 6 7 8 9 10; do
        /bin/busybox ip link show rndis0 >/dev/null 2>&1 && break
        /bin/busybox sleep 0.2
    done
    if /bin/busybox ip link show rndis0 >/dev/null 2>&1; then
        /bin/busybox ip addr replace 192.168.7.2/24 dev rndis0 2>/dev/null || true
        /bin/busybox ip link set rndis0 up 2>/dev/null || true
    fi
}

setup_usb_gadget

rescue_shell() {
    echo "=== [RESCUE] ENTERING NATIVE LINUX INITRAMFS SHELL ==="
    setup_usb_gadget
    /run/s8/touch /run/s8/udhcpd.leases
    cat <<'DHCP' > /run/s8/udhcpd.conf
start 192.168.7.10
end 192.168.7.50
interface rndis0
lease_file /run/s8/udhcpd.leases
pidfile /run/s8/udhcpd.pid
option subnet 255.255.255.0
option lease 43200
DHCP
    /run/s8/udhcpd -S /run/s8/udhcpd.conf </dev/null >/var/log/s8_udhcpd.log 2>&1 || true
    /run/s8/telnetd -l /run/s8/sh -p 2323 -b 127.0.0.1 </dev/null >/dev/null 2>&1 || true
    [ -x /run/s8/s8_usb_agentd ] && /run/s8/s8_usb_agentd </dev/null >/var/log/s8_usb_agentd.log 2>&1 &
    [ -x /run/s8/s8_dp_daemon ] && /run/s8/s8_dp_daemon </dev/null >/var/log/s8_dp_daemon.log 2>&1 &
    [ -x /run/s8/s8_button_daemon ] && /run/s8/s8_button_daemon </dev/null >/var/log/s8_button_daemon.log 2>&1 &
    [ -x /run/s8/s8_net_hotplug.sh ] && /run/s8/s8_net_hotplug.sh </dev/null >/var/log/s8_net_hotplug.log 2>&1 &
    [ -x /run/s8/s8_serial_getty.sh ] && /run/s8/s8_serial_getty.sh </dev/null >/var/log/s8_serial_getty.log 2>&1 &
    if [ -x /run/s8/s8-dropbear-arm64 ]; then
        /run/s8/dropbearkey -t ed25519 -f /run/s8/dropbear/dropbear_ed25519_host_key >/dev/null 2>&1 || true
        /run/s8/dropbear -R -B -r /run/s8/dropbear/dropbear_ed25519_host_key -P /run/s8/dropbear.pid -p 192.168.7.2:22 </dev/null >/var/log/s8_dropbear.log 2>&1 || true
    fi
    # 3 short pulses indicate rescue initramfs mode
    echo 100 > /sys/class/timed_output/vibrator/enable 2>/dev/null || true
    /bin/busybox sleep 0.35
    echo 100 > /sys/class/timed_output/vibrator/enable 2>/dev/null || true
    /bin/busybox sleep 0.35
    echo 100 > /sys/class/timed_output/vibrator/enable 2>/dev/null || true
    while true; do
        /run/s8/sleep 60
    done
}

# 6. Wait up to 10s for UFS USERDATA block device (/dev/sda24 / /dev/block/sda24)
DATA_DEV=""
for _i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
    for _cand in /dev/block/platform/11120000.ufs/by-name/USERDATA /dev/block/sda24 /dev/sda24; do
        if [ -b "$_cand" ]; then
            DATA_DEV="$_cand"
            break
        fi
    done
    [ -n "$DATA_DEV" ] && break
    if [ -r /sys/class/block/sda24/dev ]; then
        IFS=: read _maj _min < /sys/class/block/sda24/dev
        /bin/busybox mknod /dev/sda24 b "$_maj" "$_min" 2>/dev/null || true
        if [ -b /dev/sda24 ]; then
            DATA_DEV=/dev/sda24
            break
        fi
    fi
    /bin/busybox sleep 0.5
done

echo "DATA_DEV=$DATA_DEV"
[ -n "$DATA_DEV" ] || rescue_shell

# 7. Auto-heal & mount USERDATA + MicroSD
/sbin/e2fsck.static -p "$DATA_DEV" 2>/dev/null || /sbin/e2fsck.static -fy "$DATA_DEV" 2>/dev/null || true
/bin/busybox mount -t ext4 -o rw,noatime "$DATA_DEV" /mnt_data || rescue_shell
/bin/busybox mkdir -p /mnt_data/linux

if [ -b /dev/mmcblk0p1 ] || [ -b /dev/mmcblk0 ]; then
    MMC=/dev/mmcblk0
    [ -b /dev/mmcblk0p1 ] && MMC=/dev/mmcblk0p1
    /bin/busybox mount -t vfat -o rw,umask=000,iocharset=utf8 "$MMC" /media/sdcard 2>/dev/null || \
        /bin/busybox mount "$MMC" /media/sdcard 2>/dev/null || true
fi

# 8. Locate, fsck & mount target Linux rootfs (boot_target.conf -> UFS loop -> SD loop -> SD ext4 partition) -> /newroot
ROOT_TARGET=""
if [ -s /mnt_data/linux/boot_target.conf ]; then
    ROOT_TARGET=$(/bin/busybox sed -n 's/^TARGET=//p' /mnt_data/linux/boot_target.conf 2>/dev/null | /bin/busybox head -n 1)
fi
if [ -z "$ROOT_TARGET" ] || [ ! -e "$ROOT_TARGET" ]; then
    for _cand in /mnt_data/linux/rootfs.img /media/sdcard/linux/rootfs.img /dev/mmcblk0p2; do
        if [ -f "$_cand" ] || [ -b "$_cand" ]; then
            ROOT_TARGET="$_cand"
            break
        fi
    done
fi
if [ -z "$ROOT_TARGET" ]; then
    echo "No guest OS target found; starting rescue shell."
    rescue_shell
fi

echo "Selected ROOT_TARGET=$ROOT_TARGET"
/sbin/e2fsck.static -p "$ROOT_TARGET" 2>/dev/null || /sbin/e2fsck.static -fy "$ROOT_TARGET" 2>/dev/null || true

if [ -b "$ROOT_TARGET" ]; then
    /bin/busybox mount -t ext4 -o rw,noatime "$ROOT_TARGET" /newroot || rescue_shell
else
    [ -c /dev/loop-control ] || /bin/busybox mknod /dev/loop-control c 10 237 2>/dev/null || true
    [ -b /dev/loop0 ] || /bin/busybox mknod /dev/loop0 b 7 0 2>/dev/null || true
    /bin/busybox losetup -d /dev/loop0 2>/dev/null || true
    if /bin/busybox losetup /dev/loop0 "$ROOT_TARGET" 2>/dev/null; then
        /bin/busybox mount -t ext4 -o rw,noatime /dev/loop0 /newroot || rescue_shell
    else
        /bin/busybox mount -t ext4 -o rw,noatime,loop "$ROOT_TARGET" /newroot || rescue_shell
    fi
fi

# Verify a valid Linux init exists in /newroot (systemd, OpenRC/BusyBox, OpenWrt procd, or HAOS)
HAS_INIT=0
for cand in /newroot/sbin/init /newroot/init /newroot/lib/systemd/systemd /newroot/usr/lib/systemd/systemd /newroot/etc/preinit /newroot/bin/init; do
    if [ -e "$cand" ] || [ -L "$cand" ]; then
        HAS_INIT=1
        break
    fi
done
if [ "$HAS_INIT" -eq 0 ]; then
    echo "ERROR: No valid init found in $ROOT_TARGET"
    rescue_shell
fi

# 9. Prepare /newroot mountpoints, strip V4L2 nodes, preserve init log, move virtual FS & switch_root -> systemd PID 1
/bin/busybox mkdir -p /newroot/mnt/android_data /newroot/mnt/sdcard /newroot/media/sdcard /newroot/run /newroot/dev /newroot/proc /newroot/sys /newroot/var/log
/bin/busybox cp /run/initramfs/init.log /mnt_data/linux/initramfs.log 2>/dev/null || true
/bin/busybox cp /run/initramfs/init.log /newroot/var/log/s8_initramfs.log 2>/dev/null || true
/bin/busybox sync

/bin/busybox mount -o move /mnt_data /newroot/mnt/android_data || /bin/busybox mount -o bind /mnt_data /newroot/mnt/android_data || true
if /bin/busybox mountpoint -q /media/sdcard 2>/dev/null; then
    /bin/busybox mount -o move /media/sdcard /newroot/media/sdcard 2>/dev/null || true
    /bin/busybox mount -o bind /newroot/media/sdcard /newroot/mnt/sdcard 2>/dev/null || true
fi

/bin/busybox rm -f /dev/video[1-9][0-9]* /dev/v4l-subdev* 2>/dev/null || true

echo "=== Handing off to /run/s8/s8_pid1_boot.sh -> systemd PID 1 via switch_root ==="
exec </dev/null >/dev/null 2>&1
/bin/busybox umount /sys/kernel/config 2>/dev/null || true
/bin/busybox umount /dev/pts 2>/dev/null || true
/bin/busybox umount /dev/shm 2>/dev/null || true

/bin/busybox mount -o move /run /newroot/run
/bin/busybox mount -o move /dev /newroot/dev
/bin/busybox mount -o move /proc /newroot/proc
/bin/busybox mount -o move /sys /newroot/sys
[ -c /newroot/dev/null ] || /bin/busybox mknod -m 666 /newroot/dev/null c 1 3 2>/dev/null || true
[ -c /newroot/dev/console ] || /bin/busybox mknod -m 600 /newroot/dev/console c 5 1 2>/dev/null || true

exec /bin/busybox switch_root -c /dev/null /newroot /run/s8/s8_pid1_boot.sh
rescue_shell
"""


def align_up(val: int, align: int) -> int:
    return (val + align - 1) & ~(align - 1)


def make_cpio_entry(
    filename: str,
    data: bytes = b"",
    mode: int = 0o100644,
    ino: int = 200,
    rdevmajor: int = 0,
    rdevminor: int = 0,
) -> bytes:
    name_bytes = filename.encode("ascii") + b"\x00"
    filesize = len(data)
    header = (
        f"070701{ino:08X}{mode:08X}{0:08X}{0:08X}{1:08X}{0:08X}"
        f"{filesize:08X}{0:08X}{0:08X}{rdevmajor:08X}{rdevminor:08X}{len(name_bytes):08X}{0:08X}"
    ).encode("ascii")
    entry = bytearray(header)
    entry.extend(name_bytes)
    entry.extend(b"\x00" * (align_up(len(entry), 4) - len(entry)))
    entry.extend(data)
    entry.extend(b"\x00" * (align_up(len(entry), 4) - len(entry)))
    return bytes(entry)


def build_pure_linux_cpio() -> bytes:
    out = bytearray()
    ino = 100

    def next_ino() -> int:
        nonlocal ino
        ino += 1
        return ino

    # 1. Pure native Linux filesystem hierarchy (zero Android directories/files)
    dirs = [
        "bin", "sbin", "etc", "etc/firmware", "etc/firmware/wifi",
        "vendor", "vendor/firmware", "lib", "usr", "usr/bin", "usr/sbin",
        "proc", "sys", "sys/kernel", "sys/kernel/config",
        "dev", "dev/pts", "dev/shm", "dev/block", "dev/graphics",
        "tmp", "run", "mnt_data", "media", "media/sdcard", "newroot",
        "root", "root/.ssh", "var", "var/log",
    ]
    for d in dirs:
        mode = 0o041777 if d == "tmp" else (0o040700 if d.startswith("root") else 0o040755)
        out.extend(make_cpio_entry(d, b"", mode=mode, ino=next_ino()))

    # 2. Essential character & block device nodes needed before devtmpfs/systemd handoff
    dev_nodes = [
        ("dev/console", 0o020600, 5, 1),
        ("dev/null", 0o020666, 1, 3),
        ("dev/tty", 0o020666, 5, 0),
        ("dev/loop-control", 0o020600, 10, 237),
        ("dev/loop0", 0o060600, 7, 0),
        ("dev/loop1", 0o060600, 7, 1),
    ]
    for path, mode, maj, mn in dev_nodes:
        out.extend(make_cpio_entry(path, b"", mode=mode, ino=next_ino(), rdevmajor=maj, rdevminor=mn))

    # 3. Minimal POSIX /etc identity files for BusyBox & Dropbear rescue SSH
    etc_files = [
        ("etc/passwd", b"root:x:0:0:root:/root:/bin/sh\n"),
        ("etc/group", b"root:x:0:\n"),
        ("etc/shells", b"/bin/sh\n/bin/ash\n/bin/bash\n/run/s8/sh\n"),
        ("etc/nsswitch.conf", b"passwd: files\ngroup: files\nhosts: files dns\n"),
        ("etc/s8-ap-version", f"{AP_VERSION}\n".encode("ascii")),
    ]
    for path, data in etc_files:
        out.extend(make_cpio_entry(path, data, mode=0o100644, ino=next_ino()))

    # 4. Static BusyBox + applet symlinks
    if not STATIC_BB.is_file():
        raise FileNotFoundError(f"Static busybox not found: {STATIC_BB}")
    bb_bytes = STATIC_BB.read_bytes()
    out.extend(make_cpio_entry("bin/busybox", bb_bytes, mode=0o100755, ino=next_ino()))
    print(f"  + Embedded bin/busybox ({len(bb_bytes):,} B)")

    for app in BUSYBOX_BIN_APPLETS:
        out.extend(make_cpio_entry(f"bin/{app}", b"busybox", mode=0o120777, ino=next_ino()))
    for app in BUSYBOX_SBIN_APPLETS:
        out.extend(make_cpio_entry(f"sbin/{app}", b"/bin/busybox", mode=0o120777, ino=next_ino()))

    # 5. Static ARM64 AP binaries (zero dynamic shared-library dependencies)
    if E2FSCK_STATIC.is_file():
        data = E2FSCK_STATIC.read_bytes()
        out.extend(make_cpio_entry("sbin/e2fsck.static", data, mode=0o100755, ino=next_ino()))
        out.extend(make_cpio_entry("sbin/fsck.ext4", b"e2fsck.static", mode=0o120777, ino=next_ino()))
        print(f"  + Embedded sbin/e2fsck.static ({len(data):,} B)")
    else:
        raise FileNotFoundError(f"Static e2fsck not found: {E2FSCK_STATIC}")

    for src_bin, dst_name in [
        (BUTTON_DAEMON, "sbin/s8_button_daemon"),
        (DP_DAEMON, "sbin/s8_dp_daemon"),
        (USB_AGENTD, "sbin/s8_usb_agentd"),
        (DROPBEAR_BIN, "sbin/s8-dropbear-arm64"),
    ]:
        if src_bin.is_file():
            data = src_bin.read_bytes()
            out.extend(make_cpio_entry(dst_name, data, mode=0o100755, ino=next_ino()))
            print(f"  + Embedded {dst_name} ({len(data):,} B)")
        else:
            print(f"  [!] Optional binary missing: {src_bin}")

    # 6. Pure Native Linux `/init` and runtime supervisor scripts
    scripts = [
        ("init", PURE_LINUX_INIT),
        ("sbin/s8_pid1_boot.sh", S8_PID1_BOOT_SCRIPT),
        ("sbin/s8_postboot.sh", S8_POSTBOOT_SCRIPT),
        ("sbin/s8_serial_shell.sh", S8_SERIAL_SHELL_SCRIPT),
        ("sbin/s8_serial_getty.sh", S8_SERIAL_GETTY_SCRIPT),
        ("sbin/s8_net_hotplug.sh", S8_NET_HOTPLUG_SCRIPT),
        ("sbin/s8_udhcpc.script", S8_UDHCPC_SCRIPT),
    ]
    for path, content in scripts:
        out.extend(make_cpio_entry(path, content, mode=0o100755, ino=next_ino()))

    # 7. Calliope 9 DSP Audio Firmwares (etc/firmware + vendor/firmware symlinks)
    for fw in ALL_FIRMWARES:
        fw_path = WORKSPACE / "scratch" / fw
        if not fw_path.is_file():
            fw_path = AP_PREBUILT / "etc" / "firmware" / fw
        if not fw_path.is_file():
            raise FileNotFoundError(f"Required Calliope firmware missing: {fw_path}")
        out.extend(make_cpio_entry(f"etc/firmware/{fw}", fw_path.read_bytes(), mode=0o100644, ino=next_ino()))
        out.extend(make_cpio_entry(f"vendor/firmware/{fw}", f"/etc/firmware/{fw}".encode("ascii"), mode=0o120777, ino=next_ino()))

    # 8. Optional Broadcom BCM4361 Wi-Fi firmwares staged under etc/firmware/wifi/
    for wfw in WIFI_FW_FILES:
        wp = WIFI_FW_DIR / wfw
        if wp.is_file():
            data = wp.read_bytes()
            out.extend(make_cpio_entry(f"etc/firmware/wifi/{wfw}", data, mode=0o100644, ino=next_ino()))
            print(f"  + Embedded etc/firmware/wifi/{wfw} ({len(data):,} B)")

    out.extend(make_cpio_entry("TRAILER!!!", b"", mode=0, ino=0))
    out.extend(b"\x00" * (align_up(len(out), 512) - len(out)))
    return bytes(out)


def build_ap(kernel_path: Path = DEFAULT_KERNEL):
    if not kernel_path.is_file():
        raise FileNotFoundError(f"Kernel image not found: {kernel_path}")
    if not SRC_TAR.is_file():
        raise FileNotFoundError(f"Hardware boot header/DTB source tar not found: {SRC_TAR}")

    with tarfile.open(SRC_TAR, "r") as t:
        boot_bytes = t.extractfile("boot.img").read()

    magic, k_size, _, r_size, _, s_size, _, _, page_size, dt_size, _ = struct.unpack(
        "<8s10I", boot_bytes[:48]
    )
    assert magic == b"ANDROID!", "Base boot.img magic mismatch"

    k_off = page_size
    r_off = k_off + align_up(k_size, page_size)
    s_off = r_off + align_up(r_size, page_size)
    dt_off = s_off + align_up(s_size, page_size)

    kernel_blob = kernel_path.read_bytes()
    second_blob = boot_bytes[s_off:s_off + s_size] if s_size > 0 else b""
    dt_blob = boot_bytes[dt_off:dt_off + dt_size] if dt_size > 0 else b""

    print("[*] Building 100% pure native Linux initramfs (Rule 28: zero Android init/rc/sepolicy)...")
    new_cpio = build_pure_linux_cpio()
    new_ramdisk = lzma.compress(
        new_cpio,
        format=lzma.FORMAT_ALONE,
        filters=[{"id": lzma.FILTER_LZMA1, "preset": 9}],
    )

    new_header = bytearray(boot_bytes[:page_size])
    new_cmdline = b"console=null androidboot.selinux=permissive\x00"
    new_header[64:64 + 512] = new_cmdline + b"\x00" * (512 - len(new_cmdline))
    struct.pack_into("<I", new_header, 8, len(kernel_blob))
    struct.pack_into("<I", new_header, 16, len(new_ramdisk))

    out = bytearray(new_header)
    out.extend(kernel_blob)
    out.extend(b"\x00" * (align_up(len(out), page_size) - len(out)))
    out.extend(new_ramdisk)
    out.extend(b"\x00" * (align_up(len(out), page_size) - len(out)))
    if s_size > 0:
        out.extend(second_blob)
        out.extend(b"\x00" * (align_up(len(out), page_size) - len(out)))
    if dt_size > 0:
        out.extend(dt_blob)
        out.extend(b"\x00" * (align_up(len(out), page_size) - len(out)))
    out.extend(b"SEANDROIDENFORCE")

    total_len = len(out)
    print(
        f"[*] Kernel: {len(kernel_blob):,} B | Pure Linux CPIO: {len(new_cpio):,} B -> LZMA: {len(new_ramdisk):,} B | DTB: {dt_size:,} B"
    )
    print(f"[*] Total {OUT_BOOT.name}: {total_len:,} B ({total_len / (1024 * 1024):.2f} MiB)")
    assert total_len <= SDA7_HARD_LIMIT, f"FATAL: Exceeds sda7 hard limit ({SDA7_HARD_LIMIT:,} B)!"
    if total_len > SAFE_TARGET_CEILING:
        print(f"[!] WARNING: Exceeds safe target ceiling ({SAFE_TARGET_CEILING:,} B)")

    OUT_BOOT.parent.mkdir(parents=True, exist_ok=True)
    OUT_BOOT.write_bytes(bytes(out))

    for tar_path in (OUT_ODIN_RELEASE, OUT_ODIN_HISTORY):
        tar_path.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(tar_path, "w", format=tarfile.USTAR_FORMAT) as tf:
            tf.add(OUT_BOOT, arcname="boot.img")
            tf.add(OUT_BOOT, arcname="recovery.img")
        print(f"[+] Packaged Odin AP tar: {tar_path} ({tar_path.stat().st_size:,} B)")


def verify_ap():
    with tarfile.open(OUT_ODIN_RELEASE, "r") as tf:
        boot_data = tf.extractfile("boot.img").read()
    magic, k_size, _, r_size, _, _, _, _, page_size, dt_size, _ = struct.unpack("<8s10I", boot_data[:48])
    assert magic == b"ANDROID!"
    assert len(boot_data) <= SDA7_HARD_LIMIT
    r_off = page_size + align_up(k_size, page_size)
    cpio_data = lzma.decompress(boot_data[r_off:r_off + r_size])

    for req in (
        b"#!/bin/sh",
        b"switch_root",
        b"s8_pid1_boot.sh",
        b"systemd",
        b"10c00000.dwc3",
        b"rndis.usb0",
        b"acm.gs0",
        b"s8_net_hotplug.sh",
        b"s8_udhcpc.script",
        b"s8_dp_daemon",
        b"s8_usb_agentd",
        b"s8_button_daemon",
        b"s8-dropbear-arm64",
        b"e2fsck.static",
        b"calliope_sram.bin",
        b"calliope_dram.bin",
        b"calliope_iva.bin",
    ):
        assert req in cpio_data, f"Missing required native Linux AP asset: {req!r}"

    for forbidden in (
        b"service ubuntu_boot",
        b"service s8_ap_boot",
        b"mount -o bind /system_root/vendor/firmware",
        b"sepolicy",
        b"ueventd.rc",
        b"on property:sys.usb.ffs.ready",
    ):
        assert forbidden not in cpio_data, f"Forbidden legacy/Android artifact present: {forbidden!r}"

    print("[PASS] Pure native Linux AP verification complete: systemd PID 1 handoff, zero Android init/rc/sepolicy.")


if __name__ == "__main__":
    k_arg = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_KERNEL
    build_ap(k_arg)
    verify_ap()
