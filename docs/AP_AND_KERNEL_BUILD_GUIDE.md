# Samsung Galaxy S8 (`SM-G950N` / Exynos 8895) — AP & Kernel Build Engineering Guide (`docs/AP_AND_KERNEL_BUILD_GUIDE.md`)

> [!IMPORTANT]
> **AUTHORITATIVE MASTER REFERENCE:**
> This document details the exact, mathematically verified procedures for compiling the custom Linux kernel and building the Samsung Odin `AP` slot package (`boot.img`, `recovery.img`, CPIO ramdisk, Calliope DSP firmwares, and Odin `.tar` container) for the headless Samsung Galaxy S8 (`SM-G950N`, Exynos 8895, `dreamlteks`).

---

## 1. Architectural Overview & Partition Boundaries

The Samsung Galaxy S8 Exynos 8895 (`SM-G950N`) boots via Samsung's S-Boot primary bootloader. In the Samsung flashing schema, the **AP (Application Processor)** tar archive is flashed to eMMC/UFS partitions.

### Partition Map (`/dev/block/sda` UFS 2.1 Storage)
| Partition | Block Node | Allocated Size | Hard Limit | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| `BOOT` | `/dev/block/sda7` | `41,943,040` B (`40.0 MB`) | **40 MB Hard Stop** | Primary kernel + initial ramdisk |
| `RECOVERY` | `/dev/block/sda8` | `41,943,040` B (`40.0 MB`) | **40 MB Hard Stop** | Fail-safe boot image (exact twin of BOOT) |
| `USERDATA` | `/dev/block/sda15` | `~53.7 GB` (64GB model) | Unallocated OS space | Holds `/data/linux/rootfs.img` or raw ext4 OS |
| `RADIO` | `/dev/block/sda10` | `~64 MB` | Shannon 359 Baseband | CP Modem firmware (`modem.bin`) |
| `EFS` | `/dev/block/sda3` | `~20 MB` | Calibration & NVRAM | Radio NVRAM & Device Identifiers |

> [!CAUTION]
> **CRITICAL PARTITION SIZE GUARD:**
> Any `boot.img` or `recovery.img` exceeding **`41,943,040` bytes (`40 MB`)** will trigger an immediate Odin write failure (`ODIN WRITE FAIL: RECOVERY`) or cause silent flash truncation and bootloop. All ramdisk assets must be mathematically monitored.

---

## 2. Kernel Compilation (Exynos 8895 Linux 4.4.111)

### 2.1 Build Environment & Toolchain
* **Host OS:** Linux (Ubuntu 22.04 LTS or WSL2 on Windows 11).
* **Cross-Compiler:** `aarch64-linux-android-4.9` (Official Samsung CFP Toolchain) or `aarch64-linux-gnu-gcc-10` (with CFP disabled).
* **Architecture:** `ARCH=arm64`, `CROSS_COMPILE=aarch64-linux-android-`.

> [!CAUTION]
> **CRITICAL TOOLCHAIN & EL2 TRUSTZONE CFP WARNING (SEE FINDING 115):**
> Samsung Exynos 8895 enforces hardware-level **uH (micro-Hypervisor)** and **CFP (Control Flow Protection / JOPP)** executing at **Exception Level 2 (EL2)** in TrustZone.
> **DO NOT** compile production kernels using modern generic cross-compilers (such as GCC 11, 12, or 13) with `CONFIG_RKP_CFP=y`. Modern compilers emit branch relocations, PAC/BTI hints, and register allocations that trigger an immediate EL2 monitor abort during cold boot in early `head.S`, freezing the SoC at instruction 0 (drawing 0.43A quiescent current with no haptics or ADB).
> **Production Rules:**
> 1. Always use the official Samsung CFP toolchain: `aarch64-linux-android-4.9-cfp` (located at `/root/s8_kernel_build/scripts/toolchain/gcc-cfp/`).
> 2. If modern GCC (GCC 10+) must be used, you **MUST** set `CONFIG_RKP_CFP=n` and `CONFIG_RKP_CFP_JOPP=n` in defconfig.

```bash
export ARCH=arm64
export ANDROID_MAJOR_VERSION=p
export PATH="/root/s8_kernel_build/scripts/toolchain/gcc-cfp/gcc-cfp-jopp-only/aarch64-linux-android-4.9/bin:$PATH"
export CROSS_COMPILE=aarch64-linux-android-
export KCFLAGS="-w -Wno-error"
```

### 2.2 Kernel Configuration Essentials
Start from `arch/arm64/configs/exynos8895-dreamlte_defconfig` and apply these strict production overrides:

