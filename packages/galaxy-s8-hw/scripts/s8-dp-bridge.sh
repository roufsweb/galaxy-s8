#!/bin/bash
# s8-dp-bridge.sh -- Launch exynos_dp_bridge cleanly (supports X11 :1/:0 + automatic console telemetry fallback)
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export XAUTHORITY="${XAUTHORITY:-/root/.Xauthority}"

if [ -S /tmp/.X11-unix/X1 ]; then
    export DISPLAY=":1"
elif [ -S /tmp/.X11-unix/X0 ]; then
    export DISPLAY=":0"
fi

exec /usr/local/bin/exynos_dp_bridge

