# Gemini 3.8 Continuity & Handoff Runbook (`docs/GEMINI_3_8_HANDOFF.md`)

> [!IMPORTANT]
> **INSTANT CONTINUITY FOR GEMINI 3.8 HIGH / PRO / FLASH:**
> If Gemini 4 Argon quota expires, read this file and [`GEMINI.md`](file:///e:/rouf/galaxy-s8/GEMINI.md) first. Everything below reflects the exact verified state of the workspace and the live physical Samsung Galaxy S8 (`SM-G950N`, `192.168.7.2`).

---

## 1. Completed Milestones (`2026-11-13`)

1. **Skill Governance & Synthesis (`.agent/skills/`):**
   - Created [`product-namespace-and-naming`](file:///e:/rouf/galaxy-s8/.agent/skills/product-namespace-and-naming/SKILL.md) — Canonical OS-agnostic naming (`4.4.111-s8-universal-v3`, `Galaxy_S8_Linux_AP.tar`, `galaxy-s8-hw`, `rwp-v1`, `s8-*` services).
   - Created [`folder-and-file-management`](file:///e:/rouf/galaxy-s8/.agent/skills/folder-and-file-management/SKILL.md) — Industry-standard folder layout and zero root clutter.
   - Created [`project-management`](file:///e:/rouf/galaxy-s8/.agent/skills/project-management/SKILL.md) — Iron Law of Feature Isolation ("1 feature must never break another"), Full-Permission Kernel standard, and Gemini 3.8 Handoff protocol.
   - Synthesized [`galaxy-s8-native-linux`](file:///e:/rouf/galaxy-s8/.agent/skills/galaxy-s8-native-linux/SKILL.md) and [`galaxy-s8-ap-kernel-builder`](file:///e:/rouf/galaxy-s8/.agent/skills/galaxy-s8-ap-kernel-builder/SKILL.md).

2. **Industry-Standard Repository Reorganization:**
   - Moved legacy root scripts/logs/folders (`flash_ubuntu.bat`, `ubuntu_desktop.bat`, `ubuntu_shell.bat`, root `s8_flasher.py`, `S8_Imager.spec`, `boot/`, `build/`, `dist/`) into `archive/legacy_root/` and `archive/legacy_*`.
   - Removed duplicate root `Galaxy_S8_Linux_AP.tar`; canonical AP is exclusively [`releases/Galaxy_S8_Linux_AP.tar`](file:///e:/rouf/galaxy-s8/releases/Galaxy_S8_Linux_AP.tar).

3. **Kernel (`4.4.111-s8-universal-v3`) & Universal AP (`Galaxy_S8_Linux_AP.tar v3.0.0`):**
   - Pure Native Linux `systemd` / OS init as PID 1 (`switch_root` from initramfs) + `CONFIG_ANDROID_PARANOID_NETWORK=n` (unprivileged sockets for any UID) + `CONFIG_USB_UAS=y` (USB 3.1 SuperSpeed UASP storage) + `CONFIG_BRIDGE_NF_EBTABLES=y` + `panic_on_oops=0` hardware disconnect guard.
   - Multi-storage rootfs resolution (`boot_target.conf` -> `/mnt_data/linux/rootfs.img` -> `/dev/sda24` -> `/media/sdcard/linux/rootfs.img` -> `/dev/mmcblk0p2` -> `/dev/sdb`).
   - Empirical architectural limitations documented in Section 8 of [`docs/AP_AND_KERNEL_BUILD_GUIDE.md`](file:///e:/rouf/galaxy-s8/docs/AP_AND_KERNEL_BUILD_GUIDE.md).

4. **DisplayPort Cursor Alpha Fix, USB Host Switching & OS-Agnostic CLI (`galaxy-s8-hw v1.0.3`):**
   - [`src/drivers/exynos_dp_bridge.c`](file:///e:/rouf/galaxy-s8/src/drivers/exynos_dp_bridge.c) & [`src/drivers/s8_input_bridge.c`](file:///e:/rouf/galaxy-s8/src/drivers/s8_input_bridge.c): Active BGRA cursor alpha (`0xFF`), automatic USB Host (`DFP` / `source`) assertion on DisplayPort hotplug, and USB/BT input forwarding to X11 `:1`.
   - Built [`packages/dist/galaxy-s8-hw_1.0.3_arm64.deb`](file:///e:/rouf/galaxy-s8/packages/dist/galaxy-s8-hw_1.0.3_arm64.deb) and [`packages/dist/galaxy-s8-hw-1.0.3-arm64.tar.gz`](file:///e:/rouf/galaxy-s8/packages/dist/galaxy-s8-hw-1.0.3-arm64.tar.gz) (`.tar.gz` universal POSIX installer) with OS-agnostic `[s8ctl v1.0.3]` banner and installed `1.0.3` live on the phone.

5. **Polished Desktop App (`S8 Imager v2.7.0`), 6-Distro Live Matrix & 25-Point Verification Suite:**
   - Fixed GPT `sectors` vs `sectors * 512` byte selection for HAOS `18.4` EROFS->ext4, native Python `tarfile r|xz` streaming for Debian `disk.raw`, async RWP extraction polling for `SteamOS 3.6`, and terminal history `whitespace-nowrap`.
   - Live verified flash + custom partition sizing + PID 1 boot across `OpenWrt 23.05.5` (`4 GB`), `Alpine 3.20.3` (`6 GB`), `Kali Rolling` (`8 GB`), `Debian 12` (`10 GB`), `Home Assistant OS 18.4` (`12 GB`), `SteamOS 3.6 Holo` (`16 GB`), and restored Golden `Ubuntu 24.04.5 LTS Desktop` (`16 GB`, `glxgears` `513.341 FPS`, `Freedoom: Phase 2`).
   - Verified [`tests/hardware/verify_21_point_hardware.py`](file:///e:/rouf/galaxy-s8/tests/hardware/verify_21_point_hardware.py) (`25/25 PASS`), [`tests/hardware/test_full_non_regression_e2e.py`](file:///e:/rouf/galaxy-s8/tests/hardware/test_full_non_regression_e2e.py) (`6/6 PASS`), and `desktop-app` unit + Playwright E2E suites (`22/22 PASS`).

6. **Universal Versioning, Compatibility Ledger & 1-Click Rollback Governance (`Rule 30`):**
   - Synchronized [`VERSION_MANIFEST.json`](file:///e:/rouf/galaxy-s8/VERSION_MANIFEST.json), [`VERSIONS.md`](file:///e:/rouf/galaxy-s8/VERSIONS.md), and [`scripts/version_manager.py`](file:///e:/rouf/galaxy-s8/scripts/version_manager.py) with `0` version drift across all 8 layers (`S8 Imager v2.7.0`, `AP v3.0.0`, `HW v1.0.3`).

---

## 2. Quick Verification & Continuity Commands for Gemini 3.8

```powershell
# 1. Audit Universal Versioning & Zero Drift Across All 8 Project Layers
python scripts/version_manager.py --status

# 2. Run full live hardware + kernel + package non-regression suite (requires phone on USB RNDIS 192.168.7.2)
python tests/hardware/verify_21_point_hardware.py
python tests/hardware/test_full_non_regression_e2e.py

# 3. Run desktop-app unit and Playwright E2E human-flow suite
python -m unittest desktop-app/tests/test_unit_core.py desktop-app/tests/test_flash_human_flow.py desktop-app/tests/test_terminal_human_flow.py

# 4. Rebuild Universal AP & validate pre-flash gates
python scripts/build_universal_ap.py
python scripts/pre_flash_validator.py releases/Galaxy_S8_Linux_AP.tar

# 5. Rollback AP or Hardware Pack (Workspace or Live Phone)
python scripts/version_manager.py --rollback-ap 2.0.2 --live
python scripts/version_manager.py --rollback-hw 1.0.2 --live

# 6. Rebuild Project Index & Sanitize Repo
python scripts/project_index.py --build
python scripts/sanitize_repo.py
```

