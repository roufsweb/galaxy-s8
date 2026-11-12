# Project Future & Phased Execution Roadmap

## Ultimate Goal
Run full native Linux (Ubuntu ARM64) on the screenless Samsung Galaxy S8 (`SM-G950N`, Exynos 8895) with:
* Native `systemd` (PID 1)
* Working Docker engine & KVM virtualization
* Working USB Type-C port (DisplayPort 1.2 Alt Mode video output + USB Host/OTG + Power Delivery)
* Headless stability and hardware longevity (battery eliminator + active cooling)
* Turnkey desktop helper app for automated 1-click flashing, live telemetry, clean wiping, and headless USB configuration

---

## Sequential Step-by-Step Execution Plan

We execute this project **one step at a time**, verifying each step before proceeding to the next.

```
[ Step 1: Device State & Connectivity Check ]
                      │
                      ▼
[ Step 2: Kernel Defconfig Update (Docker & KVM) ]
                      │
                      ▼
[ Step 3: Kernel Compilation & Boot Image Packaging ]
                      │
                      ▼
[ Step 4: Flash Kernel & Validate Headless Control (Odin/ADB) ]
                      │
                      ▼
[ Step 5: Build & Deploy Native Ubuntu ARM64 Rootfs & Autoboot ]
                      │
                      ▼
[ Step 6: Validate Hardware Subsystems (Audio, Wi-Fi, DisplayPort, VNC Lite, OTG) ]
                      │
                      ▼
[ Step 7: Hardware Modifications for 24/7 Reliability (Battery Eliminator & Cooling) ]
                      │
                      ▼
[ Step 8: Universal Multi-Distro ARM64 Hardware Adaptation Engine ]
                      │
                      ▼
[ Step 9: Desktop EXE Hub — Live Device Telemetry, Clean Re-Flash & Headless USB Config ]
```

---

### Step 1: Device State & Connectivity Baseline
* **Goal:** Determine the current state of the phone and verify communication with PC without the screen.
* **Actions:**
  1. Check device power and bootloader states via blind key combinations.
  2. Connect to PC via high-speed USB-C cable.
  3. Verify detection in Device Manager (`PID_685D` Odin Download Mode, `PID_6860` / `ce10171ab3e9620804` ADB Recovery).
  4. Establish host communication baseline.

---

### Step 2: Kernel Configuration for Docker & KVM
* **Goal:** Enable all missing kernel namespaces, cgroups, overlayfs, and bridge network drivers in `galaxy-s8-kvm-kernel`.
* **Actions:**
  1. Add `CONFIG_PID_NS=y`, `CONFIG_IPC_NS=y`, `CONFIG_UTS_NS=y`, `CONFIG_CGROUP_DEVICE=y`, and `CONFIG_OVERLAY_FS=y` to defconfig.
  2. Strip Samsung proprietary DEFEX security lockdown.
  3. Verify KVM virtualization flags are active.

---

### Step 3: Compile Custom Linux 4.4 Kernel & Package Boot Image
* **Goal:** Build a bootable `boot.img` and package it into an Odin-flashable `.tar`.
* **Actions:**
  1. Compile using bundled toolchain and embed full 9-firmware Calliope DSP suite into ramdisk.
  2. Generate device tree image with `dtbtool`.
  3. Repack ramdisk CPIO with auto-boot trigger on `sys.usb.ffs.ready=1`.
  4. Build compact `Galaxy_S8_Linux_AP.tar`.

---

### Step 4: Flash Kernel & Validate Headless Control
* **Goal:** Flash the new kernel to the device and verify it boots with ADB access and video out.
* **Actions:**
  1. Put the device into Download Mode blindly via key combinations (**Volume Down + Bixby + Power** for 12s).
  2. Flash via Odin AP.
  3. Re-plug USB cable to trigger Windows host controller bus re-enumeration.
  4. Verify root ADB connectivity in recovery and haptic feedback alerts.

---

