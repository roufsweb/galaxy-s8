---
name: product-namespace-and-naming
description: Canonical naming convention and namespace standard for all kernels, boot images, Odin AP packages, hardware daemons, systemd services, distro packages, REST/RWP APIs, and UI components across the Galaxy S8 Native Linux project.
---

# Product Namespace & Naming Standard (`product-namespace-and-naming`)

> [!IMPORTANT]
> **UNIVERSAL OS-AGNOSTIC NAMING MANDATE:**
> This project transforms the Samsung Galaxy S8 (`SM-G950N` / Exynos 8895) into a universal native Linux computer capable of running **any** Linux distribution (Ubuntu, Debian, Alpine, Arch Linux ARM, Kali Linux, OpenWrt, Home Assistant OS, SteamOS ARM).
> **NEVER** hardcode single-distro names (such as `ubuntu`, `boot_ubuntu_autoboot.img`, `ubuntu_boot`, or `flash_ubuntu.bat`) into kernel artifacts, AP images, daemons, services, or host utilities.

---

## 1. Canonical Namespace Hierarchy

| Layer | Canonical Prefix / Namespace | Examples | Prohibited Legacy Names |
| :--- | :--- | :--- | :--- |
| **Product Brand** | `Galaxy S8 Linux` / `S8 Imager` | `S8 Imager`, `Galaxy S8 Hardware Center` | `Ubuntu Flasher`, `S8 Ubuntu Pack` |
| **Kernel `uname -r`** | `4.4.111-s8-universal-v<N>` | `4.4.111-s8-universal-v2` | `4.4.111-ubuntu`, `4.4.302-a2n` |
| **Odin AP Archive** | `Galaxy_S8_Linux_AP.tar` & `Galaxy_S8_Linux_AP_v<VER>.tar` | `releases/Galaxy_S8_Linux_AP.tar`, `releases/history/Galaxy_S8_Linux_AP_v2.0.2.tar` | `Ubuntu_24.04_GalaxyS8_Full_Odin.tar` |
| **Staging Boot Image** | `boot_universal_ap.img` & `boot_universal_ap_v<VER>.img` | `scratch/boot_universal_ap.img`, `releases/history/boot_universal_ap_v2.0.2.img` | `boot_ubuntu_autoboot.img` |
| **Tar Internal Images** | `boot.img`, `recovery.img` | Inside `Galaxy_S8_Linux_AP.tar` | Anything else (Odin requires exact names) |
| **C Hardware Daemons** | `s8_<subsystem>` or `exynos_<subsys>` | `s8_usb_agentd`, `s8_dp_daemon`, `s8_input_bridge`, `s8_button_daemon`, `exynos_dp_bridge` (`src/drivers/s8_version.h`) | `ubuntu_boot_daemon`, `test_dp` |
| **CLI Hardware Tool** | `s8ctl` | `/usr/local/bin/s8ctl` (`S8CTL_VERSION`) | `ubuntu-ctl`, `phone-ctl` |
| **Init / Systemd Units** | `s8-<subsystem>.service` | `s8-pmic-init.service`, `s8-usb-gadget.service`, `s8-dp-bridge.service`, `s8-input-bridge.service` | `ubuntu_boot`, `start_all.service` |
| **Hardware Packages** | `galaxy-s8-hw` | `galaxy-s8-hw_1.0.2_arm64.deb`, `galaxy-s8-hw-1.0.2-arm64.tar.gz`, `galaxy-s8-hw-universal-arm64.tar.gz` | `s8-ubuntu-pack.deb` |
| **Version Ledger** | `VERSION_MANIFEST.json`, `VERSIONS.md` | `VERSION_MANIFEST.json`, `VERSIONS.md`, `scripts/version_manager.py` | Unversioned ad-hoc files |
| **Transport Protocol** | `rwp-v1` (`/rwp/v1/*`) | `/rwp/v1/health`, `/rwp/v1/info`, `/rwp/v1/exec`, `/rwp/v1/pty` | `/ubuntu/exec` |
| **Rootfs Mountpoints** | `/mnt/rootfs` (staging) or `/` (PID 1) | `/mnt/rootfs` | `/mnt/ubuntu` |

