#!/sbin/sh
export PATH=/sbin:/system/bin:/system/xbin:/vendor/bin
export TMPDIR=/data/local/tmp
mkdir -p /data/local/tmp

echo "[*] Killing old wpa_supplicants..."
killall wpa_supplicant 2>/dev/null
ip addr flush dev wlan0

# Broadcom DHD firmware config
echo -n "/vendor/etc/wifi/bcmdhd_sta.bin" > /sys/module/dhd/parameters/firmware_path
echo -n "/vendor/etc/wifi/nvram.txt" > /sys/module/dhd/parameters/nvram_path
echo -n "/vendor/etc/wifi/bcmdhd_clm.blob" > /sys/module/dhd/parameters/clm_path

ip link set wlan0 up
sleep 1

# Write wpa config
cat << 'EOF' > /data/linux/wpa_ubuntu.conf
ctrl_interface=/var/run/wpa_supplicant
update_config=1

network={
    ssid="<WIFI_SSID>"
    psk="<WIFI_PASSWORD>"
    key_mgmt=WPA-PSK
}
EOF

# Ensure /run and /var/run exist in chroot
mkdir -p /mnt/ubuntu/run/wpa_supplicant
rm -rf /mnt/ubuntu/var/run
ln -s /run /mnt/ubuntu/var/run

cp /data/linux/wpa_ubuntu.conf /mnt/ubuntu/etc/wpa_ubuntu.conf

echo "[*] Starting Ubuntu wpa_supplicant..."
chroot /mnt/ubuntu /usr/bin/env PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin /usr/sbin/wpa_supplicant -B -i wlan0 -c /etc/wpa_ubuntu.conf -f /var/log/wpa.log

echo "[*] Waiting for Wi-Fi connection..."
for i in 1 2 3 4 5 6 7 8 9 10; do
    sleep 1
    STATUS=$(chroot /mnt/ubuntu /usr/bin/env PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin /usr/sbin/wpa_cli status | grep "wpa_state=")
    echo "  $STATUS"
    if echo "$STATUS" | grep -q "COMPLETED"; then
        echo "[+] Wi-Fi associated successfully!"
        break
    fi
done

echo "[*] Obtaining DHCP IP address..."
cat << 'EOF' > /data/linux/udhcpc.script
#!/sbin/sh
case "$1" in
  deconfig)
    ip addr flush dev $interface
    ;;
  bound|renew)
    ip addr flush dev $interface
    ip addr add $ip/$mask dev $interface
    if [ -n "$router" ]; then
      for r in $router; do
        ip route add default via $r dev $interface 2>/dev/null
      done
    fi
    echo "nameserver 8.8.8.8" > /etc/resolv.conf
    echo "nameserver 1.1.1.1" >> /etc/resolv.conf
    if [ -d /mnt/ubuntu/etc ]; then
      rm -f /mnt/ubuntu/etc/resolv.conf
      echo "nameserver 8.8.8.8" > /mnt/ubuntu/etc/resolv.conf
      echo "nameserver 1.1.1.1" >> /mnt/ubuntu/etc/resolv.conf
    fi
    ;;
esac
EOF
chmod 755 /data/linux/udhcpc.script
/sbin/busybox udhcpc -i wlan0 -s /data/linux/udhcpc.script -t 6 -T 2 -n -q

echo "[*] Testing internet connectivity..."
chroot /mnt/ubuntu /usr/bin/env PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin /usr/sbin/ip addr show wlan0
chroot /mnt/ubuntu /usr/bin/env PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin /usr/sbin/ip route
chroot /mnt/ubuntu /usr/bin/env PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin ping -c 3 8.8.8.8

