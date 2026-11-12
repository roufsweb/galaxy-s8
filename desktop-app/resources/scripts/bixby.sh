#!/bin/bash
action="$1"
case "$action" in
    single)
        echo 100 > /sys/class/timed_output/vibrator/enable 2>/dev/null
        DISPLAY=:1 /usr/local/bin/kgx </dev/null >/dev/null 2>&1 &
        ;;
    double)
        cur=$(cat /sys/class/leds/torch-sec1/brightness 2>/dev/null || echo 0)
        if [ "$cur" -gt 0 ]; then
            echo 0 > /sys/class/leds/torch-sec1/brightness
        else
            echo 3 > /sys/class/leds/torch-sec1/brightness
        fi
        ;;
    triple)
        echo 250 > /sys/class/timed_output/vibrator/enable 2>/dev/null
        python3 /usr/local/bin/s8_typec_daemon.py arm </dev/null >/var/log/bixby_dock.log 2>&1 &
        ;;
    long)
        echo 200 > /sys/class/timed_output/vibrator/enable 2>/dev/null
        ffmpeg -f x11grab -video_size 1920x1080 -i :1.0 -vframes 1 -y /tmp/screenshot_bixby.png </dev/null >/dev/null 2>&1
        python3 -c "import requests; requests.post('https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/sendPhoto', data={'chat_id': '<TELEGRAM_CHAT_ID>', 'caption': '📸 Galaxy S8 Action Button (Bixby Key) Long Press Triggered'}, files={'photo': open('/tmp/screenshot_bixby.png', 'rb')})\" 2>/dev/null || true
        ;;
esac