1. **DEFEX Removal (Mandatory for Linux Userland):**
   ```ini
   # CONFIG_SECURITY_DEFEX is not set
   # CONFIG_SECURITY_DEFEX_BOOT is not set
   # CONFIG_SECURITY_DEFEX_SYS_SECURE is not set
   ```
   *Rationale:* Samsung DEFEX actively intercepts system calls (`sys_mount`, `sys_chroot`, `sys_ptrace`) and panics the kernel or silently kills unprivileged processes.

2. **Container & Namespace Subsystems:**
   ```ini
   CONFIG_NAMESPACES=y
   CONFIG_UTS_NS=y
   CONFIG_IPC_NS=y
   CONFIG_USER_NS=y
   CONFIG_PID_NS=y
   CONFIG_NET_NS=y
   CONFIG_CGROUPS=y
   CONFIG_CGROUP_DEVICE=y
   CONFIG_CGROUP_CPUACCT=y
   CONFIG_CGROUP_SCHED=y
   ```
   *Rationale:* Required for Docker, systemd containers, and isolated Linux namespaces.

3. **DisplayPort & DECON Subsystems:**
   ```ini
   CONFIG_EXYNOS_DISPLAYPORT=y
   CONFIG_EXYNOS_DECON_FB=y
   CONFIG_EXYNOS_ION=y
   ```

4. **ABOX Calliope DSP Audio Subsystems:**
   ```ini
   CONFIG_SND_SOC_SAMSUNG_ABOX=y
   CONFIG_SND_SOC_SAMSUNG_MADERA=y
   CONFIG_SND_SOC_CS47L92=y
   ```

5. **TCPMSS Compilation Bug Workaround:**
   ```ini
   # CONFIG_NETFILTER_XT_TARGET_TCPMSS is not set
   ```

### 2.3 Compiling the Kernel & Generating DTB
```bash
# 1. Prepare configuration
make exynos8895-dreamlte_defconfig
# Apply custom config overrides
make olddefconfig

# 2. Compile Kernel Image
make -j$(nproc) Image
make dtbs

# 3. Assemble Device Tree Blob for Korean SM-G950N Rev 11 hardware
./scripts/dtbtool_exynos/dtbtool -s 2048 \
    --platform 0x50a6 \
    --subtype 0x217584da \
    -o arch/arm64/boot/dtb_rev11.img \
    arch/arm64/boot/dts/exynos/exynos8895-dreamlte_kor_11.dtb
```
* **Output 1:** `arch/arm64/boot/Image` (`~27-30 MB`)
* **Output 2:** `arch/arm64/boot/dtb_rev11.img` (`~2 MB`)

---

## 3. AP Package & Ramdisk Construction Pipeline

Building the AP package requires packing the kernel image, DTB, and a custom CPIO ramdisk into an Android boot image format (v0) and archiving it as an Odin `.tar`.

### 3.1 Ramdisk Structure & Font Trimming
The base ramdisk originates from TWRP (`archive/boot_twrp_exact.tar`). To stay well beneath the 40 MB partition boundary, unused TWRP assets are purged:
* **Purged Assets:**
  - `twres/fonts/DroidSansFallback.ttf` (~5.2 MB)
  - `twres/fonts/NotoSansCJKjp-Regular.ttf` (~3.5 MB)
  - `sbin/libclang_rt.ubsan_standalone-aarch64-android.so` (~1.4 MB)
* **Total Space Saved:** **~10.1 MB**, ensuring the final compressed ramdisk remains under `10.5 MB` and the total `boot.img` stays under `39 MB`.

### 3.2 Embedding the 9 Calliope DSP Audio Firmwares
The Exynos 8895 ABOX Calliope DSP requires 9 firmware binaries to operate without IPC watchdog panics. These **MUST** be placed in both `/etc/firmware/` and `/vendor/firmware/` in the CPIO ramdisk:
1. `calliope_sram.bin` (SRAM DSP firmware, 1.18 GHz clock)
2. `calliope_dram.bin` (DRAM staging blob)
3. `calliope_iva.bin` (IVA hardware accelerator)
4. `dsm.bin` (Dynamic Speaker Management)
5. `AP_AUDIO_SLSI.bin` (ABOX core parameter calibration)
6. `APBargeIn_AUDIO_SLSI.bin` (Acoustic Echo Cancellation / Barge-in)
7. `SoundBoosterParam.bin` (MAX98506 amplifier boost profile)
8. `APBiBF_AUDIO_SLSI.bin` (Beamforming DSP filter)
9. `dsm_tune.bin` (DSM acoustic tuning tables)

### 3.3 Root Cgroup Task Escape (`libprocessgroup` Immunity)
When an Android `init.rc` service terminates, Android `init` / `libprocessgroup` sends `SIGKILL` to all processes in `/acct/uid_0/pid_<pid>/`. To keep Linux background services (`sshd`, `TigerVNC`, `exynos_dp_bridge`, `dockerd`) alive indefinitely:
* **Mandatory Script Header:**
  ```sh
  #!/sbin/sh
  echo $$ > /acct/tasks 2>/dev/null || true
  ```
  This immediately moves the process into root cgroup `/acct/`, rendering all spawned children immune to `libprocessgroup` termination.

