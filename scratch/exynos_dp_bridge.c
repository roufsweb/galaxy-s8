/*
 * exynos_dp_bridge.c — Samsung Galaxy S8 (SM-G950N, Exynos 8895)
 * Native USB-C DisplayPort / HDMI Hotplug & Framebuffer Bridge
 * (/dev/ion + EXYNOS_SET_DISPLAYPORT_CONFIG + S3CFB_WIN_CONFIG on /dev/graphics/fb2)
 *
 * Implements the full Samsung Exynos 8895 DECON2 + DisplayPort hotplug state machine:
 *   1. While /sys/class/switch/hdmi/state == 0 (unplugged), keeps /dev/graphics/fb2
 *      in FB_BLANK_POWERDOWN (DECON_STATE_OFF) and polls HPD at low power.
 *   2. When a USB-C Monitor or Type-C-to-HDMI Dongle is plugged in (state == 1):
 *      - Enumerates EDID-matched timings via EXYNOS_GET_DISPLAYPORT_CONFIG
 *        (preferring 1920x1080@60Hz to match :1 1:1, or the best supported mode)
 *      - Applies the timing via EXYNOS_SET_DISPLAYPORT_CONFIG (displayport_s_dv_timings)
 *      - Calls FBIOBLANK(FB_BLANK_UNBLANK) to transition DECON2 OFF->ON and trigger
 *        displayport_enable() (s_stream(1)), waking displayport->dp_wait
 *      - Pulses the haptic vibrator (150ms) to confirm physical video lock
 *      - Streams the live :1 macOS Sonoma X11 desktop via XShmGetImage -> ION DMA-BUF
 *        -> S3CFB_WIN_CONFIG at 30 FPS until unplugged.
 */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sys/ipc.h>
#include <sys/shm.h>
#include <linux/fb.h>
#include <linux/videodev2.h>
#include <X11/Xlib.h>
#include <X11/Xutil.h>
#include <X11/extensions/XShm.h>

/* --- Exynos ION UAPI Definitions --- */
typedef int ion_user_handle_t;

struct ion_allocation_data {
    size_t len;
    size_t align;
    unsigned int heap_id_mask;
    unsigned int flags;
    ion_user_handle_t handle;
};

struct ion_fd_data {
    ion_user_handle_t handle;
    int fd;
};

#define ION_IOC_MAGIC        'I'
#define ION_IOC_ALLOC        _IOWR(ION_IOC_MAGIC, 0, struct ion_allocation_data)
#define ION_IOC_SHARE        _IOWR(ION_IOC_MAGIC, 4, struct ion_fd_data)
#define ION_HEAP_SYSTEM_MASK (1 << 0)

/* --- Exynos 8895 DECON & DisplayPort UAPI Definitions --- */
#define MAX_DECON_WIN        6
#define MAX_PLANE_CNT        3

enum decon_win_state {
    DECON_WIN_STATE_DISABLED = 0,
    DECON_WIN_STATE_COLOR,
    DECON_WIN_STATE_BUFFER,
    DECON_WIN_STATE_UPDATE,
};

enum decon_blending {
    DECON_BLENDING_NONE = 0,
    DECON_BLENDING_PREMULT = 1,
    DECON_BLENDING_COVERAGE = 2,
    DECON_BLENDING_MAX = 3,
};

enum decon_idma_type {
    IDMA_G0 = 0,
    IDMA_G1 = 1,
    IDMA_VG0 = 2,
    IDMA_VG1 = 3,
    IDMA_VGF0 = 4,
    IDMA_VGF1 = 5,
    ODMA_WB = 6,
    IDMA_G0_S = 7,
};

