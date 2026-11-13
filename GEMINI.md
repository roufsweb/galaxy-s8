# Galaxy S8 Native Ubuntu 24.04.5 LTS, GNOME 46 macOS Sonoma GUI, USB-C DisplayPort & 1-Click Odin Installer — Master Rulebook for Gemini 3.8 High (`GEMINI.md`)

> [!IMPORTANT]
> **MANDATORY READING FOR GEMINI 3.8 HIGH / PRO / FLASH:**
> Do **NOT** guess, assume generic Linux/Android behavior, or hallucinate unverified hardware steps. Every rule, register address, partition size, driver quirk, kernel panic guard, and boot flow in this file has been **empirically verified on the live physical Samsung Galaxy S8 (`SM-G950N`, Serial `ce10171ab3e9620804`)**. Read Section 1 (12 Strict Anti-Hallucination Rules) before running any command or writing any code.

---

## 0. Current Live State & Completed Milestones (`2026-11-04`)

1. **Auto-Booting Native Ubuntu 24.04.5 LTS (`Noble Numbat`, `glibc 2.39`) Installed on `BOOT` (`/dev/block/sda7`) & `RECOVERY` (`sda8`):**
   * `e:\rouf\galaxy-s8\scratch\boot_ubuntu_autoboot.img` (`38,977,552` B `<= 41,943,040` B `sda7` limit) is **already flashed to `/dev/block/sda7` and `/dev/block/sda8`** and packaged into `e:\rouf\galaxy-s8\Ubuntu_24.04_GalaxyS8_Full_Odin.tar` (`77,967,360` B).
   * Embeds all 9 Calliope DSP audio firmwares in CPIO ramdisk, self-healing dirty journal replay via `e2fsck -p`, `s8_typec_daemon.py` CC-aware Type-C power supervisor, and auto-boot `ubuntu_boot` triggered on `sys.usb.ffs.ready=1`.
   * Its `init.rc` contains:
     ```rc
     on property:sys.usb.ffs.ready=1
         start ubuntu_boot

     service ubuntu_boot /sbin/sh /data/linux/start_all.sh
         user root
         group root
         disabled
         oneshot
         seclabel u:r:recovery:s0
     ```
   * Every time the phone powers on or reboots, `/data/linux/start_all.sh` automatically runs: unlocks `1,500 mA` MAX77865 fast charging, removes the buggy `/dev/video100+` V4L2 ISP nodes, connects `wlan0` (`<WIFI_SSID>` / `<WIFI_PASSWORD>` $\rightarrow$ `192.168.0.227`), mounts `/data/linux/rootfs.img` at `/mnt/ubuntu`, starts `dbus`, `sshd` (`:22`), `Xtigervnc :1` (`:5901`), `websockify` (`:6080`), **GNOME 46 + macOS Sonoma Desktop** (`/usr/local/bin/start_gnome_macos.sh`), `exynos_dp_bridge`, and `dockerd`, then pulses the haptic motor twice (`2x 150ms`).
2. **GNOME 46 + macOS Sonoma Desktop (`[LIVE & VERIFIED]`):**
   * Top Menu Bar (`gnome-panel` with Apple menu `Applications` / `Places` on left, Clock & Session on right) + `metacity` Window Manager + `gsd-xsettings` + bottom magnifying **Plank Dock** (`Transparent` theme, `48px` zoom).
   * Genuine **GNOME 46 GTK4/libadwaita applications** verified running simultaneously on `:1`:
     * **GNOME Files 46 (`nautilus`):** Runs as `root` via `/usr/local/lib/libnautilus_root.so` (`geteuid() -> 1000` shim) + `GTK_USE_PORTAL=0` (bypasses 25-second `xdg-desktop-portal` D-Bus timeout) + WhiteSur-Dark GTK4 theme + left-side red/yellow/green traffic-light buttons.
     * **GNOME Console 46 (`kgx`) & `gnome-terminal-server`:** Clean `root@Galaxy-S8-Ubuntu:~#` prompt (`C.UTF-8` locale + Android `aid_*` supplementary GIDs `1004..3011` added to `/etc/group`).
     * **GNOME Text Editor 46 (`gnome-text-editor`), Calculator 46 (`gnome-calculator`), System Monitor 46 (`gnome-system-monitor`), GNOME Web 46 (`epiphany-browser`), and `Galaxy S8 Hardware Center` (`s8ctl`).**
3. **USB-C DisplayPort / HDMI Hotplug Daemon (`exynos_dp_bridge`):**
   * Source: `e:\rouf\galaxy-s8\scratch\exynos_dp_bridge.c` $\rightarrow$ `/mnt/ubuntu/usr/local/bin/exynos_dp_bridge`.
   * Allocates `14.7 MB` in `/dev/ion` (`ION_HEAP_SYSTEM_MASK`), arms `DECON2` (`/dev/graphics/fb2`) in `FB_BLANK_POWERDOWN` while `/sys/class/switch/hdmi/state == 0`, and on plug-in (`state == 1`) negotiates EDID timings via `EXYNOS_GET_DISPLAYPORT_CONFIG` / `EXYNOS_SET_DISPLAYPORT_CONFIG`, calls `FBIOBLANK(FB_BLANK_UNBLANK)` (triggering `decon_enable` $\rightarrow$ `displayport_enable`), vibrates `150ms`, overlays hardware mouse cursor via `XFixesGetCursorImage`, and streams `:1` via `S3CFB_WIN_CONFIG` locked to hardware vertical blanking (`FBIO_WAITFORVSYNC` @ 60 Hz).
4. **Physical Chassis Button Daemon (`s8_button_daemon`):**
   * Source: `e:\rouf\galaxy-s8\scratch\s8_button_daemon.c` $\rightarrow$ `/usr/local/bin/s8_button_daemon`.
   * Maps `/dev/input/event3` (`gpio_keys`): Power (short=display DPMS, long=graceful reboot), Volume Up/Down (35ms haptic + X11 volume keys + ALSA master), Bixby single click (GNOME Console `kgx`), Bixby double click (rear torch toggle), Bixby long press (>1.2s: full 1080p screenshot sent directly to Telegram bot `@roufsantigravitybot`).
5. **Native ALSA Audio Subsystem (Speaker & DMIC1 Mic `[LIVE & VERIFIED]`):**
   * ABOX Calliope DSP: Embedded full 9-firmware suite in ramdisk, running at 1.18 GHz without IPC timeouts.
   * Speaker Playback: ALSA `hw:0,0` routed to Maxim MAX98506 amplifier (`SPK out` / `Speaker Gain 25`), verified over-the-air with host USB microphone (4.08x SNR at 440 Hz).
   * Digital Mic 1: ALSA `hw:0,9` (WDMA1) routed to Cirrus Logic CS47L92 DMIC1, verified capturing ambient sound (245.7 RMS amplitude).
   * Default ALSA: `/etc/asound.conf` with `type asym` providing universal transparent audio for all Linux apps.
