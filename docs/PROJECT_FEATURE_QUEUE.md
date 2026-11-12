# Galaxy S8 Native Linux & S8 Imager — Project Feature Queue (`docs/PROJECT_FEATURE_QUEUE.md`)

This document tracks all planned, in-progress, and queued features across the **Device AP (Kernel/Ramdisk)**, **Backend Server Engine**, and **Frontend Desktop UI**.

---

## 📌 Feature Queue Status Overview

| ID | Component | Feature Name | Priority | Status |
| :--- | :--- | :--- | :--- | :--- |
| **AP-01** | Device AP | Hardcoded PMIC 1,500mA & UVLO 4.3V in Boot Sequence | High | **QUEUED / HARDCODED** |
| **AP-02** | Device AP | Headless TTY DisplayPort Console Fallback in `exynos_dp_bridge` | High | **QUEUED** |
| **AP-03** | Device AP | Clean Dual-Shell PTY Shims (`/sbin/sh` & Linux `chroot`) | Medium | **QUEUED** |
| **BE-01** | Backend | Roufsweb Protocol Dual-Console Streaming Bridge (PTY) | High | **PLANNED** |
| **BE-02** | Backend | Silent Pre-Flash PMIC Ingestion in `core/flasher.py` | Medium | **PLANNED** |
| **FE-01** | Frontend | Streamlined OS Flasher Hardware Status Card (Remove PMIC Toggle) | High | **READY FOR DEV** |
| **FE-02** | Frontend | Dual-Console Terminal with `xterm.js` & 1-Click OS/AP Switcher | High | **READY FOR DEV** |

---

## 🔧 Detailed Specifications

### 1. Device AP / Firmware Layer

#### `[AP-01]` Hardcoded PMIC 1,500 mA Fast Charge & UVLO 4.3V Guard
* **Role:** Prevent under-voltage SoC crashes during 8-core CPU spikes or USB-C DisplayPort handoffs.
* **Mechanism:**
  - Written directly at boot in `/data/linux/start_all.sh` (`0xBD 0x6C`, `0xC3 0x61`, `0xC0 0x3C`, `0xB9 0x9E`, `0xB7 0x05`).
  - Disable PMIC 32-minute hardware watchdog timer so charge rate never expires.
  - Background `s8_typec_daemon.py` intercepts cable disconnect/reconnect and re-applies registers within 100ms.
* **UI Impact:** Zero user toggles needed; completely automated and crash-proof.

#### `[AP-02]` Headless TTY DisplayPort Console Fallback
* **Role:** Guaranteed plug-and-play monitor output regardless of whether a Desktop GUI or Headless Minimal OS is installed.
* **Mechanism:**
  - Update `scratch/exynos_dp_bridge.c`:
    - If X11 server `:1` is active $\rightarrow$ stream desktop GUI at 1080p60.
    - If X11 server `:1` is absent (Headless mode) $\rightarrow$ render full-screen live Linux TTY console + hardware HUD (Wi-Fi IP `192.168.0.227`, SSH login string, CPU/RAM stats).

#### `[AP-03]` Clean Dual-Shell PTY Shims
* **Role:** Support interactive terminal streaming without dropping pseudo-terminal (PTY) attributes or crashing on resize.
* **Mechanism:**
  - AP Shell: Direct execution of `/sbin/sh` with Android root environment.
  - OS Shell: Execution of `chroot /mnt/ubuntu /bin/bash -l` with UTF-8 locale and PTY window size signaling (`SIGWINCH`).

---

### 2. Desktop App Backend (`desktop-app/app/`)

#### `[BE-01]` Roufsweb Protocol Dual-Console Streaming Bridge
* **Role:** Multiplex interactive terminal sessions between the host desktop app and the target phone over USB or Wi-Fi.
* **Protocol URIs:**
  - `roufsweb://console/os` $\rightarrow$ Interactive PTY bash shell inside `/mnt/ubuntu`.
  - `roufsweb://console/ap` $\rightarrow$ Interactive root shell inside `/sbin/sh`.
* **Transport:** WebSocket (`/api/ws/console?target=os|ap`) with JSON input/output chunks and resize handler (`/api/console/resize`).

#### `[BE-02]` Flasher Engine Silent PMIC Enforcement
* **Role:** Remove user toggle dependency in `desktop-app/app/core/flasher.py`.
* **Mechanism:** Step 1 of flash pipeline silently asserts PMIC registers before formatting or writing rootfs.

---

### 3. Desktop App Frontend (`desktop-app/ui/`)

#### `[FE-01]` OS Flasher Tab Simplification
* **Role:** Clean up `#pageFlash` on [`index.html`](file:///e:/rouf/galaxy-s8/desktop-app/ui/index.html).
* **Action:**
  - Remove manual "1,500mA Fast Charge" toggle card.
  - Insert permanent read-only hardware security badge:
    `Type-C DisplayPort 1080p60 • USB 3.1 Gen 1 (5 Gbps) • 1,500mA Fast Charge Locked`.

#### `[FE-02]` Dual-Console Terminal (`#pageTerminal`) with `xterm.js`
* **Role:** Real-time terminal with colors, cursor support, `htop`, and tab completion.
* **Features:**
  - Header Switcher: `[ 🐧 Linux OS Shell ]` $\longleftrightarrow$ `[ ⚡ Base AP Recovery ]`.
  - Zero manual IP/password entry; connected automatically via roufsweb protocol.
  - Instant clear, copy, and fullscreen options.

