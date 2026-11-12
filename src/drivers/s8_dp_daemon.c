/*
 * s8_dp_daemon.c -- Unified Static DisplayPort, Type-C Supervisor & Default PTY Terminal
 * Target: Samsung Galaxy S8 (SM-G950N, Exynos 8895 DECON2 /dev/graphics/fb2)
 *
 * Compiles statically (`-static -lutil`) with zero X11 or Python dependencies so it runs
 * directly from the AP ramdisk across any OS (including untested or headless minimal rootfs).
 *
 * Features:
 *   1. Single-owner Type-C CC arbitration (Rd unpowered monitor vs Rp powered dock/PC)
 *      + MAX77865 1,500mA unlock + clean disconnect watchdog.
 *   2. EDID negotiation + /dev/ion BGRA8888 double-buffered S3CFB_WIN_CONFIG on fb2.
 *   3. Built-in interactive VT/ANSI PTY Terminal + USB HID keyboard evdev input
 *      (opens inside /mnt/rootfs shell or AP /sbin/sh fallback) with live hardware header.
 *   4. Lockless shared-memory GUI mirror (/dev/shm/s8_dp_fb or /tmp/s8_dp_fb) with
 *      Ctrl+Alt+F1 toggle back to interactive PTY console.
 */

#define _GNU_SOURCE
#include "s8_dp_font.h"
#include <ctype.h>
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <linux/fb.h>
#include <linux/input.h>
#include <linux/videodev2.h>
#include <poll.h>
#include <pty.h>
#include <signal.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/file.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <sys/sysmacros.h>
#include <sys/utsname.h>
#include <sys/wait.h>
#include <termios.h>
#include <time.h>
#include <unistd.h>

#ifndef FBIO_WAITFORVSYNC
#define FBIO_WAITFORVSYNC _IOW('F', 0x20, uint32_t)
#endif

#define MAX_DECON_WIN 6
#define MAX_PLANE_CNT 3
#define NUM_BUFFERS 2
#define ION_HEAP_SYSTEM_MASK (1 << 0)
#define MAX_KBD_DEVS 8
#define TERM_MAX_COLS 160
#define TERM_MAX_ROWS 72

struct ion_allocation_data {
    size_t len;
    size_t align;
    unsigned int heap_id_mask;
    unsigned int flags;
    int handle;
};

struct ion_fd_data {
    int handle;
    int fd;
};

#define ION_IOC_ALLOC _IOWR('I', 0, struct ion_allocation_data)
#define ION_IOC_SHARE _IOWR('I', 4, struct ion_fd_data)

enum decon_idma_type {
    IDMA_G0 = 0, IDMA_G1 = 1, IDMA_VG0 = 2, IDMA_VG1 = 3,
    IDMA_VGF0 = 4, IDMA_VGF1 = 5, ODMA_WB = 6, IDMA_G0_S = 7
};

enum decon_pixel_format {
    DECON_PIXEL_FORMAT_ARGB_8888 = 0, DECON_PIXEL_FORMAT_ABGR_8888,
    DECON_PIXEL_FORMAT_RGBA_8888, DECON_PIXEL_FORMAT_BGRA_8888
};

struct decon_win_rect { int x, y; uint32_t w, h; };
struct dpp_params { uint64_t addr[MAX_PLANE_CNT]; uint32_t flip, eq_mode, comp_src; };
struct decon_frame { int x, y; uint32_t w, h, f_w, f_h; };

struct decon_win_config {
    uint32_t state;
    union {
        uint32_t color;
        struct {
            int fd_idma[3];
            int fence_fd;
            int plane_alpha;
            uint32_t blending;
            uint32_t idma_type;
            uint32_t format;
            struct dpp_params dpp_parm;
            struct decon_win_rect block_area;
            struct decon_win_rect transparent_area;
            struct decon_win_rect opaque_area;
            struct decon_frame src;
        };
        struct { int left, top, right, bottom, mode; };
    };
    struct decon_frame dst;
    bool protection;
    bool compression;
};

struct decon_win_config_data_dsu {
    int fence;
    int fd_odma;
    struct decon_win_config config[MAX_DECON_WIN + 2];
};

struct decon_win_config_data_nodsu {
    int fence;
    int fd_odma;
    struct decon_win_config config[MAX_DECON_WIN + 1];
};

struct exynos_displayport_data {
    enum {
        EXYNOS_DISPLAYPORT_STATE_PRESET = 0,
        EXYNOS_DISPLAYPORT_STATE_ENUM_PRESET,
        EXYNOS_DISPLAYPORT_STATE_AUDIO
    } state;
    struct v4l2_dv_timings timings;
    struct v4l2_enum_dv_timings etimings;
    uint32_t audio_info;
    int hdcp;
};

#define S3CFB_WIN_CONFIG_DSU _IOW('F', 209, struct decon_win_config_data_dsu)
#define S3CFB_WIN_CONFIG_NODSU _IOW('F', 209, struct decon_win_config_data_nodsu)
#define EXYNOS_GET_DISPLAYPORT_CONFIG _IOW('F', 300, struct exynos_displayport_data)
#define EXYNOS_SET_DISPLAYPORT_CONFIG _IOW('F', 301, struct exynos_displayport_data)