6. **Hardware Performance Boost & Unified Management (`s8ctl`):**
   * Octa-core CPU: 4x M2 cores pinned at 2.314 GHz + 4x A53 cores at 1.690 GHz under `performance` governor.
   * Mali-G71 MP20 GPU: 20 shader cores locked at 546 MHz Booster mode.
   * Unified CLI at `/usr/local/bin/s8ctl`: status, CPU profiles, GPU boost, Wi-Fi GUI/scan, torch, haptics, battery, audio test, Bluetooth radio.
7. **noVNC Web Remote Desktop (`:6080` / `vnc.html` `[LIVE & VERIFIED]`):**
   * Nginx reverse proxy on `:6080` with pure WebSocket forwarder on `:6081` to TigerVNC `:5901`.
   * Hardened `/usr/share/novnc/app/ui.js` with optional chaining to prevent null element exceptions, allowing interactive control of the desktop from PC or mobile browsers without requiring a physical USB hub. Password: `ubuntu`.
8. **MicroSD Storage Subsystem (`/dev/block/mmcblk0` `[LIVE & VERIFIED]`):**
   * Auto-detects 14.6 GB MicroSD card (`ESPAUDIO`, FAT32) under DW MMC host controller `11500000.dwmmc2`, auto-mounts at `/media/sdcard` and bind-mounts to `/mnt/android_data/sdcard` with `umask=000` via `/data/linux/start_all.sh`. Accessible with full read/write across FileBrowser (`:8088`), CasaOS (`:8080`), and `s8ctl sdcard`.
9. **Cellular Modem & SIM Slot Architecture (`Shannon 359`):**
   * Kernel Shannon modem drivers active (`/dev/umts_ipc0`, `/dev/umts_boot0`, `/dev/umts_rfs0`) with 8 registered LTE interfaces (`rmnet0..7`). CP Boot Daemon (`/vendor/bin/cbd`) boots with `-tss333 -bs -ml` using `RADIO` partition (`sda10`) and `EFS` (`sda3`) for SMS gateway and mobile LTE internet failover.
10. **Front Multi-Color RGB Status LED (`/sys/class/sec/led/` `[LIVE & VERIFIED]`):**
   * **Hardware Presence:** The front RGB notification LED is **PHYSICALLY CONNECTED, CONFIGURED, AND ACTIVE**.
   * Driven by MAX77865 PMIC I2C driver (`kernel/drivers/leds/leds-max77865-rgb.c`) via `/sys/class/sec/led/`:
     * `led_pattern`: Hardware presets (0=Off, 5=Fully charged / Subtle Calm Green).
     * `led_blink`: Custom RGB timing (`<0xRRGGBB> <on_ms> <off_ms>`).
     * `led_brightness`: 0–255 master level.
   * Autonomous Supervisor (`/usr/local/bin/s8_led_supervisor.py`):
     * SUBTLE GREEN (Solid): Normal healthy Linux server / desktop operation.
     * PULSING BLUE (300ms/300ms): System booting / initializing rootfs.
     * SOFT AMBER (800ms/800ms): 1500mA Fast Charging in progress (<95%).
     * CALM CYAN (Solid 0x003333): External USB-C DisplayPort / HDMI active.
     * BLINKING RED (500ms/500ms): Battery low (<15%).
     * RAPID STROBE RED (150ms/150ms): Thermal alert (>70°C) or critical fault.

---

## 0.1 AI Permanent Memory & Subsystem Architecture Ledger (Synthesized from `PROJECT_INDEX.md`)

| Subsystem / Feature | Target Hardware Node / Sysfs Path | Primary Driver / Daemon | Control API & CLI | Status & Behavior |
| :--- | :--- | :--- | :--- | :--- |
| **Front Status LED** | `/sys/class/sec/led/` (`led_pattern`, `led_blink`, `led_brightness`) | `s8_led_supervisor.py` | `s8ctl led [green\|blue\|amber\|cyan\|red\|off]` | **PRESENT & ACTIVE**. Subtle Green = Healthy server |
| **Rear Torch LED** | `/sys/class/leds/torch-sec1/brightness` (0..10) | Kernel Flash Driver | `s8ctl torch on\|off`, `GET /api/torch` | Hardware LED torch on back chassis |
| **Chassis Vibrator** | `/sys/class/timed_output/vibrator/enable` | Exynos Timed Haptic Driver | `s8ctl haptic <ms>`, `GET /api/haptic` | 150ms pulse for boot, 2x 150ms for ready |
| **Physical Buttons** | `/dev/input/event3` (`gpio_keys`: Power, VolUp, VolDown, Bixby 703) | `s8_button_daemon` | Background Supervisor PID | VolUp/Down=ALSA, Bixby=Voice Assistant / Screenshot |
| **PMIC Fast Charging** | `/sys/class/power_supply/max77865-charger/data` | MAX77865 PMIC Driver | Register sequence (0xBD, 0xC3, 0xC0 0x3C, 0xB9 0x9E) | 1,500 mA fast charge & 4.3V UVLO unlock |
| **External Display** | `/dev/graphics/fb2` on `DECON2` | `exynos_dp_bridge` + `s8_typec_daemon.py` | `s8ctl display landscape\|portrait`, `:1` | 1920x1080 60Hz DisplayPort/HDMI output |
| **Speaker Audio** | ALSA `hw:0,0` (Maxim MAX98506 Class-D Amp) | Calliope ABOX DSP (`etc/firmware/`) | `aplay`, `s8ctl sound test` | High-fidelity speaker playback |
| **Microphone** | ALSA `hw:0,9` (CS47L92 DMIC1, WDMA1) | Calliope ABOX DSP Capture | `arecord -D hw:0,9 -f S16_LE -r 16000` | Clean ambient voice capture |
| **Wi-Fi Subsystem** | `wlan0` (`192.168.0.227`), Broadcom BCM4361 | `dhd` (`/sys/module/dhd/parameters/`) | `connect_wifi.sh`, `s8ctl wifi` | Dual-band 2.4/5GHz Wi-Fi Station Mode |
| **USB Networking** | `rndis0` (`192.168.7.2/24`), CDC ACM `/dev/ttyGS0` | ConfigFS Composite Gadget | `s8_usb_agentd` (:7860), Dropbear `:22` | Zero-config USB RNDIS + serial terminal |
| **Remote Desktop** | Nginx `:6080` + Websockify `:6081` -> TigerVNC `:5901` | Xtigervnc + noVNC Web UI | `http://192.168.0.227:6080/vnc.html` | Password: `ubuntu`. Full GNOME 46 remote control |
| **Local AI Assistant** | Qwen 2.5 1.5B (`:8085`) + `whisper.cpp` + Piper TTS | `s8-voice-assistant` | Physical Bixby Key / CLI | Autonomous on-device voice conversation |
| **Animoji Avatar** | WebKitGTK window on `:1` (`/tmp/s8_avatar_state.json`) | `s8_avatar_window.py` | Real-time reactive lip-sync | 1080x1920 portrait animated face |
| **MicroSD Card** | `/dev/block/mmcblk0` -> `/media/sdcard` | DW MMC Host `11500000.dwmmc2` | `s8ctl sdcard`, FileBrowser `:8088` | Auto-mounted FAT32/ext4 external storage |

