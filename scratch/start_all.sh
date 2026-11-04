#!/sbin/sh
# Master Startup Script for Native Ubuntu 24.04.5 LTS (Noble Numbat) + macOS Sonoma GUI on Samsung Galaxy S8 (SM-G950N)
export PATH=/sbin:/system/bin:/system/xbin:/usr/bin:/bin
export TMPDIR=/tmp
mkdir -p /tmp /mnt/ubuntu

echo "=== [1/5] Configuring MAX77865 PMIC Charger & Battery Management ==="
if [ -e /sys/class/power_supply/max77865-charger/data ]; then
    echo "0xBD 0x6C" > /sys/class/power_supply/max77865-charger/data 2>/dev/null
    echo "0xC3 0x61" > /sys/class/power_supply/max77865-charger/data 2>/dev/null
    echo "0xB7 0x05" > /sys/class/power_supply/max77865-charger/data 2>/dev/null
    echo 1500 > /sys/class/power_supply/battery/batt_tune_input_charge_current 2>/dev/null
    echo 2000 > /sys/class/power_supply/battery/batt_tune_fast_charge_current 2>/dev/null
    echo 0 > /sys/class/power_supply/battery/batt_slate_mode 2>/dev/null
fi
echo "Battery: $(cat /sys/class/power_supply/battery/capacity 2>/dev/null)% ($(cat /sys/class/power_supply/battery/status 2>/dev/null), Health: $(cat /sys/class/power_supply/battery/health 2>/dev/null))"

echo "=== [2/5] Initializing Broadcom BCM4361 Wi-Fi (wlan0 -> <WIFI_SSID>) ==="
/sbin/sh /data/linux/connect_wifi.sh

echo "=== [3/5] Mounting Ubuntu 24.04.5 LTS ARM64 & System Directories ==="
if ! grep -q "/mnt/ubuntu " /proc/mounts; then
    for i in 0 1 2 3 4 5 6 7; do
        [ -b /dev/block/loop$i ] || mknod /dev/block/loop$i b 7 $i 2>/dev/null
        [ -b /dev/loop$i ] || ln -sf /dev/block/loop$i /dev/loop$i 2>/dev/null
    done
    losetup /dev/block/loop0 /data/linux/rootfs.img 2>/dev/null
    mount -t ext4 -o rw,noatime /dev/block/loop0 /mnt/ubuntu 2>/dev/null || mount -t ext4 -o loop,rw,noatime /data/linux/rootfs.img /mnt/ubuntu
fi

mkdir -p /mnt/ubuntu/proc /mnt/ubuntu/sys /mnt/ubuntu/dev /mnt/ubuntu/dev/pts /mnt/ubuntu/dev/shm /mnt/ubuntu/run /mnt/ubuntu/run/sshd /mnt/ubuntu/tmp /mnt/ubuntu/data/local/tmp /mnt/ubuntu/vendor /mnt/ubuntu/system
grep -q "/mnt/ubuntu/proc " /proc/mounts || mount -t proc proc /mnt/ubuntu/proc
grep -q "/mnt/ubuntu/sys " /proc/mounts || mount -o bind /sys /mnt/ubuntu/sys
grep -q "/mnt/ubuntu/dev " /proc/mounts || mount -o bind /dev /mnt/ubuntu/dev
grep -q "/mnt/ubuntu/dev/pts " /proc/mounts || mount -t devpts devpts /mnt/ubuntu/dev/pts
grep -q "/mnt/ubuntu/dev/shm " /proc/mounts || mount -t tmpfs -o size=512M tmpfs /mnt/ubuntu/dev/shm
grep -q "/mnt/ubuntu/run " /proc/mounts || mount -t tmpfs -o size=128M,mode=755 tmpfs /mnt/ubuntu/run
grep -q "/mnt/ubuntu/vendor " /proc/mounts || mount -o bind /system_root/vendor /mnt/ubuntu/vendor 2>/dev/null

mkdir -p /mnt/ubuntu/run/sshd /mnt/ubuntu/run/dbus /mnt/ubuntu/tmp /mnt/ubuntu/data/local/tmp /mnt/ubuntu/usr/local/src /mnt/ubuntu/usr/local/bin
chmod 755 /mnt/ubuntu/run /mnt/ubuntu/run/sshd
chown 0:0 /mnt/ubuntu/run /mnt/ubuntu/run/sshd
chmod 1777 /mnt/ubuntu/tmp /mnt/ubuntu/data/local/tmp

