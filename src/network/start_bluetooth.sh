#!/bin/bash
# Native Broadcom BCM4361 BlueZ Bluetooth Supervisor for Samsung Galaxy S8
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

rfkill unblock 0 2>/dev/null || true

if ! pgrep -x hciattach >/dev/null 2>&1; then
    hciattach /dev/ttySAC1 bcm43xx 3000000 flow 08:AE:D6:0B:70:C2 </dev/null >/var/log/hciattach.log 2>&1 &
    sleep 2
    hciconfig hci0 up 2>/dev/null || true
fi

if ! pgrep -x bluetoothd >/dev/null 2>&1; then
    /usr/libexec/bluetooth/bluetoothd --experimental </dev/null >/var/log/bluetoothd.log 2>&1 &
fi

