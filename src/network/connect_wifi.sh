#!/sbin/sh
export PATH=/sbin:/system/bin:/system/xbin:/vendor/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/bin
export TMPDIR=/data/local/tmp
mkdir -p /data/local/tmp /system_root /efs /mnt/ubuntu/run/wpa_supplicant /mnt/ubuntu/etc

echo "=== [Wi-Fi Subsystem] Initializing Broadcom BCM4361 ==="

# 1. Mount firmware dependencies
mountpoint -q /system_root || mount -o ro /dev/block/sda17 /system_root 2>/dev/null
mountpoint -q /efs || mount -o ro /dev/block/sda3 /efs 2>/dev/null
rm -rf /system /vendor
ln -s /system_root /system 2>/dev/null || true
ln -s /system_root/vendor /vendor 2>/dev/null || true

# 2. Bring up loopback interface
ip addr add 127.0.0.1/8 dev lo 2>/dev/null || true
ip link set lo up 2>/dev/null || true

# 3. Load Broadcom DHD parameters (kernel appends _b0 suffix automatically)
echo -n "/system_root/vendor/etc/wifi/bcmdhd_sta.bin" > /sys/module/dhd/parameters/firmware_path 2>/dev/null || true
echo -n "/system_root/vendor/etc/wifi/nvram.txt" > /sys/module/dhd/parameters/nvram_path 2>/dev/null || true
echo -n "/system_root/vendor/etc/wifi/bcmdhd_clm.blob" > /sys/module/dhd/parameters/clm_path 2>/dev/null || true

ip link set wlan0 up 2>/dev/null || true
sleep 1

# 4. Check for MicroSD Card Wi-Fi Configuration Drop (Raspberry Pi style)
SD_CARD_DIR="/mnt/ubuntu/media/sdcard"
[ -d "$SD_CARD_DIR" ] || SD_CARD_DIR="/data/sdcard"

if [ -d "$SD_CARD_DIR" ]; then
    # Direct wpa_supplicant.conf drop
    if [ -f "$SD_CARD_DIR/wpa_supplicant.conf" ]; then
        echo "[+] Found wpa_supplicant.conf on MicroSD card! Applying..."
        cp "$SD_CARD_DIR/wpa_supplicant.conf" /data/linux/wpa_ubuntu.conf
        cp "$SD_CARD_DIR/wpa_supplicant.conf" /mnt/ubuntu/etc/wpa_ubuntu.conf
    # Simple wifi.txt drop (ssid=... password=...)
    elif [ -f "$SD_CARD_DIR/wifi.txt" ]; then
        echo "[+] Found wifi.txt on MicroSD card! Parsing credentials..."
        RAW_SSID=$(grep -i "^ssid=" "$SD_CARD_DIR/wifi.txt" | head -n 1 | cut -d'=' -f2- | tr -d '\r\n"')
        RAW_PASS=$(grep -i "^password=" "$SD_CARD_DIR/wifi.txt" | head -n 1 | cut -d'=' -f2- | tr -d '\r\n"')

        # Fallback to SSID:PASS format
        if [ -z "$RAW_SSID" ]; then
            RAW_SSID=$(head -n 1 "$SD_CARD_DIR/wifi.txt" | cut -d':' -f1 | tr -d '\r\n"')
            RAW_PASS=$(head -n 1 "$SD_CARD_DIR/wifi.txt" | cut -d':' -f2 | tr -d '\r\n"')
        fi

        if [ -n "$RAW_SSID" ]; then
            echo "[+] Parsed SSID: $RAW_SSID"
            cat << EOF > /data/linux/wpa_ubuntu.conf
ctrl_interface=/var/run/wpa_supplicant
update_config=1

