# Galaxy S8 Native Ubuntu 24.04 LTS, macOS GUI, `systemd`, Docker & 1-Click Odin Installer — Master Instructions for Gemini 3.8 High (`GEMINI.md`)

> [!IMPORTANT]
> **MANDATORY READING FOR GEMINI 3.8 HIGH / PRO / FLASH:**
> Do **NOT** guess, assume generic Linux/Android behavior, or hallucinate unverified hardware steps. Every rule, register address, partition size, driver quirk, and boot flow in this file has been **empirically verified on the live physical Samsung Galaxy S8 (`SM-G950N`, Serial `ce10171ab3e9620804`)**. Read Section 1 (Anti-Hallucination Rules) before running any command or writing any code.

---

## 0. Ultimate Project Goal
Transform the screenless Samsung Galaxy S8 (`SM-G950N`, Exynos 8895) into:
1. **The Ultimate Native Ubuntu 24.04.5 LTS (`Noble Numbat`, `glibc 2.39`) ARM64 Computer** running with **zero Android framework overhead (`>3.1 GB` of `3.48 GB` RAM free)**, full **`systemd`** service management, and **Docker Engine**.
2. **macOS Sonoma / Cupertino Desktop GUI:**
   * WhiteSur Dark/Light GTK & Window theme (traffic-light window buttons on left), macOS BigSur/Sonoma icons, translucent top global menu bar (Apple menu, clock, Wi-Fi, audio, battery %, CPU temp), centered bottom magnifying **Plank Dock**, and Spotlight launcher.
   * Accessible simultaneously over **Web Browser noVNC (`:6080`)**, **Native VNC (`:5901`)**, and **External USB-C Monitor / Type-C-to-HDMI Dongle (`/dev/graphics/fb2`)**.
3. **100% Native Hardware Utilization (Every Chip on the Motherboard):**
   * **Wi-Fi (`wlan0`):** Broadcom BCM4361 PCIe (`dhd` driver) auto-connected to **`<WIFI_SSID>`** (password: **`<WIFI_PASSWORD>`**, IP: **`192.168.0.227`**).
   * **USB-C DisplayPort 1.2 Video Out + USB Hub (`dp_sec` / `fb2` + `/dev/ion`):** Supports both direct Type-C monitors and Type-C-to-HDMI dongles up to `1080p@60` / `4K@60` via the Exynos `/dev/ion` $\rightarrow$ `S3CFB_WIN_CONFIG` bridge (`exynos_dp_bridge`), plus USB keyboards/mice/storage.
   * **Audio (`Exynos8895-Madera` / Cirrus Logic CS47L92 + `DP Audio`):** Internal bottom speaker (`MAX98506`), 3.5mm Hi-Fi headphone jack, microphones, and USB-C HDMI digital audio (`pcmC0D22p`).
   * **Bluetooth 5.0 (`BCM4361` UART `ttySAC1` + `rfkill0`):** BlueZ stack with `/vendor/firmware/bcm4361*.hcd`.
   * **GPU (`ARM Mali-G71 MP20` `/dev/mali0`) & Hardware Video Codec (`MFC` `/dev/video6..9`):** Hardware 3D/compute and V4L2 M2M H.264/HEVC encoding/decoding.
   * **Smart Battery & PMIC (`MAX77865`):** Direct I2C register programming (`4.3V` UVLO brownout fix + 80% server charge limiter).
   * **LEDs, Torch, Haptics, Bixby Key & Sensors:** Front RGBW LED (`led_r,g,b,w`) for blind status feedback, Rear Flash Torch (`torch-sec1`), Haptic Vibrator (`/sys/class/timed_output/vibrator`), programmable **Bixby Button** (`/dev/input/event*`), and onboard Sensor Hub (Barometer, Gyro, Accel, Compass, Optical Heart-Rate `hrm_sensor`).
4. **1-Click Odin Flashable Full Native Ubuntu Installer (`Ubuntu_24.04_GalaxyS8_Full_Odin.tar`):**
   * A single `USTAR` `.tar` file flashable in Odin's `AP` slot that installs the auto-booting kernel/ramdisk (`boot.img` on `sda7`) and pre-built Ubuntu 24.04.5 LTS image so **even a user with no screen can flash once in Odin and boot automatically into a working Ubuntu + `systemd` + macOS GUI + Wi-Fi + HDMI desktop with zero manual ADB setup**.

---

## 1. Ten Strict Anti-Hallucination Rules for Gemini 3.8 High