---

## 1. Strict Anti-Hallucination & Architecture Rules for Gemini 3.8 High

> [!CAUTION]
> **NEVER VIOLATE THESE EMPIRICALLY VERIFIED HARDWARE & ARCHITECTURE RULES:**

1. **INTERNAL OLED SCREEN ABSENT (`lcdtype=-1`) & FRONT RGB STATUS LED PRESENT:**
   * **Internal OLED Screen:** The internal mobile OLED display panel is **physically absent / disconnected** (`lcdtype=-1`). Video output is strictly via external USB-C DisplayPort/HDMI (`/dev/graphics/fb2` on `DECON2`) or web remote desktop (`noVNC :6080` / `TigerVNC :5901`). Never instruct the user to check or tap the internal phone screen.
   * **Front RGB Status LED (PRESENT & ACTIVE):** The front multi-color RGB notification LED is **PHYSICALLY CONNECTED, CONFIGURED, AND ACTIVE**. Controlled via MAX77865 PMIC sysfs (`/sys/class/sec/led/`):
     - `led_pattern`: Hardware presets (0=Off, 5=Fully charged / Subtle Green).
     - `led_blink`: Custom RGB timing (`<0xRRGGBB> <on_ms> <off_ms>`).
     - `led_brightness`: 0–255 master level.
     - Supervised dynamically by `/usr/local/bin/s8_led_supervisor.py` (Subtle Green = healthy Linux operation, Pulsing Blue = booting, Soft Amber = charging, Calm Cyan = DisplayPort active, Red = low battery or thermal alert).
   * **Haptic Vibrator & Rear Torch:** Supported in parallel via `/sys/class/timed_output/vibrator/enable` and `/sys/class/leds/torch-sec1/brightness`.
2. **EXYNOS 8895 V4L2 CAMERA ISP KERNEL PANIC GUARD (`fimc_is_ixs_video_querycap`):**
   * Calling `VIDIOC_QUERYCAP` on uninitialized Samsung camera ISP nodes (`/dev/video100`..`/dev/video220`) causes an immediate NULL-pointer dereference kernel panic (`fimc_is_ixs_video_querycap+0x24/0x68` in `/proc/last_kmsg`) whenever GStreamer (`gst-plugin-scanner`), `nautilus`, `webkit`, or `pipewire` scans `/dev/video*`.
   * **ALWAYS** run `rm -f /dev/video[1-9][0-9]* /dev/v4l-subdev*` at boot before starting Ubuntu (preserving `/dev/video0..9` for the Exynos MFC hardware H.264/HEVC video codecs `/dev/video6..9`).
3. **MAX77865 PMIC `1,500 mA` FAST-CHARGE & UVLO REGISTER UNLOCK:**
   * On standard USB ports (`Cable(USB)`, `cable_type=4`), Samsung's driver defaults `CHG_CNFG_09` (`0xC0`) to `450–500 mA`, which starves the phone under load.
   * **ALWAYS** write all 5 registers to `/sys/class/power_supply/max77865-charger/data` at boot:
     ```sh
     echo "0xBD 0x6C" > /sys/class/power_supply/max77865-charger/data  # Unlock CHGPROT
     echo "0xC3 0x61" > /sys/class/power_supply/max77865-charger/data  # VCHGIN_REG UVLO = 4.3V + DISSKIP
     echo "0xC0 0x3C" > /sys/class/power_supply/max77865-charger/data  # CHG_CNFG_09 = 1500mA input current limit (60 * 25mA)
     echo "0xB9 0x9E" > /sys/class/power_supply/max77865-charger/data  # CHG_CNFG_02 = 1500mA fast charge current (30 * 50mA)
     echo "0xB7 0x05" > /sys/class/power_supply/max77865-charger/data  # CHG_CNFG_00 = MODE_BUCK | MODE_CHGR (Watchdog OFF)
     echo 1500 > /sys/class/power_supply/battery/batt_tune_input_charge_current
     echo 1500 > /sys/class/power_supply/battery/batt_tune_fast_charge_current
     ```
4. **VERIFIED ODIN DOWNLOAD MODE COMBO (HOT & COLD RESET) & POST-FLASH RE-PLUG:**
   * Keep the USB-C cable **plugged into the PC** and hold **Volume Down + Bixby + Power** continuously for **11–13 seconds** $\rightarrow$ enters Odin Download Mode (`PID_685D` on `COM17`) directly with **no need to unplug and no need to press `Volume Up`**.
   * **Stalled/Halted State Guard:** If the SoC is frozen in an unresponsive state, hold all 3 buttons for **30 seconds** to force PMIC power-latch release, release for 1 second, then hold all 3 buttons for **13 seconds** $\rightarrow$ enters Download Mode reliably.
   * **Post-Odin USB Re-Plug Rule:** After Odin flashes with green `PASS!`, Windows USB host controllers frequently keep the old `PID_685D` endpoints suspended. Unplugging and immediately re-plugging the USB-C cable triggers instant hardware bus re-enumeration, immediately bringing ADB online.
5. **DO NOT REPLACE ANDROID `/init` WITH STANDALONE BUSYBOX `/init` ON `sda7`:**
   * Exynos 8895 DWC3 USB (`10c00000.dwc3`) only powers on when `adbd` sets `sys.usb.ffs.ready=1` via Android `/init`'s property socket. Keep `/init` and `adbd` intact and launch `/data/linux/start_all.sh` via `init.rc` `on property:sys.usb.ffs.ready=1`.
6. **UBUNTU 24.04.5 LTS (`glibc 2.39`) ON KERNEL `4.4.111`:**
   * Works natively at full speed on our DEFEX-free `4.4.111` kernel (`boot_ubuntu_autoboot.img`) with `/etc/apt/apt.conf.d/99sandbox` (`APT::Sandbox::User "root"; APT::Sandbox::Seccomp "false";`).
