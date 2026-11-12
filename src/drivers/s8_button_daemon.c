/*
 * s8_button_daemon.c -- Samsung Galaxy S8 (SM-G950N, Exynos 8895)
 * Physical Chassis Button Supervisor:
 *   - Volume Up (KEY_VOLUMEUP, 115)     -> Volume Up + 35ms Haptic Click + ALSA master
 *   - Volume Down (KEY_VOLUMEDOWN, 114) -> Volume Down + 35ms Haptic Click + ALSA master
 *   - Power Button (KEY_POWER, 116)     -> Configurable Multi-Action:
 *       * Single Click (<2.5s) : DisplayPort DPMS wake (/etc/s8/power.sh fallback) + 80ms Haptic
 *       * Double Click (<450ms): Graceful System Reboot + 3-pulse Haptic
 *       * Long Press (>=2.5s)  : Graceful System Poweroff + 350ms Haptic
 *   - Bixby Button (KEY_WINK, 703)      -> Configurable Actions:
 *       * Single Click : Launch GNOME Console (kgx) + 100ms Haptic
 *       * Double Click : Toggle High-Power Rear Torch + 2x60ms Haptic
 *       * Triple Click : Arm Type-C USB DisplayPort Dock + 250ms Haptic
 *       * Long Press   : Dispatch Telegram notification + 200ms Haptic
 *
 * Self-contained zero-dependency C implementation (standard libc only).
 */

#define _GNU_SOURCE
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <linux/input.h>
#include <poll.h>
#include <signal.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

#define BIXBY_DOUBLE_CLICK_MS 400
#define BIXBY_LONG_PRESS_MS   1200
#define POWER_DOUBLE_CLICK_MS 450
#define POWER_LONG_PRESS_MS   2500

static bool is_dry_run(void) {
    const char *v = getenv("S8_BUTTON_DRY_RUN");
    return (v != NULL && strcmp(v, "1") == 0);
}

static void vibrate(int ms) {
    if (is_dry_run()) {
        return;
    }
    int fd = open("/sys/class/timed_output/vibrator/enable", O_WRONLY);
    if (fd >= 0) {
        char buf[16];
        int len = snprintf(buf, sizeof(buf), "%d", ms);
        if (len > 0) {
            ssize_t written = write(fd, buf, (size_t)len);
            (void)written;
        }
        close(fd);
    }
}

static void toggle_torch(void) {
    int cur_level = 0;
    FILE *f = fopen("/sys/class/leds/torch-sec1/brightness", "r");
    if (f) {
        if (fscanf(f, "%d", &cur_level) != 1) {
            cur_level = 0;
        }
        fclose(f);
    }

    int new_level = (cur_level > 0) ? 0 : 3;
    FILE *fw = fopen("/sys/class/leds/torch-sec1/brightness", "w");
    if (fw) {
        fprintf(fw, "%d\n", new_level);
        fclose(fw);
    }
    vibrate(60);
    usleep(80000);
    vibrate(60);
    printf("[s8_button_daemon] Torch toggled: %d -> %d\n", cur_level, new_level);
    fflush(stdout);
}

static void run_async_cmd(const char *cmd) {
    if (is_dry_run()) {
        printf("[s8_button_daemon] [DRY-RUN] exec: %s\n", cmd);
        fflush(stdout);
        return;
    }
    pid_t pid = fork();
    if (pid == 0) {
        setsid();
        int devnull = open("/dev/null", O_RDWR);
        if (devnull >= 0) {
            dup2(devnull, 0);
            dup2(devnull, 1);
            dup2(devnull, 2);
            close(devnull);
        }
        execl("/bin/sh", "sh", "-c", cmd, (char *)NULL);
        _exit(1);
    }
}