typedef struct {
    uint32_t magic; /* 0x53384642 'S8FB' */
    uint32_t width;
    uint32_t height;
    uint32_t seq;
    uint64_t timestamp_ms;
} shm_fb_hdr_t;

/* ---------- Sysfs Helpers ---------- */

static int read_int_file(const char *path, int def_val) {
    FILE *f = fopen(path, "r");
    if (!f) return def_val;
    int v = def_val;
    if (fscanf(f, "%d", &v) != 1) v = def_val;
    fclose(f);
    return v;
}

static bool read_str_file(const char *path, char *out, size_t sz) {
    FILE *f = fopen(path, "r");
    if (!f) {
        if (sz > 0) out[0] = '\0';
        return false;
    }
    if (!fgets(out, (int)sz, f)) {
        out[0] = '\0';
        fclose(f);
        return false;
    }
    fclose(f);
    size_t n = strlen(out);
    while (n > 0 && (out[n - 1] == '\n' || out[n - 1] == '\r')) out[--n] = '\0';
    return true;
}

static void write_str_file(const char *path, const char *val) {
    FILE *f = fopen(path, "w");
    if (f) {
        fprintf(f, "%s\n", val);
        fclose(f);
    }
}

static void pulse_vibrator(int ms) {
    char buf[16];
    snprintf(buf, sizeof(buf), "%d", ms);
    write_str_file("/sys/class/timed_output/vibrator/enable", buf);
}

static uint64_t now_ms(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000ULL + (uint64_t)ts.tv_nsec / 1000000ULL;
}

/* ---------- Type-C Power Arbitration & DisplayPort Negotiation ---------- */

static void apply_safe_5v_fast_charge(void) {
    write_str_file("/sys/class/power_supply/max77865-charger/data", "0xBD 0x6C");
    write_str_file("/sys/class/power_supply/max77865-charger/data", "0xC3 0x61");
    write_str_file("/sys/class/power_supply/max77865-charger/data", "0xC0 0x3C");
    write_str_file("/sys/class/power_supply/max77865-charger/data", "0xB9 0x9E");
    write_str_file("/sys/class/power_supply/max77865-charger/data", "0xB7 0x05");
    write_str_file("/sys/class/power_supply/battery/batt_tune_input_charge_current", "1500");
    write_str_file("/sys/class/power_supply/battery/batt_tune_fast_charge_current", "1500");
}

static bool is_partner_attached(void) {
    if (access("/sys/class/typec/port0/port0-partner", F_OK) == 0) return true;
    if (read_int_file("/sys/class/switch/hdmi/state", 0) > 0) return true;
    if (read_int_file("/sys/class/sec/ccic/state", 0) != 0) return true;
    return false;
}

static void reset_typec_on_detach(int fb_fd) {
    if (fb_fd >= 0) ioctl(fb_fd, FBIOBLANK, FB_BLANK_POWERDOWN);
    write_str_file("/sys/class/host_notify/usb_otg/booster", "OFF");
    write_str_file("/sys/class/host_notify/usb_otg/mode", "NONE");
    write_str_file("/sys/class/dp_sec/link", "0");
    write_str_file("/sys/class/dp_sec/dp_test", "1,0");
    write_str_file("/sys/class/dp_sec/dp_sbu_sw_sel", "0 0");
    write_str_file("/sys/class/typec/port0/port_type", "dual");
}

static int attempt_dp_link(void) {
    /* Let USB Gadget / PD settle for 600ms so PC enumeration reaches "configured". */
    usleep(600000);
    char udc_state[64] = "";
    read_str_file("/sys/class/udc/10c00000.dwc3/state", udc_state, sizeof(udc_state));
    if (strcmp(udc_state, "configured") == 0) {
        /* Actively enumerating as a USB gadget to a PC host: do not role-swap or force DP. */
        apply_safe_5v_fast_charge();
        return 0;
    }

    char prole[64] = "";
    read_str_file("/sys/class/typec/port0/power_role", prole, sizeof(prole));
    if (strstr(prole, "[source]")) {
        write_str_file("/sys/class/host_notify/usb_otg/booster", "ON");
        write_str_file("/sys/class/host_notify/usb_otg/mode", "HOST");
        write_str_file("/sys/class/typec/port0/data_role", "host");
    } else {
        write_str_file("/sys/class/host_notify/usb_otg/booster", "OFF");
        write_str_file("/sys/class/host_notify/usb_otg/mode", "NONE");
        apply_safe_5v_fast_charge();
    }

    char drole[64] = "";
    read_str_file("/sys/class/typec/port0/data_role", drole, sizeof(drole));
    if (strstr(drole, "[device]")) {
        write_str_file("/sys/class/typec/port0/data_role", "host");
        write_str_file("/sys/class/sec/ccic/role_swap", "1");
    }

    /* Probe both USB-C orientations using genuine HPD (mode 9: AUX DPCD + link training).
       Unlike force modes 22/24, mode 9 only asserts switch/hdmi/state=1 if a real DP sink answers. */
    static const char *sbu_opts[] = {"0 0", "1 0"};
    for (int s = 0; s < 2; s++) {
        write_str_file("/sys/class/dp_sec/dp_sbu_sw_sel", sbu_opts[s]);
        usleep(50000);
        write_str_file("/sys/class/dp_sec/link", "9");
        usleep(250000);
        if (read_int_file("/sys/class/switch/hdmi/state", 0) > 0) return 1;
        write_str_file("/sys/class/dp_sec/link", "0");
        usleep(40000);
    }
    return 0;
}

