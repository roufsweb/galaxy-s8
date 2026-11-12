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

---

## 1. Strict Anti-Hallucination & Architecture Rules for Gemini 3.8 High

> [!CAUTION]
> **NEVER VIOLATE THESE EMPIRICALLY VERIFIED HARDWARE & ARCHITECTURE RULES:**

1. **NO INTERNAL SCREEN OR FRONT LED EXISTS (`lcdtype=-1`):**
   * Both the internal OLED screen and the front RGB status LED assembly are **physically removed**.
   * **NEVER** instruct the user to look at the phone screen or check the front LED.
   * **ONLY** use: (a) exact second counts, (b) **Haptic Vibrations** (`/sys/class/timed_output/vibrator/enable`), (c) **Rear Flashlight Torch** (`/sys/class/leds/torch-sec1/brightness`), and (d) USB/Wi-Fi telemetry (`ce10171ab3e9620804` / `192.168.0.227`).
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

---

## 2. Key Workspace Files & Scripts Reference

| File Path | Role |
| :--- | :--- |
| [`releases/Galaxy_S8_Linux_AP.tar`](file:///e:/rouf/galaxy-s8/releases/Galaxy_S8_Linux_AP.tar) | **Universal Galaxy S8 Linux AP Kernel Odin Package** (`boot.img` with auto-boot `init.rc` + `recovery.img`, `80,527,360` B / `80.5` MB). |
| [`releases/galaxy-s8-linux-arm64.img.gz`](file:///e:/rouf/galaxy-s8/releases/galaxy-s8-linux-arm64.img.gz) | **Universal Galaxy S8 ARM64 Rootfs OS Image** (`2.8` GB gzip compressed root filesystem). |
| [`e:\rouf\galaxy-s8\scratch\boot_ubuntu_autoboot.img`](file:///e:/rouf/galaxy-s8/scratch/boot_ubuntu_autoboot.img) | Auto-booting `BOOT` partition image (`38,977,552` B), already flashed to `/dev/block/sda7` and `sda8`. |
| [`e:\rouf\galaxy-s8\scratch\build_rocksolid_boot.py`](file:///e:/rouf/galaxy-s8/scratch/build_rocksolid_boot.py) | Python builder that unpacks `boot.img` LZMA ramdisk, embeds 9 Calliope firmwares, self-healing supervisor, `s8_typec_daemon.py`, and builds `Ubuntu_24.04_GalaxyS8_Full_Odin.tar`. |
| [`e:\rouf\galaxy-s8\scratch\start_all.sh`](file:///e:/rouf/galaxy-s8/scratch/start_all.sh) | Deployed at `/data/linux/start_all.sh` — master boot supervisor (V4L2 guard, `1500mA` MAX77865 unlock, Wi-Fi, Ubuntu mount, GNOME 46 macOS GUI, VNC/noVNC, `exynos_dp_bridge`, Docker). |
| [`e:\rouf\galaxy-s8\scratch\polish_gnome_macos.sh`](file:///e:/rouf/galaxy-s8/scratch/polish_gnome_macos.sh) | Configures `/usr/local/bin/start_gnome_macos.sh`, left-side red/yellow/green traffic lights, `gsd-xsettings`, `ClockApplet`, and `libnautilus_root.so`. |
| [`e:\rouf\galaxy-s8\scratch\exynos_dp_bridge.c`](file:///e:/rouf/galaxy-s8/scratch/exynos_dp_bridge.c) | Native Exynos 8895 DECON2 USB-C DisplayPort / HDMI hotplug & `/dev/ion` `S3CFB_WIN_CONFIG` streaming daemon. |
| [`e:\rouf\galaxy-s8\scratch\s8ctl.py`](file:///e:/rouf/galaxy-s8/scratch/s8ctl.py) | Deployed at `/usr/local/bin/s8ctl` — unified CLI for Battery, Rear Torch, Haptics, DisplayPort, Bluetooth, and Sensors. |
| [`e:\rouf\galaxy-s8\scratch\connect_wifi.sh`](file:///e:/rouf/galaxy-s8/scratch/connect_wifi.sh) | Deployed at `/data/linux/connect_wifi.sh` — Broadcom BCM4361 Wi-Fi bring-up (`<WIFI_SSID>` / `<WIFI_PASSWORD>` $\rightarrow$ `192.168.0.227`). |

---

## 3. Remaining Roadmap Tasks for Next Session

1. **Test External USB-C Display / Type-C-to-HDMI Dongle Live (`Phase 2.3`):**
   * Plug in the USB-C monitor or Type-C-to-HDMI hub (with PD power connected to the hub) and verify `/var/log/exynos_dp_bridge.log` + `dmesg | grep -E "Displayport|decon"` over Wi-Fi (`ssh root@192.168.0.227`, password `ubuntu`).
2. **Audio Routing (`CS47L92` Speaker/Headphone + `pcmC0D22p` HDMI Audio) & Bluetooth (`BCM4361` `hciattach`):**
   * Configure `/etc/asound.conf` and `tinymix` paths for `Exynos8895-Madera` (`card 0`) and test `hciattach /dev/ttySAC1 bcm43xx 3000000 flow` with `/vendor/firmware/bcm4361*.hcd`.
3. **Full Kernel Rebuild with `CONFIG_PID_NS=y` / `CONFIG_CGROUP_DEVICE=y` & Bixby Key Daemon (`Phase 3`):**
   * Compile `kernel` with full container namespaces (`CONFIG_PID_NS=y`, `CONFIG_IPC_NS=y`, `CONFIG_UTS_NS=y`, `CONFIG_CGROUP_DEVICE=y`) so `systemd` PID 1 container and standard Docker containers run without flags.