> [!CAUTION]
> **NEVER VIOLATE THESE 10 VERIFIED HARDWARE RULES:**

1. **NO INTERNAL SCREEN EXISTS (`lcdtype=-1`):**
   * The phone's internal OLED screen is **physically removed**.
   * **NEVER** instruct the user to look at the screen, check for a boot logo, read a warning prompt, or tap a dialog.
   * **ONLY** use: (a) exact second counts (e.g. "hold for 11 seconds"), (b) haptic vibrations, (c) front RGB LED colors, and (d) PC USB/network enumeration (`COM17` `PID_685D` for Download Mode; `adb devices` `ce10171ab3e9620804` for live OS; `192.168.0.227` for Wi-Fi).
2. **DO NOT HALLUCINATE DOWNLOAD MODE BUTTON COMBOS:**
   * **Verified 11-Second Plugged-In Method (`SM-G950N` Rev 5):**
     1. Keep the USB-C cable **plugged into the PC**.
     2. Hold **Volume Down + Bixby + Power** all together continuously for **11 seconds**.
     3. This forces the PMIC reset (~7s) and puts S-Boot **directly into active Odin Download Mode (`PID_685D` on `COM17`)** with **NO need to unplug the cable and NO need to press `Volume Up`**.
3. **DO NOT HALLUCINATE THAT `recovery.img` IS TOO BIG FOR `BOOT` (`sda7`):**
   * `recovery.img` inside `recovery_restore.tar` was `48,234,496` B (`46.0 MB`) ONLY because it had `7,714,816` B (`7.36 MB`) of trailing `0x00` zeroes from a raw `dd` partition dump.
   * The real image ends at byte **`40,519,680` (`38.64 MB`)**, which fits inside `BOOT` (`sda7`, `41,943,040` B = `40.00 MB`) with `1.36 MB` headroom (`boot_twrp_exact.tar`).
4. **DO NOT REPLACE ANDROID `/init` WITH A STANDALONE BUSYBOX `/init` ON `sda7`:**
   * On Exynos 8895, USB (`10c00000.dwc3`) only powers on when `adbd` opens `/dev/usb-ffs/adb/ep0` and sets `sys.usb.ffs.ready=1` via Android `/init`'s `/dev/socket/property_service` (`init.recovery.usb.rc`).
   * Replacing `/init` with a raw BusyBox script leaves USB completely dead.
   * **Correct Auto-Boot Architecture:** Keep `/init`, `ueventd`, and `adbd` intact in the `boot.img` ramdisk, and add an `on boot` service in `init.recovery.samsungexynos8895.rc` that runs `/data/linux/start_all.sh` automatically on boot!
5. **DO NOT HALLUCINATE THAT UBUNTU 24.04 LTS (`glibc 2.39`) CANNOT RUN ON `4.4.111`:**
   * Earlier segfaults on Ubuntu 22.04/24.04 were caused by Samsung's `CONFIG_SECURITY_DEFEX=y` kernel trap and `apt`'s `_apt` seccomp sandbox.
   * On our DEFEX-free `4.4.111` kernel (`boot_twrp_exact.tar`), syscalls `434` (`pidfd_open`), `435` (`clone3`), and `439` (`faccessat2`) cleanly return `-ENOSYS` (`-1`), and **Ubuntu 24.04.5 LTS (`glibc 2.39`, `apt 2.8.3`)** runs natively at full speed as long as `/etc/apt/apt.conf.d/99sandbox` contains:
     ```text
     APT::Sandbox::User "root";
     APT::Sandbox::Seccomp "false";
     ```
6. **DO NOT ASSUME STANDARD XORG `fbdev` ALONE DRIVES `/dev/graphics/fb2` (USB-C DISPLAYPORT):**
   * In `drivers/video/fbdev/exynos/dpu/decon_dsi.c` (line 942), `decon_pan_display()` returns early (`if (decon->dt.out_type != DECON_OUT_DSI) return 0;`).
   * In `decon_core.c` (line 720 & 3081), `decon_2` (`/dev/graphics/fb2`, `DECON_OUT_DP`) starts hardware scanout ONLY when userspace allocates an Exynos `/dev/ion` DMA-BUF (`fd_idma[0]`) and invokes `ioctl(fb2_fd, S3CFB_WIN_CONFIG, &win_data)`.
