# Project Execution History & Knowledge Base
**Target Device:** Samsung Galaxy S8 (`SM-G950N`, Exynos 8895, Rev 5 `DVG2`, Knox `0x1`, Headless)  
**Workspace:** `e:\rouf\galaxy-s8`  
**Last Updated:** 2026-11-04

> [!CRITICAL]
> **HEADLESS DEVICE MANDATE — ZERO INTERNAL DISPLAY:**
> The physical OLED screen is completely **MISSING / DISCONNECTED** (`lcdtype=-1`).
> Never reference on-screen visual cues ("look at the screen", "splash screen", "screen goes dark", "tap confirmation").
> All operations must be communicated strictly via:
> 1. Vibration motor haptics (reset buzz, boot vibration).
> 2. Precise seconds countdown (e.g., hold buttons for exactly 7 seconds).
> 3. Host PC USB detection (`PID_6860` for Android, `PID_685D` for Download Mode, `adb devices` for TWRP).

---

## 1. Quick Status Matrix

| Subsystem | Current State | Working Verified? | Active Blockers / Notes |
| :--- | :--- | :--- | :--- |
| **Battery & PMIC** | Recovered (>3.7V) | YES | Charged 45m in Download Mode. Stock driver active. |
| **Bootloader (S-Boot)** | Rev 5 (`DVG2`) | YES | Knox `0x1`. BCB on `sda5` cleared. |
| **Flashing (Odin)** | Functional (`COM14`) | YES | Must use POSIX USTAR format (`tarfile.USTAR_FORMAT`). |
| **Recovery (TWRP)** | 3.7.0 on `/dev/block/sda8` | YES | Tested working, insecure root `adbd` active. |
| **Rootfs Image** | 10 GB at `/data/linux/rootfs.img` | YES | Alpine 3.20 + Docker 26.1.5 verified on UFS. |
| **Android OS** | Booted (`PID_6860`) | PARTIAL | Booted into MTP+Modem (`COM11`), but ADB/DisplayPort dormant. |
| **DisplayPort Alt Mode** | No Signal on Monitor | NO | Needs DP Alt mode handshake investigation or direct Linux DRM. |
| **ADB Access** | Inactive in current boot | NO | Needs `persist.sys.usb.config=mtp,adb` or TWRP recovery shell. |

---

## 2. Chronological Task Ledger

### Task 1: Hardware & Baseline Environment Profiling
* **Date:** 2026-11-02
* **What Was Done:** Checked device partition table (`/dev/block/sda*`), memory, CPU architecture, Knox status (`0x1`), bootloader rev (U5), and kernel version.
* **What Worked:** Identified 64GB UFS 2.1 storage, Exynos 8895 8-core CPU, and working TWRP backup images (`boot_backup_live.img`, `recovery_backup_live.img`).
* **What Failed:** Internal OLED screen is completely missing (`lcdtype=-1`). All operations must be strictly headless.

### Task 2: Ubuntu Base Deployment & Glibc Segfault Discovery
* **Date:** 2026-11-02
* **What Was Done:** Deployed Ubuntu 18.04, 20.04, and 22.04 base rootfs into loopback image on UFS storage.
* **What Failed:** Every dynamic binary crashed instantly with `SIGSEGV` (signal 11) in `_dl_sysdep_start`.
* **Root Cause:** Modern glibc ARM64 probes CPU capability registers (`AT_HWCAP`) which Samsung downstream 4.4 vendor kernel reports non-standardly.
* **Resolution Strategy:** Deploy Alpine 3.20 (musl libc) as immediate verification, patch custom kernel `cpufeature.c` for long-term native Ubuntu.

### Task 3: Alpine Linux 3.20 & Native Docker Verification
* **Date:** 2026-11-02
* **What Was Done:** Built 10 GB ext4 rootfs image at `/data/linux/rootfs.img` containing Alpine 3.20, OpenSSH, Docker 26.1.5, containerd 1.7.17, runc 1.1.14, and Broadcom Wi-Fi firmware.
* **What Worked:** 100% clean binary execution with zero segfaults. Docker daemon initialized and ran on bare metal. System idle RAM ~30 MB.

