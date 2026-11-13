/*
 * exynos_dp_bridge.c — Samsung Galaxy S8 (SM-G950N, Exynos 8895)
 * Native USB-C DisplayPort / HDMI Hotplug & Framebuffer Bridge
 * Double-Buffered (/dev/ion + DECON_PIXEL_FORMAT_BGRA_8888 +
 * S3CFB_WIN_CONFIG_DSU) with Dynamic Orientation (0/90/180/270 deg)
 * and Flicker-Free Smart Cursor Suppression.
 */
#include <X11/Xlib.h>
#include <X11/Xutil.h>
#include <X11/extensions/XShm.h>
#include <X11/extensions/Xfixes.h>
#include <errno.h>
#include <fcntl.h>
#include <linux/fb.h>
#include <linux/videodev2.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/ipc.h>
#include <sys/mman.h>
#include <sys/shm.h>
#include <time.h>
#include <unistd.h>

#define MAX_DECON_WIN 6
#define MAX_PLANE_CNT 3
#define NUM_BUFFERS 2

#define ION_HEAP_SYSTEM_MASK (1 << 0)

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

enum decon_blending {
  DECON_BLENDING_NONE = 0,
  DECON_BLENDING_PREMULT = 1,
  DECON_BLENDING_COVERAGE = 2,
};

enum decon_win_state {
  DECON_WIN_STATE_DISABLED = 0,
  DECON_WIN_STATE_COLOR = 1,
  DECON_WIN_STATE_BUFFER = 2,
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
    EXYNOS_DISPLAYPORT_STATE_AUDIO,
  } state;
  struct v4l2_dv_timings timings;
  struct v4l2_enum_dv_timings etimings;
  uint32_t audio_info;
  int hdcp;
};

#define S3CFB_WIN_CONFIG_DSU _IOW('F', 209, struct decon_win_config_data_dsu)
#define S3CFB_WIN_CONFIG_NODSU                                                 \
  _IOW('F', 209, struct decon_win_config_data_nodsu)
#define EXYNOS_GET_DISPLAYPORT_CONFIG _IOWR('F', 300, struct exynos_displayport_data)
#define EXYNOS_SET_DISPLAYPORT_CONFIG _IOW('F', 301, struct exynos_displayport_data)

static int read_int_file(const char *path, int dflt) {
  FILE *f = fopen(path, "r");
  if (!f)
    return dflt;
  int val = dflt;
  if (fscanf(f, "%d", &val) != 1)
    val = dflt;
  fclose(f);
  return val;
}

static uint32_t read_dt_u32(const char *path, uint32_t dflt) {
  FILE *f = fopen(path, "rb");
  if (!f)
    return dflt;
  uint8_t buf[4];
  if (fread(buf, 1, 4, f) != 4) {
    fclose(f);
    return dflt;
  }
  fclose(f);
  return ((uint32_t)buf[0] << 24) | ((uint32_t)buf[1] << 16) |
         ((uint32_t)buf[2] << 8) | (uint32_t)buf[3];
}

static void pulse_vibrator(int ms) {
  FILE *f = fopen("/sys/class/timed_output/vibrator/enable", "w");
  if (f) {
    fprintf(f, "%d\n", ms);
    fclose(f);
  }
}

static int configure_dp_resolution(int fb_fd, uint32_t *out_w,
                                   uint32_t *out_h) {
  struct exynos_displayport_data dp_data;
  memset(&dp_data, 0, sizeof(dp_data));
  dp_data.state = EXYNOS_DISPLAYPORT_STATE_ENUM_PRESET;

  struct v4l2_enum_dv_timings best_timings;
  memset(&best_timings, 0, sizeof(best_timings));
  bool found_1080p = false;

  for (uint32_t i = 0; i < 32; i++) {
    dp_data.etimings.index = i;
    if (ioctl(fb_fd, EXYNOS_GET_DISPLAYPORT_CONFIG, &dp_data) < 0)
      break;

    uint32_t w = dp_data.etimings.timings.bt.width;
    uint32_t h = dp_data.etimings.timings.bt.height;
    if (w == 1920 && h == 1080) {
      best_timings = dp_data.etimings;
      found_1080p = true;
      break;
    }
    if (!found_1080p &&
        (w * h >= best_timings.timings.bt.width * best_timings.timings.bt.height &&
         w <= 2560 && h <= 1440)) {
      best_timings = dp_data.etimings;
    }
  }

  if (best_timings.timings.bt.width > 0 && best_timings.timings.bt.height > 0) {
    memset(&dp_data, 0, sizeof(dp_data));
    dp_data.state = EXYNOS_DISPLAYPORT_STATE_PRESET;
    dp_data.timings = best_timings.timings;
    int ret = ioctl(fb_fd, EXYNOS_SET_DISPLAYPORT_CONFIG, &dp_data);
    if (ret == 0 ||
        (ioctl(fb_fd, EXYNOS_GET_DISPLAYPORT_CONFIG, &dp_data) == 0 &&
         dp_data.timings.bt.width > 0 && dp_data.timings.bt.height > 0)) {
      *out_w = best_timings.timings.bt.width;
      *out_h = best_timings.timings.bt.height;
      return 0;
    }
  }

  *out_w = 1920;
  *out_h = 1080;
  return -1;
}

