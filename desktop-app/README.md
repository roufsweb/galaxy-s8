# S8 Imager by roufsweb — Desktop Application Workspace

> **Dedicated Desktop Application Project** for Samsung Galaxy S8 (`SM-G950N`, Exynos 8895) Universal Linux OS Flasher & Hardware Manager.

---

## 1. Directory Structure

```
desktop-app/
├── app/                              # Modular Python Application Package
│   ├── __init__.py
│   ├── config.py                     # Central dynamic path resolver (bin, ui, distros, packages)
│   ├── main.py                       # Application entrypoint & native window launcher
│   ├── gui_legacy.py                 # Fallback CustomTkinter GUI shell
│   ├── core/                         # Hardware communication & domain logic
│   │   ├── __init__.py
│   │   ├── adb.py                    # Dual-transport client: ADB + USB/Wi-Fi SSH (Paramiko/raw)
│   │   ├── device.py                 # Real telemetry collector, Wi-Fi manager & S8 pack installer
│   │   ├── distros.py                # Official upstream ARM64 catalog, downloader & SHA-256 verifier
│   │   ├── flasher.py                # GPT/MBR ext4 partition extractor & /data/linux/rootfs.img writer
│   │   └── injector.py               # Minimal Rule 27 first-boot USB RNDIS + SSH connectivity seed
│   └── server/                       # Embedded REST API & Web Server
│       ├── __init__.py
│       └── api.py                    # REST API endpoints & static asset router
├── bin/                              # Platform Native Binaries
│   ├── adb.exe                       # Embedded Android Debug Bridge
│   ├── AdbWinApi.dll
│   └── AdbWinUsbApi.dll
├── resources/                        # Boot Seed Assets (Zero OS Forking)
│   ├── bin/
│   │   └── s8-dropbear-arm64         # Static upstream Dropbear SSH server for minimal seed
│   └── scripts/                      # Device helper scripts
├── tests/                            # 4-Layer Verification Test Suite (6 CI Gates)
│   ├── __init__.py
│   ├── test_app_structure.py         # Path resolution & architecture unit tests
│   ├── test_unit_core.py             # MBR/GPT extractor, catalog, and seed unit tests
│   ├── test_integration_api.py       # REST API endpoint & schema integration tests
│   ├── test_e2e_human_flow.py        # Playwright full app E2E navigation tests
│   ├── test_terminal_human_flow.py   # Playwright dual-transport terminal workflow tests
│   ├── test_flash_human_flow.py      # Playwright Flash OS & storage slider flow tests
│   └── test_performance_budget.py    # Latency budget benchmarks
├── scripts/
│   └── ci_cd_validator.py            # Automated 6-gate CI/CD verification runner
├── ui/                               # Frontend Web Assets
│   └── index.html                    # Bento Grid Single-Page Web Dashboard
├── main.py                           # Quick launcher entrypoint (python main.py)
├── server.py                         # Dev server launcher (python server.py)
├── GalaxyS8_OS_Flasher.spec          # PyInstaller standalone build specification
├── pyproject.toml                    # Standard Python project metadata
├── requirements.txt                  # Python dependencies
└── README.md                         # This file
```

---

## 2. Key Architecture & Features

### A. Bento Grid Dashboard (`ui/index.html`)
* **Color Palette:** Deep Space Charcoal (`#0F1014`), Royal Blue (`#3478F6`), and **Electric Cyan (`#38BDF8`)**.
* **Expandable Sidebar:**
  * Expanded (`w-56`): Displays the Galaxy S8 outline icon, title, and navigation items (`Flash OS`, `Hardware Dashboard`, `Root Terminal`, `Device Screen`, `Device & Network Config`).
  * Collapsed (`w-16`): Compact icon rail with collapse/expand toggle button.
* **Header:**
  * Clean branding: `S8 Imager` `by roufsweb`.
  * Top-right live transport status pill (emerald when USB RNDIS `192.168.7.2`, Wi-Fi SSH, or TWRP ADB is live; muted offline indicator otherwise).

