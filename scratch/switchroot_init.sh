#!/bin/busybox sh
export PATH=/bin:/sbin:/usr/bin:/usr/sbin

# 1. Mount essential filesystems
/bin/busybox mount -t proc proc /proc
/bin/busybox mount -t sysfs sysfs /sys
/bin/busybox mount -t devtmpfs devtmpfs /dev 2>/dev/null || /bin/busybox mount -t tmpfs tmpfs /dev

# 2. Hotplug & Device Discovery
echo /bin/busybox > /proc/sys/kernel/hotplug
/bin/busybox mdev -s

# 3. Create critical device nodes
mkdir -p /dev/block
/bin/busybox mknod -m 600 /dev/console c 5 1 2>/dev/null || true
/bin/busybox mknod -m 666 /dev/null c 1 3 2>/dev/null || true
/bin/busybox mknod -m 666 /dev/zero c 1 5 2>/dev/null || true
/bin/busybox mknod -m 666 /dev/tty c 5 0 2>/dev/null || true
/bin/busybox mknod -m 620 /dev/tty1 c 4 1 2>/dev/null || true
/bin/busybox mknod -m 660 /dev/loop-control c 10 237 2>/dev/null || true
for i in 0 1 2 3 4 5 6 7; do
    /bin/busybox mknod -m 660 /dev/loop$i b 7 $i 2>/dev/null || true
done

# Populate block devices from /sys/block/sda
for p in /sys/block/sda/sda*; do
    if [ -f "$p/dev" ]; then
        name=$(basename "$p")
        majmin=$(cat "$p/dev")
        maj=$(echo "$majmin" | cut -d: -f1)
        min=$(echo "$majmin" | cut -d: -f2)
        /bin/busybox mknod -m 660 "/dev/block/$name" b "$maj" "$min" 2>/dev/null || true
        /bin/busybox mknod -m 660 "/dev/$name" b "$maj" "$min" 2>/dev/null || true
    fi
done
# Ensure sda24 fallback node (major 259, minor 8)
/bin/busybox mknod -m 660 /dev/block/sda24 b 259 8 2>/dev/null || true
/bin/busybox mknod -m 660 /dev/sda24 b 259 8 2>/dev/null || true

echo "==================================================="
echo "  Samsung Galaxy S8 Exynos 8895 Native Linux Boot  "
echo "  Kernel: $(/bin/busybox uname -r) Knox DEFEX: OFF "
echo "==================================================="

# 4. Configure USB Gadget: ACM (Serial console) + RNDIS (USB Ethernet)
mkdir -p /config
/bin/busybox mount -t configfs none /config 2>/dev/null || true

if [ -d /config/usb_gadget ]; then
    echo "Configuring USB Gadget (ACM Serial + RNDIS)..."
    mkdir -p /config/usb_gadget/g1
    cd /config/usb_gadget/g1
    echo 0x04e8 > idVendor
    echo 0x685e > idProduct
    mkdir -p strings/0x409
    echo ce10171ab3e9620804 > strings/0x409/serialnumber
    echo Samsung > strings/0x409/manufacturer
    echo "Galaxy S8 Native Linux" > strings/0x409/product
    mkdir -p configs/c.1/strings/0x409
    echo "ACM+RNDIS" > configs/c.1/strings/0x409/configuration
    echo 500 > configs/c.1/MaxPower
    
    # Serial function
    mkdir -p functions/acm.gs0 2>/dev/null || mkdir -p functions/acm.0 2>/dev/null
    ln -s functions/acm.* configs/c.1/ 2>/dev/null || true
    
    # RNDIS function
    mkdir -p functions/rndis.rn0 2>/dev/null || mkdir -p functions/rndis.0 2>/dev/null
    ln -s functions/rndis.* configs/c.1/ 2>/dev/null || true
    
    echo 10c00000.dwc3 > UDC 2>/dev/null || true
    cd /
fi

/bin/busybox ifconfig rndis0 172.16.42.1 netmask 255.255.255.0 up 2>/dev/null || true
/bin/busybox ifconfig usb0 172.16.42.1 netmask 255.255.255.0 up 2>/dev/null || true

# 5. Wait for UFS storage (/dev/block/sda24)
echo "Locating UFS partition /dev/block/sda24..."
count=0
while [ ! -b /dev/block/sda24 ] && [ "$count" -lt 10 ]; do
    /bin/busybox sleep 1
    count=$((count + 1))
done

if [ ! -b /dev/block/sda24 ]; then
    TARGET_DEV=$(find /dev -name "*sda24*" -o -name "*USERDATA*" 2>/dev/null | head -n 1)
else
    TARGET_DEV="/dev/block/sda24"
fi

if [ -z "$TARGET_DEV" ]; then
    echo "CRITICAL: UFS userdata block device not found! Spawning emergency shell..."
    while true; do
        /bin/busybox sh < /dev/console > /dev/console 2>&1
        /bin/busybox sleep 1
    done
fi

echo "Mounting UFS userdata partition: $TARGET_DEV"
mkdir -p /mnt/data
/bin/busybox mount -t ext4 -o rw,noatime "$TARGET_DEV" /mnt/data

if [ ! -f /mnt/data/linux/rootfs.img ]; then
    echo "ERROR: /mnt/data/linux/rootfs.img not found! Spawning emergency shell..."
    while true; do
        /bin/busybox sh < /dev/console > /dev/console 2>&1
        /bin/busybox sleep 1
    done
fi

echo "Mounting Native Ubuntu ARM64 rootfs..."
mkdir -p /newroot
/bin/busybox mount -t ext4 -o loop,rw,noatime /mnt/data/linux/rootfs.img /newroot

# 6. Prepare target rootfs
mkdir -p /newroot/dev /newroot/proc /newroot/sys /newroot/mnt/data /newroot/config
/bin/busybox mknod -m 600 /newroot/dev/console c 5 1 2>/dev/null || true
/bin/busybox mknod -m 666 /newroot/dev/null c 1 3 2>/dev/null || true
/bin/busybox mknod -m 666 /newroot/dev/zero c 1 5 2>/dev/null || true
/bin/busybox mknod -m 666 /newroot/dev/tty c 5 0 2>/dev/null || true
/bin/busybox mknod -m 620 /newroot/dev/tty1 c 4 1 2>/dev/null || true

/bin/busybox mount --move /dev /newroot/dev
/bin/busybox mount --move /proc /newroot/proc
/bin/busybox mount --move /sys /newroot/sys

# 7. Select init executable
if [ -x /newroot/init ]; then
    INIT_TARGET="/init"
elif [ -x /newroot/sbin/init ]; then
    INIT_TARGET="/sbin/init"
elif [ -x /newroot/bin/bash ]; then
    INIT_TARGET="/bin/bash"
else
    INIT_TARGET="/bin/sh"
fi

echo "Switching root to Native Linux ($INIT_TARGET)..."
exec /bin/busybox switch_root /newroot "$INIT_TARGET"

# Safety net: Keep PID 1 alive indefinitely if switch_root returns
echo "Switch_root returned! Keeping PID 1 alive..."
while true; do
    /bin/busybox sleep 3600
done
