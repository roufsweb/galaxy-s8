# Acknowledgments & Credits

The **Galaxy S8 Native Linux Platform (`galaxy-s8`)** is built upon the foundational work, open-source codebases, drivers, and tools developed by the global engineering and open-source communities. We express our sincere gratitude and acknowledge the contributions of the following organizations, projects, and individuals:

---

## 1. Silicon, Hardware & Vendor Drivers

* **Samsung Electronics Co., Ltd.**
  * Exynos 8895 SoC Board Support Package (BSP) and device tree geometry for `universal8895` / `dreamlteks`.
  * S-Boot primary bootloader architecture, Odin flashing protocol, and Samsung boot header structures.
  * Hardware driver implementations:
    * DECON (Display Controller 2 / `/dev/graphics/fb2`) and Exynos ION memory management subsystem.
    * CCIC (Type-C Cable & Connector Interface Controller), S2MU004, and `dp_sec` DisplayPort Alternate Mode driver.
    * ABOX Calliope audio DSP architecture, firmware blobs, and Madera sound card integration.
    * Shannon 359 cellular baseband modem drivers (`umts_ipc`, `rmnet`).

* **Maxim Integrated (Analog Devices)**
  * MAX77865 Power Management IC (PMIC) and smart battery charger driver architecture.
  * MAX98506 Class D speaker amplifier.

* **Cirrus Logic**
  * Cirrus Logic CS47L92 / Madera low-power audio codec and Digital Microphone (DMIC1) hardware interface.

* **Broadcom Corporation**
  * Broadcom BCM4361 dual-band 802.11ac Wi-Fi PCIe driver (`dhd`) and Bluetooth 5.0 UART HCI controller stack.

---

## 2. Operating System, Kernel & Core Subsystems

* **boerck (`ohjjj1007@naver.com` / [boerck](https://github.com/boerck))**
  * Original developer of the Samsung Galaxy S8 Korean variant (`SM-G950N` / `dreamltekor`) KVM kernel tree (`android_kernel_samsung_dreamltekor_kvm`), pioneering ARM64 hardware-assisted virtualization on Exynos 8895, dtbtool packaging, and GCC 4.9 toolchain integration that our customized DEFEX-free native Linux kernel builds upon.

* **John Cadduono ([jcadduono](https://github.com/jcadduono))**
  * Exynos 8895 kernel pioneer, author of `android_kernel_samsung_universal8895`, Exynos `dtbtool` Linux build system integration, and official TWRP recovery architecture for Galaxy S8 Exynos devices.

* **Osm0sis ([osm0sis](https://github.com/osm0sis))**
  * Author of Android Image Kitchen (`AIK-Linux`), used for precision ramdisk unpacking, kernel header manipulation, and boot image assembly.

* **The Exynos 8895 Custom Kernel & XDA Community**
  * Independent researchers, ROM and kernel developers (including Jesec, Ananjaser1211, Corsicanu, Noxxxious, and Ace42) whose reverse engineering and research documented Exynos 8895 hardware quirks, PMIC power thresholds, and boot mechanisms.

* **The Linux Kernel Community & Linus Torvalds**
  * The Linux kernel codebase, POSIX driver model, ALSA audio framework, evdev input subsystem, and cgroups container infrastructure.

* **Canonical & The Ubuntu Community**
  * Ubuntu 24.04.5 LTS (`Noble Numbat`, `aarch64`) userspace root filesystem, glibc 2.39 runtime, and Debian/Ubuntu package repositories.

* **TeamWin Recovery Project (TWRP)**
  * TWRP device configuration and ramdisk staging trees for the Samsung Galaxy S8 (`dreamlte`).

* **John Wu (`topjohnwu`) & The Magisk Project**
  * The `magiskboot` binary toolchain used for precision unpacking, header parsing, ramdisk patching, and repacking of Samsung Android boot and recovery images.

---

## 3. Desktop Environment & User Interface

* **The GNOME Project**
  * GNOME 46 Desktop Environment, GTK 4.14, `libadwaita`, Metacity window manager, `gnome-panel`, Nautilus 46 file manager, GNOME Console (`kgx`), and Epiphany Web Browser.

* **Vince Liuice (`vinceliuice`)**
  * **WhiteSur GTK Theme & WhiteSur Icon Theme:** macOS Sonoma / BigSur visual styling, traffic-light window button styling, and icon assets for GTK3/GTK4.

* **Rico Tzschichholz & The Plank Dock Team**
  * Plank desktop dock application for smooth, lightweight application navigation.

* **TigerVNC Project**
  * TigerVNC (`Xtigervnc`) high-performance X11 VNC server.

* **Joel Martin & The noVNC Team**
  * noVNC (HTML5 VNC web client) and websockify (WebSocket-to-TCP proxy) enabling browser-based remote desktop access with zero client-side installation.

---

## 4. Containerization & Homelab Cloud Services

* **Docker, Inc. & The Moby Project**
  * Docker CE 26 container engine, `containerd`, and `runc` container runtimes.

* **IceWhale Technology & The CasaOS Community**
  * CasaOS: Elegant, intuitive cloud dashboard and home server management portal.

* **The Ollama Community**
  * Ollama: Local AI and large language model inference runtime on ARM64.

* **Coder & The Code-Server Community**
  * Code-Server: Full Visual Studio Code browser-based development environment.

* **Louis Lam & The Uptime Kuma Community**
  * Uptime Kuma: Self-hosted infrastructure monitoring and status dashboard.

* **The FileBrowser Team**
  * FileBrowser: Responsive web-based file management utility.

* **AdGuard Team**
  * AdGuard Home: Network-wide DNS server and telemetry blocker.

---

## 5. Maintenance & Project Leadership

* **Abdur Rouf ([roufsweb](https://github.com/roufsweb))**
  * System architecture, reverse-engineering, hardware register programming, DisplayPort ION bridge daemon, audio routing, Odin package building, automated tooling, and project documentation.
