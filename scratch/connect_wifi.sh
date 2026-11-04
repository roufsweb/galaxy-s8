#!/sbin/sh
export TMPDIR=/tmp
echo "[*] Mounting /system and /efs for Broadcom 4361 Wi-Fi & Bluetooth firmware..."
mkdir -p /system_root /efs /data/vendor/conn /data/vendor/wifi/wpa/sockets /tmp
mountpoint -q /system_root || mount -o ro /dev/block/sda17 /system_root 2>/dev/null
mountpoint -q /efs || mount -o ro /dev/block/sda3 /efs 2>/dev/null
rm -rf /system /vendor
ln -s /system_root /system
ln -s /system_root/vendor /vendor

# Bring up loopback
ip addr add 127.0.0.1/8 dev lo 2>/dev/null
ip link set lo up

# Ensure DNS is configured in both ramdisk and Ubuntu rootfs
echo "nameserver 8.8.8.8" > /etc/resolv.conf
echo "nameserver 1.1.1.1" >> /etc/resolv.conf
if [ -d /mnt/ubuntu/etc ]; then
    rm -f /mnt/ubuntu/etc/resolv.conf
    echo "nameserver 8.8.8.8" > /mnt/ubuntu/etc/resolv.conf
    echo "nameserver 1.1.1.1" >> /mnt/ubuntu/etc/resolv.conf
fi

# Check if wlan0 is already connected with an IPv4 address
if ip -4 addr show wlan0 2>/dev/null | grep -q "inet "; then
    echo "[+] wlan0 is already connected!"
    ip -4 addr show wlan0 | grep inet
    exit 0
fi

# Configure Broadcom DHD module parameters (no _b0 suffix - kernel appends it)
echo -n "/vendor/etc/wifi/bcmdhd_sta.bin" > /sys/module/dhd/parameters/firmware_path
echo -n "/vendor/etc/wifi/nvram.txt" > /sys/module/dhd/parameters/nvram_path
echo -n "/vendor/etc/wifi/bcmdhd_clm.blob" > /sys/module/dhd/parameters/clm_path

echo "[*] Bringing up wlan0..."
ip link set wlan0 up
sleep 1

# Write wpa_supplicant.conf for <WIFI_SSID>
printf 'ctrl_interface=/data/vendor/wifi/wpa/sockets\nupdate_config=1\npmf=1\n\nnetwork={\n\tssid="<WIFI_SSID>"\n\tpsk="<WIFI_PASSWORD>"\n\tkey_mgmt=WPA-PSK\n\tscan_ssid=1\n}\n' > /data/vendor/wifi/wpa/wpa_supplicant.conf
chmod 600 /data/vendor/wifi/wpa/wpa_supplicant.conf

# Kill any existing wpa_supplicant and start fresh with closed stdio
killall wpa_supplicant 2>/dev/null
sleep 1
echo "[*] Starting wpa_supplicant on wlan0 for SSID '<WIFI_SSID>'..."
LD_LIBRARY_PATH=/system/lib64:/vendor/lib64 /vendor/bin/hw/wpa_supplicant -B -i wlan0 -D nl80211 -c /data/vendor/wifi/wpa/wpa_supplicant.conf </dev/null >/dev/null 2>&1

# Wait for association
for i in 1 2 3 4 5 6 7 8 9 10; do
    sleep 1
    if dmesg | tail -n 40 | grep -q "wl_bss_connect_done succeeded"; then
        echo "[+] Associated with <WIFI_SSID>!"
        break
    fi
done

echo "[*] Requesting DHCP lease on wlan0..."
printf '#!/sbin/sh\ncase "$1" in\n  deconfig)\n    ip addr flush dev $interface\n    ;;\n  bound|renew)\n    ip addr flush dev $interface\n    ip addr add $ip/$mask dev $interface\n    if [ -n "$router" ]; then\n      for r in $router; do\n        ip route add default via $r dev $interface 2>/dev/null\n      done\n    fi\n    echo "nameserver 8.8.8.8" > /etc/resolv.conf\n    echo "nameserver 1.1.1.1" >> /etc/resolv.conf\n    if [ -d /mnt/ubuntu/etc ]; then\n      rm -f /mnt/ubuntu/etc/resolv.conf\n      echo "nameserver 8.8.8.8" > /mnt/ubuntu/etc/resolv.conf\n      echo "nameserver 1.1.1.1" >> /mnt/ubuntu/etc/resolv.conf\n    fi\n    ;;\nesac\n' > /tmp/udhcpc.script
chmod 755 /tmp/udhcpc.script
/sbin/busybox udhcpc -i wlan0 -s /tmp/udhcpc.script -t 4 -T 2 -n -q </dev/null

echo "=== WLAN0 STATUS ==="
ip -4 addr show wlan0