### 3.4 PMIC MAX77865 Fast-Charging Unlock
Standard USB ports default `CHG_CNFG_09` to 450 mA. The boot sequence must write the 5 register sequence:
```sh
echo "0xBD 0x6C" > /sys/class/power_supply/max77865-charger/data  # Unlock CHGPROT
echo "0xC3 0x61" > /sys/class/power_supply/max77865-charger/data  # VCHGIN_REG UVLO = 4.3V + DISSKIP
echo "0xC0 0x3C" > /sys/class/power_supply/max77865-charger/data  # CHG_CNFG_09 = 1500mA input limit
echo "0xB9 0x9E" > /sys/class/power_supply/max77865-charger/data  # CHG_CNFG_02 = 1500mA fast charge
echo "0xB7 0x05" > /sys/class/power_supply/max77865-charger/data  # MODE_BUCK | MODE_CHGR
```

### 3.5 Auto-Boot Triggering in `init.rc`
Android `init.rc` must trigger `ubuntu_boot` when `sys.usb.ffs.ready=1` so `adbd` is operational before userland launches:
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

---

## 4. Boot Image Header Assembly (`mkbootimg` Specifications)

The Samsung Exynos 8895 boot image uses Android Boot Image Header Format Version 0:
* **Page Size:** `2048` bytes (`0x800`)
* **Base Address:** `0x10000000`
* **Kernel Offset:** `0x00008000` (Loaded at `0x10008000`)
* **Ramdisk Offset:** `0x01000000` (Loaded at `0x11000000`)
* **Second / DTB Offset:** `0x00000000` (or appended DTB in kernel trailer)
* **Kernel Command Line:**
  ```text
  console=ram loglevel=4 androidboot.hardware=samsungexynos8895 androidboot.selinux=permissive loop.max_part=7
  ```

### Header Byte Structure (`struct boot_img_hdr`):
```text
+---------------------------------+
| Magic: "ANDROID!" (8 bytes)     |
+---------------------------------+
| Kernel Size (4 bytes, uint32)   |
| Kernel Address (4 bytes)        |
+---------------------------------+
| Ramdisk Size (4 bytes, uint32)  |
| Ramdisk Address (4 bytes)       |
+---------------------------------+
| Second Size (0) / Address       |
+---------------------------------+
| Kernel Tags Address             |
| Page Size: 2048 (4 bytes)       |
+---------------------------------+
| Header Version: 0               |
+---------------------------------+
| Product Name (16 bytes)         |
+---------------------------------+
| Command Line (512 bytes)        |
+---------------------------------+
| SHA-1 / Checksum (32 bytes)     |
+---------------------------------+
| Extra Cmdline (1024 bytes)      |
+---------------------------------+
```

---

## 5. Automated Python Builder (`build_rocksolid_boot.py`)