7. **DO NOT PASS FULL SUFFIXED FILENAMES TO `dhd` WI-FI PARAMETERS:**
   * The Broadcom `dhd` kernel module **automatically appends** `_b0` to `firmware_path` and `_r02j_b0` to `nvram_path`.
   * You MUST write:
     * `echo -n "/vendor/etc/wifi/bcmdhd_sta.bin" > /sys/module/dhd/parameters/firmware_path`
     * `echo -n "/vendor/etc/wifi/nvram.txt" > /sys/module/dhd/parameters/nvram_path`
     * `echo -n "/vendor/etc/wifi/bcmdhd_clm.blob" > /sys/module/dhd/parameters/clm_path`
8. **NEVER USE A2N KERNEL (`4.4.302`), STOCK `DEFEX` KERNEL, OR `CONFIG_KVM=y`:**
   * A2N kernel has a 3-minute charging killswitch (`[set_a2n_allow] a2n: bye bye!`).
   * Stock kernel has `CONFIG_SECURITY_DEFEX=y` (`safeplace violation` panic).
   * `CONFIG_KVM=y` panics S-Boot because EL2 is locked in TrustZone.
9. **NEVER MODIFY `/usr/sbin/runc` TO STRIP `maskedPaths`, `readonlyPaths`, OR `seccomp`:**
   * Writing scripts that strip OCI container security fields from `runc` triggers Gemini's automated safety filter and blocks your response.
   * Instead, run services natively in Ubuntu (`systemd` / `chroot` / `unshare`) or enable `CONFIG_PID_NS=y`, `CONFIG_IPC_NS=y`, `CONFIG_UTS_NS=y`, `CONFIG_CGROUP_DEVICE=y` in the kernel build.
10. **POWERSHELL + `adb shell` QUOTING RULE:**
    * Never nest `\"` inside `adb shell "..."` in Windows PowerShell—PowerShell strips inner quotes and breaks bash commands. Write scripts to `e:\rouf\galaxy-s8\scratch\<script>.sh` (converted to LF line endings), `adb push` to `/data/linux/`, and run via `adb shell "/sbin/sh /data/linux/<script>.sh"`.

---

## 2. Verified Hardware Map & Sysfs Control Reference

### A. Partition Layout (`/dev/block/platform/11120000.ufs/by-name/*`)
| Partition Name | Block Device | Exact Size | Purpose in Native Ubuntu Architecture |
| :--- | :--- | :--- | :--- |
| `BOOT` | `/dev/block/sda7` | `41,943,040` B (`40.00 MB`) | Primary boot image (`boot.img` inside `boot_twrp_exact.tar`, `38.64 MB`). |
| `RECOVERY` | `/dev/block/sda8` | `48,234,496` B (`46.00 MB`) | Rescue environment (`recovery.img` inside `recovery_restore.tar`). |
| `EFS` | `/dev/block/sda3` | `20,971,520` B (`20.00 MB`) | **PROTECTED** (IMEI + Wi-Fi MAC `/efs/wifi/.mac.info`). Mount `-o ro` only! |
| `SYSTEM` | `/dev/block/sda17` | `4,508,876,800` B (`4.20 GB`) | Mounted `-o ro` at `/system_root` for `/vendor/etc/wifi/*` and `/vendor/firmware/*` blobs. |
| `CACHE` | `/dev/block/sda18` | `314,572,800` B (`300.00 MB`) | Available for Odin flashable bootstrap/installer payload (`cache.img`). |
| `USERDATA` | `/dev/block/sda24` | `58,858,668,032` B (`54.82 GB`) | Unencrypted ext4 (`/data`). Hosts `/data/linux/rootfs.img` (Ubuntu 24.04.5 LTS) and `/data/linux/start_all.sh`. |

### B. MAX77865 PMIC Smart Battery Charger (`/sys/class/power_supply/max77865-charger/data`)
When running heavy CPU + Wi-Fi loads on a 500 mA USB port, VBUS can dip to ~4.4V and latch `CHGIN_UVLO` (`Health: Under voltage`). Always run at boot:
```sh
echo "0xBD 0x6C" > /sys/class/power_supply/max77865-charger/data  # Unlock CHGPROT
echo "0xC3 0x61" > /sys/class/power_supply/max77865-charger/data  # Set VCHGIN_REG UVLO to 4.3V + DISSKIP
echo "0xB7 0x05" > /sys/class/power_supply/max77865-charger/data  # MODE_BUCK | MODE_CHGR (Watchdog OFF)
echo 1200 > /sys/class/power_supply/battery/batt_tune_input_charge_current
echo 1800 > /sys/class/power_supply/battery/batt_tune_fast_charge_current
```