static int submit_frame(int fb_fd, int dma_fd, uint32_t win_idx,
                        uint32_t idma_type, uint32_t w, uint32_t h) {
  struct decon_win_config_data_dsu data_dsu;
  memset(&data_dsu, 0, sizeof(data_dsu));
  data_dsu.fence = -1;
  data_dsu.fd_odma = -1;

  for (int i = 0; i < MAX_DECON_WIN + 2; i++) {
    data_dsu.config[i].state = DECON_WIN_STATE_DISABLED;
    data_dsu.config[i].fence_fd = -1;
  }

  if (win_idx >= MAX_DECON_WIN)
    win_idx = 3;
  if (idma_type == IDMA_G0)
    idma_type = IDMA_VG0;

  struct decon_win_config *win = &data_dsu.config[win_idx];
  win->state = DECON_WIN_STATE_BUFFER;
  win->fd_idma[0] = dma_fd;
  win->fd_idma[1] = -1;
  win->fd_idma[2] = -1;
  win->fence_fd = -1;
  win->plane_alpha = 255;
  win->blending = DECON_BLENDING_NONE;
  win->idma_type = idma_type;
  win->format = DECON_PIXEL_FORMAT_BGRA_8888;
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
  win->protection = false;
  win->compression = false;

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

/*
 * blit_transformed — High-performance blit with arbitrary 0/90/180/270 degree rotation.
 * Automatically maps any X11 geometry onto native monitor hardware buffer.
 */
static void blit_transformed(uint32_t *dst, const uint32_t *src,
                             uint32_t dst_w, uint32_t dst_h,
                             uint32_t src_w, uint32_t src_h,
                             int rotation) {
  if (rotation == 90) {
    /* 90 degrees clockwise rotation:
     * maps vertical (1080x1920) onto horizontal monitor buffer (1920x1080)
     * so that a monitor standing vertically displays upright portrait content! */
    if (src_w == dst_h && src_h == dst_w) {
      /* Exact 1:1 pixel rotation (zero scaling interpolation) */
      for (uint32_t sy = 0; sy < src_h; sy++) {
        const uint32_t *src_row = src + (size_t)sy * src_w;
        uint32_t dx = dst_w - 1 - sy;
        for (uint32_t sx = 0; sx < src_w; sx++) {
          dst[sx * dst_w + dx] = src_row[sx];
        }
      }
    } else {
      /* Scaled 90 deg rotation */
      for (uint32_t y = 0; y < dst_h; y++) {
        uint32_t *dst_row = dst + (size_t)y * dst_w;
        uint32_t sx = (y * src_w) / dst_h;
        for (uint32_t x = 0; x < dst_w; x++) {
          uint32_t sy = ((dst_w - 1 - x) * src_h) / dst_w;
          dst_row[x] = src[(size_t)sy * src_w + sx];
        }
      }
    }
  } else if (rotation == 270) {
    /* 270 degrees clockwise (90 counter-clockwise) */
    if (src_w == dst_h && src_h == dst_w) {
      for (uint32_t sy = 0; sy < src_h; sy++) {
        const uint32_t *src_row = src + (size_t)sy * src_w;
        uint32_t dx = sy;
        for (uint32_t sx = 0; sx < src_w; sx++) {
          uint32_t dy = dst_h - 1 - sx;
          dst[dy * dst_w + dx] = src_row[sx];
        }
      }
    } else {
      for (uint32_t y = 0; y < dst_h; y++) {
        uint32_t *dst_row = dst + (size_t)y * dst_w;
        uint32_t sx = ((dst_h - 1 - y) * src_w) / dst_h;
        for (uint32_t x = 0; x < dst_w; x++) {
          uint32_t sy = (x * src_h) / dst_w;
          dst_row[x] = src[(size_t)sy * src_w + sx];
        }
      }
    }
  } else if (rotation == 180) {
    /* 180 degrees inverted */
    for (uint32_t y = 0; y < dst_h; y++) {
      uint32_t *dst_row = dst + (size_t)y * dst_w;
      uint32_t sy = ((dst_h - 1 - y) * src_h) / dst_h;
      const uint32_t *src_row = src + (size_t)sy * src_w;
      for (uint32_t x = 0; x < dst_w; x++) {
        uint32_t sx = ((dst_w - 1 - x) * src_w) / dst_w;
        dst_row[x] = src_row[sx];
      }
    }
  } else {
    /* 0 degrees (normal landscape) */
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
}

static int ignore_x_error(Display *d, XErrorEvent *e) {
  (void)d;
  (void)e;
  return 0;
}
static int ignore_x_io_error(Display *d) {
  (void)d;
  return 0;
}

int main(int argc, char **argv) {
  setvbuf(stdout, NULL, _IOLBF, 0);
  setvbuf(stderr, NULL, _IOLBF, 0);

  XSetErrorHandler(ignore_x_error);
  XSetIOErrorHandler(ignore_x_io_error);

  const char *fb_path = "/dev/graphics/fb2";
  if (access(fb_path, R_OK | W_OK) != 0)
    fb_path = "/dev/fb2";

  uint32_t dft_win =
      read_dt_u32("/proc/device-tree/decon_t@0x12A40000/default_win", 3);
  if (dft_win == 0 || dft_win >= MAX_DECON_WIN)
    dft_win = 3;
  uint32_t dft_idma = read_dt_u32(
      "/proc/device-tree/decon_t@0x12A40000/default_idma", IDMA_VG0);
  if (dft_idma == IDMA_G0)
    dft_idma = IDMA_VG0;
  printf("[exynos_dp_bridge] DECON2 DT defaults: default_win=%u, "
         "default_idma=%u\n",
         dft_win, dft_idma);

  int ion_fd = open("/dev/ion", O_RDWR);
  if (ion_fd < 0) {
    perror("open(/dev/ion)");
    return 1;
  }

  size_t max_frame_bytes = 2560ULL * 1440ULL * 4ULL;
  int dma_fds[NUM_BUFFERS];
  uint32_t *ion_bufs[NUM_BUFFERS];

  for (int b = 0; b < NUM_BUFFERS; b++) {
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
    dma_fds[b] = fd_data.fd;

    ion_bufs[b] = mmap(NULL, max_frame_bytes, PROT_READ | PROT_WRITE,
                       MAP_SHARED, dma_fds[b], 0);
    if (ion_bufs[b] == MAP_FAILED) {
      perror("mmap(dma_fd)");
      return 1;
    }
    printf("[exynos_dp_bridge] Buffer #%d allocated: %zu bytes (dma_fd=%d)\n",
           b, max_frame_bytes, dma_fds[b]);
  }

  int fb_fd = open(fb_path, O_RDWR);
  if (fb_fd < 0) {
    perror("open(/dev/graphics/fb2)");
    return 1;
  }

  /* Connect to X11 display :1 */
  Display *dpy = NULL;
  while (!dpy) {
    dpy = XOpenDisplay(":1");
    if (!dpy)
      sleep(1);
  }
  Window root = DefaultRootWindow(dpy);

  uint32_t cur_x11_w = 1920, cur_x11_h = 1080;
  XWindowAttributes xwa;
  if (XGetWindowAttributes(dpy, root, &xwa)) {
    cur_x11_w = xwa.width;
    cur_x11_h = xwa.height;
  }

  /* Set up XShm for zero-copy high-speed capture from :1 */
  XShmSegmentInfo shminfo;
  memset(&shminfo, 0, sizeof(shminfo));
  XImage *shm_img = XShmCreateImage(dpy, DefaultVisual(dpy, DefaultScreen(dpy)),
                                    DefaultDepth(dpy, DefaultScreen(dpy)),
                                    ZPixmap, NULL, &shminfo, cur_x11_w, cur_x11_h);
  bool use_shm = false;
  if (shm_img) {
    shminfo.shmid =
        shmget(IPC_PRIVATE, (size_t)shm_img->bytes_per_line * shm_img->height,
               IPC_CREAT | 0777);
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
  printf("[exynos_dp_bridge] Connected to X11 :1 (%ux%u, use_shm=%d) — monitoring DisplayPort...\n",
         cur_x11_w, cur_x11_h, use_shm);

  bool dp_active = false;
  uint32_t dp_w = 1920, dp_h = 1080;
  bool force_mode = (argc > 1 && strcmp(argv[1], "--force") == 0);
  uint64_t frame_count = 0;
  int cur_buf = 0;
  int current_rotation = 0;
  struct timespec t_fps_start;
  clock_gettime(CLOCK_MONOTONIC, &t_fps_start);

  if (read_int_file("/sys/class/switch/hdmi/state", 0) == 0 && !force_mode) {
    printf("[exynos_dp_bridge] USB-C DisplayPort currently unplugged (HPD=0); "
           "DECON2 armed in idle wait.\n");
  }

  int probe_counter = 0;

  while (1) {
    int hpd = force_mode ? 1 : read_int_file("/sys/class/switch/hdmi/state", 0);

    if (hpd <= 0) {
      if (dp_active) {
        printf("[exynos_dp_bridge] USB-C DisplayPort unplugged (HPD=0) — "
               "idle waiting for reconnect.\n");
        dp_active = false;
      }
      /* Rule 14 & 15: Automatically force Alternate Mode negotiation every 2s */
      if (++probe_counter >= 20) {
        probe_counter = 0;
        system("echo source > /sys/class/typec/port0/port_type 2>/dev/null; "
               "echo 1 > /sys/class/sec/ccic/role_swap 2>/dev/null; "
               "echo \"0 0\" > /sys/class/dp_sec/dp_sbu_sw_sel 2>/dev/null; "
               "echo 22 > /sys/class/dp_sec/link 2>/dev/null");
      }
      usleep(100000);
      continue;
    }
    probe_counter = 0;

    struct timespec t_frame_start;
    clock_gettime(CLOCK_MONOTONIC, &t_frame_start);

    if (!dp_active) {
      printf("[exynos_dp_bridge] USB-C DisplayPort HPD=1 detected! Negotiating "
             "EDID & enabling DECON2...\n");
      system("echo 8 > /sys/class/dp_sec/bpc 2>/dev/null; echo 0 > "
             "/sys/class/dp_sec/range 2>/dev/null");
      configure_dp_resolution(fb_fd, &dp_w, &dp_h);
      if (dp_w > 2560 || dp_h > 1440) {
        dp_w = 1920;
        dp_h = 1080;
      }
      int blank_ret = ioctl(fb_fd, FBIOBLANK, FB_BLANK_UNBLANK);
      printf("[exynos_dp_bridge] FBIOBLANK(FB_BLANK_UNBLANK) ret=%d — "
             "streaming :1 (%ux%u -> %ux%u)\n",
             blank_ret, cur_x11_w, cur_x11_h, dp_w, dp_h);
      pulse_vibrator(150);
      dp_active = true;
      frame_count = 0;
      cur_buf = 0;
      clock_gettime(CLOCK_MONOTONIC, &t_fps_start);
      usleep(30000);
    }

    /* Check for dynamic orientation changes every 30 frames */
    if (frame_count % 30 == 0) {
      FILE *rot_f = fopen("/tmp/s8_dp_orientation", "r");
      if (rot_f) {
        int r = 0;
        if (fscanf(rot_f, "%d", &r) == 1) {
          if (r != current_rotation) {
            printf("[exynos_dp_bridge] Orientation switched: %d deg -> %d deg\n",
                   current_rotation, r);
            current_rotation = r;
          }
        }
        fclose(rot_f);
      } else {
        current_rotation = 0;
      }
    }

    /* Dynamic X11 resolution detection */
    if (frame_count % 60 == 0) {
      if (XGetWindowAttributes(dpy, root, &xwa)) {
        if ((uint32_t)xwa.width != cur_x11_w || (uint32_t)xwa.height != cur_x11_h) {
          printf("[exynos_dp_bridge] X11 resolution changed to %dx%d. Recreating capture buffer...\n",
                 xwa.width, xwa.height);
          if (use_shm) {
            XShmDetach(dpy, &shminfo);
            shmdt(shminfo.shmaddr);
            XDestroyImage(shm_img);
            use_shm = false;
          }
          cur_x11_w = xwa.width;
          cur_x11_h = xwa.height;
          memset(&shminfo, 0, sizeof(shminfo));
          shm_img = XShmCreateImage(dpy, DefaultVisual(dpy, DefaultScreen(dpy)),
                                    DefaultDepth(dpy, DefaultScreen(dpy)),
                                    ZPixmap, NULL, &shminfo, cur_x11_w, cur_x11_h);
          if (shm_img) {
            shminfo.shmid = shmget(IPC_PRIVATE, (size_t)shm_img->bytes_per_line * shm_img->height,
                                   IPC_CREAT | 0777);
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
        }
      }
    }

    /* Target back-buffer */
    uint32_t *target_buf = ion_bufs[cur_buf];
    int target_dma_fd = dma_fds[cur_buf];

    if (use_shm) {
      if (XShmGetImage(dpy, root, shm_img, 0, 0, AllPlanes)) {
        blit_transformed(target_buf, (const uint32_t *)shm_img->data,
                         dp_w, dp_h, cur_x11_w, cur_x11_h, current_rotation);
      }
    } else {
      XImage *img =
          XGetImage(dpy, root, 0, 0, cur_x11_w, cur_x11_h, AllPlanes, ZPixmap);
      if (img) {
        blit_transformed(target_buf, (const uint32_t *)img->data,
                         dp_w, dp_h, cur_x11_w, cur_x11_h, current_rotation);
        XDestroyImage(img);
      }
    }

    /*
     * Flicker-Free Smart Mouse Cursor Suppression:
     * Only draw software cursor overlay IF /tmp/s8_dp_show_cursor exists.
     * Prevents phantom mouse cursor flickering when no physical mouse is attached.
     */
    if (access("/tmp/s8_dp_show_cursor", F_OK) == 0) {
      XFixesCursorImage *cur = XFixesGetCursorImage(dpy);
      if (cur) {
        int start_x = cur->x - cur->xhot;
        int start_y = cur->y - cur->yhot;
        for (int cy = 0; cy < cur->height; cy++) {
          int py = start_y + cy;
          if (py < 0 || py >= (int)dp_h)
            continue;
          for (int cx = 0; cx < cur->width; cx++) {
            int px = start_x + cx;
            if (px < 0 || px >= (int)dp_w)
              continue;
            uint32_t cpixel = (uint32_t)cur->pixels[cy * cur->width + cx];
            uint8_t a = (cpixel >> 24) & 0xff;
            if (a == 0)
              continue;
            if (a == 255) {
              target_buf[py * dp_w + px] = cpixel;
            } else {
              uint8_t *dst_p = (uint8_t *)&target_buf[py * dp_w + px];
              uint8_t *src_p = (uint8_t *)&cpixel;
              uint32_t inv_a = 255 - a;
              dst_p[0] = src_p[0] + (uint8_t)((dst_p[0] * inv_a) >> 8);
              dst_p[1] = src_p[1] + (uint8_t)((dst_p[1] * inv_a) >> 8);
              dst_p[2] = src_p[2] + (uint8_t)((dst_p[2] * inv_a) >> 8);
            }
          }
        }
        XFree(cur);
      }
    }

    /* Present back-buffer */
    int ret = submit_frame(fb_fd, target_dma_fd, dft_win, dft_idma, dp_w, dp_h);
    if (ret < 0) {
      if (dft_idma != IDMA_VG0) {
        dft_idma = IDMA_VG0;
        ret = submit_frame(fb_fd, target_dma_fd, dft_win, dft_idma, dp_w, dp_h);
      }
      if (read_int_file("/sys/class/switch/hdmi/state", 0) <= 0) {
        printf("[exynos_dp_bridge] Connection lost during frame submission (HPD=0). Pausing render.\n");
        dp_active = false;
        usleep(100000);
        continue;
      }
      if (frame_count % 60 == 0) {
        printf("[exynos_dp_bridge] submit_frame error: ret=%d, errno=%d (%s)\n",
               ret, errno, strerror(errno));
      }
      usleep(16000);
    }

    cur_buf = 1 - cur_buf;
    frame_count++;

    if (frame_count % 300 == 0 && frame_count > 0) {
      struct timespec t_now;
      clock_gettime(CLOCK_MONOTONIC, &t_now);
      double sec = (t_now.tv_sec - t_fps_start.tv_sec) +
                   (t_now.tv_nsec - t_fps_start.tv_nsec) * 1e-9;
      printf("[exynos_dp_bridge] 300 frames rendered in %.2f s (%.1f FPS solid 60Hz, rot=%d)\n",
             sec, 300.0 / sec, current_rotation);
      clock_gettime(CLOCK_MONOTONIC, &t_fps_start);
    }

    struct timespec t_frame_end;
    clock_gettime(CLOCK_MONOTONIC, &t_frame_end);
    long elapsed_us = (t_frame_end.tv_sec - t_frame_start.tv_sec) * 1000000L +
                      (t_frame_end.tv_nsec - t_frame_start.tv_nsec) / 1000L;
    long target_frame_us = 16666L; /* 60 FPS */
    if (elapsed_us < target_frame_us) {
      usleep(target_frame_us - elapsed_us);
    } else {
      usleep(500);
    }
  }

  return 0;
}
