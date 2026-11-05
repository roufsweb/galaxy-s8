#!/bin/bash
# Move to root cgroup to prevent Android libprocessgroup kill
echo $$ > /acct/tasks 2>/dev/null || true

export PATH=/mnt/android_data/opt/node-v18.20.4-linux-arm64/bin:$PATH
export UPTIME_KUMA_PORT=3001
export DATA_DIR=/mnt/android_data/uptime-kuma

pkill -f "node.*server/server.js" || true
sleep 1

cd /mnt/android_data/uptime-kuma-src
echo "[*] Launching Uptime Kuma natively on port 3001..."
nohup /mnt/android_data/opt/node-v18.20.4-linux-arm64/bin/node server/server.js --port 3001 </dev/null >/var/log/uptime-kuma.log 2>&1 &

sleep 3
ps aux | grep "server/server.js" | grep -v grep
curl -sI http://127.0.0.1:3001 | head -n 5