The automated tool [`scratch/build_rocksolid_boot.py`](file:///e:/rouf/galaxy-s8/scratch/build_rocksolid_boot.py) executes the full mathematical pipeline:

1. **Extracts:** Unpacks raw CPIO ramdisk from base `archive/boot_twrp_exact.tar`.
2. **Filters & Embeds:** Strips DroidSans and NotoSans fonts; writes Calliope 9 firmwares into `etc/firmware/` and `vendor/firmware/`.
3. **Injects Supervisor:** Injects `/sbin/s8_typec_daemon.py`, `/sbin/boot_supervisor.sh`, and root cgroup task escape into `/sbin/permissive.sh`.
4. **Encodes CPIO:** Formats entries in SVR4 CPIO standard (`070701` magic) aligned to 4-byte boundaries.
5. **Compresses:** Compresses ramdisk via LZMA/GZIP.
6. **Packs Boot Image:** Reassembles the 2048-byte aligned `boot.img`.
7. **Verifies Hard Limits:** Verifies `len(boot.img) <= 41,943,040 bytes`.
8. **Packages Odin AP Tarball:** Generates POSIX `ustar` tarball containing:
   * `boot.img` (Flashes to `/dev/block/sda7`)
   * `recovery.img` (Flashes to `/dev/block/sda8` as an exact fail-safe twin)

```powershell
python scratch/build_rocksolid_boot.py [custom_kernel_path]
```

### Outputs:
* `scratch/boot_ubuntu_autoboot.img` (`41,226,256` B $\le$ `41,943,040` B hardware limit, 716 KB margin)
* `releases/Galaxy_S8_Linux_AP.tar` (`82,462,720` B USTAR AP package)

---

## 6. Kernel #9 Production Hardening Milestone

Kernel #9 incorporates significant structural hardening over Kernel #8:

1. **Permanent Source-Level DEFEX/FIVE & RKP_NS_PROT Bypass:**
   - Eliminates fragile binary hex patching (`0x156c8c` -> `0x17ffff73`) that shifted between compiler passes.
   - Patched `fs/exec.c`: `invalid_drive(bprm)` unconditionally returns `0` and illegal execution panic checks are safely disabled.
   - Patched `security/defex_lsm/defex_procs.c`: `task_defex_enforce()` unconditionally returns `DEFEX_ALLOW` (`0`).
   - Disassembly verified with `aarch64-linux-gnu-objdump`: `task_defex_enforce` compiles directly to `mov w0, #0; ret`.

2. **Built-In High-Speed ZRAM + LZ4 RAM Compression:**
   - Compiled with `CONFIG_ZSMALLOC=y`, `CONFIG_ZRAM=y`, `CONFIG_ZRAM_LZ4_COMPRESS=y`, `CONFIG_CRYPTO_LZ4=y`.
   - `scratch/start_all.sh` initializes a 2 GB `/dev/zram0` device at boot using `lz4` compression algorithm, `swapon -p 100`, `vm.swappiness=100`, and `vm.page-cluster=0` for zero-latency memory expansion.

3. **In-Tree Hardware-Accelerated WireGuard (`wireguard-linux-compat`):**
   - Cleanly integrated upstream `wireguard-linux-compat` directly into `net/wireguard/`.
   - Compiled with `CONFIG_WIREGUARD=y` and `CONFIG_NET_UDP_TUNNEL=y` using ARM64 NEON crypto acceleration (`chacha20_neon`, `poly1305-arm64`).

4. **Userspace Docker & Container Hardening:**
   - Enforced `iptables-legacy` and `ip6tables-legacy` before starting `dockerd`.
   - Structured `/etc/docker/daemon.json` with `overlay2` storage driver and `cgroupfs` exec-opts.
   - Automatic cgroups v1 hierarchy mount loop (`cpuset`, `cpu`, `cpuacct`, `memory`, `devices`, `freezer`, `blkio`, `net_cls`, `pids`).

---

## 7. Flashing Procedures

### 6.1 Flashing via Odin (Windows GUI / Download Mode)
1. Keep the phone plugged into PC via USB-C.
2. Hold **Volume Down + Bixby + Power** for **11–13 seconds** until Download Mode enumerates (`PID_685D` on `COM17`).
3. Open Odin v3.14.4.
4. Select `releases/Galaxy_S8_Linux_AP.tar` in the **AP** slot.
5. Uncheck "Auto Reboot" (recommended).
6. Click **Start** $\rightarrow$ Wait for green `PASS!`.
7. **Post-Flash Re-Plug Rule:** Unplug and re-plug USB-C to clear Windows driver suspension and bring ADB online.

### 6.2 Flashing Live via ADB (Without Odin)
```powershell
adb push scratch/boot_ubuntu_autoboot.img /tmp/boot.img
adb shell "dd if=/tmp/boot.img of=/dev/block/sda7 bs=4096 conv=fsync"
adb shell "dd if=/tmp/boot.img of=/dev/block/sda8 bs=4096 conv=fsync"
adb shell "rm /tmp/boot.img && sync"
```

### 7.3 Cold Reset & Power-Loss Recovery Verification Checklist
When testing whether custom kernels and boot images survive hard power-loss, complete battery drain, or sudden disconnects:

> [!WARNING]
> **PHYSICAL BATTERY DISCONNECT RISK:**
> Repeatedly unplugging the battery cable wears down the delicate FPC motherboard socket and risks bending microscopic gold pins (rated for only ~20-30 cycles). **Use the 3 safe software cold-reset methods below**, which exercise the exact same S-Boot, PMIC, and EL2 hardware reset pathways without physical wear:

1. **PMIC Hardware Power-Latch Cold Reset (30-Second Button Combo):**
   * Keep phone connected to PC/charger.
   * Hold **Volume Down + Bixby + Power** for **30 seconds** continuously.
   * *Mechanism:* Overrides the MAX77865 PMIC watchdog latch, dropping `EN_BUCK`, dropping all SoC voltage rails, wiping DRAM retention, and initiating a true cold hardware boot through S-Boot and EL2.
2. **SoC Watchdog Hard Reset via SysRq:**
   * Run:
     ```powershell
     adb shell "echo b > /proc/sysrq-trigger"
     ```
   * *Mechanism:* Triggers an immediate hardware reboot without clean unmounting, validating `e2fsck -p -y` journal recovery and autonomous `/data/linux/start_all.sh` service bringup.
3. **Download Mode Cold Power-Cycle:**
   * Hold **Volume Down + Bixby + Power** for 12 seconds to enter Odin Download Mode.
   * From Download Mode, hold **Volume Down + Power** for 7 seconds to force a cold SoC reset from S-Boot.
