# Gemini 3.8 Continuity & Handoff Runbook (`docs/GEMINI_3_8_HANDOFF.md`)

> [!IMPORTANT]
> **INSTANT CONTINUITY FOR GEMINI 3.8 HIGH / PRO / FLASH:**
> If Gemini 4 Argon quota expires, read this file and [`GEMINI.md`](file:///e:/rouf/galaxy-s8/GEMINI.md) first. Everything below reflects the exact verified state of the workspace and the live physical Samsung Galaxy S8 (`SM-G950N`, `192.168.7.2`).

---

## 1. Completed Milestones (`2026-11-13`)

1. **Skill Governance & Synthesis (`.agent/skills/`):**
   - Created [`product-namespace-and-naming`](file:///e:/rouf/galaxy-s8/.agent/skills/product-namespace-and-naming/SKILL.md) — Canonical OS-agnostic naming (`4.4.111-s8-universal-v2`, `Galaxy_S8_Linux_AP.tar`, `galaxy-s8-hw`, `rwp-v1`, `s8-*` services).
   - Created [`folder-and-file-management`](file:///e:/rouf/galaxy-s8/.agent/skills/folder-and-file-management/SKILL.md) — Industry-standard folder layout and zero root clutter.
   - Created [`project-management`](file:///e:/rouf/galaxy-s8/.agent/skills/project-management/SKILL.md) — Iron Law of Feature Isolation ("1 feature must never break another"), Full-Permission Kernel standard, and Gemini 3.8 Handoff protocol.
   - Synthesized [`galaxy-s8-native-linux`](file:///e:/rouf/galaxy-s8/.agent/skills/galaxy-s8-native-linux/SKILL.md) and [`galaxy-s8-ap-kernel-builder`](file:///e:/rouf/galaxy-s8/.agent/skills/galaxy-s8-ap-kernel-builder/SKILL.md).

2. **Industry-Standard Repository Reorganization:**
   - Moved legacy root scripts/logs/folders (`flash_ubuntu.bat`, `ubuntu_desktop.bat`, `ubuntu_shell.bat`, root `s8_flasher.py`, `S8_Imager.spec`, `boot/`, `build/`, `dist/`) into `archive/legacy_root/` and `archive/legacy_*`.
   - Removed duplicate root `Galaxy_S8_Linux_AP.tar`; canonical AP is exclusively [`releases/Galaxy_S8_Linux_AP.tar`](file:///e:/rouf/galaxy-s8/releases/Galaxy_S8_Linux_AP.tar).

3. **Kernel (`4.4.111-s8-universal-v3`) & Universal AP (`Galaxy_S8_Linux_AP.tar v3.0.0`):**
   - Pure Native Linux `systemd` / OS init as PID 1 (`switch_root` from initramfs) + `CONFIG_ANDROID_PARANOID_NETWORK=n` (unprivileged sockets for any UID) + `CONFIG_USB_UAS=y` (USB 3.1 SuperSpeed UASP storage) + `CONFIG_BRIDGE_NF_EBTABLES=y` + `panic_on_oops=0` hardware disconnect guard.
   - Multi-storage rootfs resolution (`boot_target.conf` -> `/mnt_data/linux/rootfs.img` -> `/dev/sda24` -> `/media/sdcard/linux/rootfs.img` -> `/dev/mmcblk0p2` -> `/dev/sdb`).
   - Universal init discovery (`/sbin/init`, `/init`, `systemd`, OpenWrt `/etc/preinit`, Alpine `/bin/init`) + automatic cgroup v1 hierarchy mount (`devices`, `memory`, `cpu`, `blkio`, `freezer`, `pids`, `cpuset`) for non-systemd distros, Docker, LXC, and Home Assistant OS.
   - Dual USB ConfigFS Gadget (`rndis.usb0` `192.168.7.2` + `s8_usb_agentd :7860` + `s8_dhcpd.py` + `acm.gs0` `/dev/ttyGS0`) + USB-LAN Dongle Auto-DHCP (`RTL8152`, `AX88179`, `CDC-NCM`, `CDC-ECM`).

4. **DisplayPort Cursor Alpha Fix, USB Host Switching & Hotplug Input Bridge (`galaxy-s8-hw v1.0.2`):**
   - [`src/drivers/exynos_dp_bridge.c`](file:///e:/rouf/galaxy-s8/src/drivers/exynos_dp_bridge.c): Fixed BGRA cursor alpha blending (`0xFF` alpha enforcement) and added `ensure_usb_host_mode()` on DisplayPort hotplug (`state > 0`).
   - [`src/drivers/s8_input_bridge.c`](file:///e:/rouf/galaxy-s8/src/drivers/s8_input_bridge.c): Compiled and deployed `/usr/local/bin/s8_input_bridge` (`67,496 B`) + `s8-input-bridge.service` forwarding physical USB/Bluetooth mice & keyboards to X11 `:1` via `XTest`.
   - Built [`packages/dist/galaxy-s8-hw_1.0.2_arm64.deb`](file:///e:/rouf/galaxy-s8/packages/dist/galaxy-s8-hw_1.0.2_arm64.deb) and [`packages/dist/galaxy-s8-hw-universal-arm64.tar.gz`](file:///e:/rouf/galaxy-s8/packages/dist/galaxy-s8-hw-universal-arm64.tar.gz) (POSIX `/bin/sh` compatible across Ubuntu, Debian, Kali, Arch, Alpine OpenRC, OpenWrt procd, and Home Assistant OS) and installed `1.0.2` on the live phone.

5. **Polished Desktop App (`S8 Imager v2.6.0`) & 21-Point Hardware Verification Suite:**
   - Added OpenWrt 23.05.5 and Home Assistant OS 18.4 to [`desktop-app/app/core/distros.py`](file:///e:/rouf/galaxy-s8/desktop-app/app/core/distros.py) and `#distroModal` in [`desktop-app/ui/index.html`](file:///e:/rouf/galaxy-s8/desktop-app/ui/index.html).
   - Upgraded [`desktop-app/app/core/flasher.py`](file:///e:/rouf/galaxy-s8/desktop-app/app/core/flasher.py), [`desktop-app/app/core/injector.py`](file:///e:/rouf/galaxy-s8/desktop-app/app/core/injector.py), and [`desktop-app/ui/index.html`](file:///e:/rouf/galaxy-s8/desktop-app/ui/index.html) to support **Live RWP/SSH OS Flashing (`192.168.7.2`)**, **Target Storage Selection (`internal` UFS / `sdcard` loop / `sdcard_part`)**, and automatic `galaxy-s8-hw v1.0.2` injection.
   - Created and verified [`tests/hardware/verify_21_point_hardware.py`](file:///e:/rouf/galaxy-s8/tests/hardware/verify_21_point_hardware.py) (`21/21 PASS`) and [`tests/hardware/test_full_non_regression_e2e.py`](file:///e:/rouf/galaxy-s8/tests/hardware/test_full_non_regression_e2e.py) (`6/6 PASS` + `21/21` desktop-app unit/UI/Playwright E2E tests passed).

6. **Universal Versioning, Compatibility Ledger & 1-Click Rollback Governance (`Rule 30`):**
   - Created [`.agent/skills/versioning-and-rollback-manager/SKILL.md`](file:///e:/rouf/galaxy-s8/.agent/skills/versioning-and-rollback-manager/SKILL.md), [`VERSION_MANIFEST.json`](file:///e:/rouf/galaxy-s8/VERSION_MANIFEST.json), [`VERSIONS.md`](file:///e:/rouf/galaxy-s8/VERSIONS.md), [`src/drivers/s8_version.h`](file:///e:/rouf/galaxy-s8/src/drivers/s8_version.h), and [`scripts/version_manager.py`](file:///e:/rouf/galaxy-s8/scripts/version_manager.py).
   - Archived immutable versioned AP snapshots in `releases/history/` (`Galaxy_S8_Linux_AP_v3.0.0.tar`, `Galaxy_S8_Linux_AP_v2.0.2.tar`, `Galaxy_S8_Linux_AP_v1.0.0.tar`) and permanently staged AP ramdisk binaries in `packages/galaxy-s8-hw/prebuilt/ap_ramdisk/`.
   - Added `/api/versions` and `/api/versions/rollback` + `#versionRollbackCard` to `S8 Imager` (`v2.6.0`) + header version badge (`v2.6.0 | AP v3.0.0 | HW v1.0.2`).

---

## 2. Quick Verification & Continuity Commands for Gemini 3.8

```powershell
# 1. Audit Universal Versioning & Zero Drift Across All 8 Project Layers
python scripts/version_manager.py --status

# 2. Run full live hardware + kernel + package non-regression suite (requires phone on USB RNDIS 192.168.7.2)
python tests/hardware/test_full_non_regression_e2e.py

# 3. Run desktop-app unit, UI syntax, and Playwright E2E human-flow suite
python -m unittest desktop-app/tests/test_unit_core.py desktop-app/tests/test_ui_syntax.py desktop-app/tests/test_flash_human_flow.py

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

