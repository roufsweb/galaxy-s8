from phone_ssh import run_ssh_command

cmd = """
source /etc/profile.d/s8_gnome_env.sh
[ -f /run/user/0/dbus_session ] && source /run/user/0/dbus_session
export DISPLAY=:1

# Configure control-center launcher in gnome-panel
gsettings set org.gnome.gnome-panel.object:/org/gnome/gnome-panel/layout/objects/control-center-launcher/ toplevel-id 'top-panel'
gsettings set org.gnome.gnome-panel.object:/org/gnome/gnome-panel/layout/objects/control-center-launcher/ module-id 'launcher'
gsettings set org.gnome.gnome-panel.object:/org/gnome/gnome-panel/layout/objects/control-center-launcher/ applet-id 'launcher'
gsettings set org.gnome.gnome-panel.object:/org/gnome/gnome-panel/layout/objects/control-center-launcher/ pack-type 'end'
gsettings set org.gnome.gnome-panel.object:/org/gnome/gnome-panel/layout/objects/control-center-launcher/ pack-index 1
gsettings set org.gnome.gnome-panel.applet.launcher:/org/gnome/gnome-panel/layout/objects/control-center-launcher/ location 's8-control-center.desktop'

# Configure clock
gsettings set org.gnome.gnome-panel.object:/org/gnome/gnome-panel/layout/objects/clock/ toplevel-id 'top-panel'
gsettings set org.gnome.gnome-panel.object:/org/gnome/gnome-panel/layout/objects/clock/ module-id 'clock'
gsettings set org.gnome.gnome-panel.object:/org/gnome/gnome-panel/layout/objects/clock/ applet-id 'clock'
gsettings set org.gnome.gnome-panel.object:/org/gnome/gnome-panel/layout/objects/clock/ pack-type 'end'
gsettings set org.gnome.gnome-panel.object:/org/gnome/gnome-panel/layout/objects/clock/ pack-index 0

# Configure indicator-complete
gsettings set org.gnome.gnome-panel.object:/org/gnome/gnome-panel/layout/objects/indicator-complete/ toplevel-id 'top-panel'
gsettings set org.gnome.gnome-panel.object:/org/gnome/gnome-panel/layout/objects/indicator-complete/ module-id 'indicator'
gsettings set org.gnome.gnome-panel.object:/org/gnome/gnome-panel/layout/objects/indicator-complete/ applet-id 'indicator-complete'
gsettings set org.gnome.gnome-panel.object:/org/gnome/gnome-panel/layout/objects/indicator-complete/ pack-type 'end'
gsettings set org.gnome.gnome-panel.object:/org/gnome/gnome-panel/layout/objects/indicator-complete/ pack-index 2

# Apply layout
gsettings set org.gnome.gnome-panel.layout object-id-list "['menu-bar', 'clock', 'control-center-launcher', 'indicator-complete']"

# Restart gnome-panel cleanly
pkill -x gnome-panel
sleep 1
DISPLAY=:1 gnome-panel </dev/null >/var/log/gnome_apps/gnome-panel.log 2>&1 &
"""

out, err = run_ssh_command(cmd)
print("OUT:\n", out)
print("ERR:\n", err)
