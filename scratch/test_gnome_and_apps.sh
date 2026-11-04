#!/sbin/sh
export PATH=/sbin:/system/bin:/system/xbin:/vendor/bin

# CRITICAL EXYNOS 8895 V4L2 PANIC GUARD: remove uninitialized fimc_is /dev/video100+ nodes
rm -f /dev/video[1-9][0-9]* /dev/v4l-subdev* 2>/dev/null || true

# Run start_all.sh first if /mnt/ubuntu is not mounted
if ! mountpoint -q /mnt/ubuntu; then
    /sbin/sh /data/linux/start_all.sh
fi

chroot /mnt/ubuntu /bin/bash -c "
export DEBIAN_FRONTEND=noninteractive
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

echo '=== [1/5] Configuring Global Environment for GNOME 46 + GTK4 + UTF-8 + WebKit ==='
cat << 'EOF' > /etc/default/locale
LANG=C.UTF-8
LC_ALL=C.UTF-8
EOF

cat << 'EOF' > /etc/profile.d/s8_gnome_env.sh
export LANG=C.UTF-8
export LC_ALL=C.UTF-8
export DISPLAY=:1
export GDK_BACKEND=x11
export GSK_RENDERER=cairo
export LIBGL_ALWAYS_SOFTWARE=1
export GTK_THEME=WhiteSur-Dark
export GTK_A11Y=none
export NO_AT_BRIDGE=1
export XDG_CURRENT_DESKTOP=GNOME
export XDG_SESSION_TYPE=x11
export XDG_RUNTIME_DIR=/run/user/0
export WEBKIT_DISABLE_SANDBOX_THIS_IS_DANGEROUS=1
export WEBKIT_DISABLE_DMABUF_RENDERER=1
export WEBKIT_DISABLE_COMPOSITING_MODE=1
if [ -f /run/user/0/dbus_session ]; then
    source /run/user/0/dbus_session
fi
EOF
chmod +x /etc/profile.d/s8_gnome_env.sh
source /etc/profile.d/s8_gnome_env.sh

mkdir -p /run/user/0 /run/dbus /var/log/gnome_apps /usr/local/lib /usr/local/bin
chmod 700 /run/user/0

# Build tiny geteuid() shim so GNOME 46 Nautilus (Files) and Epiphany (Web) run cleanly as root
cat << 'EOF' > /usr/local/src/libnautilus_root.c
#include <sys/types.h>
uid_t geteuid(void) { return 1000; }
uid_t getuid(void) { return 1000; }
EOF
gcc -shared -fPIC -O2 /usr/local/src/libnautilus_root.c -o /usr/local/lib/libnautilus_root.so

cat << 'EOF' > /usr/local/bin/nautilus
#!/bin/bash
source /etc/profile.d/s8_gnome_env.sh
export LD_PRELOAD=/usr/local/lib/libnautilus_root.so
exec /usr/bin/nautilus \"\$@\"
EOF
chmod +x /usr/local/bin/nautilus

cat << 'EOF' > /usr/local/bin/epiphany-browser
#!/bin/bash
source /etc/profile.d/s8_gnome_env.sh
export LD_PRELOAD=/usr/local/lib/libnautilus_root.so
exec /usr/bin/epiphany-browser \"\$@\"
EOF
chmod +x /usr/local/bin/epiphany-browser

