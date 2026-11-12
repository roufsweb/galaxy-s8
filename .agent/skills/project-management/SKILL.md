---
name: project-management
description: Master project governance skill synthesizing milestone tracking, feature isolation rules, full-permission native kernel standards, human-flow E2E testing, and Gemini 3.8 continuity handoffs for the Galaxy S8 Native Linux project.
---

# Project Management & Non-Regression Governance (`project-management`)

> [!IMPORTANT]
> **THE IRON LAW OF FEATURE ISOLATION:**
> **No new feature, package, or kernel modification may ever degrade, block, or break an existing working feature.**
> Every capability added (e.g., DisplayPort cursor fix, USB Host role switching, Docker/HAOS namespaces, or multi-distro provisioning) MUST pass full regression verification across all existing subsystems before completion.

---

## 1. Core Architectural Pillars

### 1.1 Absolute Permission & Native Linux Kernel (`4.4.111-s8-universal-v2`)
The kernel and initramfs MUST grant **100% unrestricted native hardware access and container/OS permissions**:
1. **Real `systemd` / OS Init as PID 1:**
   - Ramdisk `/init` mounts target rootfs (`/dev/sda25`, `/dev/mmcblk0p2`, or `/data/linux/rootfs.img`), injects non-intrusive hardware bridges, and executes `switch_root` directly into the guest OS `/sbin/init` as PID 1.
2. **Zero Samsung Security Locks:**
   - `CONFIG_SECURITY_DEFEX=n`, `CONFIG_RKP_CFP=n`, `CONFIG_FIVE=n`, `CONFIG_PROCA=n`, SELinux permissive/disabled.
3. **Full Container, Supervisor & Virtualization Permissions (Docker / Home Assistant OS / LXC / OpenWrt):**
   - Full namespace suite: `CONFIG_NAMESPACES=y`, `CONFIG_USER_NS=y`, `CONFIG_PID_NS=y`, `CONFIG_NET_NS=y`, `CONFIG_IPC_NS=y`, `CONFIG_UTS_NS=y`, `CONFIG_CGROUP_NS=y`.
   - Full cgroup hierarchy: `CONFIG_CGROUPS=y`, `CONFIG_MEMCG=y`, `CONFIG_BLK_CGROUP=y`, `CONFIG_CGROUP_DEVICE=y`, `CONFIG_CGROUP_FREEZER=y`, `CONFIG_CGROUP_PIDS=y`, `CONFIG_CPUSETS=y`, `CONFIG_CGROUP_SCHED=y`, `CONFIG_FAIR_GROUP_SCHED=y`, `CONFIG_CFS_BANDWIDTH=y`.
   - Storage & network virtualization: `CONFIG_OVERLAY_FS=y`, `CONFIG_BRIDGE=y`, `CONFIG_VETH=y`, `CONFIG_MACVLAN=y`, `CONFIG_VLAN_8021Q=y`, `CONFIG_POSIX_MQUEUE=y`, `CONFIG_SECCOMP=y`, `CONFIG_BINFMT_MISC=y`.
4. **Full Native Hardware Performance:**
   - Octa-core CPU (4x Exynos M2 @ 2.314 GHz + 4x Cortex-A53 @ 1.690 GHz) with thermal-aware governor profiles.
   - Mali-G71 MP20 GPU (20 cores @ 546 MHz).
   - Calliope ABOX DSP (9 firmwares embedded in ramdisk + rootfs) driving MAX98506 speaker (`hw:0,0`) and CS47L92 DMIC1 (`hw:0,9`).

### 1.2 Universal Multi-Distro Support (`galaxy-s8-hw`)
Hardware provisioning must work out-of-the-box on **every** Linux distribution:
- **Debian / Ubuntu / Kali:** Native `.deb` (`packages/dist/galaxy-s8-hw_1.0.2_arm64.deb`) + `systemd` units.
- **Alpine / OpenWrt / Arch Linux ARM / Home Assistant OS / SteamOS:** Universal tarball (`packages/dist/galaxy-s8-hw-universal-arm64.tar.gz`) + POSIX `install-universal.sh` supporting `systemd`, `OpenRC` (`/etc/init.d/`), `procd` (OpenWrt), and `/etc/local.d/` or supervisor startup hooks.

