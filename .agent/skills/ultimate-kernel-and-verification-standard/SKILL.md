---
name: ultimate-kernel-and-verification-standard
description: Mandatory engineering specification, hardware fault-tolerance rules, native Linux FHS/permission standards, and post-build physical verification checklists for the Galaxy S8 Kernel, Multi-Distro OS Provisioning, and S8 Imager Desktop App.
---

# Ultimate Native Linux Kernel, Hardware Fault-Tolerance & Physical Verification Standard

> [!IMPORTANT]
> **MANDATORY POST-BUILD & RELEASE GATE:**
> Every kernel build (`4.4.111-s8-universal-v*`), hardware package release (`galaxy-s8-hw`), distro deployment, and `S8 Imager` desktop app update MUST satisfy the checklists in this skill.
> **Zero Synthetic Proof Rule:** Verification MUST use real physical captures, real hardware registers, real audio/sensor telemetry, and real Playwright/DOM interactions from the connected Galaxy S8 (`ce10171ab3e9620804` / `192.168.7.2`). Never use AI-generated images or fake mocks for hardware verification.

---

## 1. Ultimate Native Linux Kernel Specification (`4.4.111-s8-universal`)

### 1.1 Native Linux PID 1, FHS Paths & Zero Permission Limits
1. **Real PID 1 Init:** `switch_root` directly into the guest OS `/sbin/init` (`systemd`, `OpenRC`, OpenWrt `procd`, BusyBox `init`, or HAOS init).
2. **Pure Upstream Network & Root Permissions:**
   - Disable Android paranoid network GID locks (`# CONFIG_ANDROID_PARANOID_NETWORK is not set`) alongside `aid_inet` (`3003`) group fallback so every standard Linux user, package manager (`apt`, `apk`, `opkg`, `pacman`), and container has native socket access.
   - Disable all Samsung proprietary restrictions: `CONFIG_SECURITY_DEFEX=n`, `CONFIG_RKP_CFP=n`, `CONFIG_RKP_CFP_JOPP=n`, `CONFIG_FIVE=n`, `CONFIG_PROCA=n`, `CONFIG_TIMA=n`.
3. **Standard Linux Filesystem Hierarchy (FHS) Device & Firmware Paths:**
   - `/lib/firmware` and `/usr/lib/firmware` populated/bound alongside `/run/s8/firmware` (`firmware_class.path`).
   - `/dev/fb0`..`/dev/fb2` symlinked to `/dev/graphics/fb0..2`.
   - `/dev/dri/*`, `/dev/mali0`, `/dev/ion`, `/dev/snd/*`, `/dev/input/event*`, `/dev/ttyGS0`, `/dev/rtc0`, `/dev/watchdog` accessible at standard Linux paths.
4. **Full Docker, LXC, Proxmox & Home Assistant OS Kernel Configs:**
   - Namespaces: `NAMESPACES=y`, `USER_NS=y`, `PID_NS=y`, `NET_NS=y`, `IPC_NS=y`, `UTS_NS=y`.
   - Cgroups: `CGROUPS=y`, `MEMCG=y`, `MEMCG_SWAP=y`, `BLK_CGROUP=y`, `CGROUP_DEVICE=y`, `CGROUP_FREEZER=y`, `CGROUP_PIDS=y`, `CPUSETS=y`, `CGROUP_SCHED=y`, `FAIR_GROUP_SCHED=y`, `CFS_BANDWIDTH=y`.
   - Virtualization & Networking: `OVERLAY_FS=y`, `BRIDGE=y`, `BRIDGE_NETFILTER=y`, `VETH=y`, `MACVLAN=y`, `IPVLAN=y`, `VLAN_8021Q=y`, `TUN=y`, `POSIX_MQUEUE=y`, `SECCOMP=y`, `SECCOMP_FILTER=y`, `BINFMT_MISC=y`, `IP_NF_NAT=y`, `IP_NF_TARGET_MASQUERADE=y`, `NETFILTER_XT_MATCH_ADDRTYPE=y`, `NETFILTER_XT_MATCH_CONNTRACK=y`.

### 1.2 USB 3.1 SuperSpeed, Dual-Role (Host/Slave), Concurrent DisplayPort + Data, & Universal Dongles
1. **USB 3.1 Gen 1 (`10c00000.dwc3`):** Full 5 Gbps SuperSpeed host & gadget operation.
2. **Fast USB Storage:** `CONFIG_USB_STORAGE=y`, `CONFIG_USB_UAS=y` (UASP for external NVMe/SSD drives).
3. **USB Slave (Gadget) & Master (OTG/Host) Modes:**
   - **Slave Mode:** Composite `rndis.usb0` (`192.168.7.2` with persistent MAC) + `acm.gs0` (`/dev/ttyGS0` serial console) + `s8_usb_agentd` (`:7860`).
   - **Master Mode:** Automatic DFP/xHCI host role switching (`port_type=source`, `data_role=host`, `role_swap=1`) powering downstream USB keyboards, mice, flash drives, and Ethernet adapters.
   - **Concurrent USB-C Hub Mode:** Simultaneous DisplayPort Alt-Mode video out (`fb2`) + USB mouse/keyboard/storage data + PD power negotiation.
