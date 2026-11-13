---
name: galaxy-s8-native-linux
description: Comprehensive operational runbook for running Pure Native Linux (systemd PID 1), universal multi-distro provisioning, USB-C DisplayPort + USB Host input bridging, and RWP zero-config USB networking on the headless Samsung Galaxy S8 (Exynos SM-G950N).
---

# Samsung Galaxy S8 (`SM-G950N`) Pure Native Linux Runbook (`galaxy-s8-native-linux`)

> [!CRITICAL]
> **HEADLESS HARDWARE SPECIFICATION (`lcdtype=-1`):**
> The internal OLED screen is physically absent (`lcdtype=-1`), while the front RGB status LED is **physically present, configured, and active** (`/sys/class/sec/led/` driven by `s8_led_supervisor.py`).
> Interaction telemetry relies on: (1) Front Status LED (Green=Healthy, Blue=Booting, Amber=Charging, Cyan=DisplayPort), (2) Haptic Vibrations (`/sys/class/timed_output/vibrator/enable`), (3) Rear Torch (`/sys/class/leds/torch-sec1/brightness`), (4) exact second counts (11–13s for Download Mode), and (5) USB RNDIS (`192.168.7.2:7860`) / Serial (`/dev/ttyGS0`) / Wi-Fi (`192.168.0.227`).

---

## 1. Live Device Connectivity & RWP-v1 Control (`192.168.7.2`)

The Pure Native Linux AP boots `systemd` (or guest init) directly as **PID 1** and brings up dual USB ConfigFS endpoints automatically:
1. **USB RNDIS Ethernet:** Device IP `192.168.7.2` (Host IP `192.168.7.x` via DHCP/link).
2. **USB CDC-ACM Serial Console:** `/dev/ttyGS0` (`agetty` root login on Windows `COM*`).
3. **RWP-v1 Zero-Config Agent (`s8_usb_agentd` on `:7860`):**
   - `GET http://192.168.7.2:7860/rwp/v1/health` -> `{"status":"ok"}`
   - `GET http://192.168.7.2:7860/rwp/v1/info` -> Kernel, PID 1, SoC temp, battery %, DisplayPort state, IPs, guest OS.
   - `POST http://192.168.7.2:7860/rwp/v1/exec` -> `{"cmd": "<command>", "env": "os"}`
   - `WS ws://192.168.7.2:7860/rwp/v1/pty?env=os` -> Interactive full-color PTY shell.
4. **Remote Desktop & SSH:**
   - **noVNC Web Desktop:** `http://192.168.7.2:6080/vnc.html` (Password: `ubuntu`)
   - **TigerVNC (`:5901`):** `192.168.7.2:5901`
   - **SSH (`:22`):** `ssh root@192.168.7.2`

---

## 2. Critical Hardware Guards & Daemons (`galaxy-s8-hw`)

1. **V4L2 Camera ISP Kernel Panic Guard (`s8-pmic-init.service`):**
   ```sh
   rm -f /dev/video[1-9][0-9]* /dev/v4l-subdev*
   ```
   Prevents `gst-plugin-scanner`, `nautilus`, and `webkit` from probing uninitialized Samsung camera ISP nodes (`/dev/video100+`), while preserving `/dev/video6..9` (Exynos MFC hardware H.264/HEVC codecs).
2. **MAX77865 PMIC `1,500 mA` Fast-Charge & UVLO Unlock (`s8-pmic-init.service`):**
   Writes `0xBD 0x6C`, `0xC3 0x61`, `0xC0 0x3C`, `0xB9 0x9E`, `0xB7 0x05` to `/sys/class/power_supply/max77865-charger/data`.
3. **USB-C DisplayPort Tear-Free Pipeline (`s8_dp_daemon` + `exynos_dp_bridge`):**
   - `/sbin/s8_dp_daemon` manages `/dev/graphics/fb2` (`DECON2`), keeping it in `FB_BLANK_POWERDOWN` while `/sys/class/switch/hdmi/state == 0`, and rendering either the pure CLI console or `/dev/shm/s8_dp_fb` when `state == 1`.
   - `/usr/local/bin/exynos_dp_bridge` (`s8-dp-bridge.service`) captures X11 `:1`, composites the hardware cursor with explicit `0xFF` alpha (`DECON_PIXEL_FORMAT_BGRA_8888`), and calls `ensure_usb_host_mode()` on hotplug so USB mice/keyboards on Type-C hubs enumerate.
4. **Hotplug USB & Bluetooth Mouse/Keyboard Forwarder (`s8_input_bridge`):**
   - `/usr/local/bin/s8_input_bridge` (`s8-input-bridge.service`) monitors `/dev/input/event*` via `inotify` and injects relative pointer motion, scroll wheel, buttons, and keycodes into X11 `:1` via `XTest`.

---

## 3. Rebuilding the Universal AP & Hardware Packages

See [`galaxy-s8-ap-kernel-builder`](file:///e:/rouf/galaxy-s8/.agent/skills/galaxy-s8-ap-kernel-builder/SKILL.md) and [`product-namespace-and-naming`](file:///e:/rouf/galaxy-s8/.agent/skills/product-namespace-and-naming/SKILL.md):
```powershell
python scripts/build_universal_ap.py
python scripts/pre_flash_validator.py releases/Galaxy_S8_Linux_AP.tar
```
