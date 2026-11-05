#!/bin/bash
# CasaOS Supervisor Daemon for Samsung Galaxy S8 Chroot
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
mkdir -p /var/run/casaos /var/log/casaos

# 1. Gateway
if ! pgrep -x casaos-gateway >/dev/null 2>&1; then
    /usr/bin/casaos-gateway </dev/null >/var/log/casaos-gateway.log 2>&1 &
    sleep 1
fi

# 2. Message Bus
if ! pgrep -x casaos-message-bus >/dev/null 2>&1; then
    /usr/bin/casaos-message-bus -c /etc/casaos/message-bus.conf </dev/null >/var/log/casaos-message-bus.log 2>&1 &
fi

# 3. User Service
if ! pgrep -x casaos-user-service >/dev/null 2>&1; then
    /usr/bin/casaos-user-service -c /etc/casaos/user-service.conf </dev/null >/var/log/casaos-user-service.log 2>&1 &
fi

# 4. Local Storage
if ! pgrep -x casaos-local-storage >/dev/null 2>&1; then
    /usr/bin/casaos-local-storage -c /etc/casaos/local-storage.conf </dev/null >/var/log/casaos-local-storage.log 2>&1 &
fi

# 5. App Management
if ! pgrep -x casaos-app-management >/dev/null 2>&1; then
    /usr/bin/casaos-app-management -c /etc/casaos/app-management.conf </dev/null >/var/log/casaos-app-management.log 2>&1 &
fi

# 6. Main CasaOS Web Application
if ! pgrep -x casaos >/dev/null 2>&1; then
    /usr/bin/casaos -c /etc/casaos/casaos.conf </dev/null >/var/log/casaos.log 2>&1 &
fi

