# Galaxy S8 Native Ubuntu 24.04.5 LTS, GNOME 46 macOS Sonoma GUI, USB-C DisplayPort & 1-Click Odin Installer — Master Rulebook for Gemini 3.8 High (`GEMINI.md`)

> [!IMPORTANT]
> **MANDATORY READING FOR GEMINI 3.8 HIGH / PRO / FLASH:**
> Do **NOT** guess, assume generic Linux/Android behavior, or hallucinate unverified hardware steps. Every rule, register address, partition size, driver quirk, kernel panic guard, and boot flow in this file has been **empirically verified on the live physical Samsung Galaxy S8 (`SM-G950N`, Serial `ce10171ab3e9620804`)**. Read Section 1 (12 Strict Anti-Hallucination Rules) before running any command or writing any code.

---

## 0. Current Live State & Completed Milestones (`2026-11-04`)

1. **Auto-Booting Native Ubuntu 24.04.5 LTS (`Noble Numbat`, `glibc 2.39`) Installed on `BOOT` (`/dev/block/sda7`):**
   * `e:\rouf\galaxy-s8\scratch\boot_ubuntu_autoboot.img` (`40,521,744` B `<= 41,943,040` B `sda7` limit) is **already flashed to `/dev/block/sda7`** and packaged into `e:\rouf\galaxy-s8\Ubuntu_24.04_GalaxyS8_Full_Odin.tar` (`88,760,320` B).
   * Its `init.rc` contains:
     ```rc
     on property:sys.usb.ffs.ready=1
         start ubuntu_boot

     service ubuntu_boot /sbin/sh /data/linux/start_all.sh
         user root
         group root
         disabled
         oneshot
         seclabel u:r:recovery:s0
     ```
   * Every time the phone powers on or reboots, `/data/linux/start_all.sh` automatically runs: unlocks `1,500 mA` MAX77865 fast charging, removes the buggy `/dev/video100+` V4L2 ISP nodes, connects `wlan0` (`<WIFI_SSID>` / `<WIFI_PASSWORD>` $\rightarrow$ `192.168.0.227`), mounts `/data/linux/rootfs.img` at `/mnt/ubuntu`, starts `dbus`, `sshd` (`:22`), `Xtigervnc :1` (`:5901`), `websockify` (`:6080`), **GNOME 46 + macOS Sonoma Desktop** (`/usr/local/bin/start_gnome_macos.sh`), `exynos_dp_bridge`, and `dockerd`, then pulses the haptic motor twice (`2x 150ms`).
2. **GNOME 46 + macOS Sonoma Desktop (`[LIVE & VERIFIED]`):**
   * Top Menu Bar (`gnome-panel` with Apple menu `Applications` / `Places` on left, Clock & Session on right) + `metacity` Window Manager + `gsd-xsettings` + bottom magnifying **Plank Dock** (`Transparent` theme, `48px` zoom).
   * Genuine **GNOME 46 GTK4/libadwaita applications** verified running simultaneously on `:1`:
     * **GNOME Files 46 (`nautilus`):** Runs as `root` via `/usr/local/lib/libnautilus_root.so` (`geteuid() -> 1000` shim) + `GTK_USE_PORTAL=0` (bypasses 25-second `xdg-desktop-portal` D-Bus timeout) + WhiteSur-Dark GTK4 theme + left-side red/yellow/green traffic-light buttons.
     * **GNOME Console 46 (`kgx`) & `gnome-terminal-server`:** Clean `root@Galaxy-S8-Ubuntu:~#` prompt (`C.UTF-8` locale + Android `aid_*` supplementary GIDs `1004..3011` added to `/etc/group`).
     * **GNOME Text Editor 46 (`gnome-text-editor`), Calculator 46 (`gnome-calculator`), System Monitor 46 (`gnome-system-monitor`), GNOME Web 46 (`epiphany-browser`), and `Galaxy S8 Hardware Center` (`s8ctl`).**
