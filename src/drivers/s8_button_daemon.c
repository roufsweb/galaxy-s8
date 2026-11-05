/*
 * s8_button_daemon.c — Samsung Galaxy S8 (SM-G950N, Exynos 8895)
 * Physical Chassis Button Supervisor:
 *   - Volume Up (KEY_VOLUMEUP, 115)   -> Volume Up + 35ms Haptic Click + OSD
 *   - Volume Down (KEY_VOLUMEDOWN, 114) -> Volume Down + 35ms Haptic Click + OSD
 *   - Power Button (KEY_POWER, 116)   -> Display Toggle / Standby + 80ms Haptic
 *   - Bixby Button (KEY_WINK, 703)    -> Configurable Actions:
 *       * Single Click : Launch GNOME Console (kgx) / Focus Terminal
 *       * Double Click : Toggle High-Power Rear Torch / Flashlight
 *       * Long Press   : Capture Desktop Screenshot & Send to Telegram
 *       * Custom Hook  : Executes /etc/s8/bixby.sh <single|double|long>
 */

#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <poll.h>
#include <time.h>
#include <sys/ioctl.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <linux/input.h>
#include <X11/Xlib.h>
#include <X11/XF86keysym.h>
#include <X11/extensions/XTest.h>

#define EVENT_DEVICE "/dev/input/event3"

#define BIXBY_DOUBLE_CLICK_MS 400
#define BIXBY_LONG_PRESS_MS   1200
#define POWER_LONG_PRESS_MS   3000

static Display *dpy = NULL;

static void vibrate(int ms) {
    int fd = open("/sys/class/timed_output/vibrator/enable", O_WRONLY);
    if (fd >= 0) {
        char buf[16];
        int len = snprintf(buf, sizeof(buf), "%d", ms);
        write(fd, buf, len);
        close(fd);
    }
}

static void toggle_torch(void) {
    int cur_level = 0;
    FILE *f = fopen("/sys/class/leds/torch-sec1/brightness", "r");
    if (f) {
        fscanf(f, "%d", &cur_level);
        fclose(f);
    }

    int new_level = (cur_level > 0) ? 0 : 3;
    FILE *fw = fopen("/sys/class/leds/torch-sec1/brightness", "w");
    if (fw) {
        fprintf(fw, "%d", new_level);
        fclose(fw);
    }
    vibrate(60);
    usleep(80000);
    vibrate(60);
    printf("[s8_button_daemon] Torch toggled: %d -> %d\n", cur_level, new_level);
    fflush(stdout);
}

static void run_async_cmd(const char *cmd) {
    pid_t pid = fork();
    if (pid == 0) {
        setsid();
        int devnull = open("/dev/null", O_RDWR);
        dup2(devnull, 0);
        dup2(devnull, 1);
        dup2(devnull, 2);
        close(devnull);
        execl("/bin/sh", "sh", "-c", cmd, (char *)NULL);
        _exit(1);
    }
}

static void send_x11_keysym(KeySym sym) {
    if (!dpy) {
        dpy = XOpenDisplay(":1");
    }
    if (dpy) {
        KeyCode code = XKeysymToKeycode(dpy, sym);
        if (code != 0) {
            XTestFakeKeyEvent(dpy, code, True, CurrentTime);
            XTestFakeKeyEvent(dpy, code, False, CurrentTime);
            XFlush(dpy);
            return;
        }
    }
}

static void handle_volume_up(void) {
    vibrate(35);
    send_x11_keysym(XF86XK_AudioRaiseVolume);
    run_async_cmd("amixer -c 0 set Master 5%+ >/dev/null 2>&1 || true");
    printf("[s8_button_daemon] Volume UP\n");
    fflush(stdout);
}

static void handle_volume_down(void) {
    vibrate(35);
    send_x11_keysym(XF86XK_AudioLowerVolume);
    run_async_cmd("amixer -c 0 set Master 5%- >/dev/null 2>&1 || true");
    printf("[s8_button_daemon] Volume DOWN\n");
    fflush(stdout);
}

static void handle_power_short(void) {
    vibrate(80);
    printf("[s8_button_daemon] Power Short Press\n");
    fflush(stdout);
    run_async_cmd("if [ -f /etc/s8/power.sh ]; then /etc/s8/power.sh; else DISPLAY=:1 xset dpms force on; fi");
}

static void handle_power_long(void) {
    vibrate(300);
    printf("[s8_button_daemon] Power Long Press (>3s) -> Graceful Reboot\n");
    fflush(stdout);
    run_async_cmd("sync; sleep 1; reboot");
}