### C. Blind Status Indicators (RGBW LED, Torch & Haptics)
Since the phone has no internal OLED screen, use the front RGB LED and haptic motor to signal boot and network status to the user:
* **Front RGBW LED (`/sys/class/leds/led_{r,g,b,w}/brightness`, `0`..`255`):**
  * **Booting / Connecting Wi-Fi:** Blue (`echo 255 > /sys/class/leds/led_b/brightness`)
  * **Ubuntu + Wi-Fi + GUI Ready:** Green (`echo 0 > /sys/class/leds/led_b/brightness; echo 80 > /sys/class/leds/led_g/brightness`)
  * **Error / Low Battery Alert:** Red (`echo 255 > /sys/class/leds/led_r/brightness`)
* **Haptic Motor (`/sys/class/timed_output/vibrator/enable`):**
  * `echo 150 > /sys/class/timed_output/vibrator/enable` (150ms tactile pulse when desktop is ready).
* **Rear Flashlight / Torch (`/sys/class/leds/torch-sec1/brightness`):**
  * Write `1`..`5` to turn on rear LED torch; `0` to turn off.

---

## 3. Running `systemd` & Full Native Ubuntu Services

To provide full `systemd` (`systemctl`, `/run/systemd/system`, service units) inside Ubuntu 24.04.5 LTS while keeping the Exynos USB gadget (`10c00000.dwc3`) and `/vendor` firmware mounts alive:
1. The outer ramdisk (`boot.img`) initializes `/dev`, `/sys`, USB (`adbd`), `/system_root`, `/efs`, MAX77865 charging, and `wlan0` (`<WIFI_SSID>`).
2. It mounts `/data/linux/rootfs.img` at `/mnt/ubuntu` and launches Ubuntu's `/lib/systemd/systemd` inside a dedicated PID & mount namespace (`unshare --pid --fork --mount-proc chroot /mnt/ubuntu /lib/systemd/systemd`) OR runs our native service supervisor (`start_all.sh`) that automatically starts:
   * `dbus-daemon --system`
   * `sshd` (`port 22`, user `root`, password `ubuntu`)
   * `Xtigervnc :1` (`1920x1080`, 24-bit, password `ubuntu`) + **macOS Sonoma Desktop** (`xfce4-session` + `plank` dock + `WhiteSur` theme)
   * `websockify` (`port 6080` $\rightarrow$ `localhost:5901` noVNC Web Desktop)
   * `exynos_dp_bridge` (`/dev/ion` $\rightarrow$ `/dev/graphics/fb2` USB-C DisplayPort / HDMI output)
   * `dockerd`

---

## 4. How to Build the 1-Click Odin Flashable Package (`Ubuntu_24.04_GalaxyS8_Full_Odin.tar`)

To create a single `.tar` file that any screenless Galaxy S8 user can flash in Odin (`AP` slot) with zero post-flash terminal steps:
1. **Unpack `boot_twrp_exact.img`** (`40,519,680` B) ramdisk (LZMA) and append an `init.recovery.samsungexynos8895.rc` trigger:
   ```rc
   on property:sys.usb.ffs.ready=1
       start ubuntu_boot

   service ubuntu_boot /sbin/sh /data/linux/start_all.sh
       user root
       group root
       oneshot
       seclabel u:r:recovery:s0
   ```
2. **Repack `boot.img`** (`<= 41,943,040` B, preserving Samsung header `SRPPK29D005KU`, `second_addr=0x10f00000`, `dtb_addr=0x12000154`).
3. **Package `boot.img` + `recovery.img` (+ optional sparse `userdata.img` / `cache.img`)** using `tarfile.USTAR_FORMAT`:
   ```python
   import tarfile
   with tarfile.open("Ubuntu_24.04_GalaxyS8_Full_Odin.tar", "w", format=tarfile.USTAR_FORMAT) as t:
       t.add("boot.img", arcname="boot.img")
       t.add("recovery.img", arcname="recovery.img")
   ```
4. Once flashed via Odin, every time the phone powers on, it automatically connects to Wi-Fi (`<WIFI_SSID>`), starts SSH, launches the macOS Desktop on Web VNC (`:6080`) and USB-C HDMI (`fb2`), pulses the haptic motor twice, and lights the front RGB LED **Green**.
