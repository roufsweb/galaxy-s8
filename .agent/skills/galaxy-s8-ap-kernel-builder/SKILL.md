---
name: galaxy-s8-ap-kernel-builder
description: Operational runbook and mathematical verification guide for compiling the custom Samsung Exynos 8895 Linux kernel, constructing auto-booting boot and recovery images, embedding Calliope DSP audio firmwares, and packaging Odin AP slot tar archives on the headless Samsung Galaxy S8 (SM-G950N).
---

# Galaxy S8 Exynos 8895 — AP & Kernel Builder Runbook (`galaxy-s8-ap-kernel-builder`)

> [!CRITICAL]
> **MANDATORY HARDWARE GUARDS & PARTITION BOUNDARIES:**
> 1. **Size Hard Stop:** `boot.img` and `recovery.img` MUST be `<= 41,943,040 bytes` (`40.0 MB`). Exceeding this boundary fails Odin flashing or corrupts adjacent partition blocks (`sda7` / `sda8`).
> 2. **9 Calliope DSP Firmwares:** All 9 Calliope audio firmwares must reside directly in `etc/firmware/` and `vendor/firmware/` in the ramdisk. Never shadow `/etc/firmware` with a bind mount (causes ABOX IPC timeout and second-12 watchdog panic).
> 3. **Cgroup Task Escape:** All boot scripts must begin with `echo $$ > /acct/tasks 2>/dev/null` to escape Android `libprocessgroup` SIGKILL.
> 4. **No Internal Screen:** The phone is headless (`lcdtype=-1`). Only check vibrations, torch, and host USB/ADB status.

---

## 1. Fast Reference Commands

### Build Verified Rock-Solid Boot Image & Odin AP Package
```powershell
python scratch/build_rocksolid_boot.py
```
* **Inputs:** `archive/boot_twrp_exact.tar`, Calliope DSP firmwares.
* **Outputs:**
  * `scratch/boot_ubuntu_autoboot.img` (`38,977,552` B $\le$ `41,943,040` B limit)
  * `releases/Ubuntu_24.04_GalaxyS8_Full_Odin.tar` (`77,967,360` B USTAR archive for Odin `AP` slot)

### Flash Live via ADB (Without Odin)
```powershell
adb push scratch/boot_ubuntu_autoboot.img /tmp/boot.img
adb shell "dd if=/tmp/boot.img of=/dev/block/sda7 bs=4096 conv=fsync"
adb shell "dd if=/tmp/boot.img of=/dev/block/sda8 bs=4096 conv=fsync"
adb shell "rm /tmp/boot.img && sync"
```

### Enter Odin Download Mode (Windows / USB Host)
1. Keep the USB-C cable plugged into the PC.
2. Hold **Volume Down + Bixby + Power** for **11–13 seconds**.
3. Phone immediately enumerates in Odin Download Mode (`PID_685D` on `COM17`).
4. Select `releases/Ubuntu_24.04_GalaxyS8_Full_Odin.tar` in the **AP** slot $\rightarrow$ Start.
5. **Post-Flash USB Re-Plug:** After `PASS!`, unplug and re-plug USB-C to re-enumerate ADB endpoints.

---

## 2. Kernel Compilation Runbook (WSL2 / Linux)

### 2.1 Toolchain & Environment Variables
```bash
cd /root/s8_kernel_build
export ARCH=arm64
export ANDROID_MAJOR_VERSION=p
export PATH="/root/s8_kernel_build/scripts/toolchain/gcc-cfp/gcc-cfp-jopp-only/aarch64-linux-android-4.9/bin:$PATH"
export CROSS_COMPILE=aarch64-linux-android-
export KCFLAGS="-w -Wno-error"
```

### 2.2 Mandatory Kernel Kconfig Settings
* **DEFEX:** MUST be disabled (`# CONFIG_SECURITY_DEFEX is not set`).
* **Container Namespaces:**
  ```ini
  CONFIG_NAMESPACES=y
  CONFIG_PID_NS=y
  CONFIG_NET_NS=y
  CONFIG_IPC_NS=y
  CONFIG_UTS_NS=y
  CONFIG_CGROUP_DEVICE=y
  ```
* **DisplayPort & DECON:**
  ```ini
  CONFIG_EXYNOS_DISPLAYPORT=y
  CONFIG_EXYNOS_DECON_FB=y
  CONFIG_EXYNOS_ION=y
  ```