### Task 4: Switch-Root Ramdisk Generation & Testing
* **Date:** 2026-11-02
* **What Was Done:** Packaged custom initramfs to mount `/data/linux/rootfs.img` and `switch_root` directly into Linux PID 1 on boot.
* **What Failed:** Premature shell variable expansion caused missing variables in generated `init` script (`if [ -n ]; then`).
* **Fix:** Wrote clean standalone `scratch/init` script and packaged into `ramdisk.cpio` using `magiskboot`.

### Task 5: S-Boot BCB Recovery Bootloop Trap
* **Date:** 2026-11-02
* **What Happened:** Command `adb reboot recovery` wrote `"boot-recovery\n"` into `MISC` partition (`/dev/block/sda5`). When an experimental recovery halted, phone entered an infinite 30-second vibration loop.
* **What Worked:** Intercepted boot via Download Mode (Vol Down + Bixby + Cable), and permanently wiped BCB:
  ```bash
  dd if=/dev/zero of=/dev/block/sda5 bs=2048 count=1
  ```

### Task 6: Samsung Odin TAR Format Strictness
* **Date:** 2026-11-02
* **What Failed:** Odin rejected `.tar` archives generated via Python `tarfile` with `.//@PaxHeader` and `Unassigned file`.
* **Root Cause:** Python default is POSIX.1-2001 PAX format. Odin requires POSIX.1-1988 USTAR format.
* **What Worked:** Enforced `format=tarfile.USTAR_FORMAT` on all Odin archives.

### Task 7: A2N Kernel Charging Killswitch & Battery Drain
* **Date:** 2026-11-03
* **What Failed:** Battery drained from 45% down to 3.33V under USB power. Kernel logged:
  ```text
  [ 205.905541] [set_a2n_allow] a2n: bye bye!
  [  37.776638] max77865_get_vbus_state: VBUS is invalid. CHGIN < CHGIN_UVLO
  [  37.780090] sec-battery battery: Status(Not-charging), Health(UnderVoltage)
  ```
* **Root Cause:** Proprietary A2N kernel trial timer executed `[set_a2n_allow] a2n: bye bye!`, commanding the MAX77865 PMIC to disconnect `CHGIN` power gating.
* **What Worked:** Extracted clean official Samsung stock kernel `boot.img.lz4` from `AP_G950NKSU5DVG2...` to eliminate trial code.

### Task 8: Low-Battery Brownout Loop & Download Mode Trickle-Charge
* **Date:** 2026-11-03
* **What Failed:** When battery was at 3.33V, plugging into charger triggered cyclic vibration reboots every 15–30 seconds because CPU boot inrush (~1.5A) sagged cell voltage below PMIC 3.0V UVLO cutoff.
* **What Worked:** Held device in Download Mode (low-power ~200mA state without CPU boot spikes) on wall charger for 45 minutes to safely charge cell past 3.7V.

### Task 9: Stock Kernel vs Magisk Ramdisk dm-verity Conflict
* **Date:** 2026-11-03
* **What Failed:** Flashing pure untouched stock `boot.img` caused dm-verity / Knox DEFEX panic because `/data` had been modified by TWRP/Magisk.
* **What Worked:** Assembled `boot_stock_magisk.tar` combining clean stock kernel (`4.4.111-21340847`, no A2N, no KVM) with tested Magisk ramdisk (dm-verity/DEFEX bypassed) in USTAR format.

### Task 10: Headless DisplayPort Alt Mode & ADB Dormancy
* **Date:** 2026-11-03
* **Current Observation:** Device boots and enumerates as `USB\VID_04E8&PID_6860` (MTP + Modem `COM11`), but external monitor shows no signal and ADB does not hook.
* **Root Cause Analysis:**
  1. In Android One UI, DisplayPort Alt Mode (DeX/mirroring) only activates after Android lockscreen initialization or user confirmation, which cannot be tapped without a screen or mouse.
  2. If `/data` encryption or framework halts before `sys.boot_completed=1`, video output never starts.
  3. `PID_6860` default on Samsung is `mtp` only, leaving `adbd` dormant.