4. **Universal USB Ethernet / LAN Dongle Drivers (Plug-and-Play Reconnect + Auto-DHCP):**
   - `CONFIG_USB_RTL8152=y`, `CONFIG_USB_RTL8150=y` (Realtek 1G / 2.5G USB-C Ethernet)
   - `CONFIG_USB_NET_AX8817X=y`, `CONFIG_USB_NET_AX88179_178A=y` (ASIX USB 3.0 Gigabit)
   - `CONFIG_USB_NET_CDCETHER=y`, `CONFIG_USB_NET_CDCEEM=y`, `CONFIG_USB_NET_CDC_NCM=y`, `CONFIG_USB_NET_RNDIS_HOST=y`
   - `CONFIG_USB_NET_SMSC75XX=y`, `CONFIG_USB_NET_SMSC95XX=y`

### 1.3 Fault-Tolerance & Zero-Panic Hardware Disconnect Immunity
> [!CAUTION]
> **STRICT FAULT-TOLERANCE LAW:**
> Physically disconnecting or hot-unplugging ANY internal or external component (OLED panel, front LED, front/rear cameras, sensors, USB-C monitor, USB hub, Ethernet dongle, or MicroSD card) MUST NEVER trigger a kernel panic or reboot loop.
- **Camera ISP (`fimc-is2`):** Guard `fimc_is_ixs_video_querycap` against NULL pointers in kernel C code AND strip `/dev/video[1-9][0-9]*` at boot so missing/uninitialized cameras return `-ENODEV` safely.
- **DisplayPort (`DECON2` / `displayport`):** Never submit `S3CFB_WIN_CONFIG` while `/sys/class/switch/hdmi/state == 0`; handle cable unplug mid-frame gracefully by returning `fb2` to `FB_BLANK_POWERDOWN` without `DECON` watchdog panic.
- **Kernel Oops Handling:** Enforce `panic_on_oops=0` on driver probes so any non-fatal peripheral fault logs to `dmesg` without crashing the server.

---

## 2. Mandatory Post-Kernel-Build Physical Verification Checklist

After every kernel or AP build, execute and check off every item below on the live physical Galaxy S8:

| # | Subsystem | Physical Verification Test | Pass Criteria |
| :--- | :--- | :--- | :--- |
| **1** | **Boot & Reboot Survival** | Warm reboot (`reboot`) + Cold PMIC reset | Boots to `systemd`/init PID 1 (`192.168.7.2:7860`) in `< 30s` with 0 failed units |
| **2** | **Docker & Full Permissions** | `docker info` & container spawn test | All namespaces, cgroups, `overlay2`, and bridge networking active |
| **3** | **CPU Idle & Boost Scaling** | Measure clocks/temp at idle vs `stress-ng` | Idle: `455/741 MHz` (`< 40 C`); Load: `1.69/2.31 GHz` (`< 75 C` thermal throttle safe) |
| **4** | **Battery & PMIC Charging** | Read `max77865-charger` & `fuelgauge` | `1,500 mA` input/fast-charge unlocked; accurate voltage, current, and % telemetry |
| **5** | **USB Slave (RNDIS + ACM)** | Unplug/replug USB-C to PC | Enumerates `192.168.7.2` (`rwp-v1` `:7860`) + Serial `COM*` (`/dev/ttyGS0`) |
| **6** | **USB Master (OTG / Storage)** | Connect USB flash drive / hub | `xhci-hcd` enumerates USB 2.0/3.1 device; block device mounts at full speed |
| **7** | **USB Ethernet Dongle** | Plug/unplug/replug USB LAN adapter | Auto-detects `eth0`/`enx*`, acquires DHCP IPv4 + default route automatically |
| **8** | **USB-C DisplayPort + Input** | Connect Type-C monitor + USB mouse/KB | `fb2` outputs 1080p @ 60Hz, glitch-free cursor (`0xFF` alpha), mouse/KB control `:1` |
| **9** | **Hot-Unplug Fault Tolerance** | Unplug monitor/hub/dongle under load | Zero kernel panic; `s8_dp_daemon` blanks `fb2` cleanly; system stays online |
| **10** | **Wi-Fi (2.4G / 5G / AP Mode)** | `wlan0` scan, connect, and SoftAP test | Connects to 2.4 GHz & 5 GHz; `swlan0`/`wlan0` AP mode broadcasts SSID |
| **11** | **Bluetooth 5.0 Radio** | `hciconfig hci0` / `bluetoothctl scan` | BCM4361 Bluetooth controller UP, scanning and pairing operational |
| **12** | **Internal Speaker (`hw:0,0`)** | Play 440 Hz tone + host mic SNR check | Calliope ABOX active; MAX98506 speaker outputs clean audio |
| **13** | **3.5mm Headphone Jack** | CS47L92 headphone route & jack sense | `HP` output route and headset mic path verified in ALSA mixer |
| **14** | **Internal Microphone (`hw:0,9`)** | Record 3s PCM via `arecord -D hw:0,9` | Non-zero RMS acoustic waveform captured from `DMIC1` |
| **15** | **Rear Flash / Torch LED** | Write `1..5` to `torch-sec1/brightness` | Rear LED illuminates and turns off cleanly (`0`) |
| **16** | **Vibration / Haptic Motor** | Write `150` to `timed_output/vibrator` | Physical chassis vibrates for `150ms` |
| **17** | **Cameras & V4L2 Guard** | Probe V4L2 nodes (`/dev/video*`) | Zero kernel panic; MFC hardware codecs (`/dev/video6..9`) intact |
| **18** | **MicroSD Card (`mmcblk0`)** | Read/write benchmark on `/media/sdcard` | Mounted RW; passes file creation, checksum, and speed check |
| **19** | **SIM Slot & Shannon LTE** | Check `cbd` + `/dev/umts_*` + `rmnet0..7` | Modem daemon running; SIM/baseband interfaces registered |
| **20** | **Chassis Buttons (`event3`)** | Press Vol Up/Down, Bixby, Power | `s8_button_daemon` triggers volume, console, torch, and Telegram screenshot |
| **21** | **Internal Sensors (`iio`)** | Read `/sys/bus/iio/devices/*` & `thermal` | SensorHub / IIO devices and all 7 TMU thermal zones report live values |