network={
    ssid="$RAW_SSID"
EOF
            if [ -n "$RAW_PASS" ]; then
                echo "    psk=\"$RAW_PASS\"" >> /data/linux/wpa_ubuntu.conf
                echo "    key_mgmt=WPA-PSK" >> /data/linux/wpa_ubuntu.conf
            else
                echo "    key_mgmt=NONE" >> /data/linux/wpa_ubuntu.conf
            fi
            echo "}" >> /data/linux/wpa_ubuntu.conf
            cp /data/linux/wpa_ubuntu.conf /mnt/ubuntu/etc/wpa_ubuntu.conf
        fi
    fi
fi

# Ensure /mnt/ubuntu/etc/wpa_ubuntu.conf is in sync
if [ -f /data/linux/wpa_ubuntu.conf ] && [ ! -f /mnt/ubuntu/etc/wpa_ubuntu.conf ]; then
    cp /data/linux/wpa_ubuntu.conf /mnt/ubuntu/etc/wpa_ubuntu.conf
fi

# 5. Attempt Station Mode Connection
CONNECTED=0
if [ -f /mnt/ubuntu/etc/wpa_ubuntu.conf ]; then
    echo "[*] Connecting to configured Wi-Fi network..."
    killall wpa_supplicant 2>/dev/null || true
    ip addr flush dev wlan0 2>/dev/null || true

    rm -rf /mnt/ubuntu/var/run
    ln -s /run /mnt/ubuntu/var/run 2>/dev/null || true

    chroot /mnt/ubuntu /usr/bin/env PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin /usr/sbin/wpa_supplicant -B -i wlan0 -c /etc/wpa_ubuntu.conf </dev/null >/tmp/wpa.log 2>&1

    for i in 1 2 3 4 5 6 7 8 9 10 11 12; do
        sleep 1
        STATUS=$(chroot /mnt/ubuntu /usr/bin/env PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin /usr/sbin/wpa_cli status 2>/dev/null | grep "wpa_state=" || true)
        if echo "$STATUS" | grep -q "COMPLETED"; then
            echo "[+] Wi-Fi associated successfully!"
            CONNECTED=1
            break
        fi
    done
fi

if [ "$CONNECTED" -eq 1 ]; then
    echo "[*] Requesting DHCP lease via dhclient..."
    killall dhclient 2>/dev/null || true
    chroot /mnt/ubuntu /usr/bin/env PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin /usr/sbin/dhclient -v wlan0 </dev/null >/tmp/dhclient.log 2>&1

    # Configure DNS
    echo "nameserver 8.8.8.8" > /mnt/ubuntu/etc/resolv.conf
    echo "nameserver 1.1.1.1" >> /mnt/ubuntu/etc/resolv.conf
    echo "nameserver 8.8.8.8" > /etc/resolv.conf
    echo "nameserver 1.1.1.1" >> /etc/resolv.conf

    IP_ADDR=$(ip addr show wlan0 2>/dev/null | grep "inet " | awk '{print $2}' | cut -d'/' -f1)
    echo "[+] CONNECTED: IP is $IP_ADDR"

    # Write status to MicroSD card for easy headless lookup
    if [ -d "$SD_CARD_DIR" ]; then
        cat << EOF > "$SD_CARD_DIR/WIFI_INFO.txt"
Samsung Galaxy S8 Native Linux Server
Maintained by roufsweb (https://github.com/roufsweb)
-------------------------------------------------------
Status: CONNECTED
IP Address: $IP_ADDR
Web Desktop: http://${IP_ADDR}:6080/vnc.html (Password: ubuntu)
Native VNC:  ${IP_ADDR}:5901 (Password: ubuntu)
SSH Console: ssh root@${IP_ADDR} (Password: ubuntu)
Hardware Center: s8ctl status
-------------------------------------------------------
Timestamp: $(date 2>/dev/null || echo "Bootup")
EOF
        sync
    fi

    # Success haptic pulse (2x 150ms)
    echo 150 > /sys/class/timed_output/vibrator/enable 2>/dev/null || true
    sleep 0.25
    echo 150 > /sys/class/timed_output/vibrator/enable 2>/dev/null || true
    exit 0
fi

# 6. Fallback: Start Setup Hotspot (SoftAP Mode)
echo "[!] Wi-Fi connection failed or no network configured. Launching Setup Hotspot (GalaxyS8-Setup)..."
killall wpa_supplicant dhclient dnsmasq 2>/dev/null || true
ip addr flush dev wlan0 2>/dev/null || true

# Assign static IP
ip addr add 192.168.4.1/24 dev wlan0
ip link set wlan0 up

# Start dnsmasq DHCP & Captive DNS server
cat << 'EOF' > /tmp/dnsmasq_ap.conf
interface=wlan0
dhcp-range=192.168.4.10,192.168.4.50,255.255.255.0,12h
address=/#/192.168.4.1
no-resolv
log-queries
EOF

chroot /mnt/ubuntu /usr/bin/env PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin /usr/sbin/dnsmasq -C /tmp/dnsmasq_ap.conf </dev/null >/tmp/dnsmasq.log 2>&1 || true

# Start Open SoftAP via hostapd
cat << 'EOF' > /tmp/ap_hostapd.conf
interface=wlan0
driver=nl80211
ssid=GalaxyS8-Setup
hw_mode=g
channel=6
auth_algs=1
wmm_enabled=0
EOF

chroot /mnt/ubuntu /usr/bin/env PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin /usr/sbin/hostapd /tmp/ap_hostapd.conf </dev/null >/tmp/hostapd.log 2>&1 &

# Start Web Captive Setup Portal
if [ -f /usr/local/bin/s8_wifi_portal.py ]; then
    chroot /mnt/ubuntu /usr/bin/env PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin python3 /usr/local/bin/s8_wifi_portal.py 8080 </dev/null >/tmp/portal.log 2>&1 &
fi

# Write Hotspot setup details to MicroSD card
if [ -d "$SD_CARD_DIR" ]; then
    cat << 'EOF' > "$SD_CARD_DIR/WIFI_INFO.txt"
Samsung Galaxy S8 Native Linux Server
Maintained by roufsweb (https://github.com/roufsweb)
-------------------------------------------------------
Status: HOTSPOT SETUP MODE
Hotspot SSID: GalaxyS8-Setup (Open Network)
Hotspot IP:   192.168.4.1
Setup Portal: http://192.168.4.1:8080

INSTRUCTIONS:
1. Connect your phone, tablet, or PC to "GalaxyS8-Setup" Wi-Fi.
2. Open your browser to http://192.168.4.1:8080
3. Select your home Wi-Fi, enter your password, and click Save.
-------------------------------------------------------
EOF
    sync
fi

# Alert user with 3 short vibration pulses (3x 80ms)
for p in 1 2 3; do
    echo 80 > /sys/class/timed_output/vibrator/enable 2>/dev/null || true
    sleep 0.15
done
echo "[+] Setup Hotspot active: Connect to 'GalaxyS8-Setup' -> http://192.168.4.1:8080"