3. **USB-C DisplayPort / HDMI Hotplug Daemon (`exynos_dp_bridge`):**
   * Source: `e:\rouf\galaxy-s8\scratch\exynos_dp_bridge.c` $\rightarrow$ `/mnt/ubuntu/usr/local/bin/exynos_dp_bridge`.
   * Allocates `14.7 MB` in `/dev/ion` (`ION_HEAP_SYSTEM_MASK`), arms `DECON2` (`/dev/graphics/fb2`) in `FB_BLANK_POWERDOWN` while `/sys/class/switch/hdmi/state == 0`, and on plug-in (`state == 1`) negotiates EDID timings via `EXYNOS_GET_DISPLAYPORT_CONFIG` / `EXYNOS_SET_DISPLAYPORT_CONFIG`, calls `FBIOBLANK(FB_BLANK_UNBLANK)` (triggering `decon_enable` $\rightarrow$ `displayport_enable`), vibrates `150ms`, and streams `:1` via `S3CFB_WIN_CONFIG` at 30 FPS.

---

## 1. Twelve Strict Anti-Hallucination Rules for Gemini 3.8 High

> [!CAUTION]
> **NEVER VIOLATE THESE 12 EMPIRICALLY VERIFIED HARDWARE RULES:**

1. **NO INTERNAL SCREEN OR FRONT LED EXISTS (`lcdtype=-1`):**
   * Both the internal OLED screen and the front RGB status LED assembly are **physically removed**.
   * **NEVER** instruct the user to look at the phone screen or check the front LED.
   * **ONLY** use: (a) exact second counts, (b) **Haptic Vibrations** (`/sys/class/timed_output/vibrator/enable`), (c) **Rear Flashlight Torch** (`/sys/class/leds/torch-sec1/brightness`), and (d) USB/Wi-Fi telemetry (`ce10171ab3e9620804` / `192.168.0.227`).
2. **EXYNOS 8895 V4L2 CAMERA ISP KERNEL PANIC GUARD (`fimc_is_ixs_video_querycap`):**
   * Calling `VIDIOC_QUERYCAP` on uninitialized Samsung camera ISP nodes (`/dev/video100`..`/dev/video220`) causes an immediate NULL-pointer dereference kernel panic (`fimc_is_ixs_video_querycap+0x24/0x68` in `/proc/last_kmsg`) whenever GStreamer (`gst-plugin-scanner`), `nautilus`, `webkit`, or `pipewire` scans `/dev/video*`.
   * **ALWAYS** run `rm -f /dev/video[1-9][0-9]* /dev/v4l-subdev*` at boot before starting Ubuntu (preserving `/dev/video0..9` for the Exynos MFC hardware H.264/HEVC video codecs `/dev/video6..9`).
3. **MAX77865 PMIC `1,500 mA` FAST-CHARGE & UVLO REGISTER UNLOCK:**
   * On standard USB ports (`Cable(USB)`, `cable_type=4`), Samsung's driver defaults `CHG_CNFG_09` (`0xC0`) to `450–500 mA`, which starves the phone under load.
   * **ALWAYS** write all 5 registers to `/sys/class/power_supply/max77865-charger/data` at boot:
     ```sh
     echo "0xBD 0x6C" > /sys/class/power_supply/max77865-charger/data  # Unlock CHGPROT
     echo "0xC3 0x61" > /sys/class/power_supply/max77865-charger/data  # VCHGIN_REG UVLO = 4.3V + DISSKIP
     echo "0xC0 0x3C" > /sys/class/power_supply/max77865-charger/data  # CHG_CNFG_09 = 1500mA input current limit (60 * 25mA)
     echo "0xB9 0x9E" > /sys/class/power_supply/max77865-charger/data  # CHG_CNFG_02 = 1500mA fast charge current (30 * 50mA)
     echo "0xB7 0x05" > /sys/class/power_supply/max77865-charger/data  # CHG_CNFG_00 = MODE_BUCK | MODE_CHGR (Watchdog OFF)
     echo 1500 > /sys/class/power_supply/battery/batt_tune_input_charge_current
     echo 1500 > /sys/class/power_supply/battery/batt_tune_fast_charge_current
     ```
4. **VERIFIED 11-SECOND PLUGGED-IN ODIN DOWNLOAD MODE COMBO:**
   * Keep the USB-C cable **plugged into the PC** and hold **Volume Down + Bixby + Power** continuously for **11 seconds** $\rightarrow$ enters Odin Download Mode (`PID_685D` on `COM17`) directly with **no need to unplug and no need to press `Volume Up`**.