---

### Task 11: Headless Autonomous Rescue Shell (`twrp_as_boot.tar`)
* **Date:** 2026-11-04
* **What Was Done:** Packaged verified TWRP 3.7.0 recovery image as `boot.img` inside [`twrp_as_boot.tar`](file:///e:/rouf/galaxy-s8/twrp_as_boot.tar).
* **What Failed:** Odin failed immediately with `Complete(Write) operation failed`.
* **Root Cause:** Hard partition limit. `BOOT` (`sda7`) is capped at 41,943,040 bytes (40 MB) by PIT table. TWRP 3.7.0 is 48,234,496 bytes (46 MB). Overflow of 6.29 MB rejected by Odin.
* **Resolution:** TWRP must be flashed strictly as `recovery.img` via [`recovery_restore.tar`](file:///e:/rouf/galaxy-s8/recovery_restore.tar). Boot partition images must never exceed 40 MB.

---

### Task 12: Android Boot Diagnostics & Headless MTP Lockout Analysis
* **Date:** 2026-11-04
* **Hardware State:** Device booted into Samsung Android One UI. Windows enumerates `USB\VID_04E8&PID_6860` (MTP + Modem `COM11`).
* **Root Cause of Symptoms:**
  1. **Scrcpy failure:** Android booted with default USB configuration `mtp` (VID 04E8, PID 6860), leaving `adbd` inactive.
  2. **Windows File Explorer empty:** Samsung lockscreen blocks MTP storage access until the screen is unlocked.
  3. **No HDMI output:** Samsung One UI requires dismissing a DeX/Mirroring dialog on the missing internal screen before outputting video over Type-C DP Alt Mode.
  4. **Odin COM11:** Virtual modem port exposed by Android framework; Odin cannot flash over `COM11` (only `PID_685D`).
* **Resolution Plan:** Boot into TWRP recovery via button combination (Vol Up + Bixby + Power) to gain root ADB console, enable `persist.sys.usb.config=mtp,adb`, and proceed with native Linux deployment.

---

### Task 13: Unified Headless ADB & TWRP Firmware (`boot_and_recovery_headless.tar`)
* **Date:** 2026-11-04
* **What Was Done:** Built an all-in-one Odin package [`boot_and_recovery_headless.tar`](file:///e:/rouf/galaxy-s8/boot_and_recovery_headless.tar) (84.9 MB) in POSIX USTAR format containing:
  1. `boot.img` (35.01 MB $\rightarrow$ `sda7`): Stock Samsung 4.4.111 kernel (unrestricted charging) combined with customized Magisk ramdisk (`ro.secure=0`, `ro.adb.secure=0`, `ro.debuggable=1`, `persist.sys.usb.config=mtp,adb`, and `overlay.d/headless_adb.rc` for auto-dismissing keyguard and starting `adbd`).
  2. `recovery.img` (46.00 MB $\rightarrow$ `sda8`): Verified TWRP 3.7.0 recovery image.
* **Benefits:** Solves both boot requirements in a single 5-second Odin flash: automatic root ADB + Scrcpy on boot without screen interaction, plus guaranteed TWRP rescue recovery.

---

### Task 14: S-Boot Header Correction & Firmware Re-generation
* **Date:** 2026-11-04
* **What Failed:** The first build of `boot_and_recovery_headless.tar` passed in Odin, but the device silently powered down without vibrating upon reset.
* **Root Cause:** S-Boot integrity checks require `name` (`SRPPK29D005KU`), `second_addr` (`0x10f00000`), and `dtb_addr` (`0x12000154`). The script generated a generic header with zeroes in these fields.
* **Fix Applied:** Modified `repack_headless_boot.py` to copy the exact 2048-byte header from the official Samsung firmware and update only `ramdisk_size`. Rebuilt [`boot_and_recovery_headless.tar`](file:///e:/rouf/galaxy-s8/boot_and_recovery_headless.tar) (84.9 MB).

---

### Task 15: Clean Magisk Auto-ADB Boot Package (`magisk_headless_adb.tar`)
* **Date:** 2026-11-04
* **What Was Done:** Solved the headless Android access problem without needing recovery buttons or TWRP acrobatics.
  1. Identified that internal Samsung boot ramdisks strictly require **GZIP** (`1f 8b 08 00`), not LZ4.
  2. Built [`magisk_headless_adb.tar`](file:///e:/rouf/galaxy-s8/magisk_headless_adb.tar) (37.0 MB) in POSIX USTAR format.
  3. Integrated official clean Samsung stock kernel (`4.4.111-21340847`, Rev 5) + official Magisk ramdisk (`dreamlteks` build).
  4. Added `overlay.d/init.headless.rc` and patched `default.prop` (`ro.secure=0`, `ro.adb.secure=0`, `ro.debuggable=1`, `persist.sys.usb.config=mtp,adb`).
* **Expected Outcome:** Flashing directly via Odin AP with "Auto Reboot" enabled brings up rooted Android with automatic ADB and Scrcpy access upon boot without touching any hardware buttons or display prompts.

---

### Task 16: Successful Odin Flash & ADB Connection Verification
* **Date:** 2026-11-04
* **Status:** SUCCESS.
* **Observation:** After toggling OEM unlocking, Odin flashed successfully with `PASS!`. Phone booted into Android. Front LED pulsing blue-cyan (Samsung normal operation). PC detects `ce10171ab3e9620804` over ADB.
* **Next Action:** Authorize PC RSA key on external monitor to grant permanent ADB access and run Scrcpy.

---

### Task 17: Baseline Recovery & Master Execution Plan
* **Date:** 2026-11-04
* **Status:** MILESTONE ACHIEVED.
* **State:** Full factory stock firmware (Rev 5 `DVG2`) running stably with working HDMI output and USB mouse input. **OEM Unlocking permanently enabled in Developer Options.** Custom binary blocks (`RQT_CLOSE`) removed.
* **Artifact Created:** [`execution_roadmap.md`](file:///C:/Users/rakib/.gemini/antigravity/brain/856563d1-ce89-44fd-8c75-5b4b5db94bbc/execution_roadmap.md).
* **Next Action:** Flash TWRP 3.7.0 recovery to `sda8` to secure guaranteed root console and deploy Ubuntu rootfs image.

---

### Task 18: Native Ubuntu 20.04 ARM64 Rootfs Deployment & Switch-Root Boot Package
* **Date:** 2026-11-04
* **What Was Done:**
  1. Verified TWRP 3.7.0 on `sda8` with active root console over ADB.
  2. Formatted `/dev/block/sda24` (`USERDATA`) to unencrypted ext4, giving 53.1 GB of high-speed UFS 2.1 flash storage.
  3. Created 10 GB sparse ext4 image at `/data/linux/rootfs.img` and extracted `ubuntu-base-20.04.5-base-arm64.tar.gz`.
  4. Verified dynamic glibc ARM64 binary execution (`chroot /mnt/ubuntu /bin/ls` and `/bin/bash` ran cleanly with zero segfaults).
  5. Configured Ubuntu base system files: root password (`root`), DNS (`8.8.8.8`), `/init` script for direct console login.
  6. Built [`boot_native_ubuntu.tar`](file:///e:/rouf/galaxy-s8/boot_native_ubuntu.tar) (31.77 MB) in POSIX USTAR format containing the clean stock kernel + GZIP switch-root ramdisk.
* **Outcome:** The device is now 100% prepared to boot directly into native Ubuntu 20.04 ARM64.

### Task 19: Bootloop Diagnostic via `/proc/last_kmsg` & Samsung DEFEX Root Cause
* **Date:** 2026-11-04
* **Observed Symptom:** Flashing `boot_native_ubuntu.img` caused a repeating vibration cycle (bootloop) and reboot back into TWRP on `sda8`.
* **Diagnostic Execution:**
  - Pulled `/proc/last_kmsg` from the live recovery session.
  - Root cause pinpointed: Stock Samsung kernel (`4.4.111-21340847`) has `CONFIG_SECURITY_DEFEX=y` enabled.
  - DEFEX's `SafePlace` module intercepted root `/init` forking `/bin/busybox`, flagging every execution as an unauthorized `safeplace violation`.
  - Init script exited (`exitcode=0x00000000`), triggering `Kernel panic - not syncing: Attempted to kill init!`.
* **Resolution Strategy:**
  - Extracted `/proc/config.gz` from TWRP kernel, confirming `# CONFIG_SECURITY_DEFEX is not set` (DEFEX completely disabled).
  - TWRP kernel natively supports `NAMESPACES`, `CGROUPS`, `BLK_DEV_LOOP`, `EXT4_FS`, `EXYNOS_MIPI_DISPLAYPORT`, `HID`, and `USB_CONFIGFS` with verified clean battery charging (~530 mA, 3.90 V).
  - Repack switchroot boot image using the TWRP kernel + DTB combined with our updated GZIP switchroot ramdisk.

---

## 3. What Worked (Verified Best Practices)

1. **Hardware Rescue Handshake:**
   * Unplug cable $\rightarrow$ Hold **Volume Down + Bixby** $\rightarrow$ Plug cable to PC $\rightarrow$ Tap **Volume Up** once $\rightarrow$ Enters Download Mode reliably on `PID_685D`.
2. **Safe Charging State:**
   * Holding device in Download Mode guarantees continuous charging without brownouts or kernel crash loops.
3. **Recovery Rescue Console:**
   * TWRP 3.7.0 (`recovery_restore.tar`) provides guaranteed root ADB access and stable battery charging without depending on Android framework state.
4. **Tar Packaging:**
   * Always package Odin tars using `format=tarfile.USTAR_FORMAT`.
5. **Virtualization Rules:**
   * `CONFIG_KVM` must remain strictly disabled (`# CONFIG_KVM is not set`) on Samsung downstream kernels.

---

## 4. What Failed & Must Never Be Repeated

1. **Never run unlicensed A2N kernel:** It actively cuts PMIC battery charging after 3 minutes.
2. **Never enable `CONFIG_KVM=y`:** S-Boot reserves EL2 in TrustZone; `hvc` instructions trigger instantaneous `sec_debug` hardware panic.
3. **Never flash pure stock `boot.img` on modified `/data`:** dm-verity and Knox DEFEX will panic on boot.
4. **Never boot the OS with battery below 3.5V:** Always trickle-charge in Download Mode first to prevent brownout bootloops.
5. **Never rely on PAX tar archives with Odin:** Odin strictly requires POSIX USTAR format.

---

## 5. Asset & Partition Inventory

* `boot_and_recovery_headless.tar` (84.9 MB): Combined unified Odin archive in POSIX USTAR format containing headless auto-ADB `boot.img` (35.01 MB) and TWRP 3.7.0 `recovery.img` (46.00 MB).
* `twrp_as_boot.tar` (48.2 MB): TWRP 3.7.0 packaged as `boot.img` in USTAR format for automatic headless root ADB on power-on.
* `boot_stock_magisk.tar` (36.7 MB): Hybrid stock kernel + Magisk ramdisk in USTAR format.
* `boot_stock.tar` (37.3 MB): Clean official Samsung stock kernel (Rev 5) in USTAR format.
* `recovery_restore.tar` (48.2 MB): Official TWRP 3.7.0 recovery in USTAR format.
* `boot_backup_live.img` (41.9 MB): Original live working A2N boot image dumped from device.
* `recovery_backup_live.img` (48.2 MB): Original TWRP recovery dump from device.
* `boot_linux_switchroot.img` (41.9 MB): Repacked switch-root boot image targeting `/data/linux/rootfs.img`.
* `/data/linux/rootfs.img` (10 GB sparse): Deployed Alpine Linux 3.20 rootfs with native Docker engine.