### Step 5: Deploy Native Ubuntu ARM64 Rootfs & Autoboot
* **Goal:** Deploy Ubuntu 24.04.5 LTS (`Noble Numbat`, `glibc 2.39`, `aarch64`) root filesystem to run natively with auto-boot on battery power.
* **Actions:**
  1. Stream compressed rootfs image over USB to `/data` and decompress using octa-core `pigz`.
  2. Deploy master supervisor `/data/linux/start_all.sh` to initialize PMIC fast-charging, V4L2 panic guards, Wi-Fi, audio, and desktop.
  3. Validate standalone battery boot: disconnect USB and battery, power on via button, and verify sequential vibration pulses and Wi-Fi association.

---

### Step 6: Validate Hardware Subsystems (Audio, Wi-Fi, DisplayPort, VNC Lite, OTG)
* **Goal:** Verify and stabilize all Exynos 8895 hardware subsystems under native Linux.
* **Actions:**
  1. Broadcom BCM4361 Wi-Fi auto-association (Dual-band 2.4/5GHz, DHCP).
  2. Maxim MAX77865 PMIC 1,500 mA fast charging and 4.3V UVLO brownout protection.
  3. TigerVNC X11 server (`:5901`) and rock-solid HTML5 Web Desktop via VNC Lite (`:6080`).
  4. USB-C DisplayPort 1.2 Alt-Mode video output (`exynos_dp_bridge` double-buffered ION streaming to DECON2 at 1080p 60Hz).
  5. USB Host / OTG mode with 5V VBUS booster (`booster = ON`) for hubs, storage, mice, and keyboards.
  6. Calliope DSP audio routing (`hw:0,0` speaker out, `hw:0,9` DMIC1 mic capture).
  7. Docker CE container engine validation.

---

### Step 7: Hardware Modifications for 24/7 Reliability
* **Goal:** Ensure the device can run permanently without battery degradation or thermal throttling.
* **Actions:**
  1. Wire the 4.10V DC buck converter and 10 kΩ thermistor to bypass the lithium-ion battery.
  2. Mount heatsink and cooling fan over the exposed Exynos 8895 SoC midframe.

---

### Step 8: Universal Multi-Distro ARM64 Hardware Adaptation Engine (CORE ARCHITECTURE)
* **Goal:** Enable users anywhere in the world to download ANY standard generic ARM64 Linux image or rootfs archive (Ubuntu Noble/Jammy, Debian Bookworm/Trixie, Arch Linux ARM, Alpine, Kali ARM64, Fedora) and flash it to the Galaxy S8 with 100% automated hardware adaptation.
* **Autonomous Architecture:**
  1. **Zero-Odin Dependency for OS Changes:** The Flasher EXE directly manages UFS storage `/dev/block/sda24` (`USERDATA`) over root ADB—handling process termination, unmounting, fast storage wiping, and filesystem creation with zero kernel lock deadlocks.
  2. **Universal Image Decompression & Conversion:** Handles `.img.gz`, `.tar.xz`, `.tar.gz`, `.tar.lz4`, `.iso`, and raw `.img` files, streaming to `/data` and extracting to `/data/linux/rootfs.img`.
  3. **Automated Hardware Shim & Firmware Injection:**
     * Calliope DSP 9-firmware suite in `/etc/firmware/` and ALSA `/etc/asound.conf`.
     * Exynos 8895 USB-C DisplayPort / HDMI hardware daemon (`exynos_dp_bridge`).
     * Physical chassis button daemon (`s8_button_daemon`) and input bridge (`s8_input_bridge`).
     * MAX77865 PMIC 1,500 mA fast charge unlock & UVLO bypass.
     * V4L2 ISP kernel panic guard (`rm -f /dev/video[1-9][0-9]*`).
     * Broadcom BCM4361 Wi-Fi firmware and nvram configuration.
     * Headless remote desktop (TigerVNC `:5901` + VNC Lite Web Remote Desktop on `:6080` + OpenSSH on `:22`).
  4. **Pre-Boot System Customization:** Injects Wi-Fi credentials (`wpa_supplicant.conf`), custom hostname, and root/user passwords dynamically into any rootfs before first launch.
  5. **Custom Package Injection Pipeline:** Injects user-specified `.deb` / `.apk` / binary packages into `/mnt/ubuntu` before boot.