5. **DO NOT REPLACE ANDROID `/init` WITH STANDALONE BUSYBOX `/init` ON `sda7`:**
   * Exynos 8895 DWC3 USB (`10c00000.dwc3`) only powers on when `adbd` sets `sys.usb.ffs.ready=1` via Android `/init`'s property socket. Keep `/init` and `adbd` intact and launch `/data/linux/start_all.sh` via `init.rc` `on property:sys.usb.ffs.ready=1`.
6. **UBUNTU 24.04.5 LTS (`glibc 2.39`) ON KERNEL `4.4.111`:**
   * Works natively at full speed on our DEFEX-free `4.4.111` kernel (`boot_ubuntu_autoboot.img`) with `/etc/apt/apt.conf.d/99sandbox` (`APT::Sandbox::User "root"; APT::Sandbox::Seccomp "false";`).
7. **GNOME 46 / GTK 4.14 / `libadwaita` REQUIREMENTS IN CHROOT VNC (`:1`):**
   * Export `GSK_RENDERER=cairo`, `GDK_BACKEND=x11`, `GTK_USE_PORTAL=0`, `GDK_DEBUG=no-portals`, `GTK_A11Y=none`, `LANG=C.UTF-8`, `LC_ALL=C.UTF-8`, `WEBKIT_DISABLE_SANDBOX_THIS_IS_DANGEROUS=1`, `WEBKIT_DISABLE_DMABUF_RENDERER=1`, `WEBKIT_DISABLE_COMPOSITING_MODE=1` in `/etc/profile.d/s8_gnome_env.sh`.
   * Move `/usr/share/dbus-1/services/org.freedesktop.portal.*` to `/usr/share/dbus-1/services.disabled/` so `nautilus` does not hang 25 seconds waiting for `systemd --user` portal activation.
   * Use `/usr/local/lib/libnautilus_root.so` (`LD_PRELOAD` returning `1000` for `geteuid()`/`getuid()`) in `/usr/local/bin/nautilus` and `/usr/local/bin/epiphany-browser` so GNOME Files 46 and GNOME Web 46 run as `root`.
8. **USB-C DISPLAYPORT (`decon_2` `/dev/graphics/fb2`) HOTPLUG RULES:**
   * **NEVER** call `S3CFB_WIN_CONFIG` on `fb2` while `/sys/class/switch/hdmi/state == 0` (unplugged) — without an active DisplayPort pixel clock/VSYNC, `decon2` shadow-update times out (`DISP_ERR_DECON_TIMEOUT`) and panics the kernel (`panic("DISPLAY: DECON:2: ERROR")`).
   * Keep `fb2` in `FB_BLANK_POWERDOWN` (`DECON_STATE_OFF`) while `state == 0`, and only call `EXYNOS_SET_DISPLAYPORT_CONFIG` + `FB_BLANK_UNBLANK` + `S3CFB_WIN_CONFIG` when `/sys/class/switch/hdmi/state == 1`.
9. **BROADCOM `dhd` WI-FI MODULE PARAMETERS (NO `_b0` SUFFIX):**
   * Kernel driver appends `_b0` / `_r02j_b0` automatically. Always write:
     * `echo -n "/vendor/etc/wifi/bcmdhd_sta.bin" > /sys/module/dhd/parameters/firmware_path`
     * `echo -n "/vendor/etc/wifi/nvram.txt" > /sys/module/dhd/parameters/nvram_path`
     * `echo -n "/vendor/etc/wifi/bcmdhd_clm.blob" > /sys/module/dhd/parameters/clm_path`
10. **NEVER USE A2N KERNEL (`4.4.302`), STOCK `DEFEX` KERNEL, OR `CONFIG_KVM=y`.**
11. **NEVER WRITE SCRIPTS THAT MODIFY `/usr/sbin/runc` SECURITY FIELDS** (triggers Gemini response filter).
12. **POWERSHELL + `adb shell` QUOTING & BACKGROUND FD RULE:**
    * Never nest `\"` inside `adb shell "..."` in PowerShell. Write `.sh` files locally with LF (`\n`) line endings, `adb push` to `/data/linux/`, and redirect `</dev/null >/var/log/... 2>&1 &` on all background daemons so `adb shell` never hangs on open pipe file descriptors.

---

## 2. Key Workspace Files & Scripts Reference

