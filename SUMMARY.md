# Project Summary: Samsung Galaxy S8 (SM-G950N) Native Linux Platform

Maintained by [roufsweb](https://github.com/roufsweb)

> [!CRITICAL]
> **STRICT HEADLESS HARDWARE MANDATE:**
> The internal OLED screen is completely **MISSING / DISCONNECTED** (`lcdtype=-1`).
> Never instruct the user to observe on-screen visuals or press on-screen elements.
> Guide all physical procedures strictly via vibration motor pulses, exact seconds countdowns, and host PC USB enumeration (`PID_685D`, `PID_6860`, `adb devices`).

---

## 1. Executive Overview
This project transforms a screenless, Korean-variant Samsung Galaxy S8 (`SM-G950N`, Exynos 8895) into a high-performance native Linux (Ubuntu 24.04.5 LTS Noble Numbat ARM64) server and desktop workstation with Docker CE, GNOME 46 macOS Sonoma GUI, hardware USB-C DisplayPort 1080p60 video output, transparent ALSA audio routing, and a 1-click standalone Odin installer.

---

## 2. Hardware Specifications

| Component | Specification | Technical Implementation Notes |
| :--- | :--- | :--- |
| **Model** | Samsung Galaxy S8 Korean (`SM-G950N`) | Codename: `dreamlteks` / `dreamltekor` |
| **SoC** | Samsung Exynos 9 Octa 8895 (10nm FinFET) | 8 Cores: 4x Exynos M2 @ 2.314 GHz + 4x Cortex-A53 @ 1.690 GHz |
| **GPU** | ARM Mali-G71 MP20 | 20 execution cores locked at 546 MHz Booster mode |
| **RAM** | 4 GB LPDDR4x (PoP) | 1794 MHz high-bandwidth memory; 3.4 GB available to Linux userspace |
| **Internal Storage**| 64 GB UFS 2.1 (KLUCG4J1ED) | Dynamic online `resize2fs` scaling to 54.81 GB (and 112 GB on 128 GB models) |
| **External Storage**| DW MMC Host Controller (`11500000.dwmmc2`)| Auto-mounted MicroSD card (`/dev/block/mmcblk0`) at `/media/sdcard` |
| **Video Output** | USB-C DisplayPort 1.2 Alt Mode | Hardware DECON2 (`/dev/graphics/fb2`) 1080p60 with Porter-Duff Over cursor |
| **Power Management**| Maxim MAX77865 PMIC | Hardware register bypass to 1,500 mA fast charging and 4.3V brownout UVLO |
| **Audio Subsystem** | ABOX Calliope DSP (1.18 GHz) | Maxim MAX98506 speaker (`hw:0,0`) + CS47L92 DMIC1 mic (`hw:0,9`) |
| **Chassis Buttons** | GPIO Keys (`/dev/input/event3`) | Power (DPMS/Reboot), Vol Up/Down (Audio/Haptics), Bixby (Terminal/Torch) |
| **Wireless** | Broadcom BCM4361 | Dual-Band (2.4G & 5G VHT80), SD drop auto-config, SoftAP hotspot fallback |
| **Security / Fuse**| Samsung Knox | State: `0x1` (Unlocked bootloader, custom DEFEX-free kernel) |

---

## 3. Release Assets Inventory

* [`releases/Ubuntu_24.04_GalaxyS8_Full_Standalone_Odin.tar`](file:///e:/rouf/galaxy-s8/releases/Ubuntu_24.04_GalaxyS8_Full_Standalone_Odin.tar): Complete standalone 3.37 GB Odin AP package (`boot.img` + `recovery.img` + `userdata.img.lz4`).
* [`releases/Ubuntu_24.04_GalaxyS8_Full_Odin.tar`](file:///e:/rouf/galaxy-s8/releases/Ubuntu_24.04_GalaxyS8_Full_Odin.tar): Compact 88.4 MB kernel-only Odin package.
* [`releases/TESTING_RUNBOOK.md`](file:///e:/rouf/galaxy-s8/releases/TESTING_RUNBOOK.md): Step-by-step verification guide from stock ROM flash to desktop.
* [`releases/connect_desktop.bat`](file:///e:/rouf/galaxy-s8/releases/connect_desktop.bat): One-click USB forwarder and browser launcher for noVNC web desktop (`:6080`).
* [`releases/connect_shell.bat`](file:///e:/rouf/galaxy-s8/releases/connect_shell.bat): One-click root interactive terminal into Ubuntu 24.04 LTS.

---

## 4. Documentation & Governance Skills

* **`project-findings-manager`** (`.agent/skills/project-findings-manager/`): Enforces autonomous, zero-delay logging of all hardware, kernel, power management, and userland findings into [`FINDINGS.md`](file:///e:/rouf/galaxy-s8/FINDINGS.md) (73 findings logged).
* **`project-history-manager`** (`.agent/skills/project-history-manager/`): Maintains the chronological execution ledger in [`HISTORY.md`](file:///e:/rouf/galaxy-s8/HISTORY.md) (35 tasks logged) and provides `scripts/search_history.py`.
* **`privacy-guard`** (`.agent/skills/privacy-guard/`): Pre-commit hook and sanitizer (`scripts/sanitize_repo.py`) protecting against secret and credential leakage.
* **`galaxy-s8-native-linux`** (`.agent/skills/galaxy-s8-native-linux/`): Master operational runbook for live kernel, desktop, and DisplayPort maintenance.