# Copy latest hardware tools into Ubuntu 24.04 rootfs if present in /data/linux
[ -f /data/linux/exynos_dp_bridge.c ] && cp -f /data/linux/exynos_dp_bridge.c /mnt/ubuntu/usr/local/src/exynos_dp_bridge.c
[ -f /data/linux/s8ctl.py ] && cp -f /data/linux/s8ctl.py /mnt/ubuntu/usr/local/bin/s8ctl && chmod 755 /mnt/ubuntu/usr/local/bin/s8ctl

echo "=== [4/5] Starting OpenSSH, macOS Sonoma Desktop, TigerVNC (:5901), noVNC (:6080), USB-C DP Bridge & Docker ==="
chroot /mnt/ubuntu /bin/bash -c '
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export HOME=/root
export USER=root
export TMPDIR=/tmp

# Ensure DNS
rm -f /etc/resolv.conf
echo "nameserver 8.8.8.8" > /etc/resolv.conf
echo "nameserver 1.1.1.1" >> /etc/resolv.conf

# Start OpenSSH
mkdir -p /run/sshd
chmod 755 /run /run/sshd
/usr/sbin/sshd </dev/null >/dev/null 2>&1

# Start D-Bus
mkdir -p /run/dbus
rm -f /run/dbus/pid
dbus-daemon --system --fork </dev/null >/dev/null 2>&1

# Configure VNC password (ubuntu) & start macOS Sonoma XFCE4 + Plank + TigerVNC + noVNC
mkdir -p /root/.vnc
echo ubuntu | vncpasswd -f > /root/.vnc/passwd
chmod 600 /root/.vnc/passwd
if ! ps w | grep -v grep | grep -q "Xtigervnc :1"; then
    rm -f /tmp/.X1-lock /tmp/.X11-unix/X1
    Xtigervnc :1 -desktop "Galaxy S8 macOS Sonoma (Ubuntu 24.04 LTS)" -geometry 1920x1080 -depth 24 -rfbauth /root/.vnc/passwd -rfbport 5901 -localhost no -SecurityTypes VncAuth,TLSVnc </dev/null >/var/log/xtigervnc.log 2>&1 &
    sleep 2
    DISPLAY=:1 /bin/bash /root/.vnc/xstartup </dev/null >/var/log/xstartup.log 2>&1 &
fi

if ! ps w | grep -v grep | grep -q "websockify.*6080"; then
    websockify -D --web=/usr/share/novnc/ 6080 localhost:5901 </dev/null >/var/log/websockify.log 2>&1
fi

# Compile and start Exynos USB-C DisplayPort / HDMI Bridge (fb2 + /dev/ion)
if [ -f /usr/local/src/exynos_dp_bridge.c ] && [ ! -x /usr/local/bin/exynos_dp_bridge ]; then
    gcc -O3 /usr/local/src/exynos_dp_bridge.c -o /usr/local/bin/exynos_dp_bridge -lX11 -lXext 2>/var/log/dp_build.log
fi
if [ -x /usr/local/bin/exynos_dp_bridge ] && ! ps w | grep -v grep | grep -q "exynos_dp_bridge"; then
    nohup /usr/local/bin/exynos_dp_bridge :1 /dev/graphics/fb2 </dev/null >/var/log/exynos_dp_bridge.log 2>&1 &
fi

# Start Docker Engine
mkdir -p /sys/fs/cgroup/devices /sys/fs/cgroup/systemd
mount -t cgroup -o none,name=devices cgroup /sys/fs/cgroup/devices 2>/dev/null || true
mount -t cgroup -o none,name=systemd cgroup /sys/fs/cgroup/systemd 2>/dev/null || true
if ! ps w | grep -v grep | grep -q "dockerd"; then
    nohup dockerd --storage-driver=vfs --iptables=false --bridge=none </dev/null >/var/log/dockerd.log 2>&1 &
fi
'

# Haptic double-pulse to signal Headless Ubuntu 24.04 + macOS Sonoma Desktop Ready
echo 150 > /sys/class/timed_output/vibrator/enable 2>/dev/null
sleep 0.3
echo 150 > /sys/class/timed_output/vibrator/enable 2>/dev/null

echo "=== [5/5] All Native Ubuntu 24.04.5 LTS Services Ready ==="
ip -4 addr show wlan0 | grep inet