static void configure_dp_timings(int fb_fd, uint32_t *out_w, uint32_t *out_h) {
    struct exynos_displayport_data dp;
    struct v4l2_dv_timings best;
    bool have_best = false;
    bool have_1080p = false;
    memset(&best, 0, sizeof(best));

    write_str_file("/sys/class/dp_sec/bpc", "8");
    write_str_file("/sys/class/dp_sec/range", "0");

    for (uint32_t i = 0; i < 36; i++) {
        memset(&dp, 0, sizeof(dp));
        dp.state = EXYNOS_DISPLAYPORT_STATE_ENUM_PRESET;
        dp.etimings.index = i;
        if (ioctl(fb_fd, EXYNOS_GET_DISPLAYPORT_CONFIG, &dp) == 0) {
            uint32_t w = dp.etimings.timings.bt.width;
            uint32_t h = dp.etimings.timings.bt.height;
            uint64_t pclk = dp.etimings.timings.bt.pixelclock;
            if (dp.etimings.timings.bt.interlaced) continue;
            if (w == 1920 && h == 1080) {
                if (!have_1080p || pclk > best.bt.pixelclock) {
                    best = dp.etimings.timings;
                    have_best = true;
                    have_1080p = true;
                }
            } else if (!have_1080p && w <= 1920) {
                uint64_t area = (uint64_t)w * h;
                uint64_t best_area = (uint64_t)best.bt.width * best.bt.height;
                if (!have_best || area > best_area ||
                    (area == best_area && pclk > best.bt.pixelclock)) {
                    best = dp.etimings.timings;
                    have_best = true;
                }
            }
        }
    }
    if (!have_best) {
        memset(&dp, 0, sizeof(dp));
        dp.state = EXYNOS_DISPLAYPORT_STATE_PRESET;
        if (ioctl(fb_fd, EXYNOS_GET_DISPLAYPORT_CONFIG, &dp) == 0 && dp.timings.bt.width > 0) {
            best = dp.timings;
            have_best = true;
        }
    }
    if (have_best && best.bt.width > 0 && best.bt.height > 0) {
        memset(&dp, 0, sizeof(dp));
        dp.state = EXYNOS_DISPLAYPORT_STATE_PRESET;
        dp.timings = best;
        ioctl(fb_fd, EXYNOS_SET_DISPLAYPORT_CONFIG, &dp);
        *out_w = best.bt.width;
        *out_h = best.bt.height;
    } else {
        *out_w = 1920;
        *out_h = 1080;
    }
}

static int submit_frame(int fb_fd, int dma_fd, uint32_t win_idx, uint32_t idma_type, uint32_t w, uint32_t h, int *out_fence_fd) {
    if (out_fence_fd) *out_fence_fd = -1;
    struct decon_win_config_data_dsu dsu;
    memset(&dsu, 0, sizeof(dsu));
    dsu.fence = -1;
    dsu.fd_odma = -1;
    for (int i = 0; i < MAX_DECON_WIN + 2; i++) {
        dsu.config[i].state = 0;
        dsu.config[i].fence_fd = -1;
    }
    if (win_idx >= MAX_DECON_WIN) win_idx = 3;
    if (idma_type == IDMA_G0) idma_type = IDMA_VG0;

    struct decon_win_config *win = &dsu.config[win_idx];
    win->state = 2; /* DECON_WIN_STATE_BUFFER */
    win->fd_idma[0] = dma_fd;
    win->fd_idma[1] = -1;
    win->fd_idma[2] = -1;
    win->fence_fd = -1;
    win->plane_alpha = 255;
    win->blending = 0;
    win->idma_type = idma_type;
    win->format = DECON_PIXEL_FORMAT_BGRA_8888;
    win->src.w = w; win->src.h = h; win->src.f_w = w; win->src.f_h = h;
    win->dst.w = w; win->dst.h = h; win->dst.f_w = w; win->dst.f_h = h;

    int ret = ioctl(fb_fd, S3CFB_WIN_CONFIG_DSU, &dsu);
    if (ret == 0) {
        if (out_fence_fd) *out_fence_fd = dsu.fence;
        else if (dsu.fence >= 0) close(dsu.fence);
        return 0;
    }
    if (errno == ENOTTY) {
        struct decon_win_config_data_nodsu nodsu;
        memset(&nodsu, 0, sizeof(nodsu));
        nodsu.fence = -1;
        nodsu.fd_odma = -1;
        memcpy(nodsu.config, dsu.config, sizeof(nodsu.config));
        ret = ioctl(fb_fd, S3CFB_WIN_CONFIG_NODSU, &nodsu);
        if (ret == 0) {
            if (out_fence_fd) *out_fence_fd = nodsu.fence;
            else if (nodsu.fence >= 0) close(nodsu.fence);
        }
    }
    return ret;
}

/* ---------- Built-In Interactive VT100/ANSI PTY Terminal ---------- */

typedef struct {
    char cells[TERM_MAX_ROWS][TERM_MAX_COLS];
    uint32_t fg[TERM_MAX_ROWS][TERM_MAX_COLS];
    int cols;
    int rows;
    int cx;
    int cy;
    uint32_t cur_fg;
    int esc_state; /* 0=normal, 1=ESC, 2=CSI */
    char csi_buf[64];
    int csi_len;
    int pty_fd;
    pid_t child_pid;
    bool dirty;
} term_state_t;

