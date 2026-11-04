# Project Summary: Samsung Galaxy S8 (SM-G950N) Native Linux & Docker

> [!CRITICAL]
> **STRICT HEADLESS HARDWARE MANDATE:**
> The internal OLED screen is completely **MISSING / DISCONNECTED** (`lcdtype=-1`).
> Never instruct the user to observe on-screen visuals or press on-screen elements.
> Guide all physical procedures strictly via vibration motor pulses, exact seconds countdowns, and host PC USB enumeration (`PID_685D`, `PID_6860`, `adb devices`).

## 1. Executive Overview
This project transforms a screenless, Korean-variant Samsung Galaxy S8 (`SM-G950N`, Exynos 8895) into a high-performance, compact, headless native Linux (Ubuntu ARM64) server and workstation with Docker, KVM hardware virtualization, and USB-C DisplayPort video output.

---

## 2. Hardware Specifications

| Component | Specification | Technical Notes |
| :--- | :--- | :--- |
| **Model** | Samsung Galaxy S8 Korean (`SM-G950N`) | Codename: `dreamlteks` / `dreamltekor` |
| **SoC** | Samsung Exynos 9 Octa 8895 (10nm FinFET) | 64-bit ARMv8.0-A architecture |
| **CPU Cluster** | 4x Mongoose M2 @ 2.31 GHz + 4x Cortex-A53 @ 1.69 GHz | Big.LITTLE with EAS scheduler |
| **GPU** | ARM Mali-G71 MP20 | 20 execution cores, Bifrost 1st gen (`JM600`) |
| **RAM** | 4 GB LPDDR4x (PoP) | Fast unified memory; ample for headless workloads |
| **Storage** | 64 GB UFS 2.1 | ~800 MB/s read, ~200 MB/s write; outclasses SD/eMMC |
| **USB Interface** | USB 3.1 Gen 1 Type-C | Supports OTG, Host, DisplayPort 1.2 Alt Mode (HDMI out) |
| **Display** | None (Screen removed / disconnected) | Handled via USB-C DP Alt Mode, DeX, scrcpy, and ADB |
| **Wireless** | Broadcom BCM4361 | Wi-Fi 5 (802.11ac 2x2 MIMO) + Bluetooth 5.0 |
| **Security / Fuse**| Samsung Knox | State: `0x1` (Unlocked bootloader, custom binaries allowed) |

---

## 3. Workspace Assets Inventory

The current working directory contains key foundation files:
* `AP_G950NKSU5DVG2_...tar.md5`: Full stock Android 9 Pie (REV 5) system, boot, and vendor images.
* `galaxy-s8-stock-firmwire/`: 5-file stock package (`AP`, `BL`, `CP`, `CSC`, `HOME_CSC`, `USERDATA`).
* `galaxy-s8-kvm-kernel/`: Downstream Linux 4.4.111 kernel repository with:
  * Integrated `aarch64-linux-android-4.9` toolchain
  * `exynos8895-dreamltekor_defconfig`
  * Android Image Kitchen (`AIK-Linux`) submodule for boot image repacking
  * `build_kernel.sh` compilation script
* `boot_kvm_fixed.tar`: Pre-compiled KVM boot image packaged for Odin.
* `magisk_patched-30700_DAZdX.tar`: Rooted boot image for initial Android system access.
* `FINDINGS.md`: Centralized mission-critical hardware, kernel, power management, and tooling discoveries.
* `boot_stock_magisk.tar`: Hybrid image combining clean official Samsung stock kernel (unrestricted charging) with tested Magisk ramdisk (dm-verity/DEFEX bypassed) in pure USTAR format for Odin.
* `boot_stock.tar`: Clean official Samsung stock kernel (Rev 5) with unrestricted MAX77865 PMIC charging logic.
* `recovery_restore.tar`: Stock TWRP 3.7.0 recovery image packaged in pure POSIX USTAR format for Odin.
* `.agent/skills/project-findings-manager/`: Dedicated Antigravity skill for auditing, verifying, and logging project findings.

---

## 4. Architectural Strategy

### A. Kernel Layer (Linux 4.4 Downstream)
* Utilizes Samsung's battle-tested 4.4.111 BSP kernel to retain 100% hardware driver support (UFS 2.1, Wi-Fi 5, GPU, DP Alt Mode).
* Extends the defconfig to enable:
  * Full Docker engine support (cgroups v1/v2, namespaces, overlayfs, network bridge).
  * KVM virtualization strictly disabled (`CONFIG_KVM=n`) to avoid Samsung S-Boot TrustZone EL2 `sec_debug` panics.

### B. Userland Layer (Ubuntu 22.04 LTS ARM64)
* **Direct Boot**: The ramdisk mounts an `ext4` partition on internal UFS storage or MicroSD card and launches systemd (`/sbin/init`).
* **Dual-Boot Capability**:
  * Option 1: Primary Android in `/dev/block/boot`, Ubuntu in `/dev/block/recovery`.
  * Option 2: Android base with Ubuntu running concurrently in an LXC/chroot environment.

### C. Display & Interaction Layer
* **Video**: Hardware DisplayPort 1.2 Alt Mode over USB-C adapter or dock.
* **Control**:
  * Under Android: Samsung DeX desktop or `scrcpy` over USB.
  * Under Ubuntu: Standard OpenSSH server and X11/Wayland desktop on external monitor.