7. **GNOME 46 / GTK 4.14 / `libadwaita` REQUIREMENTS IN CHROOT VNC (`:1`):**
   * Export `GSK_RENDERER=cairo`, `GDK_BACKEND=x11`, `GTK_USE_PORTAL=0`, `GDK_DEBUG=no-portals`, `GTK_A11Y=none`, `LANG=C.UTF-8`, `LC_ALL=C.UTF-8`, `WEBKIT_DISABLE_SANDBOX_THIS_IS_DANGEROUS=1`, `WEBKIT_DISABLE_DMABUF_RENDERER=1`, `WEBKIT_DISABLE_COMPOSITING_MODE=1` in `/etc/profile.d/s8_gnome_env.sh`.
   * Move `/usr/share/dbus-1/services/org.freedesktop.portal.*` to `/usr/share/dbus-1/services.disabled/` so `nautilus` does not hang 25 seconds waiting for `systemd --user` portal activation.
   * Use `/usr/local/lib/libnautilus_root.so` (`LD_PRELOAD` returning `1000` for `geteuid()`/`getuid()`) in `/usr/local/bin/nautilus` and `/usr/local/bin/epiphany-browser` so GNOME Files 46 and GNOME Web 46 run as `root`.
8. **USB-C DISPLAYPORT (`decon_2` `/dev/graphics/fb2`) HOTPLUG RULES:**
   * **NEVER** call `S3CFB_WIN_CONFIG` on `fb2` while `/sys/class/switch/hdmi/state == 0` (unplugged) — without an active DisplayPort pixel clock/VSYNC, `decon2` shadow-update times out (`DISP_ERR_DECON_TIMEOUT`) and panics the kernel (`panic("DISPLAY: DECON:2: ERROR")`).
   * Keep `fb2` in `FB_BLANK_POWERDOWN` (`DECON_STATE_OFF`) while `state == 0`, and only call `EXYNOS_SET_DISPLAYPORT_CONFIG` + `FB_BLANK_UNBLANK` + `S3CFB_WIN_CONFIG` when `/sys/class/switch/hdmi/state == 1`.
9. **BROADCOM `dhd` WI-FI MODULE PARAMETERS (NO `_b0` SUFFIX):**
   * Kernel driver appends `_b0` / `_r02j_b0` automatically. Always write:
     * `echo -n "/vendor/etc/wifi/bcmdhd_sta.bin" > /sys/module/dhd/parameters/firmware_path`
     * `echo -n "/vendor/etc/wifi/nvram.txt" > /sys/module/dhd/parameters/nvram_path`
     * `echo -n "/vendor/etc/wifi/bcmdhd_clm.blob" > /sys/module/dhd/parameters/clm_path`
10. **NEVER USE A2N KERNEL (`4.4.302`), STOCK `DEFEX` KERNEL, OR `CONFIG_KVM=y`.**
11. **NEVER WRITE SCRIPTS THAT MODIFY `/usr/sbin/runc` SECURITY FIELDS** (triggers Gemini response filter).
12. **POWERSHELL + `adb shell` QUOTING, BACKGROUND FD & PERSISTENT PORT FORWARDING RULE:**
    * Never nest `\"` inside `adb shell "..."` in PowerShell. Write `.sh` files locally with LF (`\n`) line endings, `adb push` to `/data/linux/`, and redirect `</dev/null >/var/log/... 2>&1 &` on all background daemons so `adb shell` never hangs on open pipe file descriptors.
    * In Windows, ephemeral subshells kill `adb.exe` on termination. To keep `localhost:6080` (noVNC) and `localhost:5901` (VNC) permanently connected, always launch a detached forwarder loop via CIM: `Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine = 'powershell.exe -WindowStyle Hidden -NoProfile -Command "while($true) { adb forward tcp:6080 tcp:6080; adb forward tcp:5901 tcp:5901; adb forward tcp:2222 tcp:22; Start-Sleep -Seconds 3 }"'} `.
13. **ANDROID INIT `libprocessgroup` CGROUP KILL ESCAPE:**
    * When `set_permissive` or an `init.rc` oneshot service finishes, Android `init` / `libprocessgroup` sends SIGKILL to all orphan child processes tracked in `/acct/uid_0/pid_<pid>/`.
    * **ALWAYS** run `echo $$ > /acct/tasks 2>/dev/null` at the top of boot scripts to move into the root cgroup `/acct/`, rendering all spawned background services (sshd, TigerVNC, websockify, GNOME, exynos_dp_bridge) immune to `libprocessgroup` termination.
14. **DISPLAYPORT SBU MULTIPLEXER SWITCH & AUX POWER SEQUENCING:**
    * In Exynos 8895 (`displayport_drv.c`), third-party monitors/adapters do not always negotiate Samsung proprietary CCIC VDM, leaving the physical SBU analog switch open (`gpio_sw_oe = 1`) and AUX unpowered.
    * **ALWAYS** write `echo "0 0" > /sys/class/dp_sec/dp_sbu_sw_sel` (or `1 0` for flipped orientation) to enable the AUX switch (`gpio_sw_oe = 0`, active low) and power `VDD_DP_3P3`.
    * Use `echo 22 > /sys/class/dp_sec/link` (2 lanes @ 2.7 Gbps) or `echo 24 > /sys/class/dp_sec/link` (4 lanes @ 2.7 Gbps) to force hardware link training and flip `/sys/class/switch/hdmi/state` to 1. Toggle `echo "1,0" > /sys/class/dp_sec/dp_test` to force reset HDMI state back to 0.
15. **TYPE-C PORT ROLE: DFP / SOURCE ENFORCEMENT (`port_type = source`):**
    * In Exynos 8895, CCIC defaults to UFP (Device / Sink). When connected to a DisplayPort monitor or adapter, both sides present Rd pull-down resistors, causing an Alternate Mode negotiation deadlock (`is_dfp=0`, `VDM IRQ Status=0`).
    * **ALWAYS** write `echo source > /sys/class/typec/port0/port_type` and `echo 1 > /sys/class/sec/ccic/role_swap` to force Rp pull-up resistors and assert DFP / Host mode so the monitor identifies the phone as a DisplayPort source.