/* Dynamically resolve gpio_keys event node because probe order alternates event2/event3. */
static int find_gpio_keys_device(char *out_path, size_t out_len) {
    const char *target = getenv("S8_INPUT_NAME");
    if (!target || !target[0]) {
        target = "gpio_keys";
    }

    for (int idx = 0; idx < 32; idx++) {
        char sys_path[128];
        char name_buf[128];
        snprintf(sys_path, sizeof(sys_path), "/sys/class/input/event%d/device/name", idx);
        FILE *f = fopen(sys_path, "r");
        if (!f) {
            continue;
        }
        if (fgets(name_buf, sizeof(name_buf), f) != NULL) {
            size_t n = strcspn(name_buf, "\r\n");
            name_buf[n] = '\0';
            if (strcmp(name_buf, target) == 0) {
                fclose(f);
                snprintf(out_path, out_len, "/dev/input/event%d", idx);
                return 0;
            }
        }
        fclose(f);
    }

    /* Fallback using ioctl EVIOCGNAME in case sysfs name layout differs */
    for (int idx = 0; idx < 32; idx++) {
        char dev_path[64];
        char ev_name[128] = {0};
        snprintf(dev_path, sizeof(dev_path), "/dev/input/event%d", idx);
        int tmp_fd = open(dev_path, O_RDONLY | O_NONBLOCK);
        if (tmp_fd < 0) {
            continue;
        }
        if (ioctl(tmp_fd, EVIOCGNAME(sizeof(ev_name) - 1), ev_name) >= 0) {
            if (strcmp(ev_name, target) == 0) {
                close(tmp_fd);
                snprintf(out_path, out_len, "%s", dev_path);
                return 0;
            }
        }
        close(tmp_fd);
    }
    return -1;
}

static void handle_volume_up(void) {
    vibrate(35);
    run_async_cmd("export PATH=/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin; amixer -c 0 set Master 5%+ >/dev/null 2>&1 || true; DISPLAY=:1 xdotool key XF86AudioRaiseVolume >/dev/null 2>&1 || true");
    printf("[s8_button_daemon] Volume UP (35ms haptic)\n");
    fflush(stdout);
}

static void handle_volume_down(void) {
    vibrate(35);
    run_async_cmd("export PATH=/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin; amixer -c 0 set Master 5%- >/dev/null 2>&1 || true; DISPLAY=:1 xdotool key XF86AudioLowerVolume >/dev/null 2>&1 || true");
    printf("[s8_button_daemon] Volume DOWN (35ms haptic)\n");
    fflush(stdout);
}

static void handle_power_short(void) {
    vibrate(80);
    printf("[s8_button_daemon] Power Short Press (80ms haptic -> DPMS wake)\n");
    fflush(stdout);
    run_async_cmd("export PATH=/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin; if [ -x /etc/s8/power.sh ]; then /etc/s8/power.sh; else DISPLAY=:1 xset dpms force on >/dev/null 2>&1 || true; fi");
}

static void handle_power_double(void) {
    vibrate(60);
    if (!is_dry_run()) usleep(100000);
    vibrate(60);
    if (!is_dry_run()) usleep(100000);
    vibrate(120);
    printf("[s8_button_daemon] Power Double Press -> Graceful Reboot\n");
    fflush(stdout);
    if (!is_dry_run()) usleep(180000);
    run_async_cmd("sync; systemctl reboot || reboot");
}

static void handle_power_long(void) {
    vibrate(350);
    printf("[s8_button_daemon] Power Long Press (>=2500ms) -> Graceful Poweroff\n");
    fflush(stdout);
    if (!is_dry_run()) usleep(400000);
    run_async_cmd("sync; systemctl poweroff || poweroff");
}

static void handle_bixby_action(const char *action) {
    printf("[s8_button_daemon] Bixby Action: %s\n", action);
    fflush(stdout);

    if (strcmp(action, "double") == 0) {
        toggle_torch();
        return;
    }

    if (strcmp(action, "single") == 0) {
        vibrate(100);
        run_async_cmd("export PATH=/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin; DISPLAY=:1 /usr/local/bin/kgx </dev/null >/dev/null 2>&1 || DISPLAY=:1 gnome-terminal </dev/null >/dev/null 2>&1");
    } else if (strcmp(action, "triple") == 0) {
        vibrate(250);
        run_async_cmd("export PATH=/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin; python3 /usr/local/bin/s8_typec_daemon.py arm </dev/null >/var/log/bixby_dock.log 2>&1");
    } else if (strcmp(action, "long") == 0) {
        vibrate(200);
        run_async_cmd("export PATH=/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin; if [ -x /usr/local/bin/notify_telegram.py ]; then python3 /usr/local/bin/notify_telegram.py '[INFO] Galaxy S8 Physical Bixby Key Long Press Triggered'; fi");
    }
}

static uint64_t current_time_ms(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000ULL + (uint64_t)ts.tv_nsec / 1000000ULL;
}

static int clamp_timeout(int cur_timeout, uint64_t now, uint64_t deadline) {
    if (deadline <= now) {
        return 1;
    }
    uint64_t diff = deadline - now;
    if (diff < (uint64_t)cur_timeout) {
        return (int)(diff < 1 ? 1 : diff);
    }
    return cur_timeout;
}