---

## 3. Mandatory `S8 Imager` Desktop App Verification Checklist

Every UI view, button, and API in `desktop-app/` MUST be tested in a real-life human flow with physical device verification:

1. **Top Telemetry Bar:** Live connection badge (`USB RNDIS` / `Wi-Fi` / `Offline`), OS name, Kernel version, SoC Temp, Battery %, and DisplayPort status update in real time.
2. **Page 1 — Flash OS & Storage Partitioning:**
   - Official Distro Catalog selection (Ubuntu Desktop, Ubuntu Server, Ubuntu Base, Debian 12, Kali Linux, Alpine Linux, Arch Linux ARM, OpenWrt 23.05, Home Assistant OS 18.4, SteamOS ARM).
   - Custom local image file picker (`.img.xz`, `.img`, `.raw`, `.tar.xz`, `.tar.gz`).
   - Target Storage Medium selector (`UFS 2.1 /data/linux/rootfs.img`, `MicroSD Loop`, `MicroSD Partition`).
   - Dynamic Storage Allocation slider (`4 GB`..`48 GB`) & partition proportion bar.
   - First-Boot Seed inputs (Username, Password, Hostname, Optional Wi-Fi SSID/Password).
   - **Copy-on-Deploy Integrity:** Verifies original file in `distros/` has identical SHA-256 before and after flashing (never modifies upstream archive in place).
   - Live Flashing progress bar, log stream, Copy Logs button, Cancel button, and Post-Flash Reboot button.
3. **Page 2 — Hardware Dashboard:**
   - CPU/GPU clock & governor telemetry, RAM/ZRAM usage, UFS & MicroSD usage bars.
   - One-click Hardware Controls: Rear Torch toggle, Haptic pulse button, DisplayPort status/reset, Universal `galaxy-s8-hw` installer button.
4. **Page 3 — Dual Interactive WebSocket PTY Terminal:**
   - Live interactive xterm/PTY shell switching between `Guest OS Shell (env=os)` and `AP Base Shell (env=ap)`, command execution, ANSI color rendering, and clear/copy controls.
5. **Page 4 — Network, Wi-Fi & Remote Desktop:**
   - Live Wi-Fi SSID scanner, Wi-Fi connect form, RNDIS/LAN IP display, and 1-click noVNC Remote Desktop (`:6080`) launcher.

---

## 4. Multi-Distro Untouched Verification Matrix

Each supported ARM64 distribution must be verified from its **untouched upstream archive** in `distros/` by deploying to a staged copy, injecting `galaxy-s8-hw`, booting to PID 1, and capturing real terminal/UI proof:
- [ ] **Ubuntu 24.04.5 LTS (Desktop & Server)**
- [ ] **Debian 12 Bookworm**
- [ ] **Kali Linux ARM64**
- [ ] **Alpine Linux 3.20 (musl / OpenRC)**
- [ ] **Arch Linux ARM**
- [ ] **OpenWrt 23.05.5 (procd / Router OS)**
- [ ] **Home Assistant OS 18.4 (Supervisor / Containers)**
- [ ] **SteamOS ARM64 / Experimental Branches**