16. **ZERO-RISK GITHUB ACCOUNT PROTECTION & STRICT POLICY COMPLIANCE:**
    * **Storage & File Size Hard Limits:** Never commit or push any file exceeding 50 MB, and strictly never > 100 MB (GitHub hard rejection limit). All large images (`*.tar`, `*.img`, `*.lz4`, `*.zip`, `*.iso`, `*.bin`, `*.cpio`) and firmware dumps MUST remain strictly excluded via `.gitignore`. All large distribution binaries (`Ubuntu_24.04_GalaxyS8_Full_Standalone_Odin.tar`, 3.37 GB) must be hosted exclusively via Google Drive or external release mirrors.
    * **Zero Secret & Credential Leakage:** Never commit personal access tokens (PATs), API keys, OAuth secrets, private SSH keys, Wi-Fi passwords, or bot tokens. Always run `python scripts/sanitize_repo.py` before any commit to ensure 100% clean status.
    * **Acceptable Use & ToS Compliance:** Never commit proprietary Samsung stock system blobs or full commercial factory ROM dumps into git tracking. Maintain clean, original open-source scripts, drivers, configurations, and documentation that strictly adhere to GitHub Terms of Service and Community Guidelines.
17. **STRICT PRE-FLASH IMAGE VERIFICATION & WATCHDOG PANIC PREVENTION:**
    * **Zero Rogue Loops in Ramdisk:** `permissive.sh` MUST contain only `setenforce 0`. NEVER add background subshells (`while ! mount ...; do sleep 1; done`) or bind-mounts (`mount -o bind /system_root/... /etc/firmware`) into `permissive.sh`. Binding over `/etc/firmware` shadows the 9 embedded Calliope DSP firmwares, causing an immediate ABOX IPC timeout and kernel watchdog panic (`s3c2410_wdt` 15-second timer) at second 12.
    * **Ramdisk Firmware Integrity:** All 9 Calliope audio firmwares (`calliope_sram.bin`, `calliope_dram.bin`, `calliope_iva.bin`, `dsm.bin`, `AP_AUDIO_SLSI.bin`, `APBargeIn_AUDIO_SLSI.bin`, `SoundBoosterParam.bin`, `APBiBF_AUDIO_SLSI.bin`, `dsm_tune.bin`) MUST reside natively in `etc/firmware/` and `vendor/firmware/` in the CPIO ramdisk.
    * **Trigger Auto-Boot on `sys.usb.ffs.ready=1`:** Android `init.rc` MUST trigger `start ubuntu_boot` ONLY when `sys.usb.ffs.ready=1`. This guarantees `adbd` is fully initialized and operational as root before userland scripts run, preventing boot lockouts.
    * **Pre-Flash Automated Validator:** Never instruct a flash or ship an Odin tar without running `python scratch/build_rocksolid_boot.py` or automated verification confirming size `<= 41,943,040 B`, zero shadowing, zero rogue loops, and valid SVR4 CPIO alignment.
18. **AP SYNCHRONIZATION MANDATE (KERNEL / RAMDISK / AP ARCHIVE AUDIT):**
    * Any modification, hardware workaround, kernel parameter, boot script tweak, or driver injection tested or proven on the running OS/ROM (`/data/linux/`, chroot, ramdisk) MUST be immediately audited and backported into the Golden AP builders (`scratch/build_rocksolid_boot.py`, `arch/arm64/boot/Image`, `arch/arm64/boot/dts/exynos/exynos8895-dreamlte_kor_rev11.dtb`) and packaged into the release Odin tar archives (`Galaxy_S8_Linux_AP.tar`).
    * The AP tarball and kernel image remain the single source of truth for all users. Never leave tested fixes isolated in temporary filesystem files on the test bench.
19. **VANILLA STOCK OS FLASHING & POST-BOOT MODULAR PROVISIONING:**
    * Base operating system images flashed to userdata/system partitions must remain 100% vanilla, clean stock distributions downloaded directly from upstream mirrors (Ubuntu Rootfs, Debian Minimal, Alpine Linux, Arch Linux ARM, Kali Linux) without proprietary vendor blobs or OS rootfs modifications baked in.
    * All phone-exclusive hardware integrations that standard Single Board Computers (SBCs) lack (MAX77865 PMIC 1500mA fast charge & UVLO unlock, Broadcom BCM4361 Wi-Fi onboarding, Calliope ABOX audio routing, thermal governor, battery supervisor, rear torch, haptics, Type-C DisplayPort negotiation) MUST be modularly configured and provisioned *after* the stock OS boots, managed transparently via `/data/linux/start_all.sh`, `s8ctl`, and the S8 Imager desktop application.
20. **3-STEP VERIFICATION GATE & ROUFSWEB PROTOCOL (RWP) TRANSPORT CONTRACT:**
    * All development, CI/CD validation, and release builds must pass a strict 3-step verification architecture:
      1. **Layer 1: Backend Logic & REST APIs** (`DeviceManager`, ADB subprocess execution, HTTP endpoints `/api/status`, `/api/flash`, `/api/exec`, `/api/screen`).
      2. **Layer 2: Frontend UI & DOM Interactions** (Bento grid layout, restrained UX, state-driven CTA buttons, zero text bloat, no prompt echoes).
      3. **Layer 3: Device Connection & RWP Transport Contract** (Deterministic transport abstraction supporting Wired USB ADB and Wi-Fi RWP over SSH/WebSocket; automatic fallback, live shell streaming, and offline simulation safety).
21. **MANDATORY TELEGRAM NOTIFICATION & VISUAL VERIFICATION UPDATES:**
    * Antigravity MUST dispatch real-time asynchronous updates to the user's Telegram (`@roufsantigravitybot` -> chat ID configured in `.env`) whenever major milestones, CI/CD gates, build tasks, and verification runs finish.
    * **Visual Verification Mandate:** Every single verification process MUST generate and dispatch visual verification updates (screenshots/photos) directly to Telegram via `python scripts/send_telegram.py --photo <path> "<caption>"`.
    * In direct conversational responses, Antigravity MUST provide clickable markdown visual file links (`[Label](file:///...)`) to the verified visual screenshot artifacts so the user can visually inspect UI screens, terminal buffers, and system telemetry both in their browser/artifact viewer and on Telegram.
    * Never complete a verification cycle or deployment silently without dispatching visual proof to Telegram.
22. **STRICT BAN ON EMOJIS (CODE, COMMITS, LOGS, TELEGRAM, UI & DOCS):**
    * Emojis are strictly prohibited throughout the entire project. Never output, commit, or log emojis anywhere.
    * In Telegram updates (`@roufsantigravitybot`), replace emojis with clean bracketed ASCII status indicators: `[STAGE]`, `[INFO]`, `[OK]`, `[PASS]`, `[FAIL]`, `[ALERT]`, `[VISUAL PROOF]`.
    * In UI copy, buttons, and badges, use clean typography and Lucide SVG icons only. Never insert unicode emojis.
    * In commit messages, logs, terminal outputs, and documentation, maintain restrained, production-grade engineering prose.

