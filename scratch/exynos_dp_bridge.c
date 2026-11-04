/*
 * exynos_dp_bridge.c — Samsung Galaxy S8 (SM-G950N, Exynos 8895)
 * Native USB-C DisplayPort / HDMI Output Bridge (/dev/ion -> S3CFB_WIN_CONFIG on /dev/graphics/fb2)
 *
 * Mirrors the live X11 macOS Sonoma Desktop (:1) directly to the Exynos 8895 DECON2
 * DisplayPort hardware pipeline (/dev/graphics/fb2) so any USB-C Monitor or
 * Type-C-to-HDMI Dongle displays the desktop automatically.
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
#include <linux/fb.h>

#ifdef USE_X11
#include <X11/Xlib.h>
#include <X11/Xutil.h>
#include <sys/ipc.h>
#include <sys/shm.h>
#include <X11/extensions/XShm.h>
#endif

/* --- Exynos ION UAPI Definitions (drivers/staging/android/uapi/ion.h) --- */
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

#define ION_IOC_MAGIC       'I'
#define ION_IOC_ALLOC       _IOWR(ION_IOC_MAGIC, 0, struct ion_allocation_data)
#define ION_IOC_SHARE       _IOWR(ION_IOC_MAGIC, 4, struct ion_fd_data)
#define ION_HEAP_SYSTEM_MASK (1 << 0)

/* --- Exynos 8895 DECON UAPI Definitions (drivers/video/fbdev/exynos/dpu/decon.h) --- */
#define MAX_DECON_WIN       6
#define MAX_PLANE_CNT       3

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
    uint64_t addr[MAX_PLANE_CNT]; /* dma_addr_t on arm64 is 64-bit */
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

/* With CONFIG_SUPPORT_DSU=y (default on dreamltekor_defconfig): MAX_DECON_WIN + 2 = 8 */
struct decon_win_config_data_dsu {
    int fence;
    int fd_odma;
    struct decon_win_config config[MAX_DECON_WIN + 2];
};

/* Without CONFIG_SUPPORT_DSU: MAX_DECON_WIN + 1 = 7 */
struct decon_win_config_data_nodsu {
    int fence;
    int fd_odma;
    struct decon_win_config config[MAX_DECON_WIN + 1];
};

#define S3CFB_WIN_CONFIG_DSU   _IOW('F', 209, struct decon_win_config_data_dsu)
#define S3CFB_WIN_CONFIG_NODSU _IOW('F', 209, struct decon_win_config_data_nodsu)

static int submit_frame(int fb_fd, int dma_fd, uint32_t w, uint32_t h) {
    struct decon_win_config_data_dsu data_dsu;
    memset(&data_dsu, 0, sizeof(data_dsu));
    data_dsu.fence = -1;
    data_dsu.fd_odma = -1;

    for (int i = 0; i < MAX_DECON_WIN + 2; i++) {
        data_dsu.config[i].state = DECON_WIN_STATE_DISABLED;
        data_dsu.config[i].fence_fd = -1;
    }

    /* Configure Window 0 via IDMA_VG0 (or IDMA_G1) */
    struct decon_win_config *win = &data_dsu.config[0];
    win->state = DECON_WIN_STATE_BUFFER;
    win->fd_idma[0] = dma_fd;
    win->fd_idma[1] = -1;
    win->fd_idma[2] = -1;
    win->fence_fd = -1;
    win->plane_alpha = 255;
    win->blending = DECON_BLENDING_NONE;
    win->idma_type = IDMA_VG0;
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

int main(int argc, char **argv) {
    const char *fb_path = "/dev/graphics/fb2";
    if (access(fb_path, R_OK | W_OK) != 0)
        fb_path = "/dev/fb2";

    int ion_fd = open("/dev/ion", O_RDWR);
    if (ion_fd < 0) {
        perror("open(/dev/ion)");
        return 1;
    }

    uint32_t width = 1920, height = 1080;
    size_t frame_bytes = (size_t)width * height * 4;

    struct ion_allocation_data alloc_data = {
        .len = frame_bytes,
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

    uint32_t *ion_buf = mmap(NULL, frame_bytes, PROT_READ | PROT_WRITE, MAP_SHARED, dma_fd, 0);
    if (ion_buf == MAP_FAILED) {
        perror("mmap(dma_fd)");
        return 1;
    }

    printf("[exynos_dp_bridge] Allocated %zu bytes in Exynos ION (dma_fd=%d)\n", frame_bytes, dma_fd);

    int fb_fd = open(fb_path, O_RDWR);
    if (fb_fd < 0) {
        perror("open(/dev/graphics/fb2)");
        return 1;
    }

    /* Unblank DisplayPort DECON2 if monitor is attached */
    ioctl(fb_fd, FBIOBLANK, FB_BLANK_UNBLANK);

    if (argc > 1 && strcmp(argv[1], "--once") == 0) {
        for (size_t i = 0; i < (size_t)width * height; i++)
            ion_buf[i] = 0xFF1E1E2E; /* Sleek dark indigo test fill */
        int r = submit_frame(fb_fd, dma_fd, width, height);
        printf("[exynos_dp_bridge] Single-frame test submit_frame ret=%d (errno=%d: %s)\n",
               r, errno, strerror(errno));
        return 0;
    }

#ifdef USE_X11
    Display *dpy = NULL;
    while (!dpy) {
        dpy = XOpenDisplay(":1");
        if (!dpy)
            sleep(2);
    }
    Window root = DefaultRootWindow(dpy);
    printf("[exynos_dp_bridge] Connected to X11 display :1 — streaming to USB-C DisplayPort (%s)\n", fb_path);

    while (1) {
        /* Check if a USB-C monitor / HDMI dongle is connected */
        int hpd = 0;
        FILE *fp = fopen("/sys/class/dp_sec/dex", "r");
        if (fp) {
            if (fscanf(fp, "%d", &hpd) != 1) hpd = 0;
            fclose(fp);
        }
        XImage *img = XGetImage(dpy, root, 0, 0, width, height, AllPlanes, ZPixmap);
        if (img) {
            memcpy(ion_buf, img->data, frame_bytes);
            XDestroyImage(img);
            ioctl(fb_fd, FBIOBLANK, FB_BLANK_UNBLANK);
            submit_frame(fb_fd, dma_fd, width, height);
        }
        usleep(33000); /* ~30 FPS low-CPU mirror when active */
    }
#endif
    return 0;
}

