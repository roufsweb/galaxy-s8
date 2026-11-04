# Project Memory & Persistent Knowledge Base

## 1. Identity & Device Profile
* **Target Hardware:** Samsung Galaxy S8 Korean Variant (`SM-G950N`).
* **Kernel & Board Codename:** `dreamlteks` / `dreamltekor` (SoC: `universal8895`).
* **Current Bootloader Level:** Binary Version 5 (`REV 5` / `U5`).
* **Current Stock Build:** `G950NKSU5DVG2` (Android 9.0 Pie, One UI 1.0).
* **Bootloader Lock Status:** **Unlocked** (Knox tripped to `0x1`).
* **Physical Screen:** Detached / Non-functional. Headless workflows only.

---

## 2. Partition & Block Device Map
* **Block Device Path:** `/dev/block/platform/11120000.ufs/by-name/`
* **Key Partitions:**
  * `boot`: `/dev/block/platform/11120000.ufs/by-name/boot` (~37 MB)
  * `recovery`: `/dev/block/platform/11120000.ufs/by-name/recovery` (~45 MB)
  * `system`: `/dev/block/platform/11120000.ufs/by-name/system` (~4.5 GB)
  * `vendor`: `/dev/block/platform/11120000.ufs/by-name/vendor` (~700 MB)
  * `userdata`: `/dev/block/platform/11120000.ufs/by-name/userdata` (~53 GB)
  * `cache`: `/dev/block/platform/11120000.ufs/by-name/cache` (~300 MB)
  * `efs`: `/dev/block/platform/11120000.ufs/by-name/efs` (DO NOT OVERWRITE)

---

## 3. Kernel & Build Environment
* **Repository Path:** `E:\rouf\galaxy-s8\galaxy-s8-kvm-kernel`
* **Upstream Base:** Linux 4.4.111 (Samsung Universal 8895 BSP)
* **Target defconfig:** `arch/arm64/configs/exynos8895-dreamltekor_defconfig`
* **Bundled Toolchain:** `scripts/toolchain/gcc-cfp/gcc-cfp-jopp-only/aarch64-linux-android-4.9/bin`
* **Prefix:** `aarch64-linux-android-`
* **Ramdisk Tool:** Android Image Kitchen (`AIK-Linux`) located in `galaxy-s8-kvm-kernel/AIK-Linux`
* **Device Tree Packaging:** Built-in `dtbtool` combines generated dtbs into `dtb.img` and merges into boot image.

---

## 4. Hardware Pinouts & Modification Parameters
* **Battery Flex Pinout:**
  * `Pin 1 / VCC`: +4.10V DC (Buck converter positive)
  * `Pin 2 / GND`: Common Ground
  * `Pin 3 / THM`: Battery thermistor sensing pin. Connect via **10 kΩ resistor** to `GND`.
  * `Pin 4 / ID`: Battery fuel gauge communication line.
* **UART Serial Console:**
  * Audio Jack Interface: 3.5mm TRRS (Tip: RX, Ring 1: TX, Ring 2: ID, Sleeve: GND).
  * USB-C Interface: Fastboot/UART resistor mode using 619 kΩ between CC and GND.
  * Baud Rate: **115200 bps, 8 data bits, no parity, 1 stop bit (8N1)**.
  * Logic Level: 1.8V to 3.3V tolerant.

---

## 5. Architectural Decisions
1. **Downstream 4.4 Kernel Chosen Over Mainline:**
   Mainline Linux (6.x) is still incomplete for Exynos 8895 (missing UFS, DisplayPort Alt Mode, and Wi-Fi stability). Downstream 4.4 kernel is selected because all hardware drivers are 100% operational, and modern Docker / systemd run natively on 4.4.
2. **Dual-Boot Strategy:**
   Adopt the **Recovery Partition Technique** (Android in `boot`, Ubuntu in `recovery`) or **Concurrent Chroot/LXC** to avoid repartitioning risks on UFS storage.