static void handle_bixby_action(const char *action) {
    printf("[s8_button_daemon] Bixby Action: %s\n", action);
    fflush(stdout);

    /* Check for user custom script */
    if (access("/etc/s8/bixby.sh", X_OK) == 0) {
        char cmd[128];
        snprintf(cmd, sizeof(cmd), "/etc/s8/bixby.sh %s", action);
        run_async_cmd(cmd);
        return;
    }

    if (strcmp(action, "single") == 0) {
        vibrate(100);
        run_async_cmd("DISPLAY=:1 /usr/local/bin/kgx </dev/null >/dev/null 2>&1 || DISPLAY=:1 gnome-terminal </dev/null >/dev/null 2>&1");
    } else if (strcmp(action, "double") == 0) {
        toggle_torch();
    } else if (strcmp(action, "long") == 0) {
        vibrate(200);
        run_async_cmd("DISPLAY=:1 /usr/bin/scrot /tmp/screenshot_bixby.png && python3 /usr/local/bin/notify_telegram.py '📸 [Galaxy S8 Bixby Key]: Desktop screenshot captured!' && python3 -c \"import requests; requests.post('https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/sendPhoto', data={'chat_id': '<TELEGRAM_CHAT_ID>', 'caption': '📸 Captured via Physical Bixby Key'}, files={'photo': open('/tmp/screenshot_bixby.png', 'rb')})\" 2>/dev/null");
    }
}

static uint64_t current_time_ms(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000ULL + (uint64_t)ts.tv_nsec / 1000000ULL;
}

int main(void) {
    setvbuf(stdout, NULL, _IONBF, 0);
    setvbuf(stderr, NULL, _IONBF, 0);

    printf("[s8_button_daemon] Starting physical chassis button supervisor on %s...\n", EVENT_DEVICE);
    fflush(stdout);

    int fd = -1;
    while (fd < 0) {
        fd = open(EVENT_DEVICE, O_RDONLY | O_NONBLOCK);
        if (fd < 0) {
            perror("open(" EVENT_DEVICE ")");
            sleep(1);
        }
    }

    printf("[s8_button_daemon] Successfully opened %s (gpio_keys)!\n", EVENT_DEVICE);
    fflush(stdout);

    uint64_t power_press_time = 0;
    bool power_is_down = false;

    uint64_t bixby_press_time = 0;
    uint64_t bixby_last_release_time = 0;
    int bixby_pending_clicks = 0;
    bool bixby_is_down = false;

    struct pollfd pfd = { .fd = fd, .events = POLLIN };

    while (1) {
        int timeout_ms = 50;
        if (bixby_pending_clicks > 0) {
            uint64_t now = current_time_ms();
            if (now >= bixby_last_release_time + BIXBY_DOUBLE_CLICK_MS) {
                if (bixby_pending_clicks == 1) {
                    handle_bixby_action("single");
                } else {
                    handle_bixby_action("double");
                }
                bixby_pending_clicks = 0;
            } else {
                timeout_ms = (bixby_last_release_time + BIXBY_DOUBLE_CLICK_MS) - now;
                if (timeout_ms < 1) timeout_ms = 1;
            }
        }

        if (power_is_down) {
            uint64_t now = current_time_ms();
            if (now >= power_press_time + POWER_LONG_PRESS_MS) {
                handle_power_long();
                power_is_down = false;
            }
        }

        if (bixby_is_down) {
            uint64_t now = current_time_ms();
            if (now >= bixby_press_time + BIXBY_LONG_PRESS_MS) {
                handle_bixby_action("long");
                bixby_is_down = false;
                bixby_pending_clicks = 0;
            }
        }

        int ret = poll(&pfd, 1, timeout_ms);
        if (ret <= 0) continue;

        struct input_event ev;
        while (read(fd, &ev, sizeof(ev)) == sizeof(ev)) {
            if (ev.type != EV_KEY) continue;

            uint64_t now = current_time_ms();
            printf("[s8_button_daemon] KEY EVENT: code=%d (0x%x), val=%d\n", ev.code, ev.code, ev.value);
            fflush(stdout);

            if (ev.code == KEY_VOLUMEUP) {
                if (ev.value == 1 || ev.value == 2) {
                    handle_volume_up();
                }
            } else if (ev.code == KEY_VOLUMEDOWN) {
                if (ev.value == 1 || ev.value == 2) {
                    handle_volume_down();
                }
            } else if (ev.code == KEY_POWER) {
                if (ev.value == 1) {
                    power_press_time = now;
                    power_is_down = true;
                } else if (ev.value == 0) {
                    if (power_is_down) {
                        power_is_down = false;
                        if (now - power_press_time < POWER_LONG_PRESS_MS) {
                            handle_power_short();
                        }
                    }
                }
            } else if (ev.code == 703) { /* KEY_WINK / Bixby */
                if (ev.value == 1) {
                    bixby_press_time = now;
                    bixby_is_down = true;
                } else if (ev.value == 0) {
                    if (bixby_is_down) {
                        bixby_is_down = false;
                        uint64_t duration = now - bixby_press_time;
                        if (duration < BIXBY_LONG_PRESS_MS) {
                            bixby_pending_clicks++;
                            bixby_last_release_time = now;
                        }
                    }
                }
            }
        }
    }

    close(fd);
    if (dpy) XCloseDisplay(dpy);
    return 0;
}