int main(void) {
    setvbuf(stdout, NULL, _IONBF, 0);
    setvbuf(stderr, NULL, _IONBF, 0);
    signal(SIGCHLD, SIG_IGN);

    char event_path[64] = {0};
    printf("[s8_button_daemon] Discovering gpio_keys input device...\n");
    while (find_gpio_keys_device(event_path, sizeof(event_path)) != 0) {
        sleep(1);
    }

    int fd = -1;
    while (fd < 0) {
        fd = open(event_path, O_RDONLY | O_NONBLOCK);
        if (fd < 0) {
            perror("open(gpio_keys)");
            sleep(1);
        }
    }

    printf("[s8_button_daemon] Listening on %s (short=DPMS wake, double=reboot, hold>=2.5s=poweroff)\n", event_path);

    uint64_t power_press_time = 0;
    uint64_t power_last_release_time = 0;
    int power_pending_clicks = 0;
    bool power_is_down = false;
    bool power_long_handled = false;

    uint64_t bixby_press_time = 0;
    uint64_t bixby_last_release_time = 0;
    int bixby_pending_clicks = 0;
    bool bixby_is_down = false;

    struct pollfd pfd = { .fd = fd, .events = POLLIN };

    while (1) {
        uint64_t now = current_time_ms();
        int timeout_ms = 50;

        if (power_pending_clicks > 0 && !power_is_down) {
            if (now >= power_last_release_time + POWER_DOUBLE_CLICK_MS) {
                if (power_pending_clicks == 1) {
                    handle_power_short();
                } else {
                    handle_power_double();
                }
                power_pending_clicks = 0;
            } else {
                timeout_ms = clamp_timeout(timeout_ms, now, power_last_release_time + POWER_DOUBLE_CLICK_MS);
            }
        }

        if (bixby_pending_clicks > 0 && !bixby_is_down) {
            if (now >= bixby_last_release_time + BIXBY_DOUBLE_CLICK_MS) {
                if (bixby_pending_clicks == 1) {
                    handle_bixby_action("single");
                } else if (bixby_pending_clicks == 2) {
                    handle_bixby_action("double");
                } else {
                    handle_bixby_action("triple");
                }
                bixby_pending_clicks = 0;
            } else {
                timeout_ms = clamp_timeout(timeout_ms, now, bixby_last_release_time + BIXBY_DOUBLE_CLICK_MS);
            }
        }

        if (power_is_down) {
            if (now >= power_press_time + POWER_LONG_PRESS_MS) {
                handle_power_long();
                power_is_down = false;
                power_long_handled = true;
                power_pending_clicks = 0;
            } else {
                timeout_ms = clamp_timeout(timeout_ms, now, power_press_time + POWER_LONG_PRESS_MS);
            }
        }

        if (bixby_is_down) {
            if (now >= bixby_press_time + BIXBY_LONG_PRESS_MS) {
                handle_bixby_action("long");
                bixby_is_down = false;
                bixby_pending_clicks = 0;
            } else {
                timeout_ms = clamp_timeout(timeout_ms, now, bixby_press_time + BIXBY_LONG_PRESS_MS);
            }
        }

        int ret = poll(&pfd, 1, timeout_ms);
        if (ret < 0 && errno != EINTR) {
            break;
        }
        if (ret <= 0) {
            continue;
        }

        struct input_event ev;
        ssize_t n;
        while ((n = read(fd, &ev, sizeof(ev))) == (ssize_t)sizeof(ev)) {
            if (ev.type != EV_KEY) {
                continue;
            }

            now = current_time_ms();
            printf("[s8_button_daemon] KEY EVENT: code=%d (0x%x), val=%d\n", ev.code, ev.code, ev.value);

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
                    power_long_handled = false;
                } else if (ev.value == 0) {
                    if (power_is_down) {
                        power_is_down = false;
                        if (!power_long_handled && (now - power_press_time < POWER_LONG_PRESS_MS)) {
                            power_pending_clicks++;
                            power_last_release_time = now;
                        }
                    }
                    power_long_handled = false;
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
        if (n < 0 && errno == ENODEV) {
            close(fd);
            fd = -1;
            while (find_gpio_keys_device(event_path, sizeof(event_path)) != 0) {
                sleep(1);
            }
            fd = open(event_path, O_RDONLY | O_NONBLOCK);
            pfd.fd = fd;
        }
    }

    if (fd >= 0) {
        close(fd);
    }
    return 0;
}