enum decon_pixel_format {
    DECON_PIXEL_FORMAT_ARGB_8888 = 0,
    DECON_PIXEL_FORMAT_ABGR_8888,
    DECON_PIXEL_FORMAT_RGBA_8888,
    DECON_PIXEL_FORMAT_BGRA_8888,
    DECON_PIXEL_FORMAT_XRGB_8888,
    DECON_PIXEL_FORMAT_XBGR_8888,
    DECON_PIXEL_FORMAT_RGBX_8888,
    DECON_PIXEL_FORMAT_BGRX_8888,
};

struct decon_win_rect {
    int x;
    int y;
    uint32_t w;
    uint32_t h;
};

struct dpp_params {
    uint64_t addr[MAX_PLANE_CNT];
    uint32_t flip;
    uint32_t eq_mode;
    uint32_t comp_src;
};

struct decon_frame {
    int x;
    int y;
    uint32_t w;
    uint32_t h;
    uint32_t f_w;
    uint32_t f_h;
};

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
        struct {
            int left;
            int top;
            int right;
            int bottom;
            int mode;
        };
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
        EXYNOS_DISPLAYPORT_STATE_RECONNECTION,
        EXYNOS_DISPLAYPORT_STATE_HDCP,
        EXYNOS_DISPLAYPORT_STATE_AUDIO,
    } state;
    struct v4l2_dv_timings timings;
    struct v4l2_enum_dv_timings etimings;
    uint32_t audio_info;
    int hdcp;
};

#define S3CFB_WIN_CONFIG_DSU          _IOW('F', 209, struct decon_win_config_data_dsu)
#define S3CFB_WIN_CONFIG_NODSU        _IOW('F', 209, struct decon_win_config_data_nodsu)
#define EXYNOS_GET_DISPLAYPORT_CONFIG _IOW('F', 300, struct exynos_displayport_data)
#define EXYNOS_SET_DISPLAYPORT_CONFIG _IOW('F', 301, struct exynos_displayport_data)

static int read_int_file(const char *path, int def_val) {
    FILE *fp = fopen(path, "r");
    if (!fp) return def_val;
    int val = def_val;
    if (fscanf(fp, "%d", &val) != 1) val = def_val;
    fclose(fp);
    return val;
}

static uint32_t read_dt_u32(const char *path, uint32_t def_val) {
    FILE *fp = fopen(path, "rb");
    if (!fp) return def_val;
    uint8_t b[4];
    if (fread(b, 1, 4, fp) != 4) {
        fclose(fp);
        return def_val;
    }
    fclose(fp);
    return ((uint32_t)b[0] << 24) | ((uint32_t)b[1] << 16) | ((uint32_t)b[2] << 8) | (uint32_t)b[3];
}

static void pulse_vibrator(int ms) {
    FILE *fp = fopen("/sys/class/timed_output/vibrator/enable", "w");
    if (fp) {
        fprintf(fp, "%d\n", ms);
        fclose(fp);
    }
}

