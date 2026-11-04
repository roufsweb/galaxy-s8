#!/sbin/sh
# Master Startup Script for Native Ubuntu 20.04.5 LTS on Samsung Galaxy S8 (SM-G950N)
export PATH=/sbin:/system/bin:/system/xbin:/usr/bin:/bin
export TMPDIR=/tmp
mkdir -p /tmp /mnt/ubuntu

echo "=== [1/5] Configuring MAX77865 PMIC Charger & Battery Management ==="
if [ -e /sys/class/power_supply/max77865-charger/data ]; then
    echo "0xBD 0x6C" > /sys/class/power_supply/max77865-charger/data 2>/dev/null
    echo "0xC3 0x61" > /sys/class/power_supply/max77865-charger/data 2>/dev/null
    echo "0xB7 0x05" > /sys/class/power_supply/max77865-charger/data 2>/dev/null
    echo 1200 > /sys/class/power_supply/battery/batt_tune_input_charge_current 2>/dev/null
    echo 1800 > /sys/class/power_supply/battery/batt_tune_fast_charge_current 2>/dev/null
fi
echo "Battery: $(cat /sys/class/power_supply/battery/capacity 2>/dev/null)% ($(cat /sys/class/power_supply/battery/status 2>/dev/null), Health: $(cat /sys/class/power_supply/battery/health 2>/dev/null))"

echo "=== [2/5] Initializing Broadcom BCM4361 Wi-Fi (wlan0 -> <WIFI_SSID>) ==="
/sbin/sh /data/linux/connect_wifi.sh

echo "=== [3/5] Mounting Ubuntu 20.04.5 LTS ARM64 & Cgroups ==="
if ! grep -q "/mnt/ubuntu " /proc/mounts; then
    for i in 0 1 2 3 4 5 6 7; do
        [ -b /dev/block/loop$i ] || mknod /dev/block/loop$i b 7 $i 2>/dev/null
        [ -b /dev/loop$i ] || ln -sf /dev/block/loop$i /dev/loop$i 2>/dev/null
    done
    losetup /dev/block/loop0 /data/linux/rootfs.img 2>/dev/null
    mount -t ext4 -o rw,noatime /dev/block/loop0 /mnt/ubuntu 2>/dev/null || mount -t ext4 -o loop,rw,noatime /data/linux/rootfs.img /mnt/ubuntu
fi

mkdir -p /mnt/ubuntu/proc /mnt/ubuntu/sys /mnt/ubuntu/dev /mnt/ubuntu/dev/pts /mnt/ubuntu/dev/shm /mnt/ubuntu/run /mnt/ubuntu/run/sshd /mnt/ubuntu/tmp /mnt/ubuntu/data/local/tmp
grep -q "/mnt/ubuntu/proc " /proc/mounts || mount -t proc proc /mnt/ubuntu/proc
grep -q "/mnt/ubuntu/sys " /proc/mounts || mount -o bind /sys /mnt/ubuntu/sys
grep -q "/mnt/ubuntu/dev " /proc/mounts || mount -o bind /dev /mnt/ubuntu/dev
grep -q "/mnt/ubuntu/dev/pts " /proc/mounts || mount -t devpts devpts /mnt/ubuntu/dev/pts
grep -q "/mnt/ubuntu/dev/shm " /proc/mounts || mount -t tmpfs -o size=512M tmpfs /mnt/ubuntu/dev/shm
grep -q "/mnt/ubuntu/run " /proc/mounts || mount -t tmpfs -o size=128M,mode=755 tmpfs /mnt/ubuntu/run

mkdir -p /mnt/ubuntu/run/sshd /mnt/ubuntu/run/dbus /mnt/ubuntu/tmp /mnt/ubuntu/data/local/tmp
chmod 755 /mnt/ubuntu/run /mnt/ubuntu/run/sshd
chown 0:0 /mnt/ubuntu/run /mnt/ubuntu/run/sshd
chmod 1777 /mnt/ubuntu/tmp /mnt/ubuntu/data/local/tmp

echo "=== [4/5] Starting OpenSSH, XFCE4 Desktop, TigerVNC (:5901) & noVNC (:6080) ==="
chroot /mnt/ubuntu /bin/bash -c '
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export HOME=/root
export USER=root
export TMPDIR=/tmp

# Start OpenSSH
/usr/sbin/sshd 2>/dev/null

# Start D-Bus
rm -f /run/dbus/pid
dbus-daemon --system --fork 2>/dev/null

# Configure VNC password (ubuntu) & start XFCE4 + TigerVNC + noVNC
mkdir -p /root/.vnc
echo ubuntu | vncpasswd -f > /root/.vnc/passwd
chmod 600 /root/.vnc/passwd
if ! ps w | grep -v grep | grep -q "Xtigervnc :1"; then
    rm -f /tmp/.X1-lock /tmp/.X11-unix/X1
    vncserver :1 -geometry 1920x1080 -depth 24 -localhost no
fi
if ! ps w | grep -v grep | grep -q "websockify.*6080"; then
    websockify -D --web=/usr/share/novnc/ 6080 localhost:5901
fi

# Start Docker Engine
cgroupfs-mount 2>/dev/null
mkdir -p /sys/fs/cgroup/devices /sys/fs/cgroup/systemd
mount -t cgroup -o none,name=devices cgroup /sys/fs/cgroup/devices 2>/dev/null || true
mount -t cgroup -o none,name=systemd cgroup /sys/fs/cgroup/systemd 2>/dev/null || true
if ! ps w | grep -v grep | grep -q "dockerd"; then
    nohup dockerd --storage-driver=vfs --iptables=false --bridge=none >/var/log/dockerd.log 2>&1 &
fi
'

echo "=== [5/5] All Native Ubuntu Services Ready ==="
ip -4 addr show wlan0 | grep inet