static void term_clear(term_state_t *t) {
    for (int r = 0; r < t->rows; r++) {
        for (int c = 0; c < t->cols; c++) {
            t->cells[r][c] = ' ';
            t->fg[r][c] = 0xFFE2E8F0U;
        }
    }
    t->cx = 0;
    t->cy = 0;
    t->dirty = true;
}

static void term_scroll_up(term_state_t *t) {
    for (int r = 1; r < t->rows; r++) {
        memcpy(t->cells[r - 1], t->cells[r], (size_t)t->cols);
        memcpy(t->fg[r - 1], t->fg[r], (size_t)t->cols * sizeof(uint32_t));
    }
    for (int c = 0; c < t->cols; c++) {
        t->cells[t->rows - 1][c] = ' ';
        t->fg[t->rows - 1][c] = 0xFFE2E8F0U;
    }
}

static uint32_t ansi_fg_color(int code) {
    switch (code) {
        case 30: return 0xFF64748BU;
        case 31: return 0xFFF87171U;
        case 32: return 0xFF4ADE80U;
        case 33: return 0xFFFACC15U;
        case 34: return 0xFF60A5FAU;
        case 35: return 0xFFC084FCU;
        case 36: return 0xFF22D3EEU;
        case 37: return 0xFFE2E8F0U;
        default: return 0xFFE2E8F0U;
    }
}

static void term_putc(term_state_t *t, uint8_t ch) {
    t->dirty = true;
    if (t->esc_state == 1) {
        if (ch == '[') {
            t->esc_state = 2;
            t->csi_len = 0;
        } else {
            t->esc_state = 0;
        }
        return;
    }
    if (t->esc_state == 2) {
        if ((ch >= '0' && ch <= '9') || ch == ';' || ch == '?') {
            if (t->csi_len + 1 < (int)sizeof(t->csi_buf)) {
                t->csi_buf[t->csi_len++] = (char)ch;
            }
            return;
        }
        t->csi_buf[t->csi_len] = '\0';
        if (ch == 'H' || ch == 'f') {
            int r = 1, c = 1;
            if (sscanf(t->csi_buf, "%d;%d", &r, &c) >= 1) {
                t->cy = (r > 0 && r <= t->rows) ? r - 1 : 0;
                t->cx = (c > 0 && c <= t->cols) ? c - 1 : 0;
            } else {
                t->cx = 0; t->cy = 0;
            }
        } else if (ch == 'J') {
            if (atoi(t->csi_buf) == 2) term_clear(t);
        } else if (ch == 'K') {
            for (int c = t->cx; c < t->cols; c++) {
                t->cells[t->cy][c] = ' ';
                t->fg[t->cy][c] = 0xFFE2E8F0U;
            }
        } else if (ch == 'm') {
            if (t->csi_len == 0 || strcmp(t->csi_buf, "0") == 0) {
                t->cur_fg = 0xFFE2E8F0U;
            } else {
                char *p = t->csi_buf;
                while (*p) {
                    int val = (int)strtol(p, &p, 10);
                    if (val == 0) t->cur_fg = 0xFFE2E8F0U;
                    else if (val >= 30 && val <= 37) t->cur_fg = ansi_fg_color(val);
                    else if (val >= 90 && val <= 97) t->cur_fg = ansi_fg_color(val - 60);
                    if (*p == ';') p++;
                }
            }
        }
        t->esc_state = 0;
        return;
    }

    if (ch == 0x1B) { t->esc_state = 1; return; }
    if (ch == '\r') { t->cx = 0; return; }
    if (ch == '\n') {
        t->cx = 0;
        t->cy++;
        if (t->cy >= t->rows) {
            term_scroll_up(t);
            t->cy = t->rows - 1;
        }
        return;
    }
    if (ch == '\b' || ch == 0x7F) {
        if (t->cx > 0) t->cx--;
        return;
    }
    if (ch == '\t') {
        int next = (t->cx + 8) & ~7;
        t->cx = (next < t->cols) ? next : (t->cols - 1);
        return;
    }
    if (ch >= 32 && ch < 127) {
        t->cells[t->cy][t->cx] = (char)ch;
        t->fg[t->cy][t->cx] = t->cur_fg;
        t->cx++;
        if (t->cx >= t->cols) {
            t->cx = 0;
            t->cy++;
            if (t->cy >= t->rows) {
                term_scroll_up(t);
                t->cy = t->rows - 1;
            }
        }
    }
}