### B. Workflow Zones
* **Workflow 1: Flash OS (Unmodified Upstream Deployment)**
  * **Official OS Catalog (`#distroModal`):** Download and SHA-256 verify clean upstream ARM64 images (Ubuntu 24.04.5 Desktop `.img.xz`, Ubuntu Server, Debian 12, Kali, Arch ARM, Alpine) or pick a custom local image.
  * **First-Boot Seed:** Set initial username, password, hostname, and optional Wi-Fi credentials.
  * **Storage Provisioning:** Dynamic UFS 2.1 allocation slider (4-48 GB on `/dev/block/sda24`, 53.7 GB userdata) cleanly keeping one OS (`/data/linux/rootfs.img`).
  * **Deployment Pipeline:** Native Python `.img.xz` GPT/MBR `ext4` extraction, `/data/linux/rootfs.img` streaming write, minimal connectivity seed (`192.168.7.2` + `s8-dropbear-arm64`), and Reboot action.
* **Workflow 2: Hardware Dashboard & Device Config**
  * **Live Hardware Telemetry:** Genuine CPU frequency, free RAM, battery percentage, thermal reading, MicroSD status, and DisplayPort state polled via USB RNDIS SSH (`192.168.7.2`), Wi-Fi SSH, or TWRP ADB.
  * **One-Click S8 Hardware Pack (`INSTALL S8 PACK`):** Pushes and installs `galaxy-s8-hw_1.0.0_arm64.deb` (or universal `.tar.gz`), activating MAX77865 1,500 mA fast charging, Calliope ALSA audio, `s8_button_daemon`, `99-s8-power.conf`, DisplayPort hotplug, and optional TigerVNC/noVNC desktop bridge.
  * **Wi-Fi Hub & Identity:** Live Wi-Fi scan (`s8_wifi.py` / `nmcli`) across 2.4/5 GHz, WPA2/WPA3 connect, hostname, SSH key injection, and password management.
  * **Root Terminal & Device Screen:** Dual-transport interactive terminal (`USB RNDIS` / `RWP Wi-Fi`, `OS Root` / `AP Base`) and one-click noVNC (`:6080`) browser launch.

---

## 3. How to Run & Verify

### Launch S8 Imager
```cmd
Launch_S8_Imager.bat
```
Or directly from Python:
```bash
cd desktop-app
python main.py
```

### Run Full 6-Gate CI/CD Verification
```bash
python desktop-app/scripts/ci_cd_validator.py
```
Runs syntax compilation, secret hygiene sanitization, Layer 1 unit tests, Layer 2 API integration tests, Layer 3 Playwright human-flow automation, and Layer 4 performance budgets.

### Compiling Standalone Single-File Windows Executable
```bash
cd desktop-app
pyinstaller s8_imager.spec
```
Outputs standalone `dist/S8_Imager.exe` with bundled embedded ADB and static Dropbear SSH bootstrap binary.

---

## 4. Upstream Kernel & Hardware Credits

The Galaxy S8 native Linux operating system and flashable images build directly upon the work of upstream kernel pioneers:

* **[boerck](https://github.com/boerck)** (`ohjjj1007@naver.com`) — Original developer of the Samsung Galaxy S8 Korean variant (`SM-G950N` / `dreamltekor`) KVM kernel source tree (`android_kernel_samsung_dreamltekor_kvm`), enabling initial hardware virtualization support, dtbtool packaging, and GCC 4.9 toolchain integration that our customized DEFEX-free native Linux kernel builds upon.
* **[John Cadduono (jcadduono)](https://github.com/jcadduono)** — Exynos 8895 kernel pioneer, author of `android_kernel_samsung_universal8895`, Exynos `dtbtool` Linux build system integration, and official TWRP maintainer for Galaxy S8 Exynos devices.
* **[Osm0sis (osm0sis)](https://github.com/osm0sis)** — Author of Android Image Kitchen (`AIK-Linux`), utilized for precision ramdisk unpacking, kernel header manipulation, and boot image assembly.
* **Samsung Electronics Co., Ltd. (OSRC)** — Original Exynos 8895 Linux 4.4 Board Support Package (BSP), DECON display controller 2, CCIC DisplayPort Alternate Mode stack, Shannon 359 baseband IPC, and ABOX Calliope DSP architecture.
* **The Exynos 8895 Custom Kernel & XDA Community** — Independent kernel and recovery developers (including Jesec, Ananjaser1211, Corsicanu, Noxxxious, and Ace42) whose reverse engineering documented Exynos 8895 hardware quirks and boot sequences.


