#!/bin/bash
# Native Home Assistant Core Launcher for Galaxy S8
set -e

mkdir -p /mnt/android_data/homeassistant

# Clean any stale locks
rm -f /mnt/android_data/homeassistant/.ha_run.lock

# Kill existing instance if any
pkill -f 'ha_venv.*hass' || true
sleep 1

# Start daemon in background
nohup /mnt/android_data/ha_venv/bin/hass --config /mnt/android_data/homeassistant </dev/null >/var/log/home-assistant.log 2>&1 &
sleep 6

echo "=== Home Assistant Process ==="
ps aux | grep -v grep | grep hass || true

echo "=== Port 8123 Listening Status ==="
ss -tulpn | grep 8123 || true
tail -n 25 /var/log/home-assistant.log