static void spawn_console_pty(term_state_t *t, uint32_t dp_w, uint32_t dp_h) {
    int c = ((int)dp_w - 64) / 16;
    int r = ((int)dp_h - 120) / 18;
    t->cols = (c > 20 && c <= TERM_MAX_COLS) ? c : 100;
    t->rows = (r > 10 && r <= TERM_MAX_ROWS) ? r : 44;
    t->cur_fg = 0xFFE2E8F0U;
    t->esc_state = 0;
    term_clear(t);

    struct winsize ws = { .ws_row = (unsigned short)t->rows, .ws_col = (unsigned short)t->cols };
    pid_t pid = forkpty(&t->pty_fd, NULL, NULL, &ws);
    if (pid == 0) {
        setenv("TERM", "vt100", 1);
        setenv("HOME", "/root", 1);
        setenv("PATH", "/run/s8:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin", 1);

        if (access("/run/s8/switched_root", F_OK) == 0 || access("/etc/os-release", F_OK) == 0) {
            if (access("/bin/bash", X_OK) == 0) execl("/bin/bash", "bash", "-l", (char *)NULL);
            if (access("/bin/ash", X_OK) == 0) execl("/bin/ash", "ash", "-l", (char *)NULL);
            if (access("/bin/sh", X_OK) == 0) execl("/bin/sh", "sh", "-l", (char *)NULL);
        }

        static const char *roots[] = {"/mnt/rootfs", "/mnt/ubuntu"};
        for (int i = 0; i < 2; i++) {
            char probe[128];
            snprintf(probe, sizeof(probe), "%s/bin", roots[i]);
            if (access(probe, F_OK) == 0 && chroot(roots[i]) == 0 && chdir("/") == 0) {
                if (access("/bin/bash", X_OK) == 0) execl("/bin/bash", "bash", "-l", (char *)NULL);
                if (access("/bin/ash", X_OK) == 0) execl("/bin/ash", "ash", "-l", (char *)NULL);
                execl("/bin/sh", "sh", "-l", (char *)NULL);
            }
        }
        if (access("/run/s8/sh", X_OK) == 0) execl("/run/s8/sh", "sh", "-l", (char *)NULL);
        execl("/sbin/sh", "sh", "-l", (char *)NULL);
        execl("/bin/sh", "sh", (char *)NULL);
        _exit(127);
    }
    t->child_pid = pid;
    if (t->pty_fd >= 0) {
        fcntl(t->pty_fd, F_SETFL, fcntl(t->pty_fd, F_GETFL, 0) | O_NONBLOCK);
    }
}

/* ---------- Framebuffer Text & Software Renderer ---------- */

static void fill_rect(uint32_t *buf, uint32_t bw, uint32_t bh, int x, int y, int w, int h, uint32_t color) {
    if (x < 0) { w += x; x = 0; }
    if (y < 0) { h += y; y = 0; }
    if (x + w > (int)bw) w = (int)bw - x;
    if (y + h > (int)bh) h = (int)bh - y;
    for (int row = y; row < y + h; row++) {
        uint32_t *dst = buf + (size_t)row * bw + x;
        for (int col = 0; col < w; col++) dst[col] = color;
    }
}

static void draw_char_2x(uint32_t *buf, uint32_t bw, uint32_t bh, int x, int y, char ch, uint32_t color) {
    if (ch < 32 || ch > 126) ch = ' ';
    const uint8_t *g = S8_FONT8X8[ch - 32];
    for (int gy = 0; gy < 8; gy++) {
        int py = y + gy * 2;
        if (py < 0 || py + 1 >= (int)bh) continue;
        uint8_t bits = g[gy];
        for (int gx = 0; gx < 8; gx++) {
            if (bits & (0x80 >> gx)) {
                int px = x + gx * 2;
                if (px < 0 || px + 1 >= (int)bw) continue;
                buf[(size_t)py * bw + px] = color;
                buf[(size_t)py * bw + px + 1] = color;
                buf[(size_t)(py + 1) * bw + px] = color;
                buf[(size_t)(py + 1) * bw + px + 1] = color;
            }
        }
    }
}

static void draw_str(uint32_t *buf, uint32_t bw, uint32_t bh, int x, int y, const char *s, uint32_t color) {
    for (int i = 0; s[i]; i++) {
        if (x + i * 16 + 16 > (int)bw) break;
        draw_char_2x(buf, bw, bh, x + i * 16, y, s[i], color);
    }
}

static void render_terminal_frame(uint32_t *buf, uint32_t w, uint32_t h, const term_state_t *t) {
    fill_rect(buf, w, h, 0, 0, (int)w, (int)h, 0xFF090E17U);
    fill_rect(buf, w, h, 0, 0, (int)w, 72, 0xFF0F172AU);
    fill_rect(buf, w, h, 0, 70, (int)w, 2, 0xFF0EA5E9U);

    struct utsname u;
    uname(&u);
    int temp_mc = read_int_file("/sys/class/thermal/thermal_zone0/temp", 0);
    int batt = read_int_file("/sys/class/power_supply/battery/capacity", 0);

    char hdr[160];
    snprintf(hdr, sizeof(hdr), "GALAXY S8 UNIVERSAL TERMINAL | %s | SoC %.1fC | Batt %d%%",
             u.release, temp_mc / 1000.0, batt);
    draw_str(buf, w, h, 24, 26, hdr, 0xFF38BDF8U);

    for (int r = 0; r < t->rows; r++) {
        int py = 96 + r * 18;
        if (py + 16 >= (int)h) break;
        for (int c = 0; c < t->cols; c++) {
            int px = 32 + c * 16;
            if (r == t->cy && c == t->cx) {
                fill_rect(buf, w, h, px, py, 16, 16, 0xFF38BDF8U);
                draw_char_2x(buf, w, h, px, py, t->cells[r][c], 0xFF090E17U);
            } else if (t->cells[r][c] != ' ') {
                draw_char_2x(buf, w, h, px, py, t->cells[r][c], t->fg[r][c]);
            }
        }
    }
}

/* ---------- Minimal USB Keyboard Evdev Input Reader ---------- */