# Ensure WhiteSur GTK4/libadwaita CSS is linked for root
mkdir -p /root/.config/gtk-4.0 /root/.config/gtk-3.0
if [ -d /usr/share/themes/WhiteSur-Dark/gtk-4.0 ]; then
    cp -rf /usr/share/themes/WhiteSur-Dark/gtk-4.0/* /root/.config/gtk-4.0/ 2>/dev/null || true
fi

echo '=== [2/5] Creating GNOME + macOS Sonoma Plank Dock Items ==='
mkdir -p /root/.config/plank/dock1/launchers
rm -f /root/.config/plank/dock1/launchers/*.dockitem

create_dock_item() {
    local idx=\$1
    local desktop_file=\$2
    if [ -f \"/usr/share/applications/\$desktop_file\" ]; then
        cat << DOCK > \"/root/.config/plank/dock1/launchers/\${idx}-\${desktop_file%.desktop}.dockitem\"
[PlankDockItemPreferences]
Launcher=file:///usr/share/applications/\${desktop_file}
DOCK
    fi
}

sed -i 's|^Exec=nautilus|Exec=/usr/local/bin/nautilus|g' /usr/share/applications/org.gnome.Nautilus.desktop 2>/dev/null || true
sed -i 's|^DBusActivatable=true|DBusActivatable=false|g' /usr/share/applications/org.gnome.Nautilus.desktop 2>/dev/null || true
sed -i 's|^Exec=epiphany|Exec=/usr/local/bin/epiphany-browser|g' /usr/share/applications/org.gnome.Epiphany.desktop 2>/dev/null || true
sed -i 's|^DBusActivatable=true|DBusActivatable=false|g' /usr/share/applications/org.gnome.Epiphany.desktop 2>/dev/null || true

cat << 'EOF' > /usr/share/applications/s8-hardware-center.desktop
[Desktop Entry]
Name=Galaxy S8 Hardware Center
Comment=Manage Battery, Torch, Haptics, Audio & DisplayPort
Exec=kgx -e /bin/bash -c \"s8ctl status; echo ''; echo 'Commands: s8ctl torch <0-5> | s8ctl vibrate <ms> | s8ctl charge-limit <80|100>'; exec /bin/bash\"
Icon=preferences-system
Terminal=false
Type=Application
Categories=System;Settings;
EOF

create_dock_item 01 org.gnome.Nautilus.desktop
create_dock_item 02 org.gnome.Console.desktop
create_dock_item 03 org.gnome.TextEditor.desktop
create_dock_item 04 org.gnome.Calculator.desktop
create_dock_item 05 org.gnome.SystemMonitor.desktop
create_dock_item 06 org.gnome.Epiphany.desktop
create_dock_item 07 s8-hardware-center.desktop

echo '=== [3/5] Writing GNOME 46 macOS Sonoma Session Launcher (/usr/local/bin/start_gnome_macos.sh) ==='
cat << 'EOF' > /usr/local/bin/start_gnome_macos.sh
#!/bin/bash
rm -f /run/user/0/dbus_session
source /etc/profile.d/s8_gnome_env.sh
mkdir -p /run/user/0 /tmp/.X11-unix /var/log/gnome_apps
chmod 700 /run/user/0
chmod 1777 /tmp/.X11-unix

# Stop old desktop processes cleanly
killall -9 xfce4-session xfwm4 xfce4-panel xfdesktop plank metacity gnome-panel gnome-shell gnome-terminal-server dbus-launch 2>/dev/null || true
sleep 1

# Ensure Xtigervnc :1 is running
if ! pgrep -x Xtigervnc >/dev/null 2>&1; then
    rm -f /tmp/.X1-lock /tmp/.X11-unix/X1
    Xtigervnc :1 -geometry 1920x1080 -depth 24 -rfbport 5901 -PasswordFile /root/.vnc/passwd -AlwaysShared -AcceptKeyEvents -AcceptPointerEvents -SecurityTypes VncAuth </dev/null >/var/log/Xtigervnc.log 2>&1 &
    sleep 2
fi

# Start a persistent session D-Bus bus saved to /run/user/0/dbus_session
eval \$(dbus-launch --sh-syntax </dev/null)
echo \"export DBUS_SESSION_BUS_ADDRESS='\$DBUS_SESSION_BUS_ADDRESS'\" > /run/user/0/dbus_session
echo \"export DBUS_SESSION_BUS_PID='\$DBUS_SESSION_BUS_PID'\" >> /run/user/0/dbus_session
export DBUS_SESSION_BUS_ADDRESS

# Apply GNOME 46 macOS Sonoma gsettings on the live session D-Bus
gsettings set org.gnome.desktop.interface gtk-theme 'WhiteSur-Dark' 2>/dev/null || true
gsettings set org.gnome.desktop.interface icon-theme 'WhiteSur-dark' 2>/dev/null || true
gsettings set org.gnome.desktop.interface color-scheme 'prefer-dark' 2>/dev/null || true
gsettings set org.gnome.desktop.wm.preferences theme 'WhiteSur-Dark' 2>/dev/null || true
gsettings set org.gnome.desktop.wm.preferences button-layout 'close,minimize,maximize:menu' 2>/dev/null || true
gsettings set org.gnome.desktop.background picture-uri 'file:///usr/share/backgrounds/macos-sonoma.svg' 2>/dev/null || true
gsettings set org.gnome.desktop.background picture-uri-dark 'file:///usr/share/backgrounds/macos-sonoma.svg' 2>/dev/null || true

# Configure gnome-panel to ONLY show the macOS Top Bar
gsettings set org.gnome.gnome-panel.layout toplevel-id-list \"['top-panel']\" 2>/dev/null || true

# Configure Plank Dock
gsettings set net.launchpad.plank.dock.settings:/net/launchpad/plank/docks/dock1/ theme 'Transparent' 2>/dev/null || true
gsettings set net.launchpad.plank.dock.settings:/net/launchpad/plank/docks/dock1/ zoom-enabled true 2>/dev/null || true
gsettings set net.launchpad.plank.dock.settings:/net/launchpad/plank/docks/dock1/ zoom-percent 150 2>/dev/null || true
gsettings set net.launchpad.plank.dock.settings:/net/launchpad/plank/docks/dock1/ icon-size 48 2>/dev/null || true
gsettings set net.launchpad.plank.dock.settings:/net/launchpad/plank/docks/dock1/ hide-mode 'none' 2>/dev/null || true

# Render macOS Sonoma Aurora Wallpaper onto X11 root window
if [ -f /usr/share/backgrounds/macos-sonoma.png ]; then
    feh --bg-scale /usr/share/backgrounds/macos-sonoma.png </dev/null >/dev/null 2>&1 || true
elif [ -f /usr/share/backgrounds/macos-sonoma.svg ]; then
    feh --bg-scale /usr/share/backgrounds/macos-sonoma.svg </dev/null >/dev/null 2>&1 || true
fi

# Start GNOME Metacity Window Manager (with WhiteSur macOS traffic lights & compositing)
metacity --replace </dev/null >/var/log/gnome_apps/metacity.log 2>&1 &
sleep 1

# Start GNOME Top Panel (Applications / Places / Clock / Status Bar)
gnome-panel </dev/null >/var/log/gnome_apps/gnome-panel.log 2>&1 &
sleep 2

# Start GNOME Terminal Server on session D-Bus (with UTF-8 locale)
if [ -x /usr/libexec/gnome-terminal-server ]; then
    /usr/libexec/gnome-terminal-server </dev/null >/var/log/gnome_apps/gnome-terminal-server.log 2>&1 &
fi

# Start macOS Sonoma Magnifying Plank Dock at bottom
plank </dev/null >/var/log/gnome_apps/plank.log 2>&1 &
sleep 1
EOF
chmod +x /usr/local/bin/start_gnome_macos.sh

echo '=== [4/5] Launching GNOME 46 macOS Sonoma Desktop & Basic Apps (Staggered to Protect Battery) ==='
rm -f /var/log/gnome_apps/*.log
/usr/local/bin/start_gnome_macos.sh
source /run/user/0/dbus_session

/usr/local/bin/nautilus /root </dev/null >/var/log/gnome_apps/nautilus.log 2>&1 &
sleep 2
kgx </dev/null >/var/log/gnome_apps/kgx.log 2>&1 &
sleep 1
gnome-text-editor </dev/null >/var/log/gnome_apps/text-editor.log 2>&1 &
sleep 1
gnome-calculator </dev/null >/var/log/gnome_apps/calculator.log 2>&1 &
sleep 1
gnome-system-monitor </dev/null >/var/log/gnome_apps/system-monitor.log 2>&1 &
sleep 3

echo '=== [5/5] Checking Running Windows & Application Logs ==='
xwininfo -root -tree | grep -E 'Nautilus|Root|Home|Console|Text Editor|Calculator|System Monitor|gnome-panel|plank|Files'
for f in /var/log/gnome_apps/*.log; do
    echo \"--- \$f ---\"
    tail -n 5 \"\$f\"
done

scrot -o /tmp/gnome_macos_desktop.png </dev/null
ls -lh /tmp/gnome_macos_desktop.png
"
