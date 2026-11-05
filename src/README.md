# Galaxy S8 Native Linux Subsystems & Source Modules

This directory contains the production daemons, drivers, service wrappers, and hardware management tools for running native Ubuntu 24.04 LTS and Docker on the Samsung Galaxy S8 (Exynos 8895).

---

## Directory Architecture

```
src/
├── audio/       # ALSA DSP Calliope routing, mixer profiles, asound.conf
├── control/     # Hardware management CLI (s8ctl) and GTK Control Center
├── desktop/     # GNOME 46 + macOS Sonoma desktop environment scripts & configs
├── drivers/     # Kernel daemons: DisplayPort bridge, button mapper, input daemon
├── network/     # Broadcom BCM4361 Wi-Fi, Bluetooth HCI, port forwarders
└── services/    # Production wrappers for Docker, CasaOS, Ollama, Code-Server
```

---

## Subsystem Details

### 1. `src/drivers/`
* `exynos_dp_bridge.c`: Direct frame-buffer streaming daemon for Exynos DECON2 (`/dev/graphics/fb2`). Allocates ION memory (`/dev/ion`), listens for HDMI hotplug events (`/sys/class/switch/hdmi/state`), captures X11 display `:1`, overlays hardware cursor, and pushes buffers via `S3CFB_WIN_CONFIG` locked to 60 Hz VSYNC.
* `s8_button_daemon.c`: Physical chassis button mapper reading `/dev/input/event3` (`gpio_keys`). Handles Power, Volume Up/Down, and Bixby click actions (single-click terminal, double-click torch, long-press screenshot).
* `s8_input_bridge.c`: Virtual input device emulator bridging remote browser touch/pointer events to native Linux uinput events.

### 2. `src/audio/`
* `asound.conf`: Universal ALSA routing configuration utilizing `type asym` to bind speaker playback (`hw:0,0`, Maxim MAX98506) and digital microphone recording (`hw:0,9`, Cirrus Logic CS47L92 DMIC1) into default ALSA streams.
* `init_audio.sh`: Comprehensive mixer script setting ABOX Calliope DSP routes, WDMA1 gains, and digital amp switches.
* `mixer_paths.xml` & `mixer_gains.xml`: Hardware register definitions for the Exynos 8895 audio mixer.

### 3. `src/control/`
* `s8ctl.py`: Production command-line hardware utility deployed at `/usr/local/bin/s8ctl`. Provides management commands for CPU frequency governors, GPU clock modes, battery telemetry, rear torch LED, haptics, MicroSD status, and audio hardware checks.
* `s8_control_center.py`: GTK desktop application providing a graphical control center for hardware sensors and system profiles.

### 4. `src/desktop/`
* `start_gnome_macos.sh`: Primary desktop launcher configuring Cairo rendering, `gsd-xsettings`, `metacity`, `gnome-panel` (macOS-style top bar), and Plank dock.
* `polish_gnome_macos.sh`: Post-install script that deploys WhiteSur themes, red/yellow/green window controls, and LD_PRELOAD shims for running Nautilus and Epiphany as root.
* `nginx_novnc.conf`: Reverse proxy configuration for zero-latency WebSocket and web client delivery on port 6080.
* `apply_panel_layout.py`: DConf automator establishing the top panel applet layout.

### 5. `src/network/`
* `connect_wifi.sh`: Broadcom BCM4361 Wi-Fi bring-up script. Injects firmware paths without `_b0` suffixes to avoid kernel driver concatenation faults and associates via `wpa_supplicant`.
* `setup_wifi.sh`: Network setup helper script.
* `start_bluetooth.sh`: Initializes BCM4361 Bluetooth UART transport on `/dev/ttySAC1` via `hciattach` with 3,000,000 baud flow control.
* `adb_forward_daemon.py`: Persistent port forwarding loop ensuring Web VNC, native VNC, and SSH ports remain accessible over USB.

### 6. `src/services/`
* `start_docker.sh`: Docker daemon starter with bridge networking and rootless-safe daemon configurations.
* `start_casaos.sh`: CasaOS dashboard launcher managing web UI (:8080) and local storage mounts.
* `start_homeassistant.sh`: Home Assistant Core service runner.
* `start_uptime_kuma.sh`: Uptime Kuma monitoring service runner (:3001).
* `start_codeserver.sh`: Code-Server / VS Code web environment launcher (:8082).

