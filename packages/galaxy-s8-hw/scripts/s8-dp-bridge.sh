#!/bin/bash
# s8-dp-bridge.sh -- Wait cleanly for an active X11 display (:1 or :0) before launching exynos_dp_bridge
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

while true; do
    if [ -S /tmp/.X11-unix/X1 ]; then
        export DISPLAY=":1"
        break
    elif [ -S /tmp/.X11-unix/X0 ]; then
        export DISPLAY=":0"
        break
    fi
    sleep 2
done

export XAUTHORITY="${XAUTHORITY:-/root/.Xauthority}"
exec /usr/local/bin/exynos_dp_bridge

