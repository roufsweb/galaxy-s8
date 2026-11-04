#!/sbin/sh
# Phase 1 & Phase 2: Upgrade to Ubuntu 24.04.5 LTS (Noble Numbat) + macOS Sonoma Desktop GUI
set -e
export PATH=/sbin:/system/bin:/system/xbin:/usr/bin:/bin
export TMPDIR=/tmp

# Signal installation in progress: Front RGB LED = Blue
echo 0 > /sys/class/leds/led_r/brightness 2>/dev/null || true
echo 0 > /sys/class/leds/led_g/brightness 2>/dev/null || true
echo 255 > /sys/class/leds/led_b/brightness 2>/dev/null || true

# Ensure MAX77865 PMIC high-current charging stays active
if [ -e /sys/class/power_supply/max77865-charger/data ]; then
    echo "0xBD 0x6C" > /sys/class/power_supply/max77865-charger/data 2>/dev/null || true
    echo "0xC3 0x61" > /sys/class/power_supply/max77865-charger/data 2>/dev/null || true
    echo "0xB7 0x05" > /sys/class/power_supply/max77865-charger/data 2>/dev/null || true
    echo 1200 > /sys/class/power_supply/battery/batt_tune_input_charge_current 2>/dev/null || true
    echo 1800 > /sys/class/power_supply/battery/batt_tune_fast_charge_current 2>/dev/null || true
fi

echo "=== [1/7] Downloading Ubuntu 24.04.5 LTS (Noble Numbat) ARM64 Base Rootfs ==="
if [ -s /mnt/ubuntu/tmp/ubuntu-base-24.04.5-base-arm64.tar.gz ]; then
    mv -f /mnt/ubuntu/tmp/ubuntu-base-24.04.5-base-arm64.tar.gz /data/linux/ubuntu-base-24.04.5-base-arm64.tar.gz
fi
if [ ! -s /data/linux/ubuntu-base-24.04.5-base-arm64.tar.gz ]; then
    chroot /mnt/ubuntu /usr/bin/curl -L --retry 3 -o /tmp/ubuntu-base-24.04.5-base-arm64.tar.gz \
        https://cdimage.ubuntu.com/ubuntu-base/releases/24.04/release/ubuntu-base-24.04.5-base-arm64.tar.gz
    mv -f /mnt/ubuntu/tmp/ubuntu-base-24.04.5-base-arm64.tar.gz /data/linux/ubuntu-base-24.04.5-base-arm64.tar.gz
fi
ls -lh /data/linux/ubuntu-base-24.04.5-base-arm64.tar.gz

echo "=== [2/7] Extracting Ubuntu 24.04.5 LTS into Staging Root (/mnt/ubuntu/noble) ==="
if [ ! -x /mnt/ubuntu/noble/usr/bin/apt-get ]; then
    umount /mnt/ubuntu/noble/proc 2>/dev/null || true
    umount /mnt/ubuntu/noble/sys 2>/dev/null || true
    umount /mnt/ubuntu/noble/dev/pts 2>/dev/null || true
    umount /mnt/ubuntu/noble/dev/shm 2>/dev/null || true
    umount /mnt/ubuntu/noble/dev 2>/dev/null || true
    umount /mnt/ubuntu/noble/run 2>/dev/null || true
    rm -rf /mnt/ubuntu/noble
    mkdir -p /mnt/ubuntu/noble

    cp /data/linux/ubuntu-base-24.04.5-base-arm64.tar.gz /mnt/ubuntu/noble.tar.gz
    chroot /mnt/ubuntu /bin/tar -xzf /noble.tar.gz -C /noble
    rm -f /mnt/ubuntu/noble.tar.gz
fi

mkdir -p /mnt/ubuntu/noble/proc /mnt/ubuntu/noble/sys /mnt/ubuntu/noble/dev /mnt/ubuntu/noble/dev/pts /mnt/ubuntu/noble/dev/shm /mnt/ubuntu/noble/run /mnt/ubuntu/noble/tmp /mnt/ubuntu/noble/data/local/tmp
chmod 1777 /mnt/ubuntu/noble/tmp /mnt/ubuntu/noble/data/local/tmp