static int configure_dp_resolution(int fb_fd, uint32_t *out_w, uint32_t *out_h) {
    struct exynos_displayport_data dp_data;
    struct v4l2_dv_timings best_timings;
    bool found_best = false;
    bool found_1080p = false;

    memset(&best_timings, 0, sizeof(best_timings));

    /* Enumerate EDID-supported presets (0..35), preferring 1920x1080p */
    for (uint32_t idx = 0; idx < 36; idx++) {
        memset(&dp_data, 0, sizeof(dp_data));
        dp_data.state = EXYNOS_DISPLAYPORT_STATE_ENUM_PRESET;
        dp_data.etimings.index = idx;
        if (ioctl(fb_fd, EXYNOS_GET_DISPLAYPORT_CONFIG, &dp_data) == 0) {
            uint32_t w = dp_data.etimings.timings.bt.width;
            uint32_t h = dp_data.etimings.timings.bt.height;
            printf("[exynos_dp_bridge] EDID preset[%u]: %ux%u (pixelclock=%llu)\n",
                   idx, w, h, (unsigned long long)dp_data.etimings.timings.bt.pixelclock);
            if (!found_best || (w * h >= best_timings.bt.width * best_timings.bt.height && w <= 1920)) {
                best_timings = dp_data.etimings.timings;
                found_best = true;
            }
            if (w == 1920 && h == 1080) {
                best_timings = dp_data.etimings.timings;
                found_1080p = true;
                found_best = true;
            }
        }
    }

    if (!found_best) {
        memset(&dp_data, 0, sizeof(dp_data));
        dp_data.state = EXYNOS_DISPLAYPORT_STATE_PRESET;
        if (ioctl(fb_fd, EXYNOS_GET_DISPLAYPORT_CONFIG, &dp_data) == 0 &&
            dp_data.timings.bt.width > 0 && dp_data.timings.bt.height > 0) {
            best_timings = dp_data.timings;
            found_best = true;
        }
    }

    if (found_best) {
        memset(&dp_data, 0, sizeof(dp_data));
        dp_data.state = EXYNOS_DISPLAYPORT_STATE_PRESET;
        dp_data.timings = best_timings;
        int ret = ioctl(fb_fd, EXYNOS_SET_DISPLAYPORT_CONFIG, &dp_data);
        printf("[exynos_dp_bridge] EXYNOS_SET_DISPLAYPORT_CONFIG (%ux%u, 1080p=%d) ret=%d\n",
               best_timings.bt.width, best_timings.bt.height, found_1080p, ret);
        if (best_timings.bt.width > 0 && best_timings.bt.height > 0) {
            *out_w = best_timings.bt.width;
            *out_h = best_timings.bt.height;
            return 0;
        }
    }

    *out_w = 1920;
    *out_h = 1080;
    return -1;
}

static int submit_frame(int fb_fd, int dma_fd, uint32_t win_idx, uint32_t idma_type, uint32_t w, uint32_t h) {
    struct decon_win_config_data_dsu data_dsu;
    memset(&data_dsu, 0, sizeof(data_dsu));
    data_dsu.fence = -1;
    data_dsu.fd_odma = -1;

    for (int i = 0; i < MAX_DECON_WIN + 2; i++) {
        data_dsu.config[i].state = DECON_WIN_STATE_DISABLED;
        data_dsu.config[i].fence_fd = -1;
    }

    if (win_idx >= MAX_DECON_WIN) win_idx = 0;
    struct decon_win_config *win = &data_dsu.config[win_idx];
    win->state = DECON_WIN_STATE_BUFFER;
    win->fd_idma[0] = dma_fd;
    win->fd_idma[1] = -1;
    win->fd_idma[2] = -1;
    win->fence_fd = -1;
    win->plane_alpha = 255;
    win->blending = DECON_BLENDING_NONE;
    win->idma_type = idma_type;
    win->format = DECON_PIXEL_FORMAT_XRGB_8888;
    win->src.x = 0;
    win->src.y = 0;
    win->src.w = w;
    win->src.h = h;
    win->src.f_w = w;
    win->src.f_h = h;
    win->dst.x = 0;
    win->dst.y = 0;
    win->dst.w = w;
    win->dst.h = h;
    win->dst.f_w = w;
    win->dst.f_h = h;

    int ret = ioctl(fb_fd, S3CFB_WIN_CONFIG_DSU, &data_dsu);
    if (ret == 0) {
        if (data_dsu.fence >= 0)
            close(data_dsu.fence);
        return 0;
    }

    if (errno == ENOTTY) {
        struct decon_win_config_data_nodsu data_nodsu;
        memset(&data_nodsu, 0, sizeof(data_nodsu));
        data_nodsu.fence = -1;
        data_nodsu.fd_odma = -1;
        memcpy(data_nodsu.config, data_dsu.config, sizeof(data_nodsu.config));
        ret = ioctl(fb_fd, S3CFB_WIN_CONFIG_NODSU, &data_nodsu);
        if (ret == 0 && data_nodsu.fence >= 0)
            close(data_nodsu.fence);
    }
    return ret;
}

