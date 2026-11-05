/*
 * s8_input_bridge.c — Hotplug USB Mouse & Keyboard forwarder to X11 (:1)
 *
 * Automatically monitors /dev/input/event* for newly connected USB mice & keyboards.
 * Forwards mouse motion, clicks, wheel, and keyboard keys directly to X11 via XTest.
 *
 * Anti-Phantom Guard: Gaming mice (like Telink) report extra keys (DPI, macros).
 * Only devices with a full alphanumeric keyboard layout (>= 8 QWERTY keys)
 * are permitted to inject keyboard keycodes.
 * Full autorepeat (ev->value == 2) and Xlib error immunity included.
 */

#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <dirent.h>
#include <poll.h>
#include <sys/ioctl.h>
#include <sys/inotify.h>
#include <linux/input.h>
#include <X11/Xlib.h>
#include <X11/extensions/XTest.h>

#define MAX_DEVS 32

typedef struct {
    int fd;
    char path[64];
    char name[128];
    bool is_mouse;
    bool is_keyboard;
} input_dev_t;

static input_dev_t devs[MAX_DEVS];
static int num_devs = 0;
static Display *dpy = NULL;

static int x_error_handler(Display *d, XErrorEvent *e) {
    return 0;
}

static void check_and_add_device(const char *devpath) {
    for (int i = 0; i < num_devs; i++) {
        if (strcmp(devs[i].path, devpath) == 0)
            return;
    }

    if (num_devs >= MAX_DEVS) return;

    int fd = open(devpath, O_RDONLY | O_NONBLOCK);
    if (fd < 0) return;

    char name[128] = "Unknown";
    ioctl(fd, EVIOCGNAME(sizeof(name)), name);

    /* Ignore built-in sensors / gpio / switches */
    if (strstr(name, "ssp_context") || strstr(name, "hrm_sensor") ||
        strstr(name, "hall") || strstr(name, "Headset") || strstr(name, "gpio_keys")) {
        close(fd);
        return;
    }

    unsigned long evbit = 0;
    ioctl(fd, EVIOCGBIT(0, sizeof(evbit)), &evbit);

    bool is_mouse = false;
    bool is_kbd = false;

    if (evbit & (1 << EV_REL)) {
        unsigned long relbit = 0;
        ioctl(fd, EVIOCGBIT(EV_REL, sizeof(relbit)), &relbit);
        if ((relbit & (1 << REL_X)) || (relbit & (1 << REL_Y))) {
            is_mouse = true;
        }
    }

    if (evbit & (1 << EV_KEY)) {
        unsigned long keybit[KEY_MAX / 8 / sizeof(unsigned long) + 1] = {0};
        ioctl(fd, EVIOCGBIT(EV_KEY, sizeof(keybit)), keybit);

        if (keybit[BTN_LEFT / (sizeof(unsigned long) * 8)] & (1UL << (BTN_LEFT % (sizeof(unsigned long) * 8)))) {
            is_mouse = true;
        }

        /* Check for keyboard: requires genuine letter keys (Q through P) */
        int kbd_keys = 0;
        for (int k = KEY_Q; k <= KEY_P; k++) {
            if (keybit[k / (sizeof(unsigned long) * 8)] & (1UL << (k % (sizeof(unsigned long) * 8)))) {
                kbd_keys++;
            }
        }
        if (kbd_keys >= 8) {
            is_kbd = true;
        }
    }

    if (!is_mouse && !is_kbd) {
        close(fd);
        return;
    }

    devs[num_devs].fd = fd;
    strncpy(devs[num_devs].path, devpath, sizeof(devs[num_devs].path) - 1);
    strncpy(devs[num_devs].name, name, sizeof(devs[num_devs].name) - 1);
    devs[num_devs].is_mouse = is_mouse;
    devs[num_devs].is_keyboard = is_kbd;

    printf("[s8_input_bridge] Added input #%d: %s (%s) [Mouse=%d, Keyboard=%d]\n",
           num_devs, devpath, name, is_mouse, is_kbd);
    num_devs++;
}

static void remove_device(int idx) {
    if (idx < 0 || idx >= num_devs) return;
    printf("[s8_input_bridge] Removed input: %s (%s)\n", devs[idx].path, devs[idx].name);
    close(devs[idx].fd);
    for (int i = idx; i < num_devs - 1; i++) {
        devs[i] = devs[i + 1];
    }
    num_devs--;
}

static void scan_existing_devices(void) {
    DIR *dir = opendir("/dev/input");
    if (!dir) return;
    struct dirent *de;
    while ((de = readdir(dir)) != NULL) {
        if (strncmp(de->d_name, "event", 5) == 0) {
            char path[64];
            snprintf(path, sizeof(path), "/dev/input/%s", de->d_name);
            check_and_add_device(path);
        }
    }
    closedir(dir);
}