23. **TOOLCHAIN CFP COMPATIBILITY & COLD POWER-CYCLE VERIFICATION (FINDING 115):**
    * **EL2 TrustZone CFP Incompatibility:** Never compile production kernels using modern generic cross-compilers (GCC 11, 12, 13) with `CONFIG_RKP_CFP=y`. Samsung Exynos 8895 EL2 micro-Hypervisor (uH) aborts modern branch relocations during cold boot in early `head.S`, freezing the SoC at instruction 0 (drawing 0.43A quiescent current with no haptics or ADB). Always use the official Samsung CFP toolchain (`aarch64-linux-android-4.9-cfp`) or compile with `CONFIG_RKP_CFP=n` and `CONFIG_RKP_CFP_JOPP=n`.
    * **Safe Cold-Reset Testing Protocol:** Never repeatedly disconnect the physical battery connector to test power loss (wears down delicate FPC motherboard socket pins). Use the 3 safe software cold-reset protocols: (a) hold **Volume Down + Bixby + Power for 30 seconds** (forces MAX77865 PMIC to drop power latch and reboot cold), (b) `adb shell "echo b > /proc/sysrq-trigger"` (forces ungraceful hardware kernel reboot to test journal replay), or (c) Download Mode reboot (`Vol Down + Power` 7s).

24. **UNIVERSAL DISPLAY OUTPUT & PURE CLI CONSOLE ARCHITECTURE (FINDING 116):**
    * **DECON Framebuffer Assignment:** Never assume `/dev/fb0` maps to an external monitor. On Exynos 8895, `fb0` is hardwired to the internal mobile OLED (`DECON0`). The external USB-C DisplayPort/HDMI output is strictly `/dev/graphics/fb2` (or `/dev/fb2`) on `DECON2`.
    * **Vendor Kernel `CONFIG_VT` Guardrail:** Stock and TWRP vendor kernels explicitly disable `CONFIG_VT` and `CONFIG_FRAMEBUFFER_CONSOLE` (`fbcon`). Never call `con2fbmap` or attempt to attach to `/dev/tty1` on vendor kernels without verifying `CONFIG_VT` support.
    * **Universal Dual Output & Terminal Display:** When an external display is connected (`/sys/class/switch/hdmi/state == 1`):
      1. Always negotiate SBU switch (`echo "0 0" > /sys/class/dp_sec/dp_sbu_sw_sel`) and DFP role (`echo source > /sys/class/typec/port0/port_type`), then unblank `fb2` (`FBIOBLANK(FB_BLANK_UNBLANK)`).
      2. If a desktop GUI (X11 / Wayland) is running, stream desktop frames to `fb2`.
      3. If running in pure headless CLI/server mode (Debian, Kali, Alpine, Proxmox, OpenWrt), launch the userland framebuffer terminal engine (`fbterm` or direct `mmap` console) bound to root shell, giving an instant full-screen text terminal on the monitor.
      4. When disconnected, immediately issue `FBIOBLANK(FB_BLANK_POWERDOWN)` to prevent `DISP_ERR_DECON_TIMEOUT` kernel panics.

25. **AUTOMATED PRE-FLASH INTEGRITY VALIDATION & IMMUTABLE BASELINE AP PINNING (FINDING 117):**
    * **Mandatory Pre-Flash Validation Gate:** Never recommend flashing or build a release AP tarball without executing `python scripts/pre_flash_validator.py <path>`. All 6 quality gates must pass:
      1. Size ceiling: `boot.img` and `recovery.img` strictly `<= 41,943,040` bytes (`sda7`/`sda8` hardware limit).
      2. Kernel TrustZone EL2 CFP Compliance: Must match verified Samsung GCC 4.9 CFP production baseline (`29,382,520` bytes).
      3. Headless Display Safety: Strictly prohibits in-kernel `CONFIG_FRAMEBUFFER_CONSOLE=y` on boards with physically absent internal displays (`lcdtype=-1`). Direct monitor CLI console is driven exclusively via userland (`fbterm` on `/dev/graphics/fb2`).
      4. Calliope DSP Audio Suite: All 9 audio firmwares embedded in ramdisk CPIO without shadowing.
      5. Watchdog Timing & Non-Blocking `init.rc`: Prohibits synchronous blocking calls (e.g. `exec ... e2fsck` on large partitions) in `init.rc` that risk tripping the 15-second `s3c2410_wdt` hardware watchdog.
      6. USB Gadget Infallibility: Ramdisks must present Samsung vendor ID `04e8:6860` so Windows automatically associates pre-installed Samsung ADB drivers.
    * **Golden Baseline Kernel Immutability:** The verified Samsung GCC 4.9 CFP production kernel (`29,382,520` bytes) in `scratch/boot_proven_autoboot.img` is the single source of truth for release AP packages. Custom kernels must remain in non-release experimental slots until cold-boot verified.

26. **SINGLE-OS EXCLUSIVE DEPLOYMENT & TESTING MANDATE (ONE OS AT A TIME):**
    * **Strictly One Active & Installed OS Throughout the System:** Whenever installing, deploying, or testing an OS on the Galaxy S8 (Ubuntu, Kali, SteamOS, Debian, Alpine, Arch, etc.), **only ONE OS** may be installed and running throughout the entire device at a time.
    * **Zero Dual Desktops or Parallel Chroot Stacks:** Never run or stack two OS desktops/VNC displays (`:1` + `:2`) or dual noVNC ports (`:6080` + `:6090`) simultaneously. Always serve the single active OS on the canonical endpoints (Display `:1`, VNC `:5901`, noVNC `:6080`).
    * **Clean Replacement Lifecycle Before Switching OS:** Before installing or testing a new OS:
      1. Stop all processes, X11/VNC/noVNC servers, and D-Bus daemons of the previous OS and cleanly unmount its loop & virtual mounts (`/proc`, `/sys`, `/dev`, `/dev/pts`, `/dev/shm`, `/run`).
      2. Remove/replace the outgoing OS rootfs image in `/data/linux/` so only the single active target OS remains installed and booted cleanly throughout the whole system.
