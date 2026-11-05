#include <stdio.h>
#include <time.h>
#include <X11/Xlib.h>

int main() {
    Display *dpy = XOpenDisplay(":1");
    if (!dpy) return 1;
    Window root = DefaultRootWindow(dpy);
    
    for (int i = 0; i < 5; i++) {
        struct timespec ts1, ts2;
        clock_gettime(CLOCK_MONOTONIC, &ts1);
        XImage *img = XGetImage(dpy, root, 0, 0, 1920, 1080, AllPlanes, ZPixmap);
        clock_gettime(CLOCK_MONOTONIC, &ts2);
        long elapsed_us = (ts2.tv_sec - ts1.tv_sec) * 1000000 + (ts2.tv_nsec - ts1.tv_nsec) / 1000;
        printf("XGetImage #%d: elapsed=%ld us (%.2f ms)\n", i, elapsed_us, elapsed_us / 1000.0);
        if (img) XDestroyImage(img);
    }
    XCloseDisplay(dpy);
    return 0;
}

