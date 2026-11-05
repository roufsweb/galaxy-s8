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

#define MAX_DECON_WIN 6
#define MAX_PLANE_CNT 3

enum { DECON_WIN_STATE_DISABLED = 0, DECON_WIN_STATE_COLOR, DECON_WIN_STATE_BUFFER };
enum { DECON_BLENDING_NONE = 0 };
enum { IDMA_VG0 = 2 };
enum { DECON_PIXEL_FORMAT_XRGB_8888 = 4 };

struct decon_win_rect {
    int32_t x, y;
    uint32_t w, h;
};
struct dpp_params {
    uint64_t addr[MAX_PLANE_CNT];
    int32_t flip, eq_mode, comp_src;
};
struct decon_frame {
    int32_t x, y;
    uint32_t w, h, f_w, f_h;
};
struct decon_win_config {
    int32_t state;
    union {
        uint32_t color;
        struct {
            int32_t fd_idma[3];
            int32_t fence_fd;
            int32_t plane_alpha;
            int32_t blending;
            int32_t idma_type;
            int32_t format;
            struct dpp_params dpp_parm;
            struct decon_win_rect block_area;
            struct decon_win_rect transparent_area;
            struct decon_win_rect opaque_area;
            struct decon_frame src;
        };
        struct {
            int32_t left, top, right, bottom, mode;
        };
    };
    struct decon_frame dst;
    bool protection;
    bool compression;
};
struct decon_win_config_data_dsu {
    int32_t fence;
    int32_t fd_odma;
    struct decon_win_config config[MAX_DECON_WIN + 2];
};
#define S3CFB_WIN_CONFIG_DSU _IOW('F', 209, struct decon_win_config_data_dsu)

int main() {
    printf("[test_dp] Setting DisplayPort bpc to 8...\n");
    system("echo 8 > /sys/class/dp_sec/bpc");

    int fb_fd = open("/dev/graphics/fb2", O_RDWR);
    if (fb_fd < 0) {
        perror("open(/dev/graphics/fb2)");
        return 1;
    }

    int ion_fd = open("/dev/ion", O_RDWR);
    if (ion_fd < 0) {
        perror("open(/dev/ion)");
        return 1;
    }

    const uint32_t w = 1920, h = 1080;
    size_t frame_bytes = (size_t)w * h * 4;

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

    struct ion_fd_data fd_data = { .handle = alloc_data.handle };
    if (ioctl(ion_fd, ION_IOC_SHARE, &fd_data) < 0) {
        perror("ION_IOC_SHARE");
        return 1;
    }
    int dma_fd = fd_data.fd;

    uint32_t *buf = mmap(NULL, frame_bytes, PROT_READ | PROT_WRITE, MAP_SHARED, dma_fd, 0);
    if (buf == MAP_FAILED) {
        perror("mmap");
        return 1;
    }

    /* Fill buffer with high-visibility SMPTE-style test pattern / gradient */
    for (uint32_t y = 0; y < h; y++) {
        for (uint32_t x = 0; x < w; x++) {
            if (y < h / 3) {
                /* Color bars: White, Yellow, Cyan, Green, Magenta, Red, Blue */
                uint32_t bar = (x * 7) / w;
                uint32_t colors[7] = {
                    0x00FFFFFF, // White
                    0x00FFFF00, // Yellow
                    0x0000FFFF, // Cyan
                    0x0000FF00, // Green
                    0x00FF00FF, // Magenta
                    0x00FF0000, // Red
                    0x000000FF, // Blue
                };
                buf[y * w + x] = colors[bar];
            } else if (y < (2 * h) / 3) {
                /* Horizontal Red/Green/Blue gradients */
                uint32_t r = (x * 255) / w;
                uint32_t g = ((y - h/3) * 255) / (h/3);
                buf[y * w + x] = (r << 16) | (g << 8) | 0x80;
            } else {
                /* High-contrast checkered grid */
                bool checker = ((x / 60) + (y / 60)) % 2 == 0;
                buf[y * w + x] = checker ? 0x00FFFFFF : 0x00101010;
            }
        }
    }

    printf("[test_dp] Unblanking DECON2...\n");
    int uret = ioctl(fb_fd, FBIOBLANK, FB_BLANK_UNBLANK);
    printf("[test_dp] FBIOBLANK unblank ret=%d\n", uret);

    printf("[test_dp] Streaming 1920x1080 test pattern on Window 3 (IDMA_VG0) for 15 seconds...\n");
    for (int frame = 0; frame < 450; frame++) { // ~15 seconds @ 30 FPS
        struct decon_win_config_data_dsu dsu;
        memset(&dsu, 0, sizeof(dsu));
        dsu.fence = -1;
        dsu.fd_odma = -1;

        for (int i = 0; i < MAX_DECON_WIN + 2; i++) {
            dsu.config[i].state = DECON_WIN_STATE_DISABLED;
            dsu.config[i].fence_fd = -1;
        }

        struct decon_win_config *win = &dsu.config[3];
        win->state = DECON_WIN_STATE_BUFFER;
        win->fd_idma[0] = dma_fd;
        win->fd_idma[1] = -1;
        win->fd_idma[2] = -1;
        win->fence_fd = -1;
        win->plane_alpha = 255;
        win->blending = DECON_BLENDING_NONE;
        win->idma_type = IDMA_VG0;
        win->format = DECON_PIXEL_FORMAT_XRGB_8888;
        win->src.x = 0; win->src.y = 0; win->src.w = w; win->src.h = h; win->src.f_w = w; win->src.f_h = h;
        win->dst.x = 0; win->dst.y = 0; win->dst.w = w; win->dst.h = h; win->dst.f_w = w; win->dst.f_h = h;

        int sret = ioctl(fb_fd, S3CFB_WIN_CONFIG_DSU, &dsu);
        if (frame == 0 || frame % 90 == 0) {
            printf("[test_dp] Frame %3d: WIN_CONFIG ret=%d, fence=%d, errno=%d (%s)\n",
                   frame, sret, dsu.fence, errno, strerror(errno));
        }
        if (dsu.fence >= 0) close(dsu.fence);
        usleep(33000);
    }

    printf("[test_dp] Test complete.\n");
    munmap(buf, frame_bytes);
    close(dma_fd);
    close(ion_fd);
    close(fb_fd);
    return 0;
}