int main(void) {
    setvbuf(stdout, NULL, _IOLBF, 0);
    setvbuf(stderr, NULL, _IOLBF, 0);

    XSetErrorHandler(x_error_handler);

    printf("[s8_input_bridge] Starting hotplug USB input bridge for X11 :1...\n");

    while (!dpy) {
        dpy = XOpenDisplay(":1");
        if (!dpy) usleep(500000);
    }
    printf("[s8_input_bridge] Connected to X11 :1 with XTest support.\n");

    int inotify_fd = inotify_init1(IN_NONBLOCK);
    if (inotify_fd >= 0) {
        inotify_add_watch(inotify_fd, "/dev/input", IN_CREATE | IN_DELETE);
    }

    scan_existing_devices();

    struct pollfd pfds[MAX_DEVS + 1];

    while (1) {
        int pfd_count = 0;
        if (inotify_fd >= 0) {
            pfds[pfd_count].fd = inotify_fd;
            pfds[pfd_count].events = POLLIN;
            pfd_count++;
        }

        for (int i = 0; i < num_devs; i++) {
            pfds[pfd_count].fd = devs[i].fd;
            pfds[pfd_count].events = POLLIN;
            pfd_count++;
        }

        int poll_ret = poll(pfds, pfd_count, 1000);
        if (poll_ret < 0) {
            if (errno == EINTR) continue;
            usleep(10000);
            continue;
        }

        /* Check for hotplug notifications */
        if (inotify_fd >= 0 && (pfds[0].revents & POLLIN)) {
            char buf[512];
            ssize_t len;
            while ((len = read(inotify_fd, buf, sizeof(buf))) > 0) {
                struct inotify_event *iev;
                for (char *ptr = buf; ptr < buf + len; ptr += sizeof(struct inotify_event) + iev->len) {
                    iev = (struct inotify_event *)ptr;
                    if (iev->len > 0 && strncmp(iev->name, "event", 5) == 0) {
                        char fullpath[64];
                        snprintf(fullpath, sizeof(fullpath), "/dev/input/%s", iev->name);
                        if (iev->mask & IN_CREATE) {
                            usleep(150000);
                            check_and_add_device(fullpath);
                        } else if (iev->mask & IN_DELETE) {
                            for (int i = 0; i < num_devs; i++) {
                                if (strcmp(devs[i].path, fullpath) == 0) {
                                    remove_device(i);
                                    break;
                                }
                            }
                        }
                    }
                }
            }
        }

        /* Process input events */
        int start_idx = (inotify_fd >= 0) ? 1 : 0;
        bool need_flush = false;

        for (int i = 0; i < num_devs; i++) {
            if (pfds[start_idx + i].revents & (POLLERR | POLLHUP | POLLNVAL)) {
                remove_device(i);
                i--;
                continue;
            }

            if (pfds[start_idx + i].revents & POLLIN) {
                struct input_event evs[64];
                ssize_t n = read(devs[i].fd, evs, sizeof(evs));
                if (n <= 0) {
                    if (n < 0 && (errno == EAGAIN || errno == EWOULDBLOCK))
                        continue;
                    if (n < 0 && errno == ENODEV) {
                        remove_device(i);
                        i--;
                    }
                    continue;
                }

                int num_events = n / sizeof(struct input_event);
                for (int e = 0; e < num_events; e++) {
                    struct input_event *ev = &evs[e];

                    if (ev->type == EV_REL) {
                        if (ev->code == REL_X) {
                            XTestFakeRelativeMotionEvent(dpy, ev->value, 0, CurrentTime);
                            need_flush = true;
                        } else if (ev->code == REL_Y) {
                            XTestFakeRelativeMotionEvent(dpy, 0, ev->value, CurrentTime);
                            need_flush = true;
                        } else if (ev->code == REL_WHEEL) {
                            unsigned int btn = (ev->value > 0) ? 4 : 5;
                            XTestFakeButtonEvent(dpy, btn, True, CurrentTime);
                            XTestFakeButtonEvent(dpy, btn, False, CurrentTime);
                            need_flush = true;
                        } else if (ev->code == REL_HWHEEL) {
                            unsigned int btn = (ev->value > 0) ? 7 : 6;
                            XTestFakeButtonEvent(dpy, btn, True, CurrentTime);
                            XTestFakeButtonEvent(dpy, btn, False, CurrentTime);
                            need_flush = true;
                        }
                    } else if (ev->type == EV_KEY) {
                        /* Check for standard mouse buttons */
                        if (ev->code == BTN_LEFT || ev->code == BTN_RIGHT ||
                            ev->code == BTN_MIDDLE || ev->code == BTN_SIDE ||
                            ev->code == BTN_EXTRA) {
                            unsigned int btn = 1;
                            if (ev->code == BTN_LEFT) btn = 1;
                            else if (ev->code == BTN_MIDDLE) btn = 2;
                            else if (ev->code == BTN_RIGHT) btn = 3;
                            else if (ev->code == BTN_SIDE) btn = 8;
                            else if (ev->code == BTN_EXTRA) btn = 9;

                            XTestFakeButtonEvent(dpy, btn, ev->value != 0, CurrentTime);
                            need_flush = true;
                        } else if (devs[i].is_keyboard && ev->code < 256) {
                            /* Keyboard events: support press (1), repeat (2), and release (0) */
                            KeyCode kc = (KeyCode)(ev->code + 8);
                            XTestFakeKeyEvent(dpy, kc, ev->value != 0, CurrentTime);
                            need_flush = true;
                        }
                    }
                }
            }
        }

        if (need_flush) {
            XFlush(dpy);
        }
    }

    if (dpy) XCloseDisplay(dpy);
    return 0;
}
