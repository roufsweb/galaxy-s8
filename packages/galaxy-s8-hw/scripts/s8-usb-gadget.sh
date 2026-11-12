#!/bin/sh
# s8-usb-gadget.sh -- Samsung Galaxy S8 USB Composite RNDIS + CDC-ACM Gadget & USB-LAN Auto-DHCP
export PATH=/run/s8:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

mkdir -p /sys/kernel/config 2>/dev/null || true
mountpoint -q /sys/kernel/config 2>/dev/null || mount -t configfs none /sys/kernel/config 2>/dev/null || true

G=/sys/kernel/config/usb_gadget/g1
if [ ! -d "$G/functions/rndis.usb0" ] || [ "$(cat "$G/UDC" 2>/dev/null)" != "10c00000.dwc3" ]; then
    echo 0 > /sys/class/android_usb/android0/enable 2>/dev/null || true
    echo "" > "$G/UDC" 2>/dev/null || true
    mkdir -p "$G/strings/0x409" "$G/configs/c.1/strings/0x409" "$G/functions/rndis.usb0" "$G/functions/acm.gs0"
    echo 0x1D6B > "$G/idVendor"
    echo 0x0104 > "$G/idProduct"
    echo 0xEF > "$G/bDeviceClass"
    echo 0x02 > "$G/bDeviceSubClass" 2>/dev/null || true
    echo 0x01 > "$G/bDeviceProtocol" 2>/dev/null || true
    SERIAL=$(sed -n 's/.*androidboot.serialno=\([^ ]*\).*/\1/p' /proc/cmdline 2>/dev/null)
    [ -z "$SERIAL" ] && SERIAL="ce10171ab3e9620804"
    echo "$SERIAL" > "$G/strings/0x409/serialnumber"
    echo "Samsung" > "$G/strings/0x409/manufacturer"
    echo "Galaxy S8 Native Linux" > "$G/strings/0x409/product"
    echo "RNDIS+ACM" > "$G/configs/c.1/strings/0x409/configuration"
    echo 250 > "$G/configs/c.1/MaxPower" 2>/dev/null || true

    echo 1 > "$G/os_desc/use" 2>/dev/null || true
    echo 0xcd > "$G/os_desc/b_vendor_code" 2>/dev/null || true
    echo "MSFT100" > "$G/os_desc/qw_sign" 2>/dev/null || true
    echo "RNDIS" > "$G/functions/rndis.usb0/os_desc/interface.rndis/compatible_id" 2>/dev/null || true
    echo "5162001" > "$G/functions/rndis.usb0/os_desc/interface.rndis/sub_compatible_id" 2>/dev/null || true
    ln -sf "$G/configs/c.1" "$G/os_desc/c.1" 2>/dev/null || true

    ln -sf "$G/functions/rndis.usb0" "$G/configs/c.1/rndis.usb0" 2>/dev/null || true
    ln -sf "$G/functions/acm.gs0" "$G/configs/c.1/acm.gs0" 2>/dev/null || true
    echo "rndis,acm" > /sys/class/android_usb/android0/functions 2>/dev/null || echo "rndis" > /sys/class/android_usb/android0/functions 2>/dev/null || true
    echo "10c00000.dwc3" > "$G/UDC" 2>/dev/null || true
    echo 1 > /sys/class/android_usb/android0/enable 2>/dev/null || true
fi

for _i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
    ip link show rndis0 >/dev/null 2>&1 && break
    sleep 0.2
done

if ip link show rndis0 >/dev/null 2>&1; then
    ip addr replace 192.168.7.2/24 dev rndis0
    ip link set rndis0 up
    if command -v nmcli >/dev/null 2>&1; then
        nmcli dev set rndis0 managed no >/dev/null 2>&1 || true
    fi
    if ! pgrep -f "udhcpd.*rndis" >/dev/null 2>&1 && ! pgrep -f "dnsmasq.*rndis0" >/dev/null 2>&1; then
        if command -v dnsmasq >/dev/null 2>&1; then
            dnsmasq \
                --interface=rndis0 \
                --bind-interfaces \
                --port=0 \
                --dhcp-range=192.168.7.10,192.168.7.50,12h \
                --dhcp-option=3 \
                --dhcp-option=6 \
                --dhcp-leasefile=/run/dnsmasq-rndis.leases \
                --pid-file=/run/dnsmasq-rndis.pid 2>/dev/null || true
        elif command -v busybox >/dev/null 2>&1; then
            touch /run/s8-udhcpd.leases
            cat > /run/s8-udhcpd.conf <<'CONF'
start 192.168.7.10
end 192.168.7.50
interface rndis0
opt subnet 255.255.255.0
opt lease 43200
lease_file /run/s8-udhcpd.leases
CONF
            busybox udhcpd /run/s8-udhcpd.conf 2>/dev/null || true
        fi
    fi
fi

# Auto-DHCP background supervisor for USB Ethernet LAN dongles (eth0, usb1, enx*)
while true; do
    for netpath in /sys/class/net/*; do
        ifname=$(basename "$netpath")
        case "$ifname" in
            eth*|enx*|usb1|end*)
                ip link set "$ifname" up 2>/dev/null || true
                if ! ip -4 addr show dev "$ifname" 2>/dev/null | grep -q "inet "; then
                    if command -v dhclient >/dev/null 2>&1; then
                        dhclient -1 "$ifname" 2>/dev/null &
                    elif command -v udhcpc >/dev/null 2>&1; then
                        udhcpc -i "$ifname" -n -q 2>/dev/null &
                    elif [ -x /run/s8/udhcpc ]; then
                        /run/s8/udhcpc -i "$ifname" -s /run/s8/s8_udhcpc.script -n -q 2>/dev/null &
                    fi
                fi
                ;;
        esac
    done
    sleep 10
done
