---
name: galaxy-s8-native-linux
description: Comprehensive operational runbook for building custom kernels, repacking auto-booting boot images, managing the GNOME 46 macOS Sonoma desktop, and operating USB-C DisplayPort on the headless Samsung Galaxy S8 (Exynos SM-G950N).
---

# Samsung Galaxy S8 (`SM-G950N`) Native Ubuntu 24.04.5 LTS Runbook

> [!CRITICAL]
> **HEADLESS HARDWARE REMINDER (`lcdtype=-1`):**
> Both the internal OLED screen and the front RGB status LED are physically removed.
> Use only: (1) Haptic Vibrations (`/sys/class/timed_output/vibrator/enable`), (2) Rear Torch (`/sys/class/leds/torch-sec1/brightness`), (3) exact second counts (11s for Download Mode), and (4) ADB (`ce10171ab3e9620804`) / Wi-Fi (`192.168.0.227`).

---

## 1. Quick Recovery / Service Verification Commands

### Check Live Status (USB or Wi-Fi)
```powershell
adb forward tcp:6080 tcp:6080
adb forward tcp:5901 tcp:5901
adb shell "chroot /mnt/ubuntu /usr/local/bin/s8ctl status"
```
* **Web VNC (Browser):** `http://localhost:6080/vnc.html` or `http://192.168.0.227:6080/vnc.html` (Password: `ubuntu`)
* **TigerVNC (`:5901`):** `localhost:5901` or `192.168.0.227:5901` (Password: `ubuntu`)
* **SSH (`:22`):** `ssh root@192.168.0.227` (Password: `ubuntu`)

### Manually Restart All Services or Desktop
```powershell
adb shell "/sbin/sh /data/linux/start_all.sh"
adb shell "chroot /mnt/ubuntu /usr/local/bin/start_gnome_macos.sh"
```

---

## 2. Critical Hardware Guards (Always Active in `/data/linux/start_all.sh`)

1. **V4L2 Camera ISP Kernel Panic Guard (`fimc_is_ixs_video_querycap`):**
   ```sh
   rm -f /dev/video[1-9][0-9]* /dev/v4l-subdev*
   ```
   Prevents GStreamer (`gst-plugin-scanner`), `nautilus`, and `webkit` from probing uninitialized Samsung camera ISP nodes (`/dev/video100+`), which otherwise triggers a NULL-pointer dereference kernel panic in `fimc_is_ixs_video_querycap+0x24/0x68`. Leaves `/dev/video6..9` (Exynos MFC hardware H.264/HEVC codecs) intact.
2. **MAX77865 PMIC `1,500 mA` Fast-Charge & Brownout Unlock:**
   ```sh
   echo "0xBD 0x6C" > /sys/class/power_supply/max77865-charger/data  # Unlock CHGPROT
   echo "0xC3 0x61" > /sys/class/power_supply/max77865-charger/data  # UVLO = 4.3V + DISSKIP
   echo "0xC0 0x3C" > /sys/class/power_supply/max77865-charger/data  # CHG_CNFG_09 = 1500mA input limit
   echo "0xB9 0x9E" > /sys/class/power_supply/max77865-charger/data  # CHG_CNFG_02 = 1500mA fast charge
   echo "0xB7 0x05" > /sys/class/power_supply/max77865-charger/data  # MODE_BUCK | MODE_CHGR
   ```
3. **USB-C DisplayPort / HDMI Hotplug Bridge (`exynos_dp_bridge`):**
   * Source: `e:\rouf\galaxy-s8\scratch\exynos_dp_bridge.c`
   * Binary: `/mnt/ubuntu/usr/local/bin/exynos_dp_bridge`
   * Keeps `/dev/graphics/fb2` (`DECON2`) in `FB_BLANK_POWERDOWN` while `/sys/class/switch/hdmi/state == 0` (never submit frames when `state == 0` or `DECON2` VSYNC timeout will panic the kernel!).
   * When `/sys/class/switch/hdmi/state == 1`, negotiates EDID via `EXYNOS_GET_DISPLAYPORT_CONFIG` / `EXYNOS_SET_DISPLAYPORT_CONFIG`, calls `FBIOBLANK(FB_BLANK_UNBLANK)` to trigger `decon_enable` $\rightarrow$ `displayport_enable`, pulses the vibrator (`150ms`), and streams `:1` via `S3CFB_WIN_CONFIG` at 30 FPS.

---

## 3. Rebuilding Auto-Boot `boot.img` & 1-Click Odin Installer

Run [`e:\rouf\galaxy-s8\scratch\build_autoboot_and_odin.py`](file:///e:/rouf/galaxy-s8/scratch/build_autoboot_and_odin.py):
```powershell
python e:\rouf\galaxy-s8\scratch\build_autoboot_and_odin.py
```
* Outputs:
  * `e:\rouf\galaxy-s8\scratch\boot_ubuntu_autoboot.img` (`40,521,744` B `<= 41,943,040` B `sda7` limit)
  * `e:\rouf\galaxy-s8\Ubuntu_24.04_GalaxyS8_Full_Odin.tar` (`88,760,320` B USTAR archive for Odin `AP` slot)
* Flash live via ADB without Odin:
  ```powershell
  adb push e:\rouf\galaxy-s8\scratch\boot_ubuntu_autoboot.img /tmp/boot.img
  adb shell "dd if=/tmp/boot.img of=/dev/block/sda7 bs=4096 conv=fsync && rm /tmp/boot.img && sync"
  ```