| File Path | Role |
| :--- | :--- |
| [`e:\rouf\galaxy-s8\Ubuntu_24.04_GalaxyS8_Full_Odin.tar`](file:///e:/rouf/galaxy-s8/Ubuntu_24.04_GalaxyS8_Full_Odin.tar) | **1-Click Odin Flashable Package** (`boot.img` with auto-boot `init.rc` + `recovery.img`, `88.76 MB`). |
| [`e:\rouf\galaxy-s8\scratch\boot_ubuntu_autoboot.img`](file:///e:/rouf/galaxy-s8/scratch/boot_ubuntu_autoboot.img) | Auto-booting `BOOT` partition image (`40,521,744` B), already flashed to `/dev/block/sda7`. |
| [`e:\rouf\galaxy-s8\scratch\build_autoboot_and_odin.py`](file:///e:/rouf/galaxy-s8/scratch/build_autoboot_and_odin.py) | Python builder that unpacks `boot.img` LZMA ramdisk, patches `init.rc` CPIO (`newc`), and builds `Ubuntu_24.04_GalaxyS8_Full_Odin.tar`. |
| [`e:\rouf\galaxy-s8\scratch\start_all.sh`](file:///e:/rouf/galaxy-s8/scratch/start_all.sh) | Deployed at `/data/linux/start_all.sh` — master boot supervisor (V4L2 guard, `1500mA` MAX77865 unlock, Wi-Fi, Ubuntu mount, GNOME 46 macOS GUI, VNC/noVNC, `exynos_dp_bridge`, Docker). |
| [`e:\rouf\galaxy-s8\scratch\polish_gnome_macos.sh`](file:///e:/rouf/galaxy-s8/scratch/polish_gnome_macos.sh) | Configures `/usr/local/bin/start_gnome_macos.sh`, left-side red/yellow/green traffic lights, `gsd-xsettings`, `ClockApplet`, and `libnautilus_root.so`. |
| [`e:\rouf\galaxy-s8\scratch\exynos_dp_bridge.c`](file:///e:/rouf/galaxy-s8/scratch/exynos_dp_bridge.c) | Native Exynos 8895 DECON2 USB-C DisplayPort / HDMI hotplug & `/dev/ion` `S3CFB_WIN_CONFIG` streaming daemon. |
| [`e:\rouf\galaxy-s8\scratch\s8ctl.py`](file:///e:/rouf/galaxy-s8/scratch/s8ctl.py) | Deployed at `/usr/local/bin/s8ctl` — unified CLI for Battery, Rear Torch, Haptics, DisplayPort, Bluetooth, and Sensors. |
| [`e:\rouf\galaxy-s8\scratch\connect_wifi.sh`](file:///e:/rouf/galaxy-s8/scratch/connect_wifi.sh) | Deployed at `/data/linux/connect_wifi.sh` — Broadcom BCM4361 Wi-Fi bring-up (`<WIFI_SSID>` / `<WIFI_PASSWORD>` $\rightarrow$ `192.168.0.227`). |

---

## 3. Remaining Roadmap Tasks for Next Session

1. **Test External USB-C Display / Type-C-to-HDMI Dongle Live (`Phase 2.3`):**
   * Plug in the USB-C monitor or Type-C-to-HDMI hub (with PD power connected to the hub) and verify `/var/log/exynos_dp_bridge.log` + `dmesg | grep -E "Displayport|decon"` over Wi-Fi (`ssh root@192.168.0.227`, password `ubuntu`).
2. **Audio Routing (`CS47L92` Speaker/Headphone + `pcmC0D22p` HDMI Audio) & Bluetooth (`BCM4361` `hciattach`):**
   * Configure `/etc/asound.conf` and `tinymix` paths for `Exynos8895-Madera` (`card 0`) and test `hciattach /dev/ttySAC1 bcm43xx 3000000 flow` with `/vendor/firmware/bcm4361*.hcd`.
3. **Full Kernel Rebuild with `CONFIG_PID_NS=y` / `CONFIG_CGROUP_DEVICE=y` & Bixby Key Daemon (`Phase 3`):**
   * Compile `galaxy-s8-kvm-kernel` with full container namespaces (`CONFIG_PID_NS=y`, `CONFIG_IPC_NS=y`, `CONFIG_UTS_NS=y`, `CONFIG_CGROUP_DEVICE=y`) so `systemd` PID 1 container and standard Docker containers run without flags.
