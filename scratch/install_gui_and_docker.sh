#!/bin/bash
set -e
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export HOME=/root
export TMPDIR=/tmp
export DEBIAN_FRONTEND=noninteractive

mkdir -p /tmp /data/local/tmp /run/dbus
chmod 1777 /tmp /data/local/tmp

# Use native Wi-Fi (wlan0) directly for apt!
echo 'APT::Sandbox::User "root";' > /etc/apt/apt.conf.d/99sandbox
rm -f /etc/apt/apt.conf.d/99usbproxy

echo "[*] Installing XFCE4 Desktop GUI, Xorg (fbdev + USB input), TigerVNC, noVNC, and Docker Engine over Wi-Fi..."
apt-get update
apt-get install -y --no-install-recommends \
    xfce4 xfce4-terminal dbus-x11 x11-xserver-utils xinit \
    xserver-xorg-core xserver-xorg-video-fbdev xserver-xorg-input-evdev xserver-xorg-input-libinput \
    tigervnc-standalone-server tigervnc-common novnc websockify python3-numpy \
    fonts-dejavu-core fonts-liberation2 elementary-xfce-icon-theme \
    docker.io cgroupfs-mount iptables

# Configure iptables-legacy for Linux 4.4 kernel Docker compatibility
update-alternatives --set iptables /usr/sbin/iptables-legacy || true
update-alternatives --set ip6tables /usr/sbin/ip6tables-legacy || true

# 1. Configure VNC xstartup for XFCE4
mkdir -p /root/.vnc
cat << 'EOF' > /root/.vnc/xstartup
#!/bin/sh
unset SESSION_MANAGER
unset DBUS_SESSION_BUS_ADDRESS
export XKL_XMODMAP_DISABLE=1
exec dbus-launch --exit-with-session startxfce4
EOF
chmod 755 /root/.vnc/xstartup

# Set VNC password to "ubuntu"
echo ubuntu | vncpasswd -f > /root/.vnc/passwd
chmod 600 /root/.vnc/passwd

# 2. Configure Xorg for Samsung Exynos 8895 External USB-C DisplayPort (/dev/graphics/fb2)
mkdir -p /etc/X11/xorg.conf.d
cat << 'EOF' > /etc/X11/xorg.conf.d/99-exynos-dp.conf
Section "Device"
    Identifier  "Exynos8895-DisplayPort"
    Driver      "fbdev"
    Option      "fbdev" "/dev/graphics/fb2"
    Option      "SwapbuffersWait" "true"
EndSection

Section "Screen"
    Identifier  "DefaultScreen"
    Device      "Exynos8895-DisplayPort"
EndSection
EOF

# 3. Create /usr/local/bin/start-gui (starts VNC + noVNC web desktop AND DisplayPort fb2 desktop)
cat << 'EOF' > /usr/local/bin/start-gui
#!/bin/bash
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export HOME=/root
export TMPDIR=/tmp
export USER=root

mkdir -p /run/dbus /tmp/.X11-unix
chmod 1777 /tmp /tmp/.X11-unix
rm -f /run/dbus/pid
dbus-daemon --system --fork 2>/dev/null || true

# Ensure /dev/fb2 symlink exists for /dev/graphics/fb2
[ -e /dev/graphics/fb2 ] && [ ! -e /dev/fb2 ] && ln -s /dev/graphics/fb2 /dev/fb2
[ -e /dev/graphics/fb0 ] && [ ! -e /dev/fb0 ] && ln -s /dev/graphics/fb0 /dev/fb0

# Start TigerVNC + noVNC on :1 (port 5901 / http port 6080)
tigervncserver -kill :1 >/dev/null 2>&1 || true
rm -f /tmp/.X1-lock /tmp/.X11-unix/X1
tigervncserver :1 -geometry 1920x1080 -depth 24 -localhost no -SecurityTypes VncAuth,TLSVnc

pkill -f "websockify.*6080" 2>/dev/null || true
websockify -D --web=/usr/share/novnc/ 6080 localhost:5901

# Unblank DisplayPort framebuffer fb2 if external monitor connected
if [ -e /sys/class/graphics/fb2/blank ]; then
    echo 0 > /sys/class/graphics/fb2/blank 2>/dev/null || true
fi

echo "[+] XFCE4 GUI Desktop is LIVE!"
echo "    -> Web Browser (noVNC): http://$(ip -4 addr show wlan0 | awk '/inet / {split($2,a,"/"); print a[1]}'):6080/vnc.html (Password: ubuntu)"
echo "    -> VNC Client:          $(ip -4 addr show wlan0 | awk '/inet / {split($2,a,"/"); print a[1]}'):5901 (Password: ubuntu)"
EOF
chmod 755 /usr/local/bin/start-gui

# 4. Create /usr/local/bin/start-dp-xorg for direct USB-C HDMI monitor output on /dev/graphics/fb2
cat << 'EOF' > /usr/local/bin/start-dp-xorg
#!/bin/bash
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export HOME=/root
export TMPDIR=/tmp
[ -e /dev/graphics/fb2 ] && ln -sf /dev/graphics/fb2 /dev/fb2
# Set 1080p60 preset on DisplayPort controller if requested
echo 16 > /sys/class/dp_sec/forced_resolution 2>/dev/null || true
echo 0 > /sys/class/graphics/fb2/blank 2>/dev/null || true
startx /usr/bin/startxfce4 -- :0 vt1 -keeptty -novtswitch &
echo "[+] Started Xorg + XFCE4 on USB-C DisplayPort (/dev/graphics/fb2)!"
EOF
chmod 755 /usr/local/bin/start-dp-xorg

# 5. Create /usr/local/bin/start-docker
cat << 'EOF' > /usr/local/bin/start-docker
#!/bin/bash
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
cgroupfs-mount 2>/dev/null || true
update-alternatives --set iptables /usr/sbin/iptables-legacy 2>/dev/null || true
if ! pgrep -x dockerd >/dev/null; then
    dockerd --storage-driver=vfs >/var/log/dockerd.log 2>&1 &
    sleep 3
fi
docker info | head -n 25
EOF
chmod 755 /usr/local/bin/start-docker

echo "[+] GUI and Docker installation complete! Starting services..."
/usr/local/bin/start-gui
/usr/local/bin/start-docker

