#!/sbin/sh
export PATH=/sbin:/system/bin:/system/xbin:/vendor/bin

chroot /mnt/ubuntu /bin/bash -c "
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

echo '=== [1/5] Adding Android Supplementary Group Names & Hostname ==='
echo 'Galaxy-S8-Ubuntu' > /etc/hostname
hostname Galaxy-S8-Ubuntu 2>/dev/null || true
grep -q 'Galaxy-S8-Ubuntu' /etc/hosts || echo '127.0.1.1 Galaxy-S8-Ubuntu' >> /etc/hosts

for grp in '1004:aid_input' '1007:aid_log' '1011:aid_adb' '1015:aid_sdcard_rw' '1028:aid_sdcard_r' '3001:aid_bt_admin' '3002:aid_bt' '3003:aid_inet' '3006:aid_net_bw' '3009:aid_readproc' '3011:aid_uhid'; do
    gid=\${grp%%:*}
    gname=\${grp#*:}
    if ! grep -q \":\${gid}:\" /etc/group; then
        echo \"\${gname}:x:\${gid}:root\" >> /etc/group
    fi
done

echo '=== [2/5] Disabling D-Bus xdg-desktop-portal 25s Timeout so Nautilus Renders Instantly ==='
mkdir -p /usr/share/dbus-1/services.disabled
mv /usr/share/dbus-1/services/org.freedesktop.portal.* /usr/share/dbus-1/services.disabled/ 2>/dev/null || true
mv /usr/share/dbus-1/services/org.freedesktop.impl.portal.* /usr/share/dbus-1/services.disabled/ 2>/dev/null || true

cat << 'EOF' > /etc/profile.d/s8_gnome_env.sh
export LANG=C.UTF-8
export LC_ALL=C.UTF-8
export DISPLAY=:1
export GDK_BACKEND=x11
export GSK_RENDERER=cairo
export GTK_USE_PORTAL=0
export GDK_DEBUG=no-portals
export LIBGL_ALWAYS_SOFTWARE=1
export GTK_THEME=WhiteSur-Dark
export GTK_A11Y=none
export NO_AT_BRIDGE=1
export XDG_CURRENT_DESKTOP=GNOME
export XDG_SESSION_TYPE=x11
export XDG_RUNTIME_DIR=/run/user/0
export GST_PLUGIN_FEATURE_RANK=v4l2src:NONE,v4l2sink:NONE,v4l2deviceprovider:NONE
export WEBKIT_DISABLE_SANDBOX_THIS_IS_DANGEROUS=1
export WEBKIT_DISABLE_DMABUF_RENDERER=1
export WEBKIT_DISABLE_COMPOSITING_MODE=1
if [ -f /run/user/0/dbus_session ]; then
    source /run/user/0/dbus_session
fi
EOF
chmod +x /etc/profile.d/s8_gnome_env.sh

echo '=== [3/5] Applying macOS Sonoma Traffic-Light Buttons (Left Side + Red/Yellow/Green) to GTK3 & GTK4 ==='
mkdir -p /root/.config/gtk-3.0 /root/.config/gtk-4.0
cat << 'EOF' > /root/.config/gtk-3.0/settings.ini
[Settings]
gtk-theme-name=WhiteSur-Dark
gtk-icon-theme-name=WhiteSur-dark
gtk-font-name=Sans 10
gtk-application-prefer-dark-theme=1
gtk-decoration-layout=close,minimize,maximize:menu
EOF

cat << 'EOF' > /root/.config/gtk-4.0/settings.ini
[Settings]
gtk-theme-name=WhiteSur-Dark
gtk-icon-theme-name=WhiteSur-dark
gtk-font-name=Sans 10
gtk-application-prefer-dark-theme=1
gtk-decoration-layout=close,minimize,maximize:menu
EOF

cat << 'EOF' > /tmp/macos_traffic_lights.css
/* macOS Sonoma Red / Yellow / Green Traffic Light Window Controls */
windowcontrols button.close,
headerbar button.titlebutton.close {
    background-color: #ff5f56;
    background-image: none;
    color: transparent;
    min-width: 14px;
    min-height: 14px;
    padding: 0;
    margin: 0 3px;
    border-radius: 9999px;
    border: 1px solid rgba(0,0,0,0.2);
}
windowcontrols button.minimize,
headerbar button.titlebutton.minimize {
    background-color: #ffbd2e;
    background-image: none;
    color: transparent;
    min-width: 14px;
    min-height: 14px;
    padding: 0;
    margin: 0 3px;
    border-radius: 9999px;
    border: 1px solid rgba(0,0,0,0.2);
}
windowcontrols button.maximize,
headerbar button.titlebutton.maximize {
    background-color: #27c93f;
    background-image: none;
    color: transparent;
    min-width: 14px;
    min-height: 14px;
    padding: 0;
    margin: 0 3px;
    border-radius: 9999px;
    border: 1px solid rgba(0,0,0,0.2);
}
windowcontrols button.close:hover,
windowcontrols button.minimize:hover,
windowcontrols button.maximize:hover,
headerbar button.titlebutton.close:hover,
headerbar button.titlebutton.minimize:hover,
headerbar button.titlebutton.maximize:hover {
    color: #1e1e2e;
}
EOF

grep -q 'macOS Sonoma Red / Yellow / Green' /root/.config/gtk-4.0/gtk.css 2>/dev/null || cat /tmp/macos_traffic_lights.css >> /root/.config/gtk-4.0/gtk.css
grep -q 'macOS Sonoma Red / Yellow / Green' /root/.config/gtk-3.0/gtk.css 2>/dev/null || cat /tmp/macos_traffic_lights.css >> /root/.config/gtk-3.0/gtk.css

echo '=== [4/5] Updating start_gnome_macos.sh with Clock Applet & gsd-xsettings ==='
cat << 'EOF' > /usr/local/bin/start_gnome_macos.sh
#!/bin/bash
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

# Configure gnome-panel to show ONLY the macOS Top Bar with Menu Bar + Clock + Status
gsettings set org.gnome.gnome-panel.layout toplevel-id-list \"['top-panel']\" 2>/dev/null || true
gsettings set org.gnome.gnome-panel.layout object-id-list \"['menu-bar', 'clock', 'notification-area']\" 2>/dev/null || true
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
EOF
chmod +x /usr/local/bin/start_gnome_macos.sh

echo '=== [5/5] Restarting GNOME 46 macOS Sonoma Desktop & Launching All Basic Apps ==='
killall -9 nautilus kgx gnome-text-editor gnome-calculator gnome-system-monitor epiphany 2>/dev/null || true
/usr/local/bin/start_gnome_macos.sh
source /run/user/0/dbus_session

/usr/local/bin/nautilus /root </dev/null >/var/log/gnome_apps/nautilus.log 2>&1 &
sleep 2
kgx </dev/null >/var/log/gnome_apps/kgx.log 2>&1 &
sleep 1
gnome-calculator </dev/null >/var/log/gnome_apps/calculator.log 2>&1 &
sleep 1
gnome-system-monitor </dev/null >/var/log/gnome_apps/system-monitor.log 2>&1 &
sleep 2

scrot -o /tmp/gnome_macos_desktop.png </dev/null
ls -lh /tmp/gnome_macos_desktop.png
"