static void blit_or_scale(uint32_t *dst, const uint32_t *src,
                          uint32_t dst_w, uint32_t dst_h,
                          uint32_t src_w, uint32_t src_h) {
    if (dst_w == src_w && dst_h == src_h) {
        memcpy(dst, src, (size_t)dst_w * dst_h * 4);
        return;
    }
    for (uint32_t y = 0; y < dst_h; y++) {
        uint32_t sy = (y * src_h) / dst_h;
        const uint32_t *src_row = src + (size_t)sy * src_w;
        uint32_t *dst_row = dst + (size_t)y * dst_w;
        for (uint32_t x = 0; x < dst_w; x++) {
            uint32_t sx = (x * src_w) / dst_w;
            dst_row[x] = src_row[sx];
        }
    }
}

int main(int argc, char **argv) {
    setvbuf(stdout, NULL, _IOLBF, 0);
    setvbuf(stderr, NULL, _IOLBF, 0);

    const char *fb_path = "/dev/graphics/fb2";
    if (access(fb_path, R_OK | W_OK) != 0)
        fb_path = "/dev/fb2";

    uint32_t dft_win = read_dt_u32("/proc/device-tree/decon_t/default_win", 0);
    uint32_t dft_idma = read_dt_u32("/proc/device-tree/decon_t/default_idma", IDMA_G0);
    printf("[exynos_dp_bridge] DECON2 DT defaults: default_win=%u, default_idma=%u\n", dft_win, dft_idma);

    int ion_fd = open("/dev/ion", O_RDWR);
    if (ion_fd < 0) {
        perror("open(/dev/ion)");
        return 1;
    }

    /* Allocate 16 MB in Exynos ION (supports up to 2560x1440 / 1920x1080 RGBA) */
    size_t max_frame_bytes = 2560ULL * 1440ULL * 4ULL;
    struct ion_allocation_data alloc_data = {
        .len = max_frame_bytes,
        .align = 4096,
        .heap_id_mask = ION_HEAP_SYSTEM_MASK,
        .flags = 0,
    };
    if (ioctl(ion_fd, ION_IOC_ALLOC, &alloc_data) < 0) {
        perror("ION_IOC_ALLOC");
        return 1;
    }

    struct ion_fd_data fd_data = {
        .handle = alloc_data.handle,
    };
    if (ioctl(ion_fd, ION_IOC_SHARE, &fd_data) < 0) {
        perror("ION_IOC_SHARE");
        return 1;
    }
    int dma_fd = fd_data.fd;

    uint32_t *ion_buf = mmap(NULL, max_frame_bytes, PROT_READ | PROT_WRITE, MAP_SHARED, dma_fd, 0);
    if (ion_buf == MAP_FAILED) {
        perror("mmap(dma_fd)");
        return 1;
    }

    printf("[exynos_dp_bridge] Allocated %zu bytes in Exynos ION (dma_fd=%d)\n", max_frame_bytes, dma_fd);

    int fb_fd = open(fb_path, O_RDWR);
    if (fb_fd < 0) {
        perror("open(/dev/graphics/fb2)");
        return 1;
    }

    /* Connect to X11 display :1 */
    const uint32_t x11_w = 1920, x11_h = 1080;
    Display *dpy = NULL;
    while (!dpy) {
        dpy = XOpenDisplay(":1");
        if (!dpy)
            sleep(1);
    }
    Window root = DefaultRootWindow(dpy);

    /* Set up XShm for zero-copy high-speed capture from :1 */
    XShmSegmentInfo shminfo;
    memset(&shminfo, 0, sizeof(shminfo));
    XImage *shm_img = XShmCreateImage(dpy, DefaultVisual(dpy, DefaultScreen(dpy)),
                                      DefaultDepth(dpy, DefaultScreen(dpy)),
                                      ZPixmap, NULL, &shminfo, x11_w, x11_h);
    bool use_shm = false;
    if (shm_img) {
        shminfo.shmid = shmget(IPC_PRIVATE, (size_t)shm_img->bytes_per_line * shm_img->height, IPC_CREAT | 0600);
        if (shminfo.shmid >= 0) {
            shminfo.shmaddr = shm_img->data = shmat(shminfo.shmid, 0, 0);
            shminfo.readOnly = False;
            if (shminfo.shmaddr != (void *)-1 && XShmAttach(dpy, &shminfo)) {
                XSync(dpy, False);
                shmctl(shminfo.shmid, IPC_RMID, 0);
                use_shm = true;
            }
        }
    }
    printf("[exynos_dp_bridge] Connected to X11 :1 (use_shm=%d) — monitoring USB-C DisplayPort HPD...\n", use_shm);

    bool dp_active = false;
    uint32_t dp_w = 1920, dp_h = 1080;
    bool force_mode = (argc > 1 && strcmp(argv[1], "--force") == 0);

    /* Ensure DECON2 starts in FB_BLANK_POWERDOWN when unplugged so next HPD=1 triggers decon_enable -> displayport_enable */
    if (read_int_file("/sys/class/switch/hdmi/state", 0) == 0 && !force_mode) {
        ioctl(fb_fd, FBIOBLANK, FB_BLANK_POWERDOWN);
        printf("[exynos_dp_bridge] USB-C DisplayPort currently unplugged (HPD=0); DECON2 armed in FB_BLANK_POWERDOWN.\n");
    }

    while (1) {
        int hpd = force_mode ? 1 : read_int_file("/sys/class/switch/hdmi/state", 0);

        if (hpd <= 0) {
            if (dp_active) {
                printf("[exynos_dp_bridge] USB-C DisplayPort unplugged (HPD=0) — powering down DECON2.\n");
                ioctl(fb_fd, FBIOBLANK, FB_BLANK_POWERDOWN);
                dp_active = false;
            }
            usleep(100000); /* 100ms fast HPD poll (0% CPU) */
            continue;
        }

        if (!dp_active) {
            printf("[exynos_dp_bridge] USB-C DisplayPort HPD=1 detected! Negotiating EDID & enabling DECON2...\n");
            configure_dp_resolution(fb_fd, &dp_w, &dp_h);
            if (dp_w > 2560 || dp_h > 1440) {
                dp_w = 1920;
                dp_h = 1080;
            }
            int blank_ret = ioctl(fb_fd, FBIOBLANK, FB_BLANK_UNBLANK);
            printf("[exynos_dp_bridge] FBIOBLANK(FB_BLANK_UNBLANK) ret=%d — streaming :1 (%ux%u -> %ux%u)\n",
                   blank_ret, x11_w, x11_h, dp_w, dp_h);
            pulse_vibrator(150);
            dp_active = true;
            usleep(30000);
        }

        if (use_shm) {
            if (XShmGetImage(dpy, root, shm_img, 0, 0, AllPlanes)) {
                blit_or_scale(ion_buf, (const uint32_t *)shm_img->data, dp_w, dp_h, x11_w, x11_h);
            }
        } else {
            XImage *img = XGetImage(dpy, root, 0, 0, x11_w, x11_h, AllPlanes, ZPixmap);
            if (img) {
                blit_or_scale(ion_buf, (const uint32_t *)img->data, dp_w, dp_h, x11_w, x11_h);
                XDestroyImage(img);
            }
        }

        int ret = submit_frame(fb_fd, dma_fd, dft_win, dft_idma, dp_w, dp_h);
        if (ret < 0 && dft_idma != IDMA_VG0) {
            dft_idma = IDMA_VG0;
            submit_frame(fb_fd, dma_fd, dft_win, dft_idma, dp_w, dp_h);
        }

        usleep(33000); /* ~30 FPS */
    }

    return 0;
}
