# Project Future & Phased Execution Roadmap

## Ultimate Goal
Run full native Linux (Ubuntu ARM64) on the screenless Samsung Galaxy S8 (`SM-G950N`, Exynos 8895) with:
* Native `systemd` (PID 1)
* Working Docker engine & KVM virtualization
* Working USB Type-C port (DisplayPort 1.2 Alt Mode video output + USB Host/OTG + Power Delivery)
* Headless stability and hardware longevity (battery eliminator + active cooling)

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
[ Step 4: Flash Kernel & Validate Headless Control (ADB/scrcpy/HDMI) ]
                      │
                      ▼
[ Step 5: Build & Deploy Native Ubuntu ARM64 Rootfs ]
                      │
                      ▼
[ Step 6: Validate Docker Engine & Type-C DisplayPort Output ]
                      │
                      ▼
[ Step 7: Hardware Mods (Battery Eliminator & Active Cooling) ]
```

---

### Step 1: Device State & Connectivity Baseline (CURRENT STEP)
* **Goal:** Determine the current state of the phone and verify communication with your PC without the screen.
* **Actions:**
  1. Check if the device is currently turned on, off, or in a boot loop.
  2. Plug the device into your PC via USB cable.
  3. Verify how your PC detects it (ADB device, Samsung USB Mobile Device, or COM port in Device Manager).
  4. Test if you have a USB-C hub with HDMI out to connect to an external monitor/TV.

---

### Step 2: Kernel Configuration for Docker & KVM
* **Goal:** Enable all missing kernel namespaces, cgroups, overlayfs, and bridge network drivers in `galaxy-s8-kvm-kernel`.
* **Actions:**
  1. Add `CONFIG_CGROUP_DEVICE=y`, `CONFIG_CGROUP_PIDS=y`, `CONFIG_OVERLAY_FS=y`, and related Docker flags to `exynos8895-dreamltekor_defconfig`.
  2. Verify KVM virtualization flags are active.

---

### Step 3: Compile Custom Linux 4.4 Kernel & Package Boot Image
* **Goal:** Build a bootable `boot.img` and package it into an Odin-flashable `.tar`.
* **Actions:**
  1. Compile using the bundled `aarch64-linux-android-4.9` GCC toolchain.
  2. Build DTB using `dtbtool`.
  3. Repack ramdisk and kernel using `AIK-Linux`.
  4. Create `boot_custom_docker.tar`.

---

### Step 4: Flash Kernel & Validate Headless Control
* **Goal:** Flash the new kernel to the device and verify it boots with ADB access and video out.
* **Actions:**
  1. Put the device into Download Mode blindly via key combinations.
  2. Flash via Odin.
  3. Connect via ADB / `scrcpy` and verify kernel version (`uname -r`) and Docker compatibility (`check-config.sh`).
  4. Test external monitor output via USB-C to HDMI adapter/hub.

---

### Step 5: Deploy Native Ubuntu ARM64 Rootfs
* **Goal:** Set up an Ubuntu 22.04 LTS (arm64) root filesystem to run natively with `systemd`.
* **Actions:**
  1. Generate or extract an Ubuntu ARM64 rootfs image.
  2. Configure rootfs auto-login, OpenSSH server, and network auto-connect.
  3. Configure the boot ramdisk to mount the Ubuntu rootfs as root (`/`).

---

### Step 6: Validate Docker & Peripherals under Ubuntu
* **Goal:** Ensure Docker and USB-C Type-C peripherals work under native Linux.
* **Actions:**
  1. Run native `docker run --rm hello-world`.
  2. Verify external display (X11/framebuffer or Wayland on HDMI).
  3. Verify USB mouse, keyboard, and Gigabit Ethernet over the USB-C dock.

---

### Step 7: Hardware Modifications for 24/7 Reliability
* **Goal:** Ensure the device can run permanently without battery degradation or thermal throttling.
* **Actions:**
  1. Wire the 4.10V DC buck converter and 10 kΩ thermistor to bypass the lithium-ion battery.
  2. Mount heatsink and cooling fan over the exposed Exynos 8895 SoC midframe.

---

## Milestone Progress Log
- [x] Initial hardware, variant, and feasibility research completed.
- [x] Project governance, rules, memory, and skill files established.
- [x] **Step 1: Device State & Connectivity Baseline** (Confirmed: USB-C hub, HDMI display output, and PC communication verified)
- [ ] **Step 2: Kernel Configuration for Docker & KVM** (CURRENT STEP)
- [ ] Step 3: Compile Custom Linux 4.4 Kernel & Package Boot Image
- [ ] Step 4: Flash Kernel & Validate Headless Control
- [ ] Step 5: Deploy Native Ubuntu ARM64 Rootfs
- [ ] Step 6: Validate Docker & Peripherals under Ubuntu
- [ ] Step 7: Hardware Modifications for 24/7 Reliability
