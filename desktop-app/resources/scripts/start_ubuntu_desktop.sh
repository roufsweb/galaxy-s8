#!/bin/bash
export DISPLAY=:1
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export HOME=/root
export USER=root
rm -f /run/user/0/dbus_session
mkdir -p /run/user/0 /tmp/.X11-unix /var/log/gnome_apps /root/Desktop /root/Documents /root/Downloads /root/Pictures
chmod 700 /run/user/0
chmod 1777 /tmp/.X11-unix

# Stop any old desktop processes cleanly (including Plank dock)
killall -9 plank xfce4-session xfwm4 xfce4-panel xfdesktop metacity gnome-panel gnome-shell gnome-terminal-server gsd-xsettings dbus-launch volumeicon s8_status_icon.py 2>/dev/null || true
sleep 1

# Ensure TigerVNC :1 is running
if ! pgrep -x Xtigervnc >/dev/null 2>&1; then
    rm -f /tmp/.X1-lock /tmp/.X11-unix/X1
    Xtigervnc :1 -geometry 1920x1080 -depth 24 -rfbport 5901 -PasswordFile /root/.vnc/passwd -AlwaysShared -AcceptKeyEvents -AcceptPointerEvents -SecurityTypes VncAuth </dev/null >/var/log/Xtigervnc.log 2>&1 &
    sleep 2
fi

# Start persistent session D-Bus bus saved to /run/user/0/dbus_session
eval $(dbus-launch --sh-syntax </dev/null)
echo "export DBUS_SESSION_BUS_ADDRESS='$DBUS_SESSION_BUS_ADDRESS'" > /run/user/0/dbus_session
echo "export DBUS_SESSION_BUS_PID='$DBUS_SESSION_BUS_PID'" >> /run/user/0/dbus_session
export DBUS_SESSION_BUS_ADDRESS

# Apply Official Ubuntu 24.04 LTS (Noble Numbat) Yaru Desktop Theme
gsettings set org.gnome.desktop.interface gtk-theme 'Yaru-dark' 2>/dev/null || true
gsettings set org.gnome.desktop.interface icon-theme 'Yaru' 2>/dev/null || true
gsettings set org.gnome.desktop.interface color-scheme 'prefer-dark' 2>/dev/null || true
gsettings set org.gnome.desktop.wm.preferences theme 'Yaru-dark' 2>/dev/null || true
# Standard Ubuntu window button layout: close/minimize/maximize on TOP-RIGHT!
gsettings set org.gnome.desktop.wm.preferences button-layout ':minimize,maximize,close' 2>/dev/null || true

# Set dark Ubuntu aubergine desktop background
xsetroot -solid '#2C001E' 2>/dev/null || true

# Configure gnome-panel: Applications & Places on left, Clock + Status on right
cat << 'DCONF' > /tmp/ubuntu_panel_layout.dconf
[layout]
object-id-list=['menu-bar', 'clock', 'notification-area']
toplevel-id-list=['top-panel']

[layout/toplevels/top-panel]
alignment='center'
animation-speed='fast'
auto-hide=false
auto-hide-size=1
enable-buttons=false
expand=true
hide-delay=300
monitor=0
orientation='top'
size=28
unhide-delay=100

[layout/objects/menu-bar]
applet-id='menu-bar'
module-id='org.gnome.gnome-panel.menu'
pack-index=0
pack-type='start'
toplevel-id='top-panel'

[layout/objects/clock]
applet-id='clock'
module-id='org.gnome.gnome-panel.clock'
pack-index=0
pack-type='end'
toplevel-id='top-panel'

[layout/objects/notification-area]
applet-id='notification-area'
module-id='org.gnome.gnome-panel.notification-area'
pack-index=1
pack-type='end'
toplevel-id='top-panel'
DCONF

dconf reset -f /org/gnome/gnome-panel/ 2>/dev/null || true
dconf load /org/gnome/gnome-panel/ < /tmp/ubuntu_panel_layout.dconf 2>/dev/null || true

# Start GNOME XSettings daemon
if [ -x /usr/libexec/gsd-xsettings ]; then
    /usr/libexec/gsd-xsettings </dev/null >/var/log/gnome_apps/gsd-xsettings.log 2>&1 &
fi

# Start Metacity Window Manager
metacity --replace </dev/null >/var/log/gnome_apps/metacity.log 2>&1 &
sleep 1

# Start Top Panel
gnome-panel </dev/null >/var/log/gnome_apps/gnome-panel.log 2>&1 &
sleep 1

# Start Systray Icons
volumeicon </dev/null >/var/log/gnome_apps/volumeicon.log 2>&1 &
if [ -x /usr/local/bin/s8_status_icon.py ]; then
    /usr/local/bin/s8_status_icon.py </dev/null >/var/log/gnome_apps/s8_status_icon.log 2>&1 &
fi

# Start GNOME Terminal Server
if [ -x /usr/libexec/gnome-terminal-server ]; then
    /usr/libexec/gnome-terminal-server </dev/null >/var/log/gnome_apps/gnome-terminal-server.log 2>&1 &
fi
