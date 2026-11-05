# Samsung Galaxy S8 Native Ubuntu 24.04.5 LTS Standalone Platform Release

Maintained by [roufsweb](https://github.com/roufsweb)

## Release Package Overview

| Attribute | Specification |
| :--- | :--- |
| **Package Name** | `Ubuntu_24.04_GalaxyS8_Full_Standalone_Odin.tar` |
| **Distribution Mirror** | [Google Drive Release Mirror](https://drive.google.com/drive/folders/roufsweb-galaxy-s8) |
| **Target Hardware** | Samsung Galaxy S8 (`SM-G950N`, `SM-G950F`, `SM-G950FD`) |
| **SoC Architecture** | Samsung Exynos 8895 (`dreamlte`, `dreamlteks`, 8 cores: 4x Exynos M2 + 4x Cortex-A53) |
| **Kernel Version** | Linux `4.4.111` (DEFEX-free, patched instant `on boot` LZMA ramdisk) |
| **Userspace OS** | Ubuntu 24.04.5 LTS (`Noble Numbat`, `glibc 2.39`, `aarch64`) |
| **GUI Environment** | GNOME 46 + macOS Sonoma Theme (`metacity`, `gnome-panel`, Plank Dock) |
| **Container Engine** | Native Docker CE Engine pre-installed and enabled |
| **Package File Size** | 3,533,455,360 bytes (3.37 GB) |
| **SHA256 Checksum** | `e474f8b2c857631bf8cbefea1f3b50a62a87bfbd0e74016752eb9780e9f7a143` |
| **MD5 Checksum** | `4ca69e692d1481683a93142999079c7e` |

### Included Partition Images Inside Odin TAR

| Member File | Target Partition | Size | Description |
| :--- | :--- | :--- | :--- |
| `boot.img` | `BOOT` (`/dev/block/sda7`) | 38.31 MB | Auto-boot kernel with embedded ABOX Calliope DSP firmwares, early firmware mount, MAX77865 PMIC 1500mA fast charging, V4L2 panic guard, and instant `on boot` supervisor trigger. |
| `recovery.img` | `RECOVERY` (`/dev/block/sda8`) | 46.00 MB | Headless TWRP recovery for emergency maintenance. |
| `userdata.img.lz4` | `USERDATA` (`/dev/block/sda24`) | 3.28 GB | Complete, pristine Ubuntu 24.04.5 LTS root filesystem containing GNOME 46 desktop, Docker engine, Wi-Fi drivers, ALSA audio configurations, and hardware bridge daemons. |

---

## 1-Click Flashing Instructions via Odin 3.14.1

Flashing this single file from Odin writes the kernel, recovery, and the complete Ubuntu operating system directly to UFS storage in a single 45-second operation. No manual file pushing or ADB setup is needed.

### Step 1: Boot into Odin Download Mode
1. Connect the Galaxy S8 to your Windows PC with a USB-C data cable.
2. Press and hold **Volume Down + Bixby + Power** simultaneously for **11 to 13 seconds**.
3. The phone enters Odin Download Mode directly (recognized in Windows as `SAMSUNG Mobile USB CDC Composite Device` on an assigned COM port). No need to press Volume Up.
4. *Stalled/frozen state recovery:* If the phone is unresponsive, hold all 3 buttons for 30 seconds to force PMIC power-latch release, release for 1 second, then hold all 3 buttons for 13 seconds.

### Step 2: Flash the Standalone File in Odin
1. Launch Odin 3.14.1 on Windows.
2. Confirm the `ID:COM` box turns blue/cyan.
3. Click the **AP** button and select `Ubuntu_24.04_GalaxyS8_Full_Standalone_Odin.tar`.
4. In the Options tab, keep **Auto Reboot** and **F. Reset Time** checked.
5. Click **Start**. Odin writes `boot.img` to `sda7`, `recovery.img` to `sda8`, and `userdata.img.lz4` to `sda24`.
6. Flashing completes in approximately 45 seconds with a green **PASS!** banner.

### Step 3: Hardware Bus Re-Enumeration
1. As soon as Odin displays **PASS!**, unplug the USB-C cable and re-plug it within 1 second.
2. This resets suspended Windows USB endpoints and brings the device online immediately.

---

## Automated First-Boot Sequence

When the phone powers on, the bootloader runs `boot.img` on `sda7`. The embedded `init.rc` triggers the boot supervisor at `t=2.5s`:

```rc
on boot
    start ubuntu_boot

service ubuntu_boot /sbin/sh /data/linux/start_all.sh
    user root
    group root
    disabled
    oneshot
    seclabel u:r:recovery:s0
```

The supervisor (`/data/linux/start_all.sh`) performs the following operations automatically:
1. Escapes Android `libprocessgroup` termination by shifting PID to root cgroup (`echo $$ > /acct/tasks`).
2. Disarms uninitialized V4L2 camera ISP nodes (`rm -f /dev/video100+`) to prevent kernel NULL-dereference panic.
3. Unlocks the MAX77865 PMIC registers to draw 1,500 mA fast charging and sets brownout UVLO protection to 4.3V.
4. Connects Broadcom BCM4361 Wi-Fi across both 2.4 GHz and 5 GHz bands.
5. Auto-mounts external MicroSD storage (`/dev/block/mmcblk0`) at `/media/sdcard` and `/mnt/android_data/sdcard`.
6. Mounts the Ubuntu 24.04.5 LTS rootfs at `/mnt/ubuntu` with `/proc`, `/sys`, `/dev`, `/dev/pts`, and cgroups.
7. Launches SSH (`:22`), TigerVNC (`:5901`), noVNC web interface (`:6080`), and GNOME 46 desktop.
8. Initializes Docker daemon for user workloads.
9. Arms the USB-C DisplayPort daemon (`exynos_dp_bridge`) and physical button daemon (`s8_button_daemon`).
10. Vibrates the haptic motor twice (2x 150 ms) to signal that all services are online.

---

## Desktop Access & Helper Scripts

The `releases/` directory provides one-click Windows helpers for instant connection:

| Helper Script | Purpose | Usage |
| :--- | :--- | :--- |
| `connect_desktop.bat` | Establishes USB port forwarding for ports 6080, 5901, and 2222, then automatically opens the noVNC desktop in your default browser. | Double-click to open desktop |
| `connect_shell.bat` | Immediately opens an interactive root bash shell inside Ubuntu 24.04 LTS. | Double-click to open shell |
| `TESTING_RUNBOOK.md` | Verification checklist from stock ROM flash to full desktop operation. | See [TESTING_RUNBOOK.md](TESTING_RUNBOOK.md) |

### Remote Access Details

| Service | Protocol / Port | Address | Credentials |
| :--- | :--- | :--- | :--- |
| **noVNC Web Desktop** | HTTP `6080` | `http://localhost:6080/vnc.html` or `http://<PHONE_IP>:6080/vnc.html` | Password: `ubuntu` |
| **TigerVNC Desktop** | RFB `5901` | `localhost:5901` or `<PHONE_IP>:5901` | Password: `ubuntu` |
| **SSH Root Console** | TCP `22` / `2222` | `ssh -p 2222 root@localhost` or `ssh root@<PHONE_IP>` | User: `root` / Pass: `ubuntu` |
| **Docker Engine** | Docker Socket | `/var/run/docker.sock` | Full root access |
