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

#define MAX_DECON_WIN   6
#define MAX_PLANE_CNT   3

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
            int reserved[16];
        };
    };
    struct decon_win_rect dst;
    bool protection;
    bool compression;
};

struct decon_win_config_data_dsu {
    int fence;
    int fd_odma;
    struct decon_win_config config[MAX_DECON_WIN + 2];
};

#define S3CFB_WIN_CONFIG_DSU _IOW('F', 209, struct decon_win_config_data_dsu)

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

int main(int argc, char **argv) {
    int target_fmt = (argc > 1) ? atoi(argv[1]) : 4;
    printf("Testing format %d (sizeof win_config=%zu, data_dsu=%zu)\n",
           target_fmt, sizeof(struct decon_win_config), sizeof(struct decon_win_config_data_dsu));

    int ion_fd = open("/dev/ion", O_RDWR);
    struct ion_allocation_data alloc = { 1920 * 1080 * 4, 4096, 1 << 0, 0, 0 };
    ioctl(ion_fd, ION_IOC_ALLOC, &alloc);
    struct ion_fd_data fd_data = { alloc.handle, 0 };
    ioctl(ion_fd, ION_IOC_SHARE, &fd_data);

    uint32_t *buf = mmap(NULL, 1920 * 1080 * 4, PROT_READ | PROT_WRITE, MAP_SHARED, fd_data.fd, 0);

    /* Fill 3 vertical stripes: RED (left), GREEN (middle), BLUE (right)
     * Stored as standard 0x00RRGGBB in uint32_t */
    for (int y = 0; y < 1080; y++) {
        for (int x = 0; x < 1920; x++) {
            if (x < 640)
                buf[y * 1920 + x] = 0x00FF0000; /* RED */
            else if (x < 1280)
                buf[y * 1920 + x] = 0x0000FF00; /* GREEN */
            else
                buf[y * 1920 + x] = 0x000000FF; /* BLUE */
        }
    }

    int fb_fd = open("/dev/graphics/fb2", O_RDWR);
    struct decon_win_config_data_dsu data;
    memset(&data, 0, sizeof(data));
    data.fence = -1;
    data.fd_odma = -1;
    for (int i = 0; i < 8; i++) {
        data.config[i].state = 0;
        data.config[i].fence_fd = -1;
    }

    struct decon_win_config *win = &data.config[3];
    win->state = 1;
    win->fd_idma[0] = fd_data.fd;
    win->fd_idma[1] = -1;
    win->fd_idma[2] = -1;
    win->fence_fd = -1;
    win->plane_alpha = 255;
    win->idma_type = 2; /* IDMA_VG0 */
    win->format = target_fmt;
    win->src.w = 1920; win->src.h = 1080; win->src.f_w = 1920; win->src.f_h = 1080;
    win->dst.w = 1920; win->dst.h = 1080;

    int ret = ioctl(fb_fd, S3CFB_WIN_CONFIG_DSU, &data);
    printf("format %d: ret=%d, errno=%d\n", target_fmt, ret, errno);
    if (data.fence >= 0) close(data.fence);

    return 0;
}
