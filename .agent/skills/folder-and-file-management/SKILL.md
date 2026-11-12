---
name: folder-and-file-management
description: Industry-standard directory structure, file placement rules, artifact isolation, and workspace hygiene runbook for the Galaxy S8 Native Linux repository.
---

# Folder & File Management Standard (`folder-and-file-management`)

> [!IMPORTANT]
> **ZERO ROOT CLUTTER & STRICT SEPARATION OF CONCERNS:**
> Every file in `e:\rouf\galaxy-s8` must reside in its canonical directory based on its architectural role. Never leave temporary `.log` files, duplicate `.tar` images, legacy `.bat` scripts, or unindexed binaries in the repository root.

---

## 1. Canonical Directory Architecture

```text
e:\rouf\galaxy-s8\
├── .agent\skills\              # Agent governance, hardware, naming, and testing skills
├── .github\                    # CI/CD workflows and repository templates
├── kernel\                     # Exynos 8895 Linux 4.4.111 kernel source tree & .config
├── src\                        # Native C daemons, hardware scripts, and service templates
│   ├── drivers\                # C sources: s8_usb_agentd.c, s8_dp_daemon.c, exynos_dp_bridge.c, s8_input_bridge.c, s8_button_daemon.c
│   ├── control\                # s8ctl unified hardware CLI & Hardware Center GUI
│   ├── audio\                  # Calliope ABOX DSP firmware configs & ALSA asound.conf
│   ├── network\                # Broadcom BCM4361 Wi-Fi, RNDIS, USB-LAN DHCP, Shannon LTE scripts
│   ├── desktop\                # X11 / GNOME / XFCE session launchers & libnautilus_root.so shim
│   └── services\               # Reference init & systemd unit definitions
├── packages\                   # Multi-distro hardware support packaging
│   ├── galaxy-s8-hw\           # Source tree for galaxy-s8-hw (.deb + universal installer)
│   │   ├── DEBIAN\             # Debian/Ubuntu package control & postinst
│   │   ├── prebuilt\           # Cross-compiled arm64 binaries (s8_dp_daemon, exynos_dp_bridge, s8_input_bridge, s8_button_daemon)
│   │   ├── scripts\            # Hardware init scripts (/usr/lib/s8-hw/*)
│   │   ├── systemd\            # Systemd service units (/etc/systemd/system/s8-*.service)
│   │   └── install-universal.sh# Distro-agnostic installer (Ubuntu, Debian, Alpine, Arch, OpenWrt, HAOS, Kali)
│   └── dist\                   # Built packages: galaxy-s8-hw_1.0.2_arm64.deb & galaxy-s8-hw-universal-arm64.tar.gz
├── desktop-app\                # S8 Imager Desktop & Web Application
│   ├── app\                    # Backend core (DeviceManager, RWP client, OS catalog, flasher engine)
│   ├── ui\                     # Bento-grid web/desktop frontend (index.html, styles.css, app.js)
│   ├── tests\                  # 4-layer automated test suite (unit, API, DOM, E2E human-flow)
│   ├── main.py                 # Native desktop window entrypoint
│   └── server.py               # Local HTTP/WebSocket backend server
├── scripts\                    # Build, validation, versioning, indexing, privacy, and Telegram automation
│   ├── build_universal_ap.py   # Canonical Universal AP & Pure Linux Boot Image builder
│   ├── pre_flash_validator.py  # Mathematical pre-flash image & CPIO verifier
│   ├── version_manager.py      # Universal version & 1-click rollback manager
│   ├── reorganize_repo.py      # Automated workspace cleaner & folder structure enforcer
│   ├── project_index.py        # Autonomous PROJECT_INDEX.md generator
│   ├── sanitize_repo.py        # Secret & file-size policy sanitizer
│   ├── send_telegram.py        # Telegram notification & visual proof dispatcher
│   └── telegram_listener.py    # Reactive bi-directional Telegram listener
├── tests\                      # Hardware, kernel, benchmark, and multi-distro E2E test suites
│   ├── hardware\               # PMIC, DisplayPort, USB Host, Audio, Wi-Fi, Thermal checks
│   ├── services\               # Systemd/OpenRC/RWP daemon health checks
│   ├── benchmarks\             # CPU/GPU/Storage/Network performance benchmarks
│   └── unit\                   # Standalone unit tests
├── releases\                   # Official Odin AP tarballs, versioned snapshots, & quick-connect utilities
│   ├── history\                # Immutable versioned AP & boot snapshots (Galaxy_S8_Linux_AP_v*.tar)
│   ├── Galaxy_S8_Linux_AP.tar  # Canonical active Odin AP package (gitignored binary, verified by SHA256)
│   ├── checksums.sha256        # Cryptographic hashes of release & history artifacts
│   ├── connect_shell.bat       # Host 1-click shell launcher
│   └── connect_desktop.bat     # Host 1-click VNC desktop launcher
├── distros\                    # Downloaded vanilla upstream OS rootfs/images (gitignored)
├── docs\                       # Technical documentation & GEMINI_3_8_HANDOFF.md
├── tools\                      # Host platform binaries (adb.exe, fastboot, heimdall)
├── archive\                    # Retired legacy scripts, old boot images, and backups (gitignored)
└── scratch\                    # Temporary build intermediates and one-off probes (gitignored)
```

---

## 2. Allowed Root-Level Files

Only the following files are permitted in the top-level `e:\rouf\galaxy-s8\` directory:
1. **Core Governance & Documentation:**
   - `GEMINI.md` (Master Rulebook)
   - `VERSION_MANIFEST.json` & `VERSIONS.md` (Universal Version & Rollback Ledger)
   - `README.md` (Public project overview)
   - `FINDINGS.md` (Empirically verified hardware & kernel findings)
   - `HISTORY.md` (Chronological execution log)
   - `PROJECT_INDEX.md` & `PROJECT_VISUAL_INDEX.html` (Automated asset catalog)
   - `MISTAKES_AND_LEARNINGS.md`, `FUTURE_ROADMAP.md`, `SUMMARY.md`, `CREDITS.md`, `MEMORY.md`, `LICENSE`
2. **Configuration & Entrypoints:**
   - `.gitignore`, `.env` (gitignored)
   - `Launch_S8_Imager.bat` (Single canonical desktop app launcher)

---

## 3. File Placement & Lifecycle Rules

1. **Where to Put New Code:**
   - **C Daemons / Drivers:** Source goes in `src/drivers/<name>.c`. Compiled arm64 binary goes in `packages/galaxy-s8-hw/prebuilt/<name>` (and `scratch/` during compilation).
   - **Hardware Init Scripts:** `packages/galaxy-s8-hw/scripts/s8-<subsys>.sh` and synced to `src/services/`.
   - **Desktop App Features:** Backend in `desktop-app/app/`, frontend in `desktop-app/ui/`, tests in `desktop-app/tests/`.
   - **Temporary Test Scripts:** Always write one-off test probes to `scratch/`—never to the root directory or `scripts/`.
2. **Where to Move Legacy / Superseded Files:**
   - Move obsolete root files (`flash_ubuntu.bat`, `ubuntu_desktop.bat`, `ubuntu_shell.bat`, root `Galaxy_S8_Linux_AP.tar` duplicates, `flasher.log`, legacy `boot/` or `build/` folders) into `archive/legacy_root/` or remove duplicates after verifying `releases/Galaxy_S8_Linux_AP.tar`.
3. **Post-Reorganization Synchronization:**
   - After moving or renaming any file, always run:
     ```powershell
     python scripts/project_index.py --rebuild
     python scripts/sanitize_repo.py
     ```

