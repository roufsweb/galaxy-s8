---
name: project-index-manager
description: Operational runbook and autonomous catalog tool for maintaining, verifying, and querying the comprehensive project asset index across kernels, boot images, flashers, drivers, scripts, and documentation on the Samsung Galaxy S8 native Linux project.
---

# Project Index Manager Skill (`project-index-manager`)

> [!CRITICAL]
> **TOKEN PRESERVATION & ZERO-WASTE FILE REVIEW MANDATE:**
> 1. **Do NOT blindly read entire files or review unnecessary files.** Every token must serve the current instruction.
> 2. **Check the Index First:** Query [`PROJECT_INDEX.md`](file:///e:/rouf/galaxy-s8/PROJECT_INDEX.md) or run `python scripts/project_index.py --query "<term>"` to find the exact target file.
> 3. **Targeted Reads Only:** Use `read_file` with explicit `StartLine` and `EndLine` parameters. Never read more than 100 lines at a time unless strictly required.
> 4. **Dependency Queue Protocol:** When inspecting a file that connects to or imports other files (e.g., UI $\rightarrow$ API $\rightarrow$ Device Manager $\rightarrow$ sysfs), **do NOT immediately jump to read all connected files**. Push dependent files to a pending queue and read them *only* when the immediate task reaches that execution layer.

---

## 1. Fast Asset & Dependency Query Commands

### Search Index for Specific Files or Capabilities
```powershell
python e:\rouf\galaxy-s8\scripts\project_index.py --query "<keyword>"
```
Examples:
```powershell
python e:\rouf\galaxy-s8\scripts\project_index.py --query "flasher"
python e:\rouf\galaxy-s8\scripts\project_index.py --query "displayport"
python e:\rouf\galaxy-s8\scripts\project_index.py --query "api.py"
```

### Query Vertex-to-Back Component Graph
```powershell
python e:\rouf\galaxy-s8\scripts\project_index.py --graph "<element_or_route>"
```
Examples:
```powershell
python e:\rouf\galaxy-s8\scripts\project_index.py --graph "flash"
python e:\rouf\galaxy-s8\scripts\project_index.py --graph "status"
python e:\rouf\galaxy-s8\scripts\project_index.py --graph "terminal"
```

---

## 2. Vertex-to-Back Connectivity Quick Reference

| Frontend Element | UI Page | API Route | Backend Handler | Target Subsystem / Node |
| :--- | :--- | :--- | :--- | :--- |
| `#connStatusDot` | Global Header | `GET /api/status` | `api.py` $\rightarrow$ `device.py` | USB state, Wi-Fi ping, Battery `/sys/class/power_supply/...` |
| `#btnTorchToggle` | Global Header | `GET /api/torch` | `api.py` $\rightarrow$ `device.py` | Rear Torch `/sys/class/leds/torch-sec1/brightness` |
| `#btnHapticTest` | Global Header | `GET /api/haptic` | `api.py` $\rightarrow$ `device.py` | Vibrator `/sys/class/timed_output/vibrator/enable` |
| `#btnOpenScreen` | Global Header | `GET /api/screen` | `api.py` $\rightarrow$ `adb.py` | ADB forwards `6080`, `5901`, `2222` $\rightarrow$ noVNC desktop |
| `#rebootSelect` | Global Header | `GET /api/reboot` | `api.py` $\rightarrow$ `adb.py` | S-Boot / Download Mode (`reboot`, `reboot download`) |
| `#btnBrowseImage` | `#pageFlash` | `GET /api/browse/image` | `api.py` $\rightarrow$ `pick_native` | Windows Explorer file dialog (tar.xz, img.gz, raw img) |
| `#storageSlider` | `#pageFlash` | `GET /api/storage/info` | `api.py` $\rightarrow$ `flasher.py` | `sda15` USERDATA (53.7 GB total, 4-48 GB slider) |
| `#btnStartFlash` | `#pageFlash` | `POST /api/flash/start` | `api.py` $\rightarrow$ `flasher.py` | MAX77865 PMIC $\rightarrow$ `mkfs.ext4` $\rightarrow$ rootfs unpack |
| `#flashLogStream` | `#pageFlash` | `GET /api/flash/status` | `api.py` $\rightarrow$ `flasher.py` | Polled 500ms for progress %, status, live log buffer |
| `#cpuFreqM2/A53` | `#pageDashboard` | `GET /api/status` | `api.py` $\rightarrow$ `device.py` | Exynos 8895 M2 & A53 `/sys/devices/system/cpu/cpu*/...` |
| `#dpStateBadge` | `#pageDashboard` | `GET /api/status` | `api.py` $\rightarrow$ `device.py` | Type-C DisplayPort `/sys/class/switch/hdmi/state` |
| `#termNativeInput` | `#pageTerminal` | `GET /api/exec` | `api.py` $\rightarrow$ `adb.py` | Dual-Shell: `/sbin/sh` (AP) vs `chroot /mnt/ubuntu` (OS) |
| `#btnWifiScan` | `#pageWifi` | `GET /api/wifi/scan` | `api.py` $\rightarrow$ `device.py` | BCM4361 scan (`s8ctl wifi scan`) |
| `#btnWifiConnect` | `#pageWifi` | `GET /api/wifi/connect`| `api.py` $\rightarrow$ `adb.py` | Writes to `/data/linux/connect_wifi.sh` |

---

## 3. Dependency Queue & File Reading Protocol

When given a multi-step task involving connected files:
1. **Identify the Entry Point:** Determine the exact starting file (e.g., `desktop-app/ui/index.html` for UI, `api.py` for endpoints).
2. **Read ONLY the Relevant Function / Block:** Do not load the entire file. Use line-bounded reads.
3. **Queue Connected Targets:**
   * Step 1: Examine UI binding in `index.html`.
   * Queue Step 2: Backend route in `api.py`.
   * Queue Step 3: Core logic in `flasher.py` or `device.py`.
   * Queue Step 4: Hardware driver or shell script (`s8ctl.py`, `start_all.sh`).
4. **Execute Linearly:** Finish Step 1 completely before dequeuing Step 2. Never read all 4 files in a single pass.

---

## 4. Re-Index & Verification Directives

Whenever any new file is created, updated, or removed:
```powershell
# 1. Verify all indexed files exist on disk (zero missing files)
python e:\rouf\galaxy-s8\scripts\project_index.py --verify

# 2. Rebuild the master index catalog with the dependency graph
python e:\rouf\galaxy-s8\scripts\project_index.py --build
```