static char keycode_to_ascii(uint16_t code, bool shift) {
    static const char *num_row = "1234567890-=";
    static const char *num_shift = "!@#$%^&*()_+";
    if (code >= KEY_1 && code <= KEY_EQUAL) {
        return shift ? num_shift[code - KEY_1] : num_row[code - KEY_1];
    }
    static const char *q_row = "qwertyuiop[]";
    static const char *q_shift = "QWERTYUIOP{}";
    if (code >= KEY_Q && code <= KEY_RIGHTBRACE) {
        return shift ? q_shift[code - KEY_Q] : q_row[code - KEY_Q];
    }
    static const char *a_row = "asdfghjkl;'`";
    static const char *a_shift = "ASDFGHJKL:\"~";
    if (code >= KEY_A && code <= KEY_GRAVE) {
        return shift ? a_shift[code - KEY_A] : a_row[code - KEY_A];
    }
    static const char *z_row = "zxcvbnm,./";
    static const char *z_shift = "ZXCVBNM<>?";
    if (code >= KEY_Z && code <= KEY_SLASH) {
        return shift ? z_shift[code - KEY_Z] : z_row[code - KEY_Z];
    }
    if (code == KEY_BACKSLASH) return shift ? '|' : '\\';
    if (code == KEY_SPACE) return ' ';
    if (code == KEY_TAB) return '\t';
    if (code == KEY_ENTER || code == KEY_KPENTER) return '\r';
    if (code == KEY_BACKSPACE) return 0x7F;
    return 0;
}

static void scan_usb_keyboards(int fds[MAX_KBD_DEVS], int *count) {
    for (int i = 0; i < *count; i++) {
        if (fds[i] >= 0) close(fds[i]);
    }
    *count = 0;

    DIR *d = opendir("/dev/input");
    if (!d) return;
    struct dirent *ent;
    while ((ent = readdir(d)) != NULL && *count < MAX_KBD_DEVS) {
        if (strncmp(ent->d_name, "event", 5) != 0) continue;
        char path[64], name[128] = "";
        snprintf(path, sizeof(path), "/dev/input/%.48s", ent->d_name);
        int fd = open(path, O_RDONLY | O_NONBLOCK);
        if (fd < 0) continue;
        ioctl(fd, EVIOCGNAME(sizeof(name)), name);
        if (strstr(name, "gpio_keys") || strstr(name, "ssp_context") || strstr(name, "sec_touchscreen")) {
            close(fd);
            continue;
        }
        unsigned long evbit = 0;
        ioctl(fd, EVIOCGBIT(0, sizeof(evbit)), &evbit);
        if (evbit & (1 << EV_KEY)) {
            unsigned long keybit[KEY_MAX / 8 / sizeof(unsigned long) + 1] = {0};
            ioctl(fd, EVIOCGBIT(EV_KEY, sizeof(keybit)), keybit);
            int alpha = 0;
            for (int k = KEY_Q; k <= KEY_P; k++) {
                if (keybit[k / (sizeof(unsigned long) * 8)] & (1UL << (k % (sizeof(unsigned long) * 8)))) alpha++;
            }
            if (alpha >= 8) {
                fds[(*count)++] = fd;
                continue;
            }
        }
        close(fd);
    }
    closedir(d);
}

/* ---------- Shared-Memory GUI Mirror Reader ---------- */

static bool try_blit_shm_fb(uint32_t *dst, uint32_t dp_w, uint32_t dp_h) {
    static const char *paths[] = {
        "/dev/shm/s8_dp_fb",
        "/mnt/rootfs/dev/shm/s8_dp_fb",
        "/mnt/ubuntu/dev/shm/s8_dp_fb",
        "/tmp/s8_dp_fb"
    };
    uint64_t tnow = now_ms();
    for (int i = 0; i < 4; i++) {
        int fd = open(paths[i], O_RDONLY);
        if (fd < 0) continue;
        struct stat st;
        if (fstat(fd, &st) == 0 && (size_t)st.st_size >= sizeof(shm_fb_hdr_t)) {
            shm_fb_hdr_t hdr;
            if (read(fd, &hdr, sizeof(hdr)) == (ssize_t)sizeof(hdr) &&
                hdr.magic == 0x53384642U && hdr.width > 0 && hdr.height > 0 &&
                hdr.width <= 3840 && hdr.height <= 2160 &&
                tnow >= hdr.timestamp_ms && (tnow - hdr.timestamp_ms) < 5000ULL) {
                size_t expected = sizeof(hdr) + (size_t)hdr.width * hdr.height * 4;
                if ((size_t)st.st_size >= expected) {
                    void *map = mmap(NULL, expected, PROT_READ, MAP_SHARED, fd, 0);
                    if (map != MAP_FAILED) {
                        const uint32_t *src = (const uint32_t *)((const uint8_t *)map + sizeof(hdr));
                        if (hdr.width == dp_w && hdr.height == dp_h) {
                            memcpy(dst, src, (size_t)dp_w * dp_h * 4);
                        } else {
                            for (uint32_t y = 0; y < dp_h; y++) {
                                uint32_t sy = (y * hdr.height) / dp_h;
                                for (uint32_t x = 0; x < dp_w; x++) {
                                    uint32_t sx = (x * hdr.width) / dp_w;
                                    dst[(size_t)y * dp_w + x] = src[(size_t)sy * hdr.width + sx];
                                }
                            }
                        }
                        munmap(map, expected);
                        close(fd);
                        return true;
                    }
                }
            }
        }
        close(fd);
    }
    return false;
}

