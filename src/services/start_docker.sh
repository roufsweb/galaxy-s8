#!/bin/bash
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
cgroupfs-mount 2>/dev/null || true
mkdir -p /sys/fs/cgroup/devices /sys/fs/cgroup/systemd
mountpoint -q /sys/fs/cgroup/devices || mount -t cgroup -o none,name=devices devices /sys/fs/cgroup/devices 2>/dev/null || true
mountpoint -q /sys/fs/cgroup/systemd || mount -t cgroup -o none,name=systemd systemd /sys/fs/cgroup/systemd 2>/dev/null || true
update-alternatives --set iptables /usr/sbin/iptables-legacy 2>/dev/null || true
if ! pgrep -x dockerd >/dev/null; then
    dockerd --storage-driver=vfs --iptables=false --bridge=none </dev/null >/var/log/dockerd.log 2>&1 &
    sleep 4
fi
docker version

