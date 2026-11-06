---
name: galaxy-s8-universal-installer
description: Operational runbook and architecture for the Galaxy S8 (SM-G950N) 2-Stage Universal Drag-and-Drop OS Installer. Enforces zero-guesswork, pre-flash mathematical verification, and autonomous multi-ROM deployment via USB MTP and mass storage.
---

# Galaxy S8 2-Stage Universal OS Installer Runbook

> [!IMPORTANT]
> **ANTI-HALLUCINATION & RELIABILITY DIRECTIVE:**
> Every step in this pipeline is strictly grounded in empirical Exynos 8895 (`dreamlteks`) hardware registers, Samsung S-Boot protocol behavior, and Linux kernel 4.4.111 driver constraints. Never guess, assume, or bypass automated pre-flash validation.

---

## 1. System Architecture Overview

The Universal Installer splits installation into two decoupled, failure-immune stages:

```
+-----------------------------------------------------------------------------------------+
| STAGE 1: The 83 MB Odin Base Flasher (100% Reliable Hardware Foundation)                |
| - Flashed via Odin v3.14 in AP slot (Takes 8-10 seconds)                               |
| - Unlocks MAX77865 1500mA Fast Charge & Brownout Protection                            |
| - Pins Octa-Core CPU @ 2.31 GHz (M2) / 1.69 GHz (A53) under 'performance' governor      |
| - Embeds all 9 Calliope DSP audio firmwares (zero IPC timeouts, zero watchdog loops)    |
| - Removes buggy V4L2 camera nodes (/dev/video100+) preventing kernel panics            |
| - Exposes USB Gadget MTP + ADB to Windows: Appears as "Galaxy S8 Installer" in This PC |
+-----------------------------------------------------------------------------------------+
                                           │
                                           ▼ (User drags OS image into the drive)
+-----------------------------------------------------------------------------------------+
| STAGE 2: Autonomous On-Device Multi-ROM Deployment (Unlimited Size, 54.8 GB Storage)   |
| - Watcher daemon detects completed transfer of target OS image                         |
| - Formats /dev/block/sda24 (USERDATA) with clean ext4 and proper block boundaries       |
| - Deploys rootfs, applies aid_* supplementary GIDs (1004..3011) & Docker cgroups        |
| - Pulses haptic motor (2x 150ms) and reboots straight into the selected Linux OS        |
+-----------------------------------------------------------------------------------------+
```

---

## 2. Multi-ROM Image Ecosystem & Naming Convention

Users can place any of the following images directly into the exposed drive:

| Image Filename | OS Profile | Target Use Case | Included Components |
| :--- | :--- | :--- | :--- |
| `ubuntu-macos-desktop.img` | GNOME 46 Desktop | Daily driver workstation | WhiteSur-Dark GTK4, Plank dock, nautilus root shim, TigerVNC (`:5901`), noVNC (`:6080`), DisplayPort 60Hz. |
| `ubuntu-homelab.img` | Smart Home & Server | 24/7 Home server | Docker engine, Home Assistant, Portainer, AdGuard Home, Glances, Ollama local LLM. |
| `ubuntu-minimal-cli.img` | Headless Server | Ultra-lightweight CLI | SSH (`:22`), Python 3.12, htop, s8ctl hardware center, uses <120 MB RAM. |

---

## 3. Strict Pre-Flash Validation Checklist (`build_rocksolid_boot.py`)

Before any Odin package is created or flashed, the automated validator MUST confirm:
1. **Partition Limit:** `boot.img` size `<= 41,943,040` bytes (`sda7` limit).
2. **Zero Rogue Loops:** `sbin/permissive.sh` contains ONLY `setenforce 0`. No background subshells, no mount polling.
3. **Firmware Integrity:** All 9 Calliope DSP audio firmware binaries exist in `etc/firmware/` and `vendor/firmware/` inside the CPIO archive.
4. **Zero Shadowing:** Ramdisk never mounts `/system_root` or external partitions over `/etc/firmware`.
5. **Clean Trigger:** `init.rc` triggers supervisor on `property:sys.usb.ffs.ready=1` (ADB root always online).
6. **Auto-Repair:** `exec /sbin/e2fsck -p /dev/block/sda24` runs before mounting `/data` to heal uncommitted dirty journals from abrupt power cuts in <200ms.

---

## 4. Operational Recovery Protocol

If the phone enters an unresponsive latch-off state after multiple crashes:
1. Keep the USB-C cable plugged into the PC.
2. Hold **Volume Down + Bixby + Power** (all three buttons) continuously for **12 seconds**.
3. Release immediately when Odin detects `0:[COM5]` (Samsung Download Mode).
4. Load `releases/Ubuntu_24.04_GalaxyS8_Full_Odin.tar` in the **AP** slot and click **Start** (8 seconds).
5. Unplug and re-plug the USB-C cable upon seeing green `PASS!`.
6. Phone boots into the USB MTP installer drive in **16.5 seconds**.

