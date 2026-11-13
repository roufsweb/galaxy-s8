# Galaxy S8 Native Linux & S8 Imager — Project Feature Queue (`docs/PROJECT_FEATURE_QUEUE.md`)

This document tracks all completed, planned, and queued features across the **Device AP (Kernel/Ramdisk)**, **Backend Server Engine**, and **Frontend Desktop UI**, incorporating recent architectural decisions (BYOI flasher standard, zero mockups, and Docker containerization).

---

## 1. Feature Status Overview

| ID | Component | Feature Name | Priority | Status | Reconciled Decision / Note |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **AP-01** | Device AP | Hardcoded PMIC 1,500mA & UVLO 4.3V in Boot Sequence | High | **[VERIFIED / LIVE]** | Written at boot via `/data/linux/start_all.sh` & guarded by `s8_typec_daemon.py`. |
| **AP-02** | Device AP | Headless TTY DisplayPort Console Fallback in `exynos_dp_bridge` | High | **QUEUED (ACTIVE FOCUS)** | Unblocks headless/minimal distros (Alpine/Debian) on external HDMI monitors without X11 `:1`. |
| **AP-03** | Device AP | Clean Dual-Shell PTY Shims (`/sbin/sh` & Linux `chroot`) | Medium | **[VERIFIED / LIVE]** | Operational via `/api/terminal/exec` and `device_manager.py` (`target=os` / `target=ap`). |
| **AP-04** | Device AP | Pure Native Linux (systemd PID 1) Early Init Architecture | High | **QUEUED (CORE GOAL)** | Transition from Android ramdisk `/init` + chroot to direct native Linux PID 1 with full permission standards. |
| **AP-05** | Device AP | Universal USB-C Multi-Function Dock & OTG Peripheral Bridge | Medium | **PLANNED** | Simultaneous HDMI + USB 3.0 Storage + Mouse/Keyboard + Ethernet dongles with 5V booster arbitration. |
| **BE-01** | Backend | Roufsweb Protocol Dual-Console Streaming Bridge (PTY) | High | **[VERIFIED / LIVE]** | Operational in `desktop-app/app/server/api.py` and WebSocket endpoints. |
| **BE-02** | Backend | Silent Pre-Flash PMIC Ingestion in `core/flasher.py` | Medium | **[VERIFIED / LIVE]** | Flasher step 1 asserts PMIC fast charge & UVLO before formatting or writing rootfs. |
| **BE-03** | Backend | Dynamic UFS Partition Geometry Sizing & Ext4 Formatting | Medium | **PLANNED** | Configurable rootfs slice allocation (`4 GB - 48 GB`) with mandatory `-O ^extents` format standard. |
| **FE-01** | Frontend | Streamlined OS Flasher UI (Pure BYOI Standard) | High | **[VERIFIED / LIVE]** | Purged 177-line OS Catalog modal. Enforces Bring Your Own Image (Rufus / BalenaEtcher standard). |
| **FE-02** | Frontend | Dual-Console Terminal with 1-Click OS/AP Switcher | High | **[VERIFIED / LIVE]** | Live terminal with real-time output, command history, and instant `[OS Shell]` / `[Base AP]` switching. |
| **FE-03** | Frontend | Live Wi-Fi AP Remote Scan & Profile Synchronization | Medium | **PLANNED** | In-app network configuration on Page 4 triggering `s8ctl wifi-scan` and syncing `wpa_supplicant.conf`. |

---

## 2. Reconciled Architectural Decisions (Colliding Decisions Purged)

The following legacy concepts have been audited and explicitly purged from the project roadmap to prevent regressions:

1. **Purged: In-App "Official OS Catalog" & Image Hosting (Finding 131):**
   * *Legacy Concept:* In-app modal with download buttons for multi-gigabyte OS distributions.
   * *New Standard:* The project develops the **Universal Exynos 8895 Kernel AP, S8 Hardware Pack (`galaxy-s8-hw`), and Flashing Engine**. We do not host or distribute third-party OS distributions. The S8 Imager is a pure **Bring Your Own Image (BYOI)** flasher adhering to industry standards (Rufus / BalenaEtcher).
2. **Purged: In-App Ethereum / Web3 Wallet & Donation Modal (Finding 132):**
   * *Legacy Concept:* In-app `donateModal` and `Buy Me a Coffee` button with ERC-20 address.
   * *New Standard:* Complete removal from desktop app UI. Zero external financial or tipping modals in production binaries.