27. **ZERO-FORK UPSTREAM DISTRO MANDATE & STANDALONE HARDWARE PACKAGE ARCHITECTURE (`galaxy-s8-hw`):**
    * **Never Build or Ship Modified/Forked Distro Images:** Base operating system images stored in `distros/`, selected in `S8 Imager`, or flashed onto `/data/linux/rootfs.img` MUST be **100% unmodified official upstream ARM64 releases** downloaded directly from vendor mirrors (`cdimage.ubuntu.com`, `cloud.debian.org`, `kali.org`, `dl-cdn.alpinelinux.org`, `os.archlinuxarm.org`, etc.) and verified by upstream SHA-256 checksums. Custom-baked distro rootfs archives (e.g., customized chroot builds, baked desktop themes, or hardcoded personal credentials) MUST NOT be shipped or flashed as default OS images.
    * **Minimal First-Boot Connectivity Seed Only During Flash:** Because the headless Galaxy S8 (`lcdtype=-1`) has no physical screen or keyboard on first boot, `S8 Imager` extracts the unmodified upstream rootfs cleanly (including GPT/MBR Linux partition extraction for `.img.xz`/`.raw`) and applies **only** the minimal connectivity/safety seed required for first-boot reachability: USB ConfigFS RNDIS (`192.168.7.2` + DHCP), OpenSSH server / first-boot credentials configured by the user in `S8 Imager`, V4L2 camera ISP `/dev/video100+` udev panic guard, and disabling non-existent board `fstab` boot partitions (such as `+raspi` `LABEL=system-boot`).
    * **All Hardware Integration Lives in `galaxy-s8-hw` (`packages/galaxy-s8-hw/`):** Phone-specific daemons and drivers (`s8_button_daemon` + `99-s8-power.conf`, `exynos_dp_bridge`, `s8ctl`, MAX77865 `1500mA` fast charge + UVLO, Broadcom BCM4361 Wi-Fi helper, Calliope ALSA routing, `s8-time-sync`, Type-C DisplayPort supervisor, Android socket GIDs) MUST be packaged cleanly into `galaxy-s8-hw_<ver>_arm64.deb` and universal `galaxy-s8-hw-<ver>-arm64.tar.gz` (`install.sh`), installable post-boot in one click from `S8 Imager` (or manually via `dpkg -i` / `./install.sh`) with zero AI agent involvement.
    * **Real-Human Zero-AI Parity:** Every user workflow — official OS download + SHA-256 check, flashing in `S8 Imager`, first-boot USB RNDIS SSH setup, 1-click `galaxy-s8-hw` package installation, Wi-Fi scan/connect, noVNC/DisplayPort usage, and long-press/button control — MUST work end-to-end inside `S8 Imager` and be documented in plain-English user instructions without requiring any AI agent or ad-hoc manual patching.
28. **MANDATORY NATIVE LINUX `systemd` PID 1 & PROGRESSIVE DE-ANDROIDIZATION MANDATE:**
    * **Native `systemd` PID 1 Across All Future Kernel & AP Builds:** Every kernel and AP image (`boot_s8_universal.img` / `Galaxy_S8_Linux_AP.tar`) built from this rule onward MUST boot pure native Linux `/init` and hand off PID 1 to the guest OS `systemd` (`/sbin/init` or `/lib/systemd/systemd`) via `switch_root` whenever a `systemd` rootfs is present (with clean non-systemd `/sbin/init` or AP recovery shell fallback when an embedded/Alpine/OpenWrt or uninitialized disk is detected), eliminating Android `/init` and `init.rc` chaining.
    * **Progressive Kernel De-Androidization:** Every kernel iteration MUST audit and disable non-essential Android-only kernel subsystems (`CONFIG_ANDROID_LOW_MEMORY_KILLER`, `CONFIG_ANDROID_BINDER_IPC`, `CONFIG_ASHMEM`, `CONFIG_ANDROID_INTF_ALARM_DEV`, `CONFIG_ANDROID_PARANOID_NETWORK`, `CONFIG_ANDROID_TIMED_GPIO`, `CONFIG_NETFILTER_XT_MATCH_QTAGUID`, `CONFIG_NETFILTER_XT_MATCH_QUOTA2`, Android MTP/PTP/Accessory/DM USB gadget functions, and Android SELinux where hardware-safe) while preserving required Exynos 8895 safety invariants (`# CONFIG_RKP_CFP is not set`, `# CONFIG_VT is not set`, `CONFIG_ANDROID_TIMED_OUTPUT=y` for MAX77865 haptics, `CONFIG_USB_CONFIGFS_ACM=y`, `CONFIG_USB_CONFIGFS_RNDIS=y`, `CONFIG_DEVTMPFS_MOUNT=y`, `CONFIG_CGROUPS=y`, `CONFIG_NAMESPACES=y`).