* **ABOX Audio:**
  ```ini
  CONFIG_SND_SOC_SAMSUNG_ABOX=y
  CONFIG_SND_SOC_CS47L92=y
  ```
* **Netfilter TCPMSS Fix:**
  ```ini
  # CONFIG_NETFILTER_XT_TARGET_TCPMSS is not set
  ```

### 2.3 Compilation Commands
```bash
make exynos8895-dreamlte_defconfig
make olddefconfig
make -j$(nproc) Image
make dtbs

# Generate Korean SM-G950N Rev 11 Device Tree
./scripts/dtbtool_exynos/dtbtool -s 2048 \
    --platform 0x50a6 \
    --subtype 0x217584da \
    -o arch/arm64/boot/dtb_rev11.img \
    arch/arm64/boot/dts/exynos/exynos8895-dreamlte_kor_11.dtb
```

---

## 3. Ramdisk & AP Package Assembly Rules

### 3.1 TWRP Ramdisk Slimming
To guarantee the boot image stays under the 40 MB partition boundary, remove heavy TWRP fonts from the CPIO ramdisk:
* `twres/fonts/DroidSansFallback.ttf` (saves 5.2 MB)
* `twres/fonts/NotoSansCJKjp-Regular.ttf` (saves 3.5 MB)
* `sbin/libclang_rt.ubsan_standalone-aarch64-android.so` (saves 1.4 MB)
* Total savings: **~10.1 MB**

### 3.2 Embedding Calliope Audio DSP Firmware Suite
The 9 required firmware binaries:
1. `calliope_sram.bin`
2. `calliope_dram.bin`
3. `calliope_iva.bin`
4. `dsm.bin`
5. `AP_AUDIO_SLSI.bin`
6. `APBargeIn_AUDIO_SLSI.bin`
7. `SoundBoosterParam.bin`
8. `APBiBF_AUDIO_SLSI.bin`
9. `dsm_tune.bin`

Place each binary in:
* `etc/firmware/<fw_name>`
* `vendor/firmware/<fw_name>`

### 3.3 Root Cgroup Task Escape
In `sbin/permissive.sh`:
```sh
#!/sbin/sh
echo $$ > /acct/tasks 2>/dev/null || true
/sbin/busybox setenforce 0 2>/dev/null || setenforce 0 2>/dev/null || true
```

### 3.4 Auto-Boot Trigger Hook in `init.rc`
```rc
on property:sys.usb.ffs.ready=1
    setprop sys.usb.config adb
    start ubuntu_boot

service ubuntu_boot /sbin/sh /sbin/boot_supervisor.sh
    user root
    group root
    disabled
    oneshot
    seclabel u:r:recovery:s0
```

### 3.5 MAX77865 PMIC Power Sequence (in `boot_supervisor.sh`)
```sh
echo "0xBD 0x6C" > /sys/class/power_supply/max77865-charger/data
echo "0xC3 0x61" > /sys/class/power_supply/max77865-charger/data
echo "0xC0 0x3C" > /sys/class/power_supply/max77865-charger/data
echo "0xB9 0x9E" > /sys/class/power_supply/max77865-charger/data
echo "0xB7 0x05" > /sys/class/power_supply/max77865-charger/data
```

---

## 4. Boot Image Header Specifications

* **Header Version:** 0
* **Page Size:** `2048` (`0x800`)
* **Base:** `0x10000000`
* **Kernel Load Address:** `0x10008000`
* **Ramdisk Load Address:** `0x11000000`
* **Cmdline:**
  ```text
  console=ram loglevel=4 androidboot.hardware=samsungexynos8895 androidboot.selinux=permissive loop.max_part=7
  ```

---

## 5. Verification Checklist Before Release

- [ ] File size of `boot.img` $\le$ `41,943,040 bytes` (`40.0 MB`).
- [ ] File size of `recovery.img` $\le$ `41,943,040 bytes` (`40.0 MB`).
- [ ] Ramdisk SVR4 CPIO magic `070701` with 4-byte padding.
- [ ] Zero bind-mount loops in `permissive.sh`.
- [ ] All 9 Calliope DSP binaries verified present in CPIO catalog.
- [ ] Odin tarball formatted as standard POSIX `ustar`.
- [ ] SHA-256 and MD5 checksums generated and matched.

