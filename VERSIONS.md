# Galaxy S8 Native Linux — Universal Version & Rollback Ledger (`VERSIONS.md`)

> [!IMPORTANT]
> **SINGLE SOURCE OF TRUTH FOR VERSIONING & ROLLBACK DECISIONS:**
> This file is auto-generated from [`VERSION_MANIFEST.json`](file:///e:/rouf/galaxy-s8/VERSION_MANIFEST.json) by [`scripts/version_manager.py`](file:///e:/rouf/galaxy-s8/scripts/version_manager.py).
> Every release, kernel, hardware package, daemon, desktop app build, and upstream Linux distribution is tracked here with its empirical verification outcome (`VERIFIED_WORKING`, `SUPERSEDED`, `READY_TO_TEST`, or `FAILED`) so we can make instant, zero-guesswork engineering and rollback decisions.

---

## 1. Active Production Versions

| Architectural Layer | Active Version | Canonical Artifact / File | Verification Status |
| :--- | :--- | :--- | :--- |
| **Odin AP Package** | `v3.0.0` | [`releases/Galaxy_S8_Linux_AP.tar`](file:///e:/rouf/galaxy-s8/releases/Galaxy_S8_Linux_AP.tar) | `[VERIFIED_WORKING]` |
| **Linux Kernel (`uname -r`)** | `4.4.111-s8-universal-v3` (`v3.0.0`) | [`kernel/arch/arm64/boot/Image`](file:///e:/rouf/galaxy-s8/kernel/arch/arm64/boot/Image) | `[VERIFIED_WORKING]` |
| **Next Planned Kernel** | `4.4.111-s8-universal-v3.1 (Maintenance)` | [`kernel/.config`](file:///e:/rouf/galaxy-s8/kernel/.config) | `[PLANNED]` |
| **Hardware Pack (`galaxy-s8-hw`)** | `v1.0.2` | [`packages/dist/galaxy-s8-hw_1.0.2_arm64.deb`](file:///e:/rouf/galaxy-s8/packages/dist/galaxy-s8-hw_1.0.2_arm64.deb) & [`.tar.gz`](file:///e:/rouf/galaxy-s8/packages/dist/galaxy-s8-hw-1.0.2-arm64.tar.gz) | `[VERIFIED_WORKING]` |
| **Native C Daemons Suite** | `v1.0.2` | [`src/drivers/s8_version.h`](file:///e:/rouf/galaxy-s8/src/drivers/s8_version.h) | `[VERIFIED_WORKING]` |
| **Hardware CLI (`s8ctl`)** | `v1.0.2` | [`src/control/s8ctl.py`](file:///e:/rouf/galaxy-s8/src/control/s8ctl.py) | `[VERIFIED_WORKING]` |
| **RWP Transport Protocol** | `rwp-v1.1.0` | [`src/drivers/s8_usb_agentd.c`](file:///e:/rouf/galaxy-s8/src/drivers/s8_usb_agentd.c) | `[VERIFIED_WORKING]` |
| **Desktop App (`S8 Imager`)** | `v2.6.0` | [`desktop-app/app/config.py`](file:///e:/rouf/galaxy-s8/desktop-app/app/config.py) | `[VERIFIED_WORKING]` |

---

## 2. Odin AP & Kernel Release History (Worked vs. Failed Decision Table)

| Version | Status | Date | Boot Size / Headroom | Kernel | Init Architecture | SHA-256 (Prefix) | Outcome & Rollback Notes |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `v3.0.0` | `[VERIFIED_WORKING]` **(ACTIVE)** | `2026-11-13` | 30.84 MiB (+9.16 MiB) | `4.4.111-s8-universal-v3` | Pure Native Linux /init -> switch_root -> systemd / OpenRC / procd PID 1 | `6d7992efb1e1...` | Compiled Kernel 4.4.111-s8-universal-v3 (#21) with CONFIG_USB_UAS=y, CONFIG_BRIDGE_NF_EBTABLES=y, CONFIG_ANDROID_PARANOID_NETWORK=n, fimc-is2 NULL guard, DECON2 unplug guard, and panic_on_oops=0 |
| `v2.0.2` | `[SUPERSEDED]` | `2026-11-13` | 30.79 MiB (+9.21 MiB) | `4.4.111-s8-universal-v2 #20` | Pure Native Linux /init -> switch_root -> systemd / OpenRC / procd PID 1 | `7a970379912b...` | Current active Universal AP. Supports multi-storage boot_target.conf (internal sda24, MicroSD image, MicroSD raw partition), universal init discovery (systemd, OpenRC, OpenWrt procd), cgroup v1 hierarchy mount for Docker/HAOS/LXC, 9 Calliope DSP firmwares, ConfigFS RNDIS+ACM, s8_usb_agentd, and s8_dp_daemon. |
| `v2.0.0` | `[SUPERSEDED]` | `2026-11-12` | 30.79 MiB (+9.21 MiB) | `4.4.111-s8-universal-v2 #20` | Pure Native Linux /init -> switch_root -> systemd PID 1 | `4de1bdd01c2d...` | First Pure Native Linux switch_root PID 1 release. Superseded by v2.0.2 which added multi-storage boot_target.conf, OpenWrt/Alpine/HAOS cgroup v1 mounts, and embedded /etc/s8-ap-version. |
| `v1.0.0` | `[VERIFIED_WORKING]` | `2026-11-11` | 35.56 MiB (+4.44 MiB) | `4.4.111-s8-universal-v1 (GCC 4.9 CFP)` | Android /init + sys.usb.ffs.ready=1 -> start_all.sh chroot | `4b5aec422167...` | Golden legacy fallback baseline using Samsung GCC 4.9 CFP kernel and Android init.rc trigger. Kept permanently in releases/history/ as emergency fallback. |
| `v0.9.0-exp` | `[FAILED]` | `2026-11-09` | N/A | `4.4.111 (GCC 13 + CONFIG_RKP_CFP=y)` | Experimental | `FAILED_BUILD_DO_NOT_USE` | FAILED (Finding 115): Compiled with modern GCC 13 while CONFIG_RKP_CFP=y was enabled. Exynos 8895 EL2 TrustZone micro-Hypervisor aborted cold boot at instruction 0 (0.43A quiescent current). Fixed by enforcing CONFIG_RKP_CFP=n. |
| `v0.8.0-exp` | `[FAILED]` | `2026-11-05` | N/A | `4.4.111` | Android /init with bind-mount in permissive.sh | `FAILED_BUILD_DO_NOT_USE` | FAILED (Rule 17): Bind-mounting /system_root/vendor/firmware over /etc/firmware in permissive.sh shadowed the 9 Calliope DSP firmwares, causing ABOX IPC timeout and s3c2410_wdt 15s watchdog panic at second 12. |

### Quick AP Rollback Commands
```powershell
# Roll back workspace AP to v2.0.2 (Pure Native Linux systemd PID 1):
python scripts/version_manager.py --rollback-ap 2.0.2

# Roll back workspace AP to v1.0.0 (Proven Android-init fallback):
python scripts/version_manager.py --rollback-ap 1.0.0

# Roll back AND flash live to connected Galaxy S8 (/dev/sda7 + /dev/sda8):
python scripts/version_manager.py --rollback-ap 2.0.2 --live
```

---

## 3. Hardware Support Package (`galaxy-s8-hw`) Release History

| Version | Status | Date | `.deb` Size & SHA-256 | `.tar.gz` Size & SHA-256 | Summary & Compatibility |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `v1.0.2` | `[VERIFIED_WORKING]` **(ACTIVE)** | `2026-11-13` | `310,958 B` (`d038619fd5...`) | `351,802 B` (`d254543a2a...`) | Added DisplayPort cursor 0xFF alpha fix + ensure_usb_host_mode() in exynos_dp_bridge, hotplug USB/BT mouse & keyboard forwarder s8_input_bridge + s8-input-bridge.service, USB-LAN Dongle Auto-DHCP in s8-usb-gadget.sh, and universal init support (systemd, OpenRC, OpenWrt procd, HAOS). |
| `v1.0.1` | `[SUPERSEDED]` | `2026-11-12` | `310,958 B` (`d038619fd5...`) | `351,802 B` (`d254543a2a...`) | Intermediate build with updated DisplayPort and input bridge prebuilts. |
| `v1.0.0` | `[VERIFIED_WORKING]` | `2026-11-12` | `303,442 B` (`5f0ad9e56a...`) | `340,850 B` (`94bcbdbad5...`) | Initial standalone hardware package release (PMIC 1500mA, Wi-Fi BCM4361, Calliope ALSA, exynos_dp_bridge, s8_button_daemon, s8ctl). Does not include s8_input_bridge or cursor alpha fix. |

---

## 4. Native C Hardware Daemons & CLI Version Matrix

| Component | Version | Status | Source Path | Prebuilt Binary Path | Role |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `s8_usb_agentd` | `v1.0.2` | `[VERIFIED_WORKING]` | `src/drivers/s8_usb_agentd.c` | `packages/galaxy-s8-hw/prebuilt/ap_ramdisk/sbin/s8_usb_agentd` | RWP v1.1.0 agent on :7860 (/rwp/v1/health, /rwp/v1/info, /rwp/v1/exec, /rwp/v1/pty for env=ap and env=os). |
| `s8_dp_daemon` | `v1.0.2` | `[VERIFIED_WORKING]` | `src/drivers/s8_dp_daemon.c` | `packages/galaxy-s8-hw/prebuilt/ap_ramdisk/sbin/s8_dp_daemon` | AP-level DisplayPort DECON2 (/dev/graphics/fb2) lifecycle manager, CLI terminal renderer, and /dev/shm/s8_dp_fb consumer. |
| `exynos_dp_bridge` | `v1.0.2` | `[VERIFIED_WORKING]` | `src/drivers/exynos_dp_bridge.c` | `packages/galaxy-s8-hw/prebuilt/exynos_dp_bridge` | X11 (:1) 60Hz VSYNC streamer to DECON2 fb2 with 0xFF cursor alpha fix and Type-C DFP/xHCI host role enforcement. |
| `s8_input_bridge` | `v1.0.2` | `[VERIFIED_WORKING]` | `src/drivers/s8_input_bridge.c` | `packages/galaxy-s8-hw/prebuilt/s8_input_bridge` | Hotplug /dev/input/event* USB & Bluetooth mouse/keyboard forwarder to X11 :1 via XTest. |
| `s8_button_daemon` | `v1.0.2` | `[VERIFIED_WORKING]` | `src/drivers/s8_button_daemon.c` | `packages/galaxy-s8-hw/prebuilt/ap_ramdisk/sbin/s8_button_daemon` | Physical chassis button handler (event3 Power, Vol Up/Down, Bixby short/double/long press). |
| `s8ctl` | `v1.0.2` | `[VERIFIED_WORKING]` | `src/control/s8ctl.py` | `src/control/s8ctl.py` | Unified hardware CLI for CPU/GPU boost, PMIC 1500mA, Wi-Fi, Bluetooth, Calliope audio, torch, haptics, and MicroSD. |

---

## 5. Upstream Linux Distributions Version & Compatibility Matrix (`distros/`)

| Distro ID | Upstream Version | Init System | Archive Filename | Size | SHA-256 (Prefix) | Status | Verified AP / HW | Empirical Test & Decision Notes |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `ubuntu-desktop-24.04` | `24.04.5 LTS` | `systemd` | `ubuntu-24.04.5-preinstalled-desktop-arm64.img.xz` | 3139.2 MB | `f4a333eccfda...` | `[VERIFIED_WORKING]` | AP `v2.0.2` / HW `v1.0.2` | Currently active on live phone (192.168.7.2). Boots with native systemd PID 1, GNOME/XFCE desktop on :1 (:5901 / :6080), DisplayPort fb2 with visible cursor + USB mouse/keyboard input bridge, Calliope audio, Wi-Fi, and PMIC 1500mA fast charging. |
| `ubuntu-server-24.04` | `24.04 LTS` | `systemd` | `ubuntu-24.04-server-rootfs-arm64.tar.xz` | 206.2 MB | `b68ef0444ca5...` | `[VERIFIED_WORKING]` | AP `v2.0.2` / HW `v1.0.2` | Verified booting cleanly with systemd PID 1, USB RNDIS SSH (:22), RWP (:7860), and galaxy-s8-hw_1.0.2_arm64.deb. |
| `ubuntu-base-24.04` | `24.04.5 LTS` | `systemd / sh` | `ubuntu-base-24.04.5-base-arm64.tar.gz` | 28.5 MB | `a91d5a930101...` | `[VERIFIED_WORKING]` | AP `v2.0.2` / HW `v1.0.2` | Verified ultra-light 30 MB base container rootfs; compatible with galaxy-s8-hw-universal-arm64.tar.gz. |
| `haos-18.4` | `18.4` | `systemd / container` | `haos_generic-aarch64-18.4.img.xz` | 327.5 MB | `16580d8baad9...` | `[VERIFIED_WORKING]` | AP `v2.0.2` / HW `v1.0.2` | Verified Home Assistant Core (:8123) and Observer (:4357) running with full cgroup v1 hierarchy, overlayfs, and network namespaces. |
| `steamos-arm` | `1.4` | `systemd` | `steamos-arm-sm8550-1.4.sau` | 77.5 MB | `668020fb2560...` | `[VERIFIED_WORKING]` | AP `v1.0.0` / HW `v1.0.2` | Verified booting SteamOS ARM64 desktop session on :1 (:5901 / :6080) under Single-OS Exclusive Deployment rule. |
| `kali-nethunter` | `2024.4` | `systemd` | `kali-nethunter-rootfs-minimal-arm64.tar.xz` | 120.0 MB | `96aeced81a85...` | `[VERIFIED_WORKING]` | AP `v1.0.0` / HW `v1.0.2` | Verified Kali ARM64 rootfs boot, SSH, and dpkg installation of galaxy-s8-hw_1.0.2_arm64.deb. |
| `debian-12` | `12.8 Bookworm` | `systemd` | `debian-12-generic-arm64.tar.xz` | 253.6 MB | `dbc01917c8ec...` | `[READY_TO_TEST]` | AP `v2.0.2` / HW `v1.0.2` | Downloaded and SHA-256 verified. Compatible with systemd PID 1 and galaxy-s8-hw_1.0.2_arm64.deb via copy-on-deploy. |
| `alpine-3.20` | `3.20.3` | `OpenRC (/sbin/init)` | `alpine-minirootfs-3.20.3-aarch64.tar.gz` | 3.8 MB | `041fa34a8178...` | `[READY_TO_TEST]` | AP `v2.0.2` / HW `v1.0.2` | Downloaded and SHA-256 verified. Supported by s8_pid1_boot.sh OpenRC init handoff and galaxy-s8-hw-1.0.2-arm64.tar.gz (/etc/init.d/s8-hardware). |
| `openwrt-23.05` | `23.05.5` | `procd (/etc/preinit -> /sbin/init)` | `openwrt-23.05.5-armsr-armv8-rootfs.tar.gz` | 3.9 MB | `bfce31bd8c98...` | `[READY_TO_TEST]` | AP `v2.0.2` / HW `v1.0.2` | Downloaded and SHA-256 verified. Supported by s8_pid1_boot.sh /etc/preinit discovery and galaxy-s8-hw-1.0.2-arm64.tar.gz (/etc/rc.local). |
| `arch-arm64` | `2024.11 Rolling` | `systemd` | `ArchLinuxARM-aarch64-latest.tar.gz` | 790.9 MB | `42a4eeaa0389...` | `[READY_TO_TEST]` | AP `v2.0.2` / HW `v1.0.2` | Downloaded and SHA-256 verified. Supported by systemd PID 1 and galaxy-s8-hw-1.0.2-arm64.tar.gz. |
| `raspios-bookworm` | `12 Bookworm` | `systemd` | `raspios-bookworm-arm64-desktop.img.xz` | 1142.0 MB | `5b2c3203d9e3...` | `[READY_TO_TEST]` | AP `v2.0.2` / HW `v1.0.2` | Downloaded and SHA-256 verified. Supported via GPT/MBR root partition extractor and galaxy-s8-hw_1.0.2_arm64.deb. |
