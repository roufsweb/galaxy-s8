---
name: galaxy-s8-native-linux
description: Comprehensive operational runbook for building custom kernels, repacking boot images, deploying native Ubuntu ARM64 rootfs, and managing headless DisplayPort operation on the Samsung Galaxy S8 (Exynos SM-G950N).
---

# Samsung Galaxy S8 (SM-G950N) Native Linux Runbook

> [!CRITICAL]
> **HEADLESS HARDWARE REMINDER — NO INTERNAL DISPLAY:**
> The physical OLED display is missing / disconnected (`lcdtype=-1`).
> Never ask the user to check on-screen prompts or watch for logos/splashes.
> All instructions must rely solely on haptic feedback (vibrations), precise second counts, and PC USB status (`PID_685D`, `PID_6860`, `adb devices`).

## Overview
This skill guides the agent and developer through compiling kernels, packaging boot images, deploying Ubuntu rootfs, and debugging headless hardware on the Korean Samsung Galaxy S8 (`dreamlteks` / `universal8895`).

---

## 1. Kernel Compilation Procedure

### Directory & Toolchain
* Source Tree: `E:\rouf\galaxy-s8\galaxy-s8-kvm-kernel`
* Toolchain: GCC 4.9 bundled at `scripts/toolchain/gcc-cfp/gcc-cfp-jopp-only/aarch64-linux-android-4.9/bin`
* Cross Compile Prefix: `aarch64-linux-android-`

### Build Command Sequence (Bash / WSL / Linux)
```bash
cd /path/to/galaxy-s8-kvm-kernel

# 1. Environment Exports
export ARCH=arm64
export ANDROID_MAJOR_VERSION=p
export PATH=$(pwd)/scripts/toolchain/gcc-cfp/gcc-cfp-jopp-only/aarch64-linux-android-4.9/bin:$PATH
export CROSS_COMPILE=aarch64-linux-android-

# 2. Defconfig Generation
make clean && make mrproper
make exynos8895-dreamltekor_defconfig

# 3. Kernel Compilation
make -j$(nproc)
```

---

## 2. Boot Image Repacking (AIK-Linux)

1. Unpack original stock `boot.img` using Android Image Kitchen:
   ```bash
   cd AIK-Linux
   ./unpackimg.sh boot.img
   ```
2. Copy newly compiled kernel image and generated DTB:
   ```bash
   cp ../arch/arm64/boot/Image split_img/boot.img-zImage
   cp ../arch/arm64/boot/dtb.img split_img/boot.img-dt
   ```
3. Repack the boot image:
   ```bash
   ./repackimg.sh
   mv image-new.img boot_custom.img
   ```
4. Package into an Odin-flashable tarball:
   ```bash
   tar -H ustar -c boot_custom.img > boot_custom.tar
   ```

---

## 3. Headless Blind Flashing (Odin Download Mode)

Because the phone has no screen:
1. Ensure the phone is completely off (hold **Power + Volume Down** for 12 seconds with USB cable disconnected).
2. Press and hold **Volume Down + Bixby**.
3. Plug in the USB-C cable connected to the host PC.
4. Release buttons, then press **Volume Up** once to confirm entry into Download Mode.
5. In Odin on PC:
   - Verify `ID:COM` turns blue/green with status `Added!`.
   - Place the `.tar` image into the **AP** slot.
   - Click **Start**. The phone will flash and reboot automatically.

---

## 4. Headless Android Setup & ADB Configuration

When booting Android for the first time without a display:
```bash
# Bypass Setup Wizard completely
adb wait-for-device
adb shell settings put global setup_wizard_has_run 1
adb shell settings put secure user_setup_complete 1
adb shell pm disable-user com.google.android.setupwizard
adb shell pm disable-user com.sec.android.app.SecSetupWizard

# Disable lockscreen
adb shell locksettings set-disabled true

# Launch scrcpy for instant PC GUI control
scrcpy --stay-awake --turn-screen-off
```

---

## 5. Docker Kernel Configuration Checklist

Before compiling the kernel, ensure these flags are active in `arch/arm64/configs/exynos8895-dreamltekor_defconfig`:
```ini
CONFIG_NAMESPACES=y
CONFIG_CGROUPS=y
CONFIG_CGROUP_DEVICE=y
CONFIG_CGROUP_PIDS=y
CONFIG_MEMCG=y
CONFIG_OVERLAY_FS=y
CONFIG_BRIDGE=y
CONFIG_VETH=y
CONFIG_IP_NF_IPTABLES=y
CONFIG_IP_NF_FILTER=y
CONFIG_IP_NF_NAT=y
CONFIG_IP_NF_TARGET_MASQUERADE=y
```

