#!/sbin/sh
# ==============================================================================
# Galaxy S8 (SM-G950N) Native Ubuntu 24.04.5 LTS Master Service Supervisor
# ==============================================================================
export PATH=/sbin:/system/bin:/system/xbin:/vendor/bin

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
echo 1500 > /sys/class/power_supply/battery/batt_tune_fast_charge_current 2>/dev/null || true
echo 0 > /sys/class/power_supply/battery/batt_slate_mode 2>/dev/null || true

BATT_CAP=$(cat /sys/class/power_supply/battery/capacity 2>/dev/null || echo 50)
if [ "$BATT_CAP" -lt 20 ]; then
    echo "Battery at ${BATT_CAP}% — parking big cluster CPU5..7 and capping CPU4 to 741 MHz for fast charging..."
    echo 741000 > /sys/devices/system/cpu/cpu4/cpufreq/scaling_max_freq 2>/dev/null || true
    for c in 5 6 7; do
        echo 0 > /sys/devices/system/cpu/cpu${c}/online 2>/dev/null || true
    done
fi

echo "=== [2/6] Connecting Broadcom BCM4361 Wi-Fi (<WIFI_SSID>) in Background ==="
if [ -f /data/linux/connect_wifi.sh ]; then
    /sbin/sh /data/linux/connect_wifi.sh </dev/null >/data/linux/wifi.log 2>&1 &
fi

echo "=== [3/6] Mounting Ubuntu 24.04.5 LTS Rootfs (/data/linux/rootfs.img) ==="
mkdir -p /mnt/ubuntu
if ! mountpoint -q /mnt/ubuntu; then
    losetup /dev/block/loop0 /data/linux/rootfs.img 2>/dev/null || true
    mount -t ext4 -o rw,noatime /dev/block/loop0 /mnt/ubuntu || mount -t ext4 -o loop,rw,noatime /data/linux/rootfs.img /mnt/ubuntu
fi

mkdir -p /mnt/ubuntu/proc /mnt/ubuntu/sys /mnt/ubuntu/dev /mnt/ubuntu/dev/pts /mnt/ubuntu/dev/shm /mnt/ubuntu/run /mnt/ubuntu/run/dbus /mnt/ubuntu/run/user/0 /mnt/ubuntu/tmp/.X11-unix
chmod 700 /mnt/ubuntu/run/user/0
chmod 1777 /mnt/ubuntu/tmp /mnt/ubuntu/tmp/.X11-unix /mnt/ubuntu/dev/shm

mountpoint -q /mnt/ubuntu/proc || mount -t proc proc /mnt/ubuntu/proc
mountpoint -q /mnt/ubuntu/sys || mount -t sysfs sysfs /mnt/ubuntu/sys
mountpoint -q /mnt/ubuntu/dev || mount -o bind /dev /mnt/ubuntu/dev
mountpoint -q /mnt/ubuntu/dev/pts || mount -t devpts devpts /mnt/ubuntu/dev/pts
mountpoint -q /mnt/ubuntu/dev/shm || mount -t tmpfs -o size=512M tmpfs /mnt/ubuntu/dev/shm

echo "=== [4/6] Installing Hardware Tools (s8ctl + exynos_dp_bridge) ==="
mkdir -p /mnt/ubuntu/usr/local/bin /mnt/ubuntu/usr/local/src /mnt/ubuntu/var/log/gnome_apps
if [ -f /data/linux/s8ctl.py ]; then
    cp /data/linux/s8ctl.py /mnt/ubuntu/usr/local/bin/s8ctl
    chmod +x /mnt/ubuntu/usr/local/bin/s8ctl
fi
if [ -f /data/linux/exynos_dp_bridge.c ]; then
    cp /data/linux/exynos_dp_bridge.c /mnt/ubuntu/usr/local/src/exynos_dp_bridge.c
fi

echo "=== [5/6] Starting Ubuntu 24.04.5 LTS Services & GNOME 46 macOS Sonoma Desktop ==="
chroot /mnt/ubuntu /bin/bash -c "
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
/usr/sbin/sshd </dev/null >/dev/null 2>&1 || true

# 3. Compile Exynos 8895 USB-C DisplayPort / HDMI Bridge if gcc is installed
if [ -f /usr/local/src/exynos_dp_bridge.c ] && command -v gcc >/dev/null 2>&1; then
    gcc -O3 /usr/local/src/exynos_dp_bridge.c -o /usr/local/bin/exynos_dp_bridge -lX11 -lXext 2>/dev/null || true
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

# 5. Launch GNOME 46 macOS Sonoma Desktop
if [ -x /usr/local/bin/start_gnome_macos.sh ]; then
    /usr/local/bin/start_gnome_macos.sh </dev/null >/var/log/start_gnome_macos.log 2>&1
fi

# 6. Start noVNC / Websockify (:6080 -> localhost:5901)
if ! pgrep -f 'websockify.*6080' >/dev/null 2>&1; then
    websockify -D --web=/usr/share/novnc/ 6080 localhost:5901 </dev/null >/dev/null 2>&1 || true
fi

# 7. Start Exynos USB-C DisplayPort / HDMI Hotplug Daemon
if [ -x /usr/local/bin/exynos_dp_bridge ] && ! pgrep -x exynos_dp_bridge >/dev/null 2>&1; then
    nohup /usr/local/bin/exynos_dp_bridge </dev/null >/var/log/exynos_dp_bridge.log 2>&1 &
fi

# 8. Start Docker Engine
if command -v dockerd >/dev/null 2>&1 && ! pgrep -x dockerd >/dev/null 2>&1; then
    for cg in cpu cpuacct memory devices freezer blkio pids; do
        mkdir -p /sys/fs/cgroup/\$cg
        mountpoint -q /sys/fs/cgroup/\$cg || mount -t cgroup -o \$cg cgroup /sys/fs/cgroup/\$cg 2>/dev/null || true
    done
    nohup dockerd --iptables=false --bridge=none --storage-driver=vfs </dev/null >/var/log/dockerd.log 2>&1 &
fi
"

echo "=== [6/6] Signaling Headless Ready (Double Haptic Vibration) ==="
echo 150 > /sys/class/timed_output/vibrator/enable 2>/dev/null || true
sleep 1
echo 150 > /sys/class/timed_output/vibrator/enable 2>/dev/null || true
echo "Ubuntu 24.04.5 LTS + GNOME 46 macOS Sonoma Desktop Ready!"
