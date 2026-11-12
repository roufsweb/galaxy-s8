---
name: galaxy-s8-ap-kernel-builder
description: Operational runbook and mathematical verification guide for compiling the custom Samsung Exynos 8895 Linux kernel (4.4.111-s8-universal-v2), constructing Pure Native Linux systemd PID 1 boot images, embedding Calliope DSP firmwares, and packaging Odin AP slot tar archives on the headless Samsung Galaxy S8 (SM-G950N).
---

# Galaxy S8 Exynos 8895 — Universal AP & Kernel Builder Runbook (`galaxy-s8-ap-kernel-builder`)

> [!CRITICAL]
> **MANDATORY HARDWARE GUARDS & PARTITION BOUNDARIES:**
> 1. **Size Hard Stop:** `boot.img` and `recovery.img` MUST be `<= 41,943,040 bytes` (`40.0 MB`, `/dev/sda7` and `/dev/sda8`).
> 2. **9 Calliope DSP Firmwares:** All 9 Calliope audio firmwares (`calliope_sram.bin`, `calliope_dram.bin`, `calliope_iva.bin`, `dsm.bin`, `AP_AUDIO_SLSI.bin`, `APBargeIn_AUDIO_SLSI.bin`, `SoundBoosterParam.bin`, `APBiBF_AUDIO_SLSI.bin`, `dsm_tune.bin`) must reside directly in `etc/firmware/` and `vendor/firmware/`.
> 3. **Pure Native Linux PID 1 (`switch_root`):** Ramdisk `/init` is a staticBusyBox POSIX script that configures PMIC 1500mA fast charge, mounts target rootfs (`/dev/sda25`, `/dev/mmcblk0p2`, or `/data/linux/rootfs.img`), injects `/usr/sbin/s8-usb-gadget.sh` and `s8_usb_agentd`, and executes `switch_root` into the guest OS `/sbin/init` as PID 1.
> 4. **USB ConfigFS UEVENT Bridge:** `CONFIG_USB_CONFIGFS_UEVENT=y` MUST remain enabled in `.config` so `drivers/usb/manager/usb_typec_manager_notifier.c` activates DWC3 endpoints on cold boot.

---

## 1. Fast Reference Commands

### Build Universal Linux AP Package & Hardware Bundles
```powershell
python scripts/build_universal_ap.py
python scripts/pre_flash_validator.py releases/Galaxy_S8_Linux_AP.tar
```
* **Outputs:**
  * `scratch/boot_universal_ap.img` (`<= 41,943,040` B)
  * `releases/Galaxy_S8_Linux_AP.tar` (USTAR archive containing `boot.img` + `recovery.img` for Odin `AP` slot)
  * `packages/dist/galaxy-s8-hw_1.0.2_arm64.deb` (Debian/Ubuntu/Kali package)
  * `packages/dist/galaxy-s8-hw-universal-arm64.tar.gz` (Universal distro-agnostic tarball for Alpine, OpenWrt, Arch, Home Assistant OS, SteamOS)

### Live Kernel/AP Update Over RWP (`192.168.7.2`) Without Odin
When the phone is already running Linux on RNDIS (`192.168.7.2:7860`), `/dev/sda7` (`BOOT`) and `/dev/sda8` (`RECOVERY`) can be updated directly in-place using `dd bs=4096 conv=fsync`.

### Enter Odin Download Mode (Hardware Combo)
1. Keep the USB-C cable plugged into the PC.
2. Hold **Volume Down + Bixby + Power** continuously for **11–13 seconds**.
3. Phone enumerates in Odin Download Mode (`PID_685D`).
4. Select `releases/Galaxy_S8_Linux_AP.tar` in the **AP** slot -> Start.
5. After `PASS!`, unplug and re-plug the USB-C cable to trigger host bus re-enumeration.

---

## 2. Kernel Compilation Runbook (WSL2 `/root/s8_kernel_build`)

### 2.1 Toolchain & Environment Variables
```bash
cd /root/s8_kernel_build
export ARCH=arm64
export ANDROID_MAJOR_VERSION=p
export PATH="/root/s8_kernel_build/scripts/toolchain/gcc-cfp/gcc-cfp-jopp-only/aarch64-linux-android-4.9/bin:$PATH"
export CROSS_COMPILE=aarch64-linux-android-
export KCFLAGS="-w -Wno-error"
```

### 2.2 Mandatory Full-Permission Kconfig Flags
```ini
# Zero Samsung Restrictions
# CONFIG_SECURITY_DEFEX is not set
# CONFIG_RKP_CFP is not set
# CONFIG_RKP_CFP_JOPP is not set
# CONFIG_FIVE is not set
# CONFIG_PROCA is not set

# Full Systemd, Docker, LXC & Home Assistant OS Permissions
CONFIG_NAMESPACES=y
CONFIG_USER_NS=y
CONFIG_PID_NS=y
CONFIG_NET_NS=y
CONFIG_IPC_NS=y
CONFIG_UTS_NS=y
CONFIG_CGROUPS=y
CONFIG_CGROUP_DEVICE=y
CONFIG_CGROUP_FREEZER=y
CONFIG_CGROUP_PIDS=y
CONFIG_CGROUP_SCHED=y
CONFIG_FAIR_GROUP_SCHED=y
CONFIG_CFS_BANDWIDTH=y
CONFIG_MEMCG=y
CONFIG_BLK_CGROUP=y
CONFIG_CPUSETS=y
CONFIG_OVERLAY_FS=y
CONFIG_POSIX_MQUEUE=y
CONFIG_SECCOMP=y
CONFIG_SECCOMP_FILTER=y
CONFIG_BINFMT_MISC=y
CONFIG_BRIDGE=y
CONFIG_VETH=y
CONFIG_MACVLAN=y
CONFIG_VLAN_8021Q=y

# USB ConfigFS RNDIS + ACM + UEVENT Bridge
CONFIG_USB_CONFIGFS_UEVENT=y
CONFIG_USB_CONFIGFS_RNDIS=y
CONFIG_USB_RNDIS_MULTIPACKET=y
CONFIG_USB_CONFIGFS_ACM=y
CONFIG_USB_CONFIGFS_F_FS=y

# DisplayPort, DECON & ABOX Audio
CONFIG_EXYNOS_DISPLAYPORT=y
CONFIG_EXYNOS_DECON_FB=y
CONFIG_EXYNOS_ION=y
CONFIG_SND_SOC_SAMSUNG_ABOX=y
CONFIG_SND_SOC_CS47L92=y
```
