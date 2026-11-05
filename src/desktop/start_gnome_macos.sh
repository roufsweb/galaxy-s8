#!/bin/bash
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
rm -f /run/user/0/dbus_session
source /etc/profile.d/s8_gnome_env.sh
mkdir -p /run/user/0 /tmp/.X11-unix /var/log/gnome_apps /root/Desktop /root/Documents /root/Downloads /root/Pictures
chmod 700 /run/user/0
chmod 1777 /tmp/.X11-unix

# Stop old desktop processes cleanly
killall -9 xfce4-session xfwm4 xfce4-panel xfdesktop plank metacity gnome-panel gnome-shell gnome-terminal-server gsd-xsettings dbus-launch 2>/dev/null || true
sleep 1

# Ensure Xtigervnc :1 is running
if ! pgrep -x Xtigervnc >/dev/null 2>&1; then
    rm -f /tmp/.X1-lock /tmp/.X11-unix/X1
    Xtigervnc :1 -geometry 1920x1080 -depth 24 -rfbport 5901 -PasswordFile /root/.vnc/passwd -AlwaysShared -AcceptKeyEvents -AcceptPointerEvents -SecurityTypes VncAuth </dev/null >/var/log/Xtigervnc.log 2>&1 &
    sleep 2
fi

# Start a persistent session D-Bus bus saved to /run/user/0/dbus_session
eval $(dbus-launch --sh-syntax </dev/null)
echo "export DBUS_SESSION_BUS_ADDRESS='$DBUS_SESSION_BUS_ADDRESS'" > /run/user/0/dbus_session
echo "export DBUS_SESSION_BUS_PID='$DBUS_SESSION_BUS_PID'" >> /run/user/0/dbus_session
export DBUS_SESSION_BUS_ADDRESS

# Apply GNOME 46 macOS Sonoma gsettings on the live session D-Bus
gsettings set org.gnome.desktop.interface gtk-theme 'WhiteSur-Dark' 2>/dev/null || true
gsettings set org.gnome.desktop.interface icon-theme 'WhiteSur-dark' 2>/dev/null || true
gsettings set org.gnome.desktop.interface color-scheme 'prefer-dark' 2>/dev/null || true
gsettings set org.gnome.desktop.wm.preferences theme 'WhiteSur-Dark' 2>/dev/null || true
gsettings set org.gnome.desktop.wm.preferences button-layout 'close,minimize,maximize:menu' 2>/dev/null || true
gsettings set org.gnome.desktop.background picture-uri 'file:///usr/share/backgrounds/macos-sonoma.svg' 2>/dev/null || true
gsettings set org.gnome.desktop.background picture-uri-dark 'file:///usr/share/backgrounds/macos-sonoma.svg' 2>/dev/null || true

# Configure gnome-panel to show ONLY the macOS Top Bar with Menu Bar + Clock + Status
gsettings set org.gnome.gnome-panel.layout toplevel-id-list "['top-panel']" 2>/dev/null || true
gsettings set org.gnome.gnome-panel.layout object-id-list "['menu-bar', 'clock', 'notification-area']" 2>/dev/null || true
gsettings set org.gnome.gnome-panel.object:/org/gnome/gnome-panel/layout/objects/clock/ toplevel-id 'top-panel' 2>/dev/null || true
gsettings set org.gnome.gnome-panel.object:/org/gnome/gnome-panel/layout/objects/clock/ object-iid 'ClockAppletFactory::ClockApplet' 2>/dev/null || true
gsettings set org.gnome.gnome-panel.object:/org/gnome/gnome-panel/layout/objects/clock/ pack-type 'end' 2>/dev/null || true
gsettings set org.gnome.gnome-panel.object:/org/gnome/gnome-panel/layout/objects/clock/ pack-index 0 2>/dev/null || true

# Configure Plank Dock
gsettings set net.launchpad.plank.dock.settings:/net/launchpad/plank/docks/dock1/ theme 'Transparent' 2>/dev/null || true
gsettings set net.launchpad.plank.dock.settings:/net/launchpad/plank/docks/dock1/ zoom-enabled true 2>/dev/null || true
gsettings set net.launchpad.plank.dock.settings:/net/launchpad/plank/docks/dock1/ zoom-percent 150 2>/dev/null || true
gsettings set net.launchpad.plank.dock.settings:/net/launchpad/plank/docks/dock1/ icon-size 48 2>/dev/null || true
gsettings set net.launchpad.plank.dock.settings:/net/launchpad/plank/docks/dock1/ hide-mode 'none' 2>/dev/null || true

# Start GNOME XSettings daemon so GTK4/libadwaita apps honor left-side traffic lights and dark mode
if [ -x /usr/libexec/gsd-xsettings ]; then
    /usr/libexec/gsd-xsettings </dev/null >/var/log/gnome_apps/gsd-xsettings.log 2>&1 &
fi

# Render macOS Sonoma Aurora Wallpaper onto X11 root window
if [ -f /usr/share/backgrounds/macos-sonoma.png ]; then
    feh --bg-scale /usr/share/backgrounds/macos-sonoma.png </dev/null >/dev/null 2>&1 || true
elif [ -f /usr/share/backgrounds/macos-sonoma.svg ]; then
    feh --bg-scale /usr/share/backgrounds/macos-sonoma.svg </dev/null >/dev/null 2>&1 || true
fi

# Start GNOME Metacity Window Manager
metacity --replace </dev/null >/var/log/gnome_apps/metacity.log 2>&1 &
sleep 1

# Start GNOME Top Panel
gnome-panel </dev/null >/var/log/gnome_apps/gnome-panel.log 2>&1 &
sleep 1

# Start GNOME Terminal Server
if [ -x /usr/libexec/gnome-terminal-server ]; then
    /usr/libexec/gnome-terminal-server </dev/null >/var/log/gnome_apps/gnome-terminal-server.log 2>&1 &
fi

# Start macOS Sonoma Magnifying Plank Dock at bottom
plank </dev/null >/var/log/gnome_apps/plank.log 2>&1 &
sleep 1