grep -q "/mnt/ubuntu/noble/proc " /proc/mounts || mount -t proc proc /mnt/ubuntu/noble/proc
grep -q "/mnt/ubuntu/noble/sys " /proc/mounts || mount -o bind /sys /mnt/ubuntu/noble/sys
grep -q "/mnt/ubuntu/noble/dev " /proc/mounts || mount -o bind /dev /mnt/ubuntu/noble/dev
grep -q "/mnt/ubuntu/noble/dev/pts " /proc/mounts || mount -t devpts devpts /mnt/ubuntu/noble/dev/pts
grep -q "/mnt/ubuntu/noble/dev/shm " /proc/mounts || mount -t tmpfs -o size=512M tmpfs /mnt/ubuntu/noble/dev/shm
grep -q "/mnt/ubuntu/noble/run " /proc/mounts || mount -t tmpfs -o size=128M,mode=755 tmpfs /mnt/ubuntu/noble/run

echo "=== [3/7] Configuring Ubuntu 24.04.5 LTS Network, APT Sandbox & Android GIDs ==="
cat << 'EOF' > /mnt/ubuntu/noble/etc/resolv.conf
nameserver 8.8.8.8
nameserver 1.1.1.1
nameserver 192.168.0.1
EOF

echo "Galaxy-S8-Ubuntu" > /mnt/ubuntu/noble/etc/hostname
cat << 'EOF' > /mnt/ubuntu/noble/etc/hosts
127.0.0.1   localhost Galaxy-S8-Ubuntu
::1         localhost ip6-localhost ip6-loopback
EOF

cat << 'EOF' > /mnt/ubuntu/noble/etc/apt/apt.conf.d/99sandbox
APT::Sandbox::User "root";
APT::Sandbox::Seccomp "false";
Acquire::Retries "3";
EOF

chroot /mnt/ubuntu/noble /bin/bash -c '
set -e
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export DEBIAN_FRONTEND=noninteractive
export TMPDIR=/tmp

grep -q "^aid_inet:" /etc/group || echo "aid_inet:x:3003:root,_apt" >> /etc/group
grep -q "^aid_net_raw:" /etc/group || echo "aid_net_raw:x:3004:root,_apt" >> /etc/group
usermod -a -G 3003,3004 root 2>/dev/null || true
usermod -a -G 3003,3004 _apt 2>/dev/null || true

echo "=== [4/7] Installing Base System, Networking, Audio, Bluetooth, GUI & Docker in Ubuntu 24.04.5 ==="
apt-get install -y --no-install-recommends \
    systemd systemd-sysv dbus dbus-x11 sudo ca-certificates curl wget git nano htop neofetch \
    openssh-server wpasupplicant iw wireless-tools isc-dhcp-client iproute2 net-tools iputils-ping \
    build-essential pkg-config python3 python3-pil \
    alsa-utils pulseaudio pavucontrol bluez \
    xfce4 xfce4-goodies xfce4-terminal xfce4-whiskermenu-plugin xfce4-taskmanager xfce4-power-manager xfce4-pulseaudio-plugin \
    plank rofi thunar gvfs feh \
    netsurf-gtk \
    tigervnc-standalone-server tigervnc-common novnc websockify \
    xserver-xorg-core xserver-xorg-video-fbdev xserver-xorg-input-libinput xserver-xorg-input-evdev x11-xserver-utils \
    fonts-inter fonts-cantarell fonts-noto-color-emoji fonts-dejavu-core \
    gtk2-engines-murrine gtk2-engines-pixbuf sassc libglib2.0-dev-bin libxml2-utils \
    docker.io containerd runc cgroupfs-mount iptables

echo "=== [5/7] Installing WhiteSur macOS Sonoma Theme, Icons, Cursors & Wallpaper ==="
mkdir -p /tmp/macos-theme /usr/share/backgrounds
cd /tmp/macos-theme

if [ ! -d WhiteSur-gtk-theme ]; then
    git clone --depth=1 https://github.com/vinceliuice/WhiteSur-gtk-theme.git
