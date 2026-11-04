#!/system/bin/sh
chroot /data/linux/mnt /lib/ld-linux-aarch64.so.1 /bin/bash -c "
export PATH=/usr/bin:/bin:/usr/sbin:/sbin
echo 'Testing ls in PATH:'
/bin/ls -la /lib
echo '--- aarch64-linux-gnu ld ---'
/bin/ls -la /lib/aarch64-linux-gnu/ld*
"
