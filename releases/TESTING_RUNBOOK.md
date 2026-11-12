# Samsung Galaxy S8 Native Ubuntu 24.04.5 LTS End-to-End Testing Runbook

Maintained by [roufsweb](https://github.com/roufsweb)

This runbook guides you step-by-step through resetting a Samsung Galaxy S8 (Exynos 8895 / `SM-G950N`, `SM-G950F`, `SM-G950FD`) to official factory stock firmware and testing our complete, standalone native Ubuntu 24.04 LTS platform installation with zero manual file transfers.

---

## Prerequisites & Required Tools

1. **Samsung Galaxy S8** (Exynos 8895).
2. **Windows PC** with:
   * Official Samsung Mobile USB Drivers installed.
   * Samsung Odin 3.14.1 (or Odin 3.13.1).
   * Android SDK Platform-Tools (`adb.exe` in system PATH).
3. **USB-C to USB-A Data Cable** connected directly to a rear motherboard USB 3.0 port.
4. **Firmware Packages:**
   * Official Samsung Stock Firmware (4-file AP, BL, CP, CSC for your model variant).
   * Standalone 1-Click Odin Package: `releases/Ubuntu_24.04_GalaxyS8_Full_Standalone_Odin.tar` (3.37 GB).

---

## Phase 1: Reset to Factory Stock Android

1. Put the Galaxy S8 into Download Mode:
   * Power off the device.
   * Hold **Volume Down + Bixby + Power** simultaneously for **11 to 13 seconds**.
2. In Odin 3.14.1:
   * Load the stock firmware files: `BL`, `AP`, `CP`, and `CSC` into their respective slots.
   * Click **Start** and allow Odin to complete the write (green **PASS!**).
3. First Boot into Stock Android:
   * Complete the initial Android setup wizard.
   * Connect to Wi-Fi to register device status with Samsung servers.

---

## Phase 2: Unlock the Bootloader (OEM Unlocking)

1. Open **Settings > About Phone > Software Information**.
2. Tap **Build Number** 7 times continuously until "Developer mode has been enabled" appears.
3. Return to **Settings > Developer Options**:
   * Enable **OEM Unlocking** (confirm the bootloader warning dialog).
   * Enable **USB Debugging**.
4. Power off the phone.

---

## Phase 3: Flash the Standalone Ubuntu Package via Odin

1. Put the phone into Download Mode:
   * Ensure the USB-C cable is connected to the PC.
   * Hold **Volume Down + Bixby + Power** simultaneously for **11 to 13 seconds**.
   * Release all buttons. Odin will display a blue COM port in the `ID:COM` box (`PID_685D`).
2. In Odin 3.14.1:
   * Click **AP** and select `releases/Ubuntu_24.04_GalaxyS8_Full_Standalone_Odin.tar`.
   * Verify under Options that **Auto Reboot** and **F. Reset Time** are checked.
   * Click **Start**.
   * Odin writes:
     * `boot.img` -> `BOOT` (`/dev/block/sda7`)
     * `recovery.img` -> `RECOVERY` (`/dev/block/sda8`)
     * `userdata.img.lz4` -> `USERDATA` (`/dev/block/sda24`)
   * Total flash duration is approximately 45 seconds.
3. Upon Green **PASS!**:
   * Unplug the USB-C cable and plug it right back in within 1 second.
   * This triggers Windows host controller bus re-enumeration, bringing ADB online immediately (`ce10171ab3e9620804`).

---

## Phase 4: Instant Automated First Boot

No manual file pushing or ADB setup scripts are required. The entire operating system was already written directly to `USERDATA` (`sda24`) by Odin.

1. The device powers on and executes `boot.img` on `sda7`.
2. At `t=2.5s`, the kernel triggers `start_all.sh` via the instant `on boot` hook.
3. The supervisor mounts the complete Ubuntu 24.04 rootfs, configures audio, starts Wi-Fi, brings up GNOME 46 desktop, launches TigerVNC (`:5901`), noVNC web interface (`:6080`), and SSH (`:22`).
4. At `t=12-15s`, the phone vibrates twice (2x 150 ms) to indicate that all desktop and networking services are active.
5. In your Windows file explorer, navigate to the `releases/` directory and double-click:
   ```cmd
   connect_desktop.bat
   ```
   This forwards USB ports and automatically launches your browser directly into the GNOME 46 macOS desktop at `http://localhost:6080/vnc.html` (Password: `ubuntu`).

---

## Phase 5: Complete Subsystem Verification Checklist

Execute these checks to verify that every hardware and software subsystem is operating cleanly:

### 1. Instant Boot Timing Check
* Open an ADB shell or SSH console and check uptime:
  ```bash
  adb shell "uptime"
  ```
* Power cycle the phone by holding the Power button for 8 seconds.
* Count the boot duration:
  * Phone powers on -> single haptic buzz.
  * At t=2.5s, kernel executes `on boot -> start ubuntu_boot`.
  * At t=12-15s, phone emits a double haptic pulse (2x 150 ms).
  * System is fully online in **under 15 seconds**.

### 2. Remote Desktop & GUI Check
* Open `http://localhost:6080/vnc.html` in your browser.
* Enter password: `ubuntu`.
* Verify:
  * Top macOS-style panel with Clock and Applications menu is rendered.
  * Bottom magnifying Plank dock is active.
  * Launch GNOME Console (`kgx`), GNOME Files (`nautilus`), and GNOME Web (`epiphany-browser`). All open smoothly without D-Bus timeouts.

### 3. Dual-Band Wi-Fi (2.4 GHz & 5 GHz) Check
* Open a terminal on the phone and scan for local networks:
  ```bash
  s8ctl wifi scan
  ```
* Verify:
  * Channels in Band 1 (2.4 GHz) and Band 2 (5 GHz) are detected.
  * Connect to your 5 GHz SSID (`ROUF_5G` or equivalent):
    ```bash
    s8ctl wifi connect "ROUF_5G" "YourPassword"
    ```
  * Verify link frequency is 5 GHz (`5180` to `5825` MHz):
    ```bash
    iw dev wlan0 link
    ```

### 4. Battery & MAX77865 PMIC Fast-Charge Check
* Query hardware telemetry:
  ```bash
  s8ctl status
  ```
* Verify:
  * Battery capacity reports accurate percentage (e.g. `100%`).
  * Current draw reflects fast charging (`> 300 mA` up to `1,500 mA`).
  * Battery health indicates `Good`.

### 5. Acoustic Hardware Check (Speaker & Microphone)
* Test speaker playback via Maxim MAX98506 amplifier:
  ```bash
  s8ctl audio test
  ```
  A clear 440 Hz acoustic sine wave plays through the bottom chassis speaker.
* Test digital microphone recording via Cirrus Logic CS47L92 DMIC1:
  ```bash
  arecord -D hw:0,9 -f S16_LE -r 48000 -c 2 -d 3 /tmp/test_mic.wav
  ```

### 6. MicroSD Storage Subsystem Check
* Insert a MicroSD card into the top tray.
* Query storage status:
  ```bash
  s8ctl sdcard
  ```
* Verify: Status reflects `MOUNTED @ /media/sdcard` with full read and write capacity.

### 7. Physical Chassis Buttons & Haptics Check
* Press **Volume Up** or **Volume Down**: emits a short 35 ms haptic click and adjusts master volume.
* Press **Bixby**:
  * Single click: launches terminal.
  * Double click: toggles the rear camera flashlight torch.
* Short press **Power**: toggles display DPMS power state.

### 8. USB-C DisplayPort 1080p60 Hardware Output Check
* Connect a USB-C to HDMI adapter or USB-C monitor.
* Verify:
  * Phone pulses haptic motor once for 150 ms to confirm video lock.
  * External display immediately shows the 1920x1080 @ 60 Hz GNOME desktop.
  * Hardware mouse cursor tracks smoothly with zero tearing.

### 9. Cold Power-Cycle & Power-Loss Recovery Check
* **Objective:** Verify that the system autonomously recovers from sudden power cuts, dead battery conditions, or cold resets with automatic ext4 journal replay and PMIC fast-charge re-negotiation.
* **Hardware Warning:** Avoid repeatedly disconnecting the physical battery cable (the motherboard FPC socket is rated for only ~20-30 cycles). Use the safe, 100% equivalent methods below:
* **Procedure A (PMIC Cold Reset via Hardware Latch):**
  1. Hold **Volume Down + Bixby + Power** for **30 seconds** continuously.
  2. Release all buttons. The MAX77865 PMIC drops `EN_BUCK`, wipes DRAM state, and initiates a true cold boot via S-Boot and EL2 TrustZone.
  3. Verify: Phone boots, double-vibrates (`2x 150ms`), unlocks 1500 mA fast charging, and ADB enumerates automatically.
* **Procedure B (Hard Power-Loss via Kernel SysRq):**
  1. Run:
     ```powershell
     adb shell "echo b > /proc/sysrq-trigger"
     ```
  2. The kernel immediately reboots without clean filesystem unmounting.
  3. Verify: `e2fsck -p -y /data/linux/rootfs.img` automatically replays the dirty journal, and the Linux desktop / services resume with zero orphaned inodes.