fi
cd WhiteSur-gtk-theme
./install.sh -t all -c Dark -c Light || ./install.sh

cd /tmp/macos-theme
if [ ! -d WhiteSur-icon-theme ]; then
    git clone --depth=1 https://github.com/vinceliuice/WhiteSur-icon-theme.git
fi
cd WhiteSur-icon-theme
./install.sh

cd /tmp
rm -rf /tmp/macos-theme

# Generate a sleek macOS Sonoma Dark/Aurora 1920x1080 Wallpaper using Python PIL
python3 - << "PYEOF"
from PIL import Image, ImageDraw
import math

w, h = 1920, 1080
img = Image.new("RGB", (w, h))
pix = img.load()

for y in range(h):
    ny = y / h
    for x in range(w):
        nx = x / w
        # macOS Sonoma aurora gradient (deep indigo -> violet -> magenta -> teal glow)
        wave1 = math.sin(nx * 4.5 + ny * 2.0) * 0.5 + 0.5
        wave2 = math.cos(nx * 3.0 - ny * 3.5) * 0.5 + 0.5
        r = int(18 + 95 * (1 - ny) * wave1 + 45 * wave2 * (1 - abs(ny - 0.55) * 1.8))
        g = int(16 + 42 * wave2 + 70 * (1 - abs(ny - 0.65) * 1.9) * (1 - nx * 0.4))
        b = int(48 + 140 * (1 - ny * 0.6) + 45 * wave1)
        pix[x, y] = (max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))

img.save("/usr/share/backgrounds/macos-sonoma.png", "PNG")
PYEOF

echo "=== [6/7] Configuring macOS Cupertino Top Bar, Left Traffic-Light Buttons, Plank Dock & SSH ==="
echo "root:ubuntu" | chpasswd
mkdir -p /run/sshd
chmod 755 /run/sshd
sed -i "s/^#*PermitRootLogin.*/PermitRootLogin yes/" /etc/ssh/sshd_config
sed -i "s/^#*PasswordAuthentication.*/PasswordAuthentication yes/" /etc/ssh/sshd_config
ssh-keygen -A

# Configure XFCE4 macOS Sonoma Desktop Layout
mkdir -p /root/.config/xfce4/xfconf/xfce-perchannel-xml /root/.config/autostart /root/.config/plank/dock1/launchers /root/.vnc

# 1. Window Manager: WhiteSur-Dark + macOS Left Traffic-Light Buttons (Close, Minimize, Maximize on Left: CMH|O)
cat << "EOF" > /root/.config/xfce4/xfconf/xfce-perchannel-xml/xfwm4.xml
<?xml version="1.0" encoding="UTF-8"?>
<channel name="xfwm4" version="1.0">
  <property name="general" type="empty">
    <property name="theme" type="string" value="WhiteSur-Dark"/>
    <property name="button_layout" type="string" value="CMH|"/>
    <property name="title_font" type="string" value="Inter Semi-Bold 10"/>
    <property name="title_alignment" type="string" value="center"/>
    <property name="use_compositing" type="bool" value="true"/>
    <property name="frame_opacity" type="int" value="95"/>
    <property name="shadow_under_dock_windows" type="bool" value="true"/>
  </property>
</channel>
EOF

# 2. GTK Theme, Icon Theme & Font: WhiteSur-Dark + WhiteSur-dark icons + Inter 10
cat << "EOF" > /root/.config/xfce4/xfconf/xfce-perchannel-xml/xsettings.xml
<?xml version="1.0" encoding="UTF-8"?>
<channel name="xsettings" version="1.0">
  <property name="Net" type="empty">
    <property name="ThemeName" type="string" value="WhiteSur-Dark"/>
    <property name="IconThemeName" type="string" value="WhiteSur-dark"/>
  </property>
  <property name="Gtk" type="empty">
    <property name="FontName" type="string" value="Inter 10"/>
    <property name="MonospaceFontName" type="string" value="Monospace 10"/>
    <property name="DecorationLayout" type="string" value="close,minimize,maximize:menu"/>
  </property>
</channel>
EOF

