---
name: versioning-and-rollback-manager
description: Universal semantic versioning standard, compatibility matrix ledger, drift prevention, and 1-click rollback runbook for all releases, kernels, Odin AP images, hardware packages, daemons, desktop app builds, and upstream Linux distributions on the Galaxy S8 Native Linux project.
---

# Universal Versioning & Rollback Governance (`versioning-and-rollback-manager`)

> [!IMPORTANT]
> **ZERO VERSION DRIFT & INSTANT ROLLBACK MANDATE:**
> Every artifact in the Galaxy S8 Native Linux project — Kernel builds, Odin AP tarballs, Boot images, `galaxy-s8-hw` packages, C daemons, `s8ctl`, `S8 Imager` desktop app, RWP protocol, and all downloaded upstream Linux distributions — MUST carry an explicit version tracked in [`VERSION_MANIFEST.json`](file:///e:/rouf/galaxy-s8/VERSION_MANIFEST.json) and rendered in [`VERSIONS.md`](file:///e:/rouf/galaxy-s8/VERSIONS.md).
> Never overwrite a working release without archiving its versioned snapshot in `releases/history/` and recording whether each version **worked** (`VERIFIED_WORKING`) or **failed** (`FAILED` / `ROLLED_BACK`).

---

## 1. Alignment with Naming & Folder Standards

This skill works in strict lockstep with [`.agent/skills/product-namespace-and-naming/SKILL.md`](file:///e:/rouf/galaxy-s8/.agent/skills/product-namespace-and-naming/SKILL.md) and [`.agent/skills/folder-and-file-management/SKILL.md`](file:///e:/rouf/galaxy-s8/.agent/skills/folder-and-file-management/SKILL.md):

| Component Layer | Canonical Version Format | Versioned Artifact Path | Canonical Active Pointer / Copy |
| :--- | :--- | :--- | :--- |
| **1. Kernel (`uname -r`)** | `4.4.111-s8-universal-v<MAJOR>.<MINOR>.<PATCH>` | `releases/history/Image_v<VER>` | `kernel/arch/arm64/boot/Image` |
| **2. Odin AP Release** | `v<MAJOR>.<MINOR>.<PATCH>` | `releases/history/Galaxy_S8_Linux_AP_v<VER>.tar` | `releases/Galaxy_S8_Linux_AP.tar` |
| **3. Boot Image (`sda7`/`sda8`)** | `v<MAJOR>.<MINOR>.<PATCH>` | `releases/history/boot_universal_ap_v<VER>.img` | `scratch/boot_universal_ap.img` |
| **4. Hardware Pack (`.deb`)** | `<MAJOR>.<MINOR>.<PATCH>` | `packages/dist/galaxy-s8-hw_<VER>_arm64.deb` | `packages/dist/galaxy-s8-hw_<ACTIVE_VER>_arm64.deb` |
| **5. Hardware Pack (`.tar.gz`)** | `<MAJOR>.<MINOR>.<PATCH>` | `packages/dist/galaxy-s8-hw-<VER>-arm64.tar.gz` | `packages/dist/galaxy-s8-hw-universal-arm64.tar.gz` |
| **6. Native C Daemons & `s8ctl`** | `<MAJOR>.<MINOR>.<PATCH>` | `src/drivers/s8_version.h` (`S8_SUITE_VERSION`) | `packages/galaxy-s8-hw/prebuilt/*` |
| **7. RWP Transport Protocol** | `rwp-v<MAJOR>.<MINOR>.<PATCH>` | `/rwp/v1/health` & `/rwp/v1/info` (`protocol_version`) | `src/drivers/s8_usb_agentd.c` |
| **8. Desktop App (`S8 Imager`)** | `<MAJOR>.<MINOR>.<PATCH>` | `desktop-app/app/config.py` (`APP_VERSION`) | Displayed in UI Header & `/api/status` |
| **9. Upstream Distros (`distros/`)** | `<UPSTREAM_VER>` + SHA-256 | `distros/<canonical-upstream-filename>` | Tracked in `VERSION_MANIFEST.json` (`distros` matrix) |

---

## 2. Semantic Versioning Rules (`MAJOR.MINOR.PATCH`)

1. **`MAJOR` Increment (`v1.x.x` -> `v2.0.0` -> `v3.0.0`):**
   - Architectural boot or kernel milestones:
     - `v1.0.0`: Android `/init` + `init.rc` chroot handoff baseline (`Galaxy_S8_Linux_AP_v1.0.0.tar`).
     - `v2.0.x`: Pure Native Linux `/init` `switch_root` -> `systemd` / universal init PID 1 (`Galaxy_S8_Linux_AP_v2.0.2.tar`).
     - `v3.0.0`: Recompiled Exynos 8895 Kernel with `CONFIG_ANDROID_PARANOID_NETWORK=n`, `CONFIG_USB_UAS=y`, built-in USB Ethernet dongles, and kernel-level disconnect panic guards.
2. **`MINOR` Increment (`v2.0.0` -> `v2.1.0`):**
   - New hardware features, new init support (e.g., adding OpenWrt `procd` / Alpine `OpenRC` / HAOS cgroup hierarchy), new daemon capabilities (`s8_input_bridge`), or new storage targets (`sdcard`, `sdcard_part`).
3. **`PATCH` Increment (`v1.0.1` -> `v1.0.2`):**
   - Bug fixes, non-regression fixes, cursor alpha fixes, buffer size fixes, or script hardening that preserve backward compatibility.

---

## 3. Verification Status Classification (Decision Matrix)

Every versioned release (AP, Kernel, Hardware Pack) and every tested Distro in `VERSION_MANIFEST.json` MUST be assigned one of the following empirical statuses:

- **`VERIFIED_WORKING`**: Passed `pre_flash_validator.py` (6/6 gates) AND verified on physical hardware (`SM-G950N` `192.168.7.2`) with `test_full_non_regression_e2e.py`. Safe for production and instant rollback target.
- **`SUPERSEDED`**: Previously verified working on physical hardware, now replaced by a newer `VERIFIED_WORKING` version. Retained in `releases/history/` or `packages/dist/` for rollback comparison.
- **`EXPERIMENTAL`**: Built and passed static pre-flash validation, awaiting full 21-point physical hardware and cold-boot verification.
- **`FAILED`**: Tested and failed validation or physical boot (e.g., `v0.8.0-exp` `permissive.sh` firmware shadowing watchdog panic; `v0.9.0-exp` GCC 13 `CONFIG_RKP_CFP=y` EL2 TrustZone cold-boot halt). Logged permanently in `VERSION_MANIFEST.json` with exact root cause so no agent or engineer ever repeats the mistake.
- **`READY_TO_TEST`** (Distros only): Official upstream archive downloaded in `distros/`, SHA-256 recorded, awaiting live deployment test with the active AP + Hardware Pack.

---

## 4. Mandatory CLI Workflows (`scripts/version_manager.py`)

Never edit version strings manually across scattered files. Always use `scripts/version_manager.py`:

### 4.1 Check Overall Version Health & Drift
```powershell
python scripts/version_manager.py --status
```
Verifies that `VERSION_MANIFEST.json`, `VERSIONS.md`, `desktop-app/app/config.py`, `src/drivers/s8_version.h`, `packages/galaxy-s8-hw/build_packages.py`, `releases/Galaxy_S8_Linux_AP.tar`, `packages/dist/`, and `distros/` are 100% synchronized with zero drift.

### 4.2 Synchronize All Code & Package Headers from Manifest
```powershell
python scripts/version_manager.py --sync
```
Propagates active versions from `VERSION_MANIFEST.json` into:
- `src/drivers/s8_version.h`
- `src/control/s8ctl`
- `packages/galaxy-s8-hw/build_packages.py`
- `desktop-app/app/config.py`
- `releases/checksums.sha256`
- `VERSIONS.md`

### 4.3 Snapshot & Record a New AP Release
```powershell
python scripts/version_manager.py --snapshot-ap 2.0.2 --status VERIFIED_WORKING --notes "Pure Native Linux PID 1 switch_root + multi-storage boot_target.conf + cgroup v1 mounts"
```

### 4.4 Record Distro Compatibility Outcome
```powershell
python scripts/version_manager.py --record-distro ubuntu-desktop-24.04 --status VERIFIED_WORKING --ap 2.0.2 --hw 1.0.2 --notes "Systemd PID 1, GNOME/XFCE VNC :5901, DisplayPort fb2 + USB mouse/kb, Calliope audio, PMIC 1500mA all passing"
```

### 4.5 Instant 1-Click Rollback (Workspace + Live Device)
```powershell
# Roll back workspace AP to a known-good version:
python scripts/version_manager.py --rollback-ap 1.0.0

# Roll back workspace AP AND flash directly to connected phone (/dev/sda7 + /dev/sda8):
python scripts/version_manager.py --rollback-ap 2.0.2 --live

# Roll back Hardware Pack to a specific version:
python scripts/version_manager.py --rollback-hw 1.0.1 --live
```

---

## 5. Pre-Commit & Release Versioning Gate

Before completing any build, package update, kernel change, or OS test:
1. Bump or confirm the target semantic version in `VERSION_MANIFEST.json`.
2. Run `python scripts/version_manager.py --sync` and `python scripts/version_manager.py --status`.
3. Confirm `VERSIONS.md` reflects what worked, what failed, and which version is active.