---

### Step 9: Desktop EXE Hub — Live Device Telemetry, Clean Re-Flash & Headless USB Config (FUTURE ROADMAP)
* **Goal:** Upgrade `GalaxyS8_OS_Flasher.exe` into a comprehensive desktop workstation control hub that provides real-time device status recognition, 1-click clean re-flashing/distro switching, and live USB-based headless system/network configuration without requiring an external monitor, keyboard, or mouse.

#### 9.1: Live Post-Flash Device Telemetry & OS Status Inspector
* **Capabilities:**
  1. **Running OS & Distro Identification:** Dynamically inspects the connected phone to detect whether native Linux is actively running or currently flashed. Reports the active distribution name and version (e.g., `Ubuntu 24.04.5 LTS Noble Numbat`), Kernel version (`4.4.111-cyanogenmod`), system architecture (`aarch64`), and rootfs image size/utilization.
  2. **Live Network Telemetry:** Displays current assigned IP address (`wlan0`), associated Wi-Fi SSID, link quality/signal strength, gateway, and active listening network ports (OpenSSH `:22`, TigerVNC `:5901`, VNC Lite Web Desktop `:6080`, CasaOS `:8080`).
  3. **Headless Hardware Health Telemetry:** Reads and displays real-time battery charge percentage (%), charge current (mA), MAX77865 PMIC charging status, battery temperature, SoC temperature, and CPU cluster clock frequencies.
  4. **Visual Status Badges:** Presents clear color-coded status badges: `[ONLINE - UBUNTU 24.04 RUNNING]`, `[CHARGING - 1500mA FAST]`, `[RECOVERY / BOOTING]`, or `[NO OS INSTALLED]`.

#### 9.2: Clean Distro Re-Flash Engine (Full Wipe & Fresh Deploy)
* **Capabilities:**
  1. **Safe Chroot Process & Storage Release:** Automatically terminates all running daemons inside `/mnt/ubuntu`, detaches loop devices (`losetup -D`), and safely releases block device locks on `/dev/block/sda24`.
  2. **Complete Storage Purge:** Cleanly wipes `/data/linux/*` and previous rootfs images in under 1.5 seconds without filesystem corruption or UFS deadlock.
  3. **1-Click Distro Switching:** Allows selecting any new generic ARM64 Linux image from disk and flashing it with full automated Exynos hardware shim injection.
  4. **Zero-Brick Guarantee:** Executes 100% over root ADB in recovery mode without flashing bootloader partitions or requiring Odin intervention.

#### 9.3: Live Headless USB Network & System Configuration Hub (In-App Running Window)
* **Goal:** Enable users anywhere in the world to connect their phone to PC via a single USB cable and configure or reconfigure Wi-Fi, network IPs, and credentials on a running system without needing an external monitor, keyboard, or mouse.
* **Capabilities:**
  1. **Live Wi-Fi Configuration Window:**
     * Remotely scans available Wi-Fi access points visible to the phone's Broadcom BCM4361 radio.
     * Configure or change Wi-Fi SSID and Password (WPA-PSK, WPA2, WPA3, or Open networks).
     * Toggle between DHCP automatic IP assignment and Static IP configuration (Static IP Address, Subnet Mask, Default Gateway, Primary/Secondary DNS).
     * Applies changes live to `/data/linux/wpa_ubuntu.conf` and signals `wpa_supplicant` and `dhclient` to re-associate immediately without rebooting the device.
  2. **Live System Identity & Credential Management:**
     * Change device hostname on the fly.
     * Update root and user login passwords securely.
     * Inject and manage SSH public keys (`authorized_keys`) for passwordless remote access.
  3. **Seamless Headless User Experience:**
     * Eliminates the traditional chicken-and-egg problem of headless Linux setup. Any user, regardless of their local network environment, can configure networking and credentials in seconds directly from the desktop GUI.

---

## Milestone Progress Log

> [!NOTE]
> **Checkmark Rule:** Items marked `[x]` have been empirically verified or confirmed working on physical hardware by the user. Items marked `[ ]` are pending user hardware verification or represent upcoming roadmap features.