# 3. Desktop Wallpaper: macOS Sonoma Aurora
cat << "EOF" > /root/.config/xfce4/xfconf/xfce-perchannel-xml/xfce4-desktop.xml
<?xml version="1.0" encoding="UTF-8"?>
<channel name="xfce4-desktop" version="1.0">
  <property name="backdrop" type="empty">
    <property name="screen0" type="empty">
      <property name="monitorVNC-0" type="empty">
        <property name="workspace0" type="empty">
          <property name="color-style" type="int" value="0"/>
          <property name="image-style" type="int" value="5"/>
          <property name="last-image" type="string" value="/usr/share/backgrounds/macos-sonoma.png"/>
        </property>
      </property>
      <property name="monitor0" type="empty">
        <property name="workspace0" type="empty">
          <property name="color-style" type="int" value="0"/>
          <property name="image-style" type="int" value="5"/>
          <property name="last-image" type="string" value="/usr/share/backgrounds/macos-sonoma.png"/>
        </property>
      </property>
    </property>
  </property>
  <property name="desktop-icons" type="empty">
    <property name="style" type="int" value="2"/>
    <property name="icon-size" type="uint" value="48"/>
  </property>
</channel>
EOF

# 4. Single Top macOS Global Menu Bar (Panel 1 at top, NO bottom XFCE panel because Plank is the bottom macOS dock!)
cat << "EOF" > /root/.config/xfce4/xfconf/xfce-perchannel-xml/xfce4-panel.xml
<?xml version="1.0" encoding="UTF-8"?>
<channel name="xfce4-panel" version="1.0">
  <property name="configver" type="int" value="2"/>
  <property name="panels" type="array">
    <value type="int" value="1"/>
    <property name="dark-mode" type="bool" value="true"/>
    <property name="panel-1" type="empty">
      <property name="position" type="string" value="p=6;x=0;y=0"/>
      <property name="length" type="uint" value="100"/>
      <property name="position-locked" type="bool" value="true"/>
      <property name="icon-size" type="uint" value="16"/>
      <property name="size" type="uint" value="28"/>
      <property name="background-style" type="uint" value="1"/>
      <property name="background-rgba" type="array">
        <value type="double" value="0.10"/>
        <value type="double" value="0.10"/>
        <value type="double" value="0.14"/>
        <value type="double" value="0.82"/>
      </property>
      <property name="plugin-ids" type="array">
        <value type="int" value="1"/>
        <value type="int" value="2"/>
        <value type="int" value="3"/>
        <value type="int" value="4"/>
        <value type="int" value="5"/>
        <value type="int" value="6"/>
        <value type="int" value="7"/>
      </property>
    </property>
  </property>
  <property name="plugins" type="empty">
    <property name="plugin-1" type="string" value="whiskermenu">
      <property name="button-title" type="string" value="     Finder   File   Edit   View   Go   Window   Help  "/>
      <property name="show-button-title" type="bool" value="true"/>
      <property name="show-button-icon" type="bool" value="false"/>
    </property>
    <property name="plugin-2" type="string" value="separator">
      <property name="expand" type="bool" value="true"/>
      <property name="style" type="uint" value="0"/>
    </property>
    <property name="plugin-3" type="string" value="systray"/>
    <property name="plugin-4" type="string" value="pulseaudio">
      <property name="enable-keyboard-shortcuts" type="bool" value="true"/>
    </property>
    <property name="plugin-5" type="string" value="power-manager-plugin"/>
    <property name="plugin-6" type="string" value="clock">
      <property name="digital-layout" type="uint" value="3"/>
      <property name="digital-time-format" type="string" value="  %a %b %d   %I:%M %p  "/>
      <property name="digital-time-font" type="string" value="Inter Medium 10"/>
    </property>
    <property name="plugin-7" type="string" value="actions"/>
  </property>
</channel>
EOF

# 5. Configure Plank Dock (Centered Bottom macOS Dock with Smooth Icon Magnification)
cat << "EOF" > /root/.config/autostart/plank.desktop
[Desktop Entry]
Type=Application
Name=Plank macOS Dock
Exec=plank
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
EOF

