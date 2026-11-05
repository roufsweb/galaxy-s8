#!/bin/bash
set -e
# Restore launcher script
cat << 'EOF' > /mnt/android_data/opt/code-server-4.145.0-linux-arm64/bin/code-server
#!/bin/sh
ROOT="/mnt/android_data/opt/code-server-4.145.0-linux-arm64"
exec "$ROOT/lib/node" "$ROOT" "$@"
EOF
chmod +x /mnt/android_data/opt/code-server-4.145.0-linux-arm64/bin/code-server

# Symlink to /usr/local/bin
ln -sf /mnt/android_data/opt/code-server-4.145.0-linux-arm64/bin/code-server /usr/local/bin/code-server

# Configuration
mkdir -p /root/.config/code-server
cat << 'EOF' > /root/.config/code-server/config.yaml
bind-addr: 0.0.0.0:8443
auth: password
password: admin12345678
cert: false
EOF

# Kill any existing instance
pkill -f 'node.*code-server' || true
sleep 1

# Start in background
nohup /usr/local/bin/code-server </dev/null >/var/log/code-server.log 2>&1 &
sleep 5

echo "=== Code-Server Processes ==="
ps aux | grep -v grep | grep node || true

echo "=== Network Listening on 8443 ==="
ss -tulpn | grep 8443 || true
cat /var/log/code-server.log