3. **Purged: KVM Virtualization (`CONFIG_KVM=y`) (Finding 115, Rule 10, Rule 23):**
   * *Legacy Concept:* Running KVM virtual machines inside the 4.4 kernel on Exynos 8895.
   * *New Standard:* Samsung's EL2 micro-hypervisor (uH) strictly controls EL2 exception vectors. Compiling `CONFIG_KVM=y` causes immediate hypervisor traps and SoC reboots. All virtualization on the platform is standardized on **Docker CE and Linux Containerization (`cgroups`, `namespaces`, `overlayfs`)**.
4. **Purged: Manual Hardware Toggles (PMIC 1500mA, UVLO 4.3V, Governor):**
   * *Legacy Concept:* Exposing manual checkboxes in UI to enable fast charging or UVLO brownout protection.
   * *New Standard:* Hardware protection must be 100% automated and fail-safe. PMIC registers (`0xBD 0x6C`, `0xC3 0x61`, `0xC0 0x3C`, `0xB9 0x9E`, `0xB7 0x05`) are hardcoded at early boot and enforced before every flash cycle.
5. **Purged: Static Decorative Mockups & Hallucinated Microcopy:**
   * *Legacy Concept:* Hardcoded strings such as `Exynos 8895 @ 60Hz`, `1500mA Constant`, and fake Ubuntu metadata before image selection.
   * *New Standard:* Strict compliance with `production-ui-design-guard`. Every UI badge, value, and label represents real physical hardware telemetry or dynamic user selection.

---

## 3. Active Priority Feature Specifications

### `[AP-02]` Headless TTY DisplayPort Console Fallback in `exynos_dp_bridge`
* **Problem Holding Us Back:**
  `scratch/exynos_dp_bridge.c` contains `while (!dpy) { dpy = XOpenDisplay(":1"); sleep(1); }`. When a user runs a headless Linux distribution (Alpine Linux, minimal Debian Server, Home Assistant, OpenWrt) without an active X11 desktop, the bridge blocks forever and external HDMI monitors remain completely unpowered.
* **Architecture Solution:**
  1. Implement non-blocking display connection check (`XOpenDisplay(":1")`).
  2. If X11 `:1` is active: Stream desktop GUI frames at 1080p60 via double-buffered ION DMA (`S3CFB_WIN_CONFIG`).
  3. If X11 `:1` is absent (Headless mode): Fall back to userland framebuffer console rendering (drawing live CLI text / system status HUD with Wi-Fi IP, SSH command, CPU/RAM telemetry, and terminal output) directly to `/dev/graphics/fb2`.
  4. Dynamic auto-switching: As soon as a desktop environment starts, seamlessly switch from TTY HUD to X11 streaming.

### `[AP-04]` Pure Native Linux (systemd PID 1) Early Init Architecture
* **Target Objective:**
  Achieve true native Linux system execution where `systemd` runs as PID 1 directly from the root filesystem, eliminating chroot overhead while maintaining DWC3 USB initialization.
* **Key Milestones:**
  1. Early Ramdisk USB Handshake: Ensure DWC3 PHY initialization (`10c00000.dwc3`) and gadget setup complete before pivot.
  2. Switch root / Pivot Root: Mount `/dev/block/sda24` (`USERDATA`) at `/sysroot` and execute `/sbin/init` (systemd) directly as PID 1.
  3. Systemd Hardware Service Pack: Install `galaxy-s8-hw.service` inside the target distro to handle PMIC registers, Calliope DSP audio routing, Wi-Fi onboarding, and display bridge natively via systemd units.

### `[AP-05]` Universal USB-C Multi-Function Dock & OTG Peripheral Bridge
* **Target Objective:**
  Guarantee that connecting a multi-port USB-C adapter (providing HDMI out + multiple USB 3.0 ports + USB Ethernet) reliably powers accessories and enumerates all attached devices.
* **Mechanism:**
  - Dynamic CCIC VDM negotiation with Type-C power arbitration.
  - Assert 5V VBUS booster (`booster = ON`) when dock requires bus power, while safely switching to sink mode when external USB-PD charger is connected to dock pass-through port.
  - Enforce continuous DW MMC and DWC3 USB host polling.

### `[FE-03]` Live Wi-Fi AP Remote Scan & Profile Synchronization
* **Target Objective:**
  Enable users on Page 4 (Device Configuration) to click "Scan Networks" to view live Wi-Fi SSIDs and signal strength detected by the S8's BCM4361 radio, select an SSID, enter the passphrase, and immediately connect without manual terminal editing.