29. **ULTIMATE NATIVE LINUX KERNEL, HARDWARE FAULT-TOLERANCE & PHYSICAL VERIFICATION CHECKLIST MANDATE:**
    * **Full Specification & Checklists:** Enforced via [`.agent/skills/ultimate-kernel-and-verification-standard/SKILL.md`](file:///e:/rouf/galaxy-s8/.agent/skills/ultimate-kernel-and-verification-standard/SKILL.md).
    * **Native FHS Paths & Zero Permission Limits:** Every standard Linux distro (Ubuntu, Debian, Kali, Alpine, Arch, OpenWrt, Home Assistant OS, SteamOS) must find standard Linux device nodes (`/dev/fb0..2`, `/dev/dri/*`, `/dev/mali0`, `/dev/ion`, `/dev/snd/*`, `/dev/input/event*`, `/dev/ttyGS0`, `/lib/firmware`) and have 100% unrestricted Docker/container/supervisor permissions (`USER_NS`, `PID_NS`, `NET_NS`, `IPC_NS`, `UTS_NS`, all 11 cgroups, `OVERLAY_FS`, `BRIDGE`, `VETH`, `MACVLAN`, `POSIX_MQUEUE`, `SECCOMP`, `BINFMT_MISC`, and `CONFIG_ANDROID_PARANOID_NETWORK=n`).
    * **USB 3.1 SuperSpeed, Dual-Role (Host/Slave), Concurrent DisplayPort + Data, & Universal Dongles:** Full support for USB 3.1 (`10c00000.dwc3`), UASP fast storage (`CONFIG_USB_UAS=y`), simultaneous USB-C DisplayPort video out + USB keyboard/mouse/hub data + PD charging, and plug-and-play USB Ethernet dongles (`RTL8152`/`8153`/`8156`, `AX88179`, `CDC-ECM`/`NCM`/`EEM`, `RNDIS_HOST`, `SMSC75XX`/`95XX`) with automatic DHCP reconnect.
    * **Zero-Panic Hardware Disconnect Fault-Tolerance:** Physically removing or hot-unplugging any module (OLED screen, front LED, cameras, sensors, USB-C monitor, USB hub, Ethernet dongle, or MicroSD) MUST NEVER cause a kernel panic or reboot loop (`fimc_is_ixs_video_querycap` NULL guard, `DECON2` unplug guard, `panic_on_oops=0`).
    * **Dynamic Idle Cool-Down & Full Boost Scaling:** At idle, CPU clocks down to `455 MHz` (A53) / `741 MHz` (M2) keeping SoC cool (`< 40 C`), and boosts to `1.690 GHz` / `2.314 GHz` + `546 MHz` Mali-G71 MP20 GPU under load with automatic TMU thermal throttling protection.
    * **21-Point Physical Hardware Verification & Zero Synthetic Proof:** After every kernel build, all 21 hardware subsystems (warm/cold reboot survival, Docker permissions, CPU idle/boost scaling, PMIC 1500mA + battery fuelgauge, USB Slave RNDIS+ACM, USB Master OTG storage, USB Ethernet dongle auto-DHCP, DisplayPort + mouse/keyboard input, hot-unplug immunity, Wi-Fi 2.4G/5G/AP mode, Bluetooth 5.0, speaker `hw:0,0`, 3.5mm headphone jack, DMIC1 microphone `hw:0,9`, rear flash/torch, haptic vibrator, camera V4L2 safety, MicroSD RW, SIM/Shannon LTE modem, chassis buttons, and IIO sensors) MUST be verified using real physical telemetry and real device captures — never AI-generated images or fake mocks.
    * **Copy-on-Deploy Untouched Distro Rule:** Upstream archives in `distros/` must never be modified in place; always copy/extract to a staging container before applying seeds or `galaxy-s8-hw`.
30. **UNIVERSAL VERSIONING, COMPATIBILITY LEDGER & NON-DESTRUCTIVE ROLLBACK MANDATE:**
    * **Full Specification & CLI Runbook:** Enforced via [`.agent/skills/versioning-and-rollback-manager/SKILL.md`](file:///e:/rouf/galaxy-s8/.agent/skills/versioning-and-rollback-manager/SKILL.md), [`VERSION_MANIFEST.json`](file:///e:/rouf/galaxy-s8/VERSION_MANIFEST.json), [`VERSIONS.md`](file:///e:/rouf/galaxy-s8/VERSIONS.md), and [`scripts/version_manager.py`](file:///e:/rouf/galaxy-s8/scripts/version_manager.py).
    * **Version Everything Across All 8 Layers:** Every Odin AP package (`releases/history/Galaxy_S8_Linux_AP_v<VER>.tar`), Kernel build (`4.4.111-s8-universal-v<VER>`), Boot image (`boot_universal_ap_v<VER>.img`), Hardware Support Package (`galaxy-s8-hw_<VER>_arm64.deb` & `galaxy-s8-hw-<VER>-arm64.tar.gz`), Native C daemon suite (`src/drivers/s8_version.h`), `s8ctl` CLI (`S8CTL_VERSION`), RWP transport protocol (`rwp-v<VER>`), Desktop App (`S8 Imager` `APP_VERSION`), and Upstream Distro (`distros/` catalog) MUST be explicitly versioned and tracked in `VERSION_MANIFEST.json`.
    * **Worked vs. Failed Decision Ledger:** Every release and tested distro MUST record its empirical status (`VERIFIED_WORKING`, `SUPERSEDED`, `EXPERIMENTAL`, `READY_TO_TEST`, or `FAILED`) along with SHA-256 checksums, boot headroom, and root-cause notes so we always know which version worked, which version failed, and why.
    * **Immutable Release History & 1-Click Rollback:** Never overwrite a working AP or hardware package without preserving its versioned archive in `releases/history/` or `packages/dist/`. Use `python scripts/version_manager.py --rollback-ap <ver> [--live]` or `--rollback-hw <ver> [--live]` for instant rollback, and always run `python scripts/version_manager.py --sync` + `--status` to guarantee zero version drift.

---

## 2. Key Workspace Files & Scripts Reference

| File Path | Role |
| :--- | :--- |
| [`VERSION_MANIFEST.json`](file:///e:/rouf/galaxy-s8/VERSION_MANIFEST.json) & [`VERSIONS.md`](file:///e:/rouf/galaxy-s8/VERSIONS.md) | **Universal Version & Rollback Ledger** tracking every AP, Kernel, Hardware Pack, Daemon, Desktop App, and Distro compatibility status. |
| [`scripts/version_manager.py`](file:///e:/rouf/galaxy-s8/scripts/version_manager.py) | **Universal Version & 1-Click Rollback CLI** (`--status`, `--sync`, `--snapshot-ap`, `--record-distro`, `--rollback-ap`, `--rollback-hw`). |
| [`releases/Galaxy_S8_Linux_AP.tar`](file:///e:/rouf/galaxy-s8/releases/Galaxy_S8_Linux_AP.tar) | **Canonical Universal Galaxy S8 Pure Native Linux Odin AP Package** (`v2.0.2`, `boot.img` + `recovery.img`, `64,583,680` B; versioned snapshots in `releases/history/`). |
| [`scripts/build_universal_ap.py`](file:///e:/rouf/galaxy-s8/scripts/build_universal_ap.py) | **Master Pure Native Linux AP Builder** (`switch_root` -> PID 1, multi-storage `boot_target.conf`, 9 Calliope firmwares, RNDIS+ACM, `s8_usb_agentd`, `s8_dp_daemon`). |
| [`packages/galaxy-s8-hw/`](file:///e:/rouf/galaxy-s8/packages/galaxy-s8-hw/build_packages.py) | **Universal Multi-Distro Hardware Pack Source & Builder** (outputs `galaxy-s8-hw_1.0.2_arm64.deb` and `galaxy-s8-hw-universal-arm64.tar.gz`). |
| [`src/drivers/`](file:///e:/rouf/galaxy-s8/src/drivers/) | **Native C Hardware Daemons:** `s8_version.h`, `s8_usb_agentd.c`, `s8_dp_daemon.c`, `exynos_dp_bridge.c`, `s8_input_bridge.c`, `s8_button_daemon.c`. |
| [`desktop-app/`](file:///e:/rouf/galaxy-s8/desktop-app/main.py) | **S8 Imager Desktop & Web Application (`v2.7.0`)** (Universal BYOI flasher + version ledger, live RWP/SSH & Recovery flasher, storage selector, dual PTY shell, telemetry dashboard). |
| [`tests/hardware/test_full_non_regression_e2e.py`](file:///e:/rouf/galaxy-s8/tests/hardware/test_full_non_regression_e2e.py) | **Full-Stack Live Hardware & Non-Regression Test Suite.** |
| [`docs/GEMINI_3_8_HANDOFF.md`](file:///e:/rouf/galaxy-s8/docs/GEMINI_3_8_HANDOFF.md) | **Live Continuity Runbook for Gemini 3.8.** |
