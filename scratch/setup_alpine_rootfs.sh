#!/system/bin/sh
set -e

echo "=== Cleaning previous mounts ==="
umount -l /data/linux/mnt/dev/pts 2>/dev/null || true
umount -l /data/linux/mnt/dev 2>/dev/null || true
umount -l /data/linux/mnt/proc 2>/dev/null || true
umount -l /data/linux/mnt/sys 2>/dev/null || true
umount -l /data/linux/mnt 2>/dev/null || true
losetup -D 2>/dev/null || true

echo "=== Removing temporary test files ==="
rm -rf /data/local/tmp/ubuntu18 /data/local/tmp/alpine /data/local/tmp/ubuntu-base-18.04.5-base-arm64.tar.gz /data/local/tmp/ubuntu-base-20.04.5-base-arm64.tar.gz /data/local/tmp/ubuntu-base-22.04.4-base-arm64.tar.gz 2>/dev/null || true

echo "=== Formatting rootfs.img ==="
mke2fs -t ext4 -F /data/linux/rootfs.img

echo "=== Mounting rootfs.img ==="
mkdir -p /data/linux/mnt
mount -o loop /data/linux/rootfs.img /data/linux/mnt

echo "=== Extracting Alpine Linux minirootfs ==="
tar -xzf /data/local/tmp/alpine-test.tar.gz -C /data/linux/mnt/

echo "=== Setting up base configurations ==="
echo "nameserver 8.8.8.8" > /data/linux/mnt/etc/resolv.conf
echo "nameserver 1.1.1.1" >> /data/linux/mnt/etc/resolv.conf
echo "galaxy-s8" > /data/linux/mnt/etc/hostname
cat << 'EOF' > /data/linux/mnt/etc/hosts
127.0.0.1   localhost galaxy-s8
::1         localhost ip6-localhost ip6-loopback
EOF

echo "=== Setting up APK repositories ==="
cat << 'EOF' > /data/linux/mnt/etc/apk/repositories
https://dl-cdn.alpinelinux.org/alpine/v3.20/main
https://dl-cdn.alpinelinux.org/alpine/v3.20/community
EOF

echo "=== Copying Broadcom Wi-Fi / Bluetooth firmware ==="
mkdir -p /data/linux/mnt/lib/firmware/brcm
cp /system/vendor/firmware/bcm4361* /data/linux/mnt/lib/firmware/brcm/ 2>/dev/null || true
cp -r /system/vendor/etc/wifi /data/linux/mnt/etc/ 2>/dev/null || true

echo "=== Mounting virtual filesystems for chroot setup ==="
mount -o bind /dev /data/linux/mnt/dev
mount -t devpts devpts /data/linux/mnt/dev/pts
mount -t proc proc /data/linux/mnt/proc
mount -t sysfs sysfs /data/linux/mnt/sys

echo "=== Installing core packages via apk ==="
chroot /data/linux/mnt /bin/sh -c '
export PATH=/bin:/sbin:/usr/bin:/usr/sbin
apk update
apk add --no-cache openrc openssh bash curl ca-certificates docker iptables iproute2 eudev util-linux shadow
'

echo "=== Configuring OpenSSH and Root Account ==="
chroot /data/linux/mnt /bin/sh -c '
export PATH=/bin:/sbin:/usr/bin:/usr/sbin
# Set root password to "root"
echo "root:root" | chpasswd
# Configure sshd
sed -i "s/#PermitRootLogin.*/PermitRootLogin yes/" /etc/ssh/sshd_config
sed -i "s/#PermitEmptyPasswords.*/PermitEmptyPasswords no/" /etc/ssh/sshd_config
ssh-keygen -A
'

echo "=== Configuring Network Interfaces (USB Gadget & Local) ==="
cat << 'EOF' > /data/linux/mnt/etc/network/interfaces
auto lo
iface lo inet loopback

auto usb0
iface usb0 inet static
    address 172.16.42.1
    netmask 255.255.255.0

auto rndis0
iface rndis0 inet static
    address 172.16.42.1
    netmask 255.255.255.0
EOF

echo "=== Enabling Default OpenRC Services ==="
chroot /data/linux/mnt /bin/sh -c '
export PATH=/bin:/sbin:/usr/bin:/usr/sbin
rc-update add devfs sysinit 2>/dev/null || true
rc-update add dmesg sysinit 2>/dev/null || true
rc-update add udev sysinit 2>/dev/null || true
rc-update add udev-trigger sysinit 2>/dev/null || true
rc-update add networking boot 2>/dev/null || true
rc-update add sshd default 2>/dev/null || true
rc-update add docker default 2>/dev/null || true
'

echo "=== Configuring inittab for DisplayPort / TTY console ==="
cat << 'EOF' > /data/linux/mnt/etc/inittab
# /etc/inittab for Galaxy S8 Native Linux
::sysinit:/sbin/openrc sysinit
::sysinit:/sbin/openrc boot
::wait:/sbin/openrc default

# Native Framebuffer (DisplayPort HDMI monitor) consoles
tty1::respawn:/sbin/getty 38400 tty1
tty2::respawn:/sbin/getty 38400 tty2
tty3::respawn:/sbin/getty 38400 tty3

# USB Serial Gadget console (connect PC via serial terminal if needed)
ttyGS0::respawn:/sbin/getty -L 115200 ttyGS0 vt100

::ctrlaltdel:/sbin/reboot
::shutdown:/sbin/openrc shutdown
EOF

echo "=== Alpine Rootfs Configuration Complete! ==="
