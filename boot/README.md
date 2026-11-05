# Galaxy S8 Boot Subsystem & Image Packaging

This directory contains the tools and scripts used to construct, unpack, patch, and package the auto-booting kernel images for the Samsung Galaxy S8 (`SM-G950N`, Exynos 8895).

---

## Files in this Directory

| File | Purpose |
| :--- | :--- |
| `build_autoboot_and_odin.py` | Unpacks stock/TWRP `boot.img`, extracts the LZMA ramdisk, patches `init.rc` for auto-booting Ubuntu, rebuilds the `newc` CPIO ramdisk, and packages `Ubuntu_24.04_GalaxyS8_Full_Odin.tar`. |
| `start_all.sh` | Master boot supervisor deployed at `/data/linux/start_all.sh` on the phone. Orchestrates cgroup isolation, hardware panic guards, PMIC fast-charging registers, network bring-up, rootfs mounting, desktop daemons, and homelab containers. |

---

## Technical Constraints & Partition Boundaries

1. **Partition Limits (`sda7` BOOT):**
   * The `BOOT` partition (`/dev/block/sda7`) has an exact maximum capacity of `41,943,040` bytes (40 MB).
   * Any kernel image exceeding 40 MB will fail Odin flashing or cause partition truncation. The compiled auto-boot image is sized at `40,521,744` bytes, leaving approximately 1.4 MB of safety margin.

2. **DWC3 USB Power-On Prerequisite:**
   * In Exynos 8895, the Synopsis DesignWare USB 3.0 controller (`10c00000.dwc3`) requires the Android `adbd` daemon to set `sys.usb.ffs.ready=1` via Android `/init`'s property socket. Replacing Android `/init` with a standalone busybox `/init` cuts off USB bus power and bricks ADB communication.
   * Auto-booting is accomplished cleanly by triggering on `property:sys.usb.ffs.ready=1` in `init.rc`.

3. **Android Cgroup Kill Escape:**
   * Android `init` / `libprocessgroup` monitors child processes spawned by oneshot services in `/acct/uid_0/pid_<pid>/`. When the script finishes, `libprocessgroup` sends SIGKILL to all descendant processes.
   * `start_all.sh` immediately executes `echo $$ > /acct/tasks` to move into the root cgroup, ensuring background daemons (sshd, TigerVNC, GNOME, Docker) remain permanently alive.

