#!/sbin/sh
# ==============================================================================
# Galaxy S8 (SM-G950N) Native Ubuntu 24.04.5 LTS Master Service Supervisor
# ==============================================================================
export PATH=/sbin:/system/bin:/system/xbin:/vendor/bin

# CRITICAL CGROUP ESCAPE:
# Android init's libprocessgroup kills all child processes in the set_permissive
# cgroup (/acct/uid_0/pid_*) when the service finishes.
# Writing PID to /acct/tasks moves the supervisor to the root cgroup so all
# spawned daemons (sshd, Xtigervnc, websockify, GNOME, exynos_dp_bridge) are IMMUNE.
echo $$ > /acct/tasks 2>/dev/null || true

# CRITICAL USB ADB ENUMERATION:
# Enforce sys.usb.config=adb so Android init's configfs binds UDC to 10c00000.dwc3
if [ -x /sbin/setprop ]; then
    /sbin/setprop sys.usb.config adb 2>/dev/null || true
elif [ -x /proc/1/root/sbin/setprop ]; then
    chroot /proc/1/root /sbin/setprop sys.usb.config adb 2>/dev/null || true
fi

# Enforce full permissions on /sbin for adb shell
chmod 755 /sbin /sbin/* 2>/dev/null || true
if [ -d /proc/1/root/sbin ]; then
    chmod 755 /proc/1/root/sbin /proc/1/root/sbin/* 2>/dev/null || true
fi

echo "=== [1/6] Unlocking MAX77865 PMIC Charger (1500mA Input/Fast Charge) & V4L2 Panic Guard ==="
# CRITICAL EXYNOS 8895 KERNEL PANIC GUARD:
# Samsung's fimc_is_ixs_video_querycap() dereferences NULL in kernel mode if GStreamer
# (gst-plugin-scanner / pipewire / nautilus / webkit) calls VIDIOC_QUERYCAP on /dev/video100+.
# Remove the uninitialized fimc_is /dev/video100+ nodes while keeping MFC hardware codecs (/dev/video6..9).
rm -f /dev/video[1-9][0-9]* /dev/v4l-subdev* 2>/dev/null || true

echo "0xBD 0x6C" > /sys/class/power_supply/max77865-charger/data 2>/dev/null || true
echo "0xC3 0x61" > /sys/class/power_supply/max77865-charger/data 2>/dev/null || true
echo "0xC0 0x3C" > /sys/class/power_supply/max77865-charger/data 2>/dev/null || true
echo "0xB9 0x9E" > /sys/class/power_supply/max77865-charger/data 2>/dev/null || true
echo "0xB7 0x05" > /sys/class/power_supply/max77865-charger/data 2>/dev/null || true
echo 1500 > /sys/class/power_supply/battery/batt_tune_input_charge_current 2>/dev/null || true
echo 1500 > /sys/class/power_supply/battery/batt_tune_fast_charge_current 2>/dev/null
# Enable IPv4 forwarding for Docker & CasaOS containers
echo 1 > /proc/sys/net/ipv4/ip_forward 2>/dev/null || true
echo 0 > /sys/class/power_supply/battery/batt_slate_mode 2>/dev/null || true

BATT_CAP=$(cat /sys/class/power_supply/battery/capacity 2>/dev/null || echo 50)
if [ "$BATT_CAP" -lt 20 ]; then
    echo "Battery at ${BATT_CAP}% — parking big cluster CPU5..7 and capping CPU4 to 741 MHz for fast charging..."
    echo 741000 > /sys/devices/system/cpu/cpu4/cpufreq/scaling_max_freq 2>/dev/null || true
    for c in 5 6 7; do
        echo 0 > /sys/devices/system/cpu/cpu${c}/online 2>/dev/null || true
    done
fi

echo "=== [2/6] Mounting Ubuntu 24.04.5 LTS Rootfs (/data/linux/rootfs.img) ==="
# DYNAMIC STORAGE EXPANSION (64 GB vs 128 GB UFS Variants):
# Automatically expands the ext4 filesystem on /dev/block/sda24 (USERDATA) to 100% of the
# physical flash capacity. Adapts transparently from 54.8 GB on 64 GB models to ~112 GB
# on 128 GB models (SM-G955N / SM-G9550 Emperor Edition).
/sbin/resize2fs /dev/block/sda24 2>/dev/null || true

mkdir -p /mnt/ubuntu
if ! mountpoint -q /mnt/ubuntu; then
    if [ -f /data/linux/rootfs.img ]; then
        # CRITICAL FAIL-SAFE: Self-healing dirty journal replay across sudden power cuts / battery disconnects
        /sbin/e2fsck -p -y /data/linux/rootfs.img 2>/dev/null || true
        losetup /dev/block/loop0 /data/linux/rootfs.img 2>/dev/null || true
        mount -t ext4 -o rw,noatime /dev/block/loop0 /mnt/ubuntu 2>/dev/null || mount -t ext4 -o loop,rw,noatime /data/linux/rootfs.img /mnt/ubuntu
    else
        mount -t ext4 -o rw,noatime /dev/block/sda17 /mnt/ubuntu 2>/dev/null || true
    fi
fi

mkdir -p /mnt/ubuntu/proc /mnt/ubuntu/sys /mnt/ubuntu/dev /mnt/ubuntu/dev/pts /mnt/ubuntu/dev/shm /mnt/ubuntu/run /mnt/ubuntu/run/dbus /mnt/ubuntu/run/user/0 /mnt/ubuntu/tmp/.X11-unix /mnt/ubuntu/var/log /mnt/ubuntu/var/log/gnome_apps
chmod 700 /mnt/ubuntu/run/user/0
chmod 1777 /mnt/ubuntu/tmp /mnt/ubuntu/tmp/.X11-unix /mnt/ubuntu/dev/shm

mountpoint -q /mnt/ubuntu/proc || mount -t proc proc /mnt/ubuntu/proc
mountpoint -q /mnt/ubuntu/sys || mount -t sysfs sysfs /mnt/ubuntu/sys
mountpoint -q /mnt/ubuntu/dev || mount -o bind /dev /mnt/ubuntu/dev
mountpoint -q /mnt/ubuntu/dev/pts || mount -t devpts devpts /mnt/ubuntu/dev/pts
mountpoint -q /mnt/ubuntu/dev/shm || mount -t tmpfs -o size=512M tmpfs /mnt/ubuntu/dev/shm
mkdir -p /mnt/ubuntu/sys/kernel/config
mountpoint -q /mnt/ubuntu/sys/kernel/config || mount -o bind /sys/kernel/config /mnt/ubuntu/sys/kernel/config 2>/dev/null || true

# Expose standard Linux framebuffer (/dev/fb0 -> DisplayPort /dev/graphics/fb2)
ln -sf /dev/graphics/fb2 /dev/fb0 2>/dev/null || true
ln -sf /dev/graphics/fb2 /mnt/ubuntu/dev/fb0 2>/dev/null || true

# Bind high-speed 43GB UFS 2.1 data partition & activate swap
mkdir -p /mnt/ubuntu/mnt/android_data
mountpoint -q /mnt/ubuntu/mnt/android_data || mount -o bind /data /mnt/ubuntu/mnt/android_data 2>/dev/null || true
if [ -f /data/swapfile ]; then
    swapon /data/swapfile 2>/dev/null || true
fi

# Auto-detect and mount MicroSD Card (/dev/block/mmcblk0)
if [ -b /dev/block/mmcblk0 ]; then
    echo "=== Auto-mounting MicroSD Card (/dev/block/mmcblk0) ==="
    mkdir -p /mnt/ubuntu/media/sdcard /mnt/ubuntu/mnt/sdcard /mnt/ubuntu/mnt/android_data/sdcard /data/sdcard
    MMC_DEV=/dev/block/mmcblk0
    if [ -b /dev/block/mmcblk0p1 ]; then
        MMC_DEV=/dev/block/mmcblk0p1
    fi
    mount -t vfat -o rw,umask=000,iocharset=utf8 $MMC_DEV /mnt/ubuntu/media/sdcard 2>/dev/null || mount $MMC_DEV /mnt/ubuntu/media/sdcard 2>/dev/null || true
    mount --bind /mnt/ubuntu/media/sdcard /mnt/ubuntu/mnt/sdcard 2>/dev/null || true
    mount --bind /mnt/ubuntu/media/sdcard /mnt/ubuntu/mnt/android_data/sdcard 2>/dev/null || true
    mount --bind /mnt/ubuntu/media/sdcard /data/sdcard 2>/dev/null || true
fi

echo "=== [3/6] Connecting Broadcom BCM4361 Wi-Fi (<WIFI_SSID>) in Background ==="
if [ -f /data/linux/connect_wifi.sh ]; then
    /sbin/sh /data/linux/connect_wifi.sh </dev/null >/data/linux/wifi.log 2>&1 &
fi

echo "=== [4/6] Installing Hardware Tools (s8ctl + exynos_dp_bridge + start_ubuntu_desktop) ==="
mkdir -p /mnt/ubuntu/usr/local/bin /mnt/ubuntu/usr/local/src /mnt/ubuntu/var/log/gnome_apps
if [ -f /data/linux/start_ubuntu_desktop.sh ]; then
    cp /data/linux/start_ubuntu_desktop.sh /mnt/ubuntu/usr/local/bin/start_ubuntu_desktop.sh
    chmod +x /mnt/ubuntu/usr/local/bin/start_ubuntu_desktop.sh
fi
if [ -f /data/linux/s8ctl.py ]; then
    cp /data/linux/s8ctl.py /mnt/ubuntu/usr/local/bin/s8ctl
    chmod +x /mnt/ubuntu/usr/local/bin/s8ctl
fi
if [ -f /data/linux/s8_typec_daemon.py ]; then
    cp /data/linux/s8_typec_daemon.py /mnt/ubuntu/usr/local/bin/s8_typec_daemon.py
    chmod +x /mnt/ubuntu/usr/local/bin/s8_typec_daemon.py
fi
if [ -f /data/linux/exynos_dp_bridge.c ]; then
    cp /data/linux/exynos_dp_bridge.c /mnt/ubuntu/usr/local/src/exynos_dp_bridge.c
fi
if [ -f /data/linux/init_audio.sh ]; then
    cp /data/linux/init_audio.sh /mnt/ubuntu/usr/local/bin/init_audio.sh
    chmod +x /mnt/ubuntu/usr/local/bin/init_audio.sh
fi
if [ -f /data/linux/asound.conf ]; then
    cp /data/linux/asound.conf /mnt/ubuntu/etc/asound.conf
fi

echo "=== [5/6] Starting Ubuntu 24.04.5 LTS Services & GNOME 46 macOS Sonoma Desktop ==="
CHROOT_SHELL=/bin/sh
[ -x /mnt/ubuntu/bin/bash ] && CHROOT_SHELL=/bin/bash
chroot /mnt/ubuntu $CHROOT_SHELL -c "
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export HOME=/root
export USER=root
export LANG=C.UTF-8
export LC_ALL=C.UTF-8
export DISPLAY=:1

# 1. Start D-Bus system daemon
rm -f /run/dbus/pid
dbus-daemon --system --fork </dev/null >/dev/null 2>&1 || true

# 2. Start OpenSSH Server (:22)
mkdir -p /run/sshd
if ! pgrep -x sshd >/dev/null 2>&1; then
    /usr/sbin/sshd -E /var/log/sshd.log </dev/null >/dev/null 2>&1 || true
fi

# 2b. Initialize Native ALSA Audio Hardware (Speaker & DMIC1 Mic)
if [ -x /usr/local/bin/init_audio.sh ]; then
    /usr/local/bin/init_audio.sh </dev/null >/var/log/init_audio.log 2>&1 || true
fi

# 3. Compile Exynos 8895 USB-C DisplayPort / HDMI Bridge if gcc is installed
if [ -f /usr/local/src/exynos_dp_bridge.c ] && command -v gcc >/dev/null 2>&1; then
    gcc -O3 /usr/local/src/exynos_dp_bridge.c -o /usr/local/bin/exynos_dp_bridge -lX11 -lXext -lXfixes 2>/dev/null || true
    chmod +x /usr/local/bin/exynos_dp_bridge 2>/dev/null || true
fi

# 4. Start TigerVNC X11 Server (:1 -> port 5901, 1920x1080 24-bit)
mkdir -p /root/.vnc
if [ ! -f /root/.vnc/passwd ]; then
    echo ubuntu | vncpasswd -f > /root/.vnc/passwd
    chmod 600 /root/.vnc/passwd
fi

if ! pgrep -x Xtigervnc >/dev/null 2>&1; then
    rm -f /tmp/.X1-lock /tmp/.X11-unix/X1
    Xtigervnc :1 -geometry 1920x1080 -depth 24 -rfbport 5901 -PasswordFile /root/.vnc/passwd -AlwaysShared -AcceptKeyEvents -AcceptPointerEvents -SecurityTypes VncAuth </dev/null >/var/log/Xtigervnc.log 2>&1 &
    sleep 2
fi

# 5. Launch Desktop Session (Debian PIXEL / Ubuntu GNOME)
if [ -x /usr/local/bin/start_debian_desktop.sh ]; then
    /usr/local/bin/start_debian_desktop.sh </dev/null >/var/log/start_debian_desktop.log 2>&1
elif [ -x /usr/local/bin/start_ubuntu_desktop.sh ]; then
    /usr/local/bin/start_ubuntu_desktop.sh </dev/null >/var/log/start_ubuntu_desktop.log 2>&1
fi

# 6. Start Nginx (:6080) & Pure Websockify (:6081 -> 127.0.0.1:5901)
if ! pgrep -x nginx >/dev/null 2>&1; then
    nginx </dev/null >/var/log/nginx.log 2>&1 || true
fi
if ! pgrep -f 'websockify.*6081' >/dev/null 2>&1; then
    python3 /usr/bin/websockify -D --log-file=/var/log/websockify.log 6081 127.0.0.1:5901 || true
fi

# 7. Exynos USB-C DisplayPort Daemon (always active in background waiting safely for HPD)
if [ -x /usr/local/bin/exynos_dp_bridge ] && ! pgrep -x exynos_dp_bridge >/dev/null 2>&1; then
    nohup /usr/local/bin/exynos_dp_bridge </dev/null >/var/log/exynos_dp_bridge.log 2>&1 &
fi

# 7a. Galaxy S8 Type-C Multi-Role & Hotplug Daemon (PC vs Display vs USB OTG storage/inputs)
if [ -x /usr/local/bin/s8_typec_daemon.py ] && ! pgrep -f s8_typec_daemon.py >/dev/null 2>&1; then
    (while true; do python3 /usr/local/bin/s8_typec_daemon.py; sleep 2; done) </dev/null >/var/log/s8_typec_daemon.log 2>&1 &
fi

# 7b. Start USB Input Event Bridge (Mouse & Keyboard -> X11 :1 Supervised)
if [ -x /usr/local/bin/s8_input_bridge ] && ! pgrep -x s8_input_bridge >/dev/null 2>&1; then
    (while true; do /usr/local/bin/s8_input_bridge; sleep 1; done) </dev/null >/var/log/s8_input_bridge.log 2>&1 &
fi

# 7c. Start Physical Chassis Button Supervisor (Power, VolUp, VolDown, Bixby)
if [ -x /usr/local/bin/s8_button_daemon ] && ! pgrep -x s8_button_daemon >/dev/null 2>&1; then
    (while true; do /usr/local/bin/s8_button_daemon; sleep 1; done) </dev/null >/var/log/s8_button_daemon.log 2>&1 &
fi

# 7d. Start S8 macOS Control Center & Wi-Fi Tray Indicator
if [ -f /usr/local/bin/s8_status_icon.py ] && ! pgrep -f s8_status_icon >/dev/null 2>&1; then
    (while true; do python3 /usr/local/bin/s8_status_icon.py; sleep 2; done) </dev/null >/var/log/s8_status_icon.log 2>&1 &
fi

# 7e. Start Broadcom BCM4361 Native Bluetooth (BlueZ)
if [ -x /usr/local/bin/start_bluetooth.sh ]; then
    /usr/local/bin/start_bluetooth.sh </dev/null >/var/log/bluetooth_boot.log 2>&1 &
fi

# 8. Start Native Docker Engine (overlay2 + bridge + iptables)
if command -v dockerd >/dev/null 2>&1 && ! pgrep -x dockerd >/dev/null 2>&1; then
    /usr/local/bin/mount_cgroups.sh </dev/null >/dev/null 2>&1 || true
    update-alternatives --set iptables /usr/sbin/iptables-legacy 2>/dev/null || true
    update-alternatives --set ip6tables /usr/sbin/ip6tables-legacy 2>/dev/null || true
    nohup dockerd </dev/null >/var/log/dockerd.log 2>&1 &
fi

# 9. Start CasaOS Personal Cloud Ecosystem
if [ -x /usr/local/bin/start_casaos.sh ]; then
    (sleep 5; /usr/local/bin/start_casaos.sh) </dev/null >/var/log/casaos_boot.log 2>&1 &
fi

# 10. Start Hardware Sensor Supervisor & Standard Linux Emulation Daemon
if [ -x /usr/local/bin/s8_sensor_daemon ] && ! pgrep -f s8_sensor_daemon >/dev/null 2>&1; then
    /usr/bin/python3 /usr/local/bin/s8_sensor_daemon </dev/null >/var/log/s8_sensor_daemon.log 2>&1 &
fi

"

echo "=== [6/6] Signaling Headless Ready (Double Haptic Vibration) ==="
echo 150 > /sys/class/timed_output/vibrator/enable 2>/dev/null || true
sleep 1
echo 150 > /sys/class/timed_output/vibrator/enable 2>/dev/null || true
echo "Ubuntu 24.04.5 LTS + GNOME 46 macOS Sonoma Desktop Ready!"
