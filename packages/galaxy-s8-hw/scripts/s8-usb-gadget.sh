#!/bin/bash
# s8-usb-gadget.sh -- Samsung Galaxy S8 USB ConfigFS RNDIS Ethernet Gadget & DHCP
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

mkdir -p /sys/kernel/config
mountpoint -q /sys/kernel/config || mount -t configfs none /sys/kernel/config 2>/dev/null || true

G=/sys/kernel/config/usb_gadget/g1
if [ ! -d "$G/functions/rndis.usb0" ] || [ "$(cat "$G/UDC" 2>/dev/null)" != "10c00000.dwc3" ]; then
    echo 0 > /sys/class/android_usb/android0/enable 2>/dev/null || true
    echo "" > "$G/UDC" 2>/dev/null || true
    mkdir -p "$G/strings/0x409" "$G/configs/c.1/strings/0x409" "$G/functions/rndis.usb0"
    echo 0x04E8 > "$G/idVendor"
    echo 0x6863 > "$G/idProduct"
    echo 0xE0 > "$G/bDeviceClass"
    echo 0x01 > "$G/bDeviceSubClass" 2>/dev/null || true
    echo 0x03 > "$G/bDeviceProtocol" 2>/dev/null || true
    SERIAL=$(sed -n 's/.*androidboot.serialno=\([^ ]*\).*/\1/p' /proc/cmdline 2>/dev/null)
    [ -z "$SERIAL" ] && SERIAL="ce10171ab3e9620804"
    echo "$SERIAL" > "$G/strings/0x409/serialnumber"
    echo "Samsung" > "$G/strings/0x409/manufacturer"
    echo "Galaxy S8 Native Linux" > "$G/strings/0x409/product"
    echo "RNDIS" > "$G/configs/c.1/strings/0x409/configuration"
    echo 250 > "$G/configs/c.1/MaxPower" 2>/dev/null || true
    ln -sf "$G/functions/rndis.usb0" "$G/configs/c.1/rndis.usb0" 2>/dev/null || true
    echo rndis > /sys/class/android_usb/android0/functions 2>/dev/null || true
    echo "10c00000.dwc3" > "$G/UDC" 2>/dev/null || true
    echo 1 > /sys/class/android_usb/android0/enable 2>/dev/null || true
fi

for i in $(seq 1 25); do
    ip link show rndis0 >/dev/null 2>&1 && break
    sleep 0.2
done

if ip link show rndis0 >/dev/null 2>&1; then
    ip addr replace 192.168.7.2/24 dev rndis0
    ip link set rndis0 up
    # Tell NetworkManager not to tear down rndis0
    if command -v nmcli >/dev/null 2>&1; then
        nmcli dev set rndis0 managed no >/dev/null 2>&1 || true
    fi
    if command -v dnsmasq >/dev/null 2>&1; then
        exec dnsmasq \
            --keep-in-foreground \
            --no-daemon \
            --interface=rndis0 \
            --bind-interfaces \
            --port=0 \
            --dhcp-range=192.168.7.10,192.168.7.50,12h \
            --dhcp-option=3 \
            --dhcp-option=6 \
            --dhcp-leasefile=/run/dnsmasq-rndis.leases \
            --pid-file=/run/dnsmasq-rndis.pid
    elif command -v busybox >/dev/null 2>&1 && busybox udhcpd --help >/dev/null 2>&1; then
        cat > /run/s8-udhcpd.conf <<'CONF'
start 192.168.7.10
end 192.168.7.50
interface rndis0
opt subnet 255.255.255.0
opt lease 43200
lease_file /run/s8-udhcpd.leases
CONF
        exec busybox udhcpd -f /run/s8-udhcpd.conf
    fi
fi

while true; do
    sleep 60
done