for app in thunar xfce4-terminal netsurf xfce4-taskmanager pavucontrol xfce4-settings-manager; do
    if [ -f "/usr/share/applications/${app}.desktop" ]; then
        cat << EOF > "/root/.config/plank/dock1/launchers/${app}.dockitem"
[PlankDockItemPreferences]
Launcher=file:///usr/share/applications/${app}.desktop
EOF
    fi
done

# 6. Configure VNC xstartup to launch macOS Sonoma XFCE4 + Plank Dock
cat << "EOF" > /root/.vnc/xstartup
#!/bin/sh
unset SESSION_MANAGER
unset DBUS_SESSION_BUS_ADDRESS
export XKL_XMODMAP_DISABLE=1
export GTK_THEME=WhiteSur-Dark
(sleep 3 && GDK_BACKEND=x11 plank >/dev/null 2>&1 &) &
(sleep 4 && feh --bg-fill /usr/share/backgrounds/macos-sonoma.png >/dev/null 2>&1 || true) &
exec dbus-launch --exit-with-session startxfce4
EOF
chmod 755 /root/.vnc/xstartup
echo ubuntu | vncpasswd -f > /root/.vnc/passwd
chmod 600 /root/.vnc/passwd
'

echo "=== [7/7] Atomically Swapping Ubuntu 24.04.5 LTS + macOS Sonoma Desktop into /mnt/ubuntu ==="
mkdir -p /mnt/ubuntu/noble/etc/wpa_supplicant
cp -f /mnt/ubuntu/etc/wpa_supplicant/wpa_supplicant.conf /mnt/ubuntu/noble/etc/wpa_supplicant/wpa_supplicant.conf 2>/dev/null || true

umount /mnt/ubuntu/noble/proc 2>/dev/null || true
umount /mnt/ubuntu/noble/sys 2>/dev/null || true
umount /mnt/ubuntu/noble/dev/pts 2>/dev/null || true
umount /mnt/ubuntu/noble/dev/shm 2>/dev/null || true
umount /mnt/ubuntu/noble/dev 2>/dev/null || true
umount /mnt/ubuntu/noble/run 2>/dev/null || true

# Stop old 20.04 desktop & daemons (keep wpa_supplicant alive so wlan0 stays connected!)
for p in Xtigervnc websockify xfce4-session xfce4-panel xfconfd dbus-daemon sshd dockerd containerd; do
    killall -9 $p 2>/dev/null || true
done

mkdir -p /mnt/ubuntu/.old2004
for item in /mnt/ubuntu/*; do
    base=$(basename "$item")
    case "$base" in
        noble|proc|sys|dev|run|tmp|data|.old2004|lost+found) ;;
        *) mv "$item" /mnt/ubuntu/.old2004/ 2>/dev/null || rm -rf "$item" ;;
    esac
done

for item in /mnt/ubuntu/noble/*; do
    base=$(basename "$item")
    case "$base" in
        proc|sys|dev|run|tmp|data|lost+found) ;;
        *) mv "$item" /mnt/ubuntu/ ;;
    esac
done

rm -rf /mnt/ubuntu/.old2004 /mnt/ubuntu/noble /mnt/ubuntu/tmp/.X1-lock /mnt/ubuntu/tmp/.X11-unix

# Launch all services in Ubuntu 24.04.5 LTS
/sbin/sh /data/linux/start_all.sh

# Signal Ready: Front RGB LED = Green + 2 Haptic Vibrations
echo 0 > /sys/class/leds/led_r/brightness 2>/dev/null || true
echo 0 > /sys/class/leds/led_b/brightness 2>/dev/null || true
echo 80 > /sys/class/leds/led_g/brightness 2>/dev/null || true
echo 150 > /sys/class/timed_output/vibrator/enable 2>/dev/null || true
sleep 1
echo 150 > /sys/class/timed_output/vibrator/enable 2>/dev/null || true

echo "=== SUCCESS: Ubuntu 24.04.5 LTS + macOS Sonoma Desktop GUI is LIVE! ==="
chroot /mnt/ubuntu /bin/bash -c 'cat /etc/os-release | head -n 4'