static void write_pty(int fd, const void *buf, size_t len) {
    ssize_t n = write(fd, buf, len);
    (void)n;
}

/* ---------- Main Daemon Loop ---------- */

static void ensure_fb2_node(void) {
    struct stat st;
    if (lstat("/dev/graphics/fb2", &st) != 0 || !S_ISCHR(st.st_mode)) {
        mkdir("/dev/graphics", 0755);
        unlink("/dev/graphics/fb2");
        mknod("/dev/graphics/fb2", S_IFCHR | 0660, makedev(29, 2));
        unlink("/dev/fb2");
        if (symlink("/dev/graphics/fb2", "/dev/fb2") != 0) {}
    }
}

static void wait_and_close_fence(int *fence_fd) {
    if (*fence_fd >= 0) {
        struct pollfd pfd = { .fd = *fence_fd, .events = POLLIN };
        poll(&pfd, 1, 60);
        close(*fence_fd);
        *fence_fd = -1;
    }
}

int main(void) {
    signal(SIGPIPE, SIG_IGN);

    mkdir("/dev/shm", 01777);
    chmod("/dev/shm", 01777);

    int lock_fd = open("/dev/.s8_dp_daemon.lock", O_CREAT | O_RDWR, 0644);
    if (lock_fd >= 0 && flock(lock_fd, LOCK_EX | LOCK_NB) != 0) {
        fprintf(stderr, "[s8_dp_daemon] Another instance holds /dev/.s8_dp_daemon.lock; exiting.\n");
        return 0;
    }

    int ion_fd = -1;
    int fb_fd = -1;
    for (int retry = 0; retry < 15; retry++) {
        ensure_fb2_node();
        if (ion_fd < 0) ion_fd = open("/dev/ion", O_RDWR);
        if (fb_fd < 0) fb_fd = open("/dev/graphics/fb2", O_RDWR);
        if (fb_fd < 0) fb_fd = open("/dev/fb2", O_RDWR);
        if (ion_fd >= 0 && fb_fd >= 0) break;
        usleep(300000);
    }
    if (ion_fd < 0 || fb_fd < 0) {
        fprintf(stderr, "[s8_dp_daemon] Cannot open /dev/ion or fb2 (%s)\n", strerror(errno));
        return 1;
    }

    size_t buf_sz = 1920 * 1080 * 4;
    uint32_t *ion_bufs[NUM_BUFFERS] = {NULL, NULL};
    int dma_fds[NUM_BUFFERS] = {-1, -1};
    for (int i = 0; i < NUM_BUFFERS; i++) {
        struct ion_allocation_data alloc = { .len = buf_sz, .align = 4096, .heap_id_mask = ION_HEAP_SYSTEM_MASK };
        if (ioctl(ion_fd, ION_IOC_ALLOC, &alloc) < 0) return 1;
        struct ion_fd_data share = { .handle = alloc.handle };
        if (ioctl(ion_fd, ION_IOC_SHARE, &share) < 0) return 1;
        dma_fds[i] = share.fd;
        ion_bufs[i] = mmap(NULL, buf_sz, PROT_READ | PROT_WRITE, MAP_SHARED, share.fd, 0);
        if (ion_bufs[i] == MAP_FAILED) return 1;
    }

    ioctl(fb_fd, FBIOBLANK, FB_BLANK_POWERDOWN);
    printf("[s8_dp_daemon] Static DP supervisor + PTY terminal ready.\n");
    fflush(stdout);

    bool was_attached = false;
    bool dp_active = false;
    bool force_console = false;
    bool was_gui = false;
    uint32_t dp_w = 1920, dp_h = 1080;
    int cur_buf = 0;
    int buf_fences[NUM_BUFFERS] = {-1, -1};
    int term_dirty_frames = 2;
    uint64_t last_term_tick = 0;

    term_state_t term;
    memset(&term, 0, sizeof(term));
    term.pty_fd = -1;

    int kbd_fds[MAX_KBD_DEVS];
    int kbd_cnt = 0;
    bool shift_down = false, ctrl_down = false, alt_down = false;
    uint64_t last_kbd_scan = 0;

    while (1) {
        bool attached = is_partner_attached();
        int hdmi = read_int_file("/sys/class/switch/hdmi/state", 0);

        if (!attached && was_attached) {
            wait_and_close_fence(&buf_fences[0]);
            wait_and_close_fence(&buf_fences[1]);
            reset_typec_on_detach(fb_fd);
            dp_active = false;
            was_attached = false;
            printf("[s8_dp_daemon] Partner detached -> fb2 powered down.\n");
            fflush(stdout);
        }

        if (attached && !was_attached) {
            was_attached = true;
            if (hdmi == 0) attempt_dp_link();
            hdmi = read_int_file("/sys/class/switch/hdmi/state", 0);
        }

        if (hdmi <= 0) {
            if (dp_active) {
                wait_and_close_fence(&buf_fences[0]);
                wait_and_close_fence(&buf_fences[1]);
                ioctl(fb_fd, FBIOBLANK, FB_BLANK_POWERDOWN);
                dp_active = false;
            }
            usleep(400000);
            continue;
        }

        if (!dp_active) {
            configure_dp_timings(fb_fd, &dp_w, &dp_h);
            if (dp_w * dp_h * 4 > buf_sz) { dp_w = 1920; dp_h = 1080; }
            ioctl(fb_fd, FBIOBLANK, FB_BLANK_UNBLANK);
            pulse_vibrator(120);
            if (term.pty_fd < 0) spawn_console_pty(&term, dp_w, dp_h);
            scan_usb_keyboards(kbd_fds, &kbd_cnt);
            last_kbd_scan = now_ms();
            term_dirty_frames = 2;
            last_term_tick = 0;
            dp_active = true;
            usleep(50000);
            printf("[s8_dp_daemon] DisplayPort ACTIVE (%ux%u).\n", dp_w, dp_h);
            fflush(stdout);
        }

        if (now_ms() - last_kbd_scan > 3000ULL) {
            scan_usb_keyboards(kbd_fds, &kbd_cnt);
            last_kbd_scan = now_ms();
        }

        /* Respawn PTY if shell exited */
        if (term.child_pid > 0 && waitpid(term.child_pid, NULL, WNOHANG) > 0) {
            close(term.pty_fd);
            term.pty_fd = -1;
            spawn_console_pty(&term, dp_w, dp_h);
        }

        /* Read PTY output into terminal grid */
        if (term.pty_fd >= 0) {
            uint8_t pbuf[2048];
            ssize_t n;
            while ((n = read(term.pty_fd, pbuf, sizeof(pbuf))) > 0) {
                for (ssize_t i = 0; i < n; i++) term_putc(&term, pbuf[i]);
            }
        }

        /* Read USB keyboard events into PTY (when in console mode or Ctrl+Alt+F1 toggle) */
        for (int k = 0; k < kbd_cnt; k++) {
            struct input_event ev;
            while (read(kbd_fds[k], &ev, sizeof(ev)) == (ssize_t)sizeof(ev)) {
                if (ev.type != EV_KEY) continue;
                if (ev.code == KEY_LEFTSHIFT || ev.code == KEY_RIGHTSHIFT) {
                    shift_down = (ev.value != 0);
                    continue;
                }
                if (ev.code == KEY_LEFTCTRL || ev.code == KEY_RIGHTCTRL) {
                    ctrl_down = (ev.value != 0);
                    continue;
                }
                if (ev.code == KEY_LEFTALT || ev.code == KEY_RIGHTALT) {
                    alt_down = (ev.value != 0);
                    continue;
                }
                if (ev.value == 0) continue;
                if (ctrl_down && alt_down && ev.code == KEY_F1) {
                    force_console = !force_console;
                    term.dirty = true;
                    continue;
                }
                if (term.pty_fd >= 0) {
                    if (ctrl_down && ev.code >= KEY_A && ev.code <= KEY_Z) {
                        char ch = keycode_to_ascii(ev.code, false);
                        if (ch >= 'a' && ch <= 'z') {
                            uint8_t ctrl_c = (uint8_t)(ch - 'a' + 1);
                            write_pty(term.pty_fd, &ctrl_c, 1);
                        }
                    } else if (ev.code == KEY_UP) {
                        write_pty(term.pty_fd, "\x1b[A", 3);
                    } else if (ev.code == KEY_DOWN) {
                        write_pty(term.pty_fd, "\x1b[B", 3);
                    } else if (ev.code == KEY_RIGHT) {
                        write_pty(term.pty_fd, "\x1b[C", 3);
                    } else if (ev.code == KEY_LEFT) {
                        write_pty(term.pty_fd, "\x1b[D", 3);
                    } else {
                        char ch = keycode_to_ascii(ev.code, shift_down);
                        if (ch != 0) write_pty(term.pty_fd, &ch, 1);
                    }
                }
            }
        }

        if (term.dirty) {
            term.dirty = false;
            term_dirty_frames = 2;
        }
        uint64_t cur_ms = now_ms();
        if (cur_ms - last_term_tick >= 1000ULL) {
            last_term_tick = cur_ms;
            if (term_dirty_frames == 0) term_dirty_frames = 1;
        }

        wait_and_close_fence(&buf_fences[cur_buf]);
        uint32_t *target = ion_bufs[cur_buf];
        bool gui_rendered = false;
        if (!force_console) {
            gui_rendered = try_blit_shm_fb(target, dp_w, dp_h);
        }
        if (!gui_rendered && was_gui) {
            term_dirty_frames = 2;
        }
        was_gui = gui_rendered;

        bool need_present = gui_rendered || (term_dirty_frames > 0);
        if (!gui_rendered && need_present) {
            render_terminal_frame(target, dp_w, dp_h, &term);
            if (term_dirty_frames > 0) term_dirty_frames--;
        }

        if (need_present) {
            int new_fence = -1;
            if (submit_frame(fb_fd, dma_fds[cur_buf], 3, IDMA_VG0, dp_w, dp_h, &new_fence) == 0) {
                buf_fences[cur_buf] = new_fence;
                cur_buf = 1 - cur_buf;
                uint32_t crtc = 0;
                ioctl(fb_fd, FBIO_WAITFORVSYNC, &crtc);
            } else {
                if (new_fence >= 0) close(new_fence);
                usleep(16666);
            }
        } else {
            usleep(16666);
        }
    }
    return 0;
}
