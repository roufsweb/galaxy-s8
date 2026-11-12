#!/bin/bash
# Uninstaller for Galaxy S8 Hardware Pack
set -e
if [ -d /run/systemd/system ] && command -v systemctl >/dev/null 2>&1; then
    for svc in s8-dp-bridge.service s8-novnc-ws.service s8-vnc.service s8-buttons.service s8-typec.service s8-led.service s8-time-sync.service s8-bluetooth.service s8-usb-gadget.service s8-hardware.service; do
        systemctl disable --now "$svc" 2>/dev/null || true
    done
    systemctl daemon-reload 2>/dev/null || true
fi
rm -f /etc/systemd/system/s8-*.service
rm -f /etc/systemd/logind.conf.d/99-s8-power.conf
rm -f /etc/udev/rules.d/99-s8-no-fimc.rules /etc/udev/rules.d/99-s8-devlinks.rules /etc/udev/rules.d/60-persistent-v4l.rules
rm -f /usr/local/bin/s8ctl /usr/local/bin/s8-dp /usr/local/bin/s8_wifi.py /usr/local/bin/s8-hardware-init.sh /usr/local/bin/s8-usb-gadget.sh /usr/local/bin/s8-time-sync.py /usr/local/bin/s8-dp-bridge.sh /usr/local/bin/s8-vnc-setup.sh /usr/local/bin/s8_button_daemon /usr/local/bin/exynos_dp_bridge /usr/local/bin/s8_typec_daemon.py /usr/local/bin/s8_led_supervisor.py /usr/local/bin/init_audio.sh /usr/local/bin/start_bluetooth.sh
rm -f /usr/local/libexec/galaxy-s8-hw-setup.sh /etc/s8-hw-version /etc/init.d/s8-hardware
echo "[galaxy-s8-hw] Uninstalled."