### 1.3 Human-Flow End-to-End (E2E) Testing Architecture
Testing must replicate **real human workflows** across all 4 layers simultaneously:
1. **Layer 1 — Desktop App UI & DOM Flow:** User opens `S8 Imager`, views live telemetry, selects any OS distribution and storage target (`internal` UFS / `sdcard` / `loop`), configures Wi-Fi/SSH, and triggers flashing or terminal sessions.
2. **Layer 2 — Backend & RWP Transport (`192.168.7.2:7860`):** Zero-config USB RNDIS + CDC-ACM Serial (`/dev/ttyGS0`) + WebSocket PTY (`env=os` and `env=ap`).
3. **Layer 3 — Live Hardware & Subsystem Non-Regression Matrix:**
   - Verify PID 1 (`systemd` / init running cleanly, 0 failed units).
   - Verify PMIC 1500mA fast charge & V4L2 camera panic guard (`/dev/video100+` removed, `/dev/video6..9` MFC intact).
   - Verify USB-C DisplayPort (`s8_dp_daemon` + `exynos_dp_bridge` running, cursor alpha `0xFF` clean).
   - Verify Input Bridge (`s8_input_bridge` connected to X11 `:1` with `XTest`).
   - Verify Audio (Calliope ABOX bound, ALSA playback/capture cards active).
   - Verify Network (USB RNDIS `192.168.7.2`, USB Ethernet DHCP auto-config, Broadcom Wi-Fi `wlan0`).
   - Verify Performance & Thermal safety (CPU/GPU clocks healthy, SoC temp `< 55 C` idle).

---

## 2. Synthesized Documentation, Versioning & Tracking Workflow

Whenever a hardware fix, kernel build, distro test, or architectural milestone completes, synchronize the 5 tracking ledgers:
1. **`VERSION_MANIFEST.json` & `VERSIONS.md`** (via [`versioning-and-rollback-manager`](file:///e:/rouf/galaxy-s8/.agent/skills/versioning-and-rollback-manager/SKILL.md)): Run `python scripts/version_manager.py --sync` and `python scripts/version_manager.py --status` to record the exact version, SHA-256, and empirical status (`VERIFIED_WORKING` vs. `FAILED`).
2. **`FINDINGS.md`** (via [`project-findings-manager`](file:///e:/rouf/galaxy-s8/.agent/skills/project-findings-manager/SKILL.md)): Record empirical root cause, register/code fix, and verification output.
3. **`HISTORY.md`** (via [`project-history-manager`](file:///e:/rouf/galaxy-s8/.agent/skills/project-history-manager/SKILL.md)): Append chronological execution entry.
4. **`PROJECT_INDEX.md`** (via [`project-index-manager`](file:///e:/rouf/galaxy-s8/.agent/skills/project-index-manager/SKILL.md)): Run `python scripts/project_index.py --build`.
5. **`docs/GEMINI_3_8_HANDOFF.md`**: Update the live continuity runbook so Gemini 3.8 can resume instantaneously at any point.

---

## 3. Mandatory Gemini 3.8 Continuity Handoff Protocol

Because high-tier model quota (Gemini 4 Argon) is finite, **after completing each major function or milestone**:
1. Update [`docs/GEMINI_3_8_HANDOFF.md`](file:///e:/rouf/galaxy-s8/docs/GEMINI_3_8_HANDOFF.md) with:
   - Exact completed work and verified state on the live phone (`192.168.7.2`).
   - Remaining queued tasks in priority order.
   - Exact copy-pasteable commands for Gemini 3.8 to run next.
2. Include a concise **`### Gemini 3.8 Continuity Prompt`** block at the bottom of your response to the user so they can copy-paste it directly into Gemini 3.8 if their quota expires.