---

## 2. Binary & Service Naming Matrix

### 2.1 Core C Binaries (`src/drivers/` -> `/sbin/` or `/usr/local/bin/`)
1. **`s8_usb_agentd`** (`src/drivers/s8_usb_agentd.c`):
   - Runs on `:7860` across USB RNDIS (`192.168.7.2`), Wi-Fi, or USB Ethernet.
   - Implements the `rwp-v1` protocol (`/rwp/v1/health`, `/rwp/v1/info`, `/rwp/v1/exec`, `/rwp/v1/pty`).
2. **`s8_dp_daemon`** (`src/drivers/s8_dp_daemon.c`):
   - Universal DisplayPort `DECON2` (`/dev/graphics/fb2`) lifecycle manager, pure CLI terminal renderer, and `/dev/shm/s8_dp_fb` consumer.
3. **`exynos_dp_bridge`** (`src/drivers/exynos_dp_bridge.c`):
   - X11 (`:1`) frame capturer, alpha-correct hardware cursor compositor, and Type-C DFP/xHCI host role arbitrator (`ensure_usb_host_mode()`).
4. **`s8_input_bridge`** (`src/drivers/s8_input_bridge.c`):
   - Hotplug `/dev/input/event*` USB & Bluetooth mouse/keyboard forwarder to X11 `:1` via `XTest`.
5. **`s8_button_daemon`** (`src/drivers/s8_button_daemon.c`):
   - Physical chassis button daemon (`event3` Power, Volume Up/Down, Bixby short/double/long press).
6. **`s8ctl`** (`src/control/s8ctl`):
   - Unified POSIX/Python CLI for CPU/GPU boost, PMIC 1500mA fast charge, Wi-Fi, Bluetooth, Calliope audio, torch, haptics, and MicroSD.

### 2.2 Systemd & Universal Init Service Names
All service units inside `packages/galaxy-s8-hw/systemd/` MUST use the `s8-` prefix:
- `s8-pmic-init.service` — MAX77865 1500mA fast charge & V4L2 camera panic guard (`rm -f /dev/video[1-9][0-9]*`).
- `s8-usb-gadget.service` — Dual ConfigFS USB RNDIS (`192.168.7.2`) + CDC-ACM Serial (`/dev/ttyGS0`) + `s8_usb_agentd` + USB Ethernet DHCP auto-configuration.
- `s8-wifi-init.service` — Broadcom BCM4361 `dhd` firmware/nvram/clm loader & `wpa_supplicant` / AP failover.
- `s8-audio-init.service` — Calliope ABOX DSP & CS47L92 / MAX98506 ALSA routing.
- `s8-modem-init.service` — Shannon 359 LTE modem (`cbd`) & `rmnet0..7` setup.
- `s8-vnc.service` — TigerVNC `:1` (`:5901`) & noVNC WebSockets (`:6080`).
- `s8-desktop.service` — Desktop session manager.
- `s8-dp-bridge.service` — `exynos_dp_bridge` X11-to-DisplayPort streamer.
- `s8-input-bridge.service` — `s8_input_bridge` USB/BT mouse & keyboard forwarder.
- `s8-buttons.service` — `s8_button_daemon` chassis key handler.

---

## 3. Pre-Commit & Build Naming Audit Checklist

Before packaging any release or committing code:
1. Verify zero occurrences of `boot_ubuntu_autoboot.img` in active builders (`scripts/build_universal_ap.py` must output `scratch/boot_universal_ap.img` and `releases/Galaxy_S8_Linux_AP.tar`).
2. Verify all host scripts in root and `releases/` use OS-agnostic names (`Launch_S8_Imager.bat`, `connect_shell.bat`, `connect_desktop.bat`).
3. Verify all API endpoints in `desktop-app/` and `s8_usb_agentd` adhere to `/api/*` (local backend) and `/rwp/v1/*` (device transport).