- [x] **Initial Research & Feasibility** (Headless SM-G950N Exynos 8895 architecture confirmed).
- [x] **Project Governance & Rulebook** (`GEMINI.md`, 20 anti-hallucination & architecture rules, AP synchronization mandate, vanilla stock OS invariant, memory management established).
- [x] **Step 1: Device State & Connectivity Baseline** (Confirmed: USB-C cable detection, root ADB in recovery mode, Odin COM port communication verified).
- [x] **Step 2: Kernel Configuration for Docker & KVM** (Applied `CONFIG_PID_NS=y`, `CONFIG_CGROUP_DEVICE=y`, DEFEX disabled in kernel source).
- [x] **Step 3: Compile Custom Linux 4.4 Kernel & Package Boot Image** (`boot_ubuntu_autoboot.img` 38.9 MB on `sda7` with 9 Calliope DSP firmwares).
- [x] **Step 4: Flash Kernel & Validate Headless Control** (Odin AP flash passes, haptic sequence signals boot, USB bus re-enumerates).
- [x] **Step 5: Deploy Native Ubuntu ARM64 Rootfs & Autoboot** (Verified by user: phone boots natively on battery alone, executes sequential vibration alerts, and associates to Wi-Fi at 192.168.0.227).
- [x] **Basic OS Flashing via Desktop EXE** (Verified by user: flasher transfers image to 100%, tracks UFS progress, extracts rootfs on octa-core CPU, and launches).
- [x] **Broadcom BCM4361 Wi-Fi Auto-Association** (Verified by user: phone automatically connects to local Wi-Fi network at boot).
- [x] **Maxim MAX77865 PMIC 1500mA Fast Charging** (Verified: hardware register unlock bypasses 500mA limit to charge without brownout).
- [x] **Vanilla Stock OS Flashing & Modular Layering Architecture** (Codified: base OS images remain 100% upstream stock; phone-specific battery, Wi-Fi, audio, and display configurations are applied post-boot via desktop app / supervisor).
- [x] **Roufsweb Protocol (RWP) Dual Transport & 3-Step CI/CD Protocol** (Implemented: Wired USB ADB & Wi-Fi RWP dual-transport contract with 3-step verification across Backend, Frontend, and Transport).
- [ ] **Step 6: Validate Hardware Subsystems (Audio, Wi-Fi, DisplayPort, VNC Lite, OTG)**:
  - [x] USB-C DisplayPort 1.2 Alt-Mode external display output (Verified by user: display worked immediately on cable plug-in; survived cold power cycles).
  - [x] Type-C CC Pin Dynamic Power Arbitration & Fast Disconnect Watchdog (Integrated: smart detection of unpowered vs self-powered monitors, fast watchdog disarms booster to prevent PC USB conflicts, safe 5V fast charging).
  - [ ] Web Remote Desktop via VNC Lite (Standalone `vnc_lite.html` deployed with automatic reconnect and canvas scaling pending user test).
  - [ ] USB Host / OTG Peripherals (External flash drives, mice, keyboards via multi-function dock pending user hardware test).
  - [ ] ALSA Audio Playback & Capture (Maxim MAX98506 speaker and CS47L92 DMIC1 microphone pending user live listening test).
  - [ ] Docker CE Container Runtime (`docker run --rm hello-world`).
- [ ] **Step 7: Hardware Modifications for 24/7 Reliability** (Battery eliminator 4.10V buck converter + active heatsink cooling).
- [ ] **Step 8: Universal Multi-Distro ARM64 Hardware Adaptation Engine** (Autonomous deployment of generic non-Ubuntu ARM64 distributions).
- [ ] **Step 9: Desktop EXE Hub — Live Device Telemetry, Clean Re-Flash & Headless USB Config**:
  - [ ] 9.1: Live Post-Flash Device Telemetry & OS Status Inspector in Desktop EXE.
  - [ ] 9.2: Clean Distro Re-Flash Engine (Full Storage Wipe & Fresh Deploy).
  - [ ] 9.3: Live Headless USB Network & System Configuration Hub (In-App Running Window).
