#include <stdio.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/ioctl.h>
#include <linux/fb.h>
#include <stdint.h>
#include <time.h>

int main() {
    int fd = open("/dev/graphics/fb2", O_RDWR);
    if (fd < 0) {
        perror("open /dev/graphics/fb2");
        return 1;
    }
    printf("Successfully opened /dev/graphics/fb2 (fd=%d)\n", fd);
    
    for (int i = 0; i < 5; i++) {
        struct timespec ts1, ts2;
        clock_gettime(CLOCK_MONOTONIC, &ts1);
        uint32_t crtc = 0;
        int ret = ioctl(fd, FBIO_WAITFORVSYNC, &crtc);
        clock_gettime(CLOCK_MONOTONIC, &ts2);
        long elapsed_us = (ts2.tv_sec - ts1.tv_sec) * 1000000 + (ts2.tv_nsec - ts1.tv_nsec) / 1000;
        printf("VSYNC #%d: ret=%d, elapsed=%ld us (%.2f Hz)\n", i, ret, elapsed_us, 1000000.0 / elapsed_us);
    }
    close(fd);
    return 0;
}

