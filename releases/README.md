# Samsung Galaxy S8 Native Linux — Odin AP Boot Package & Hardware Pack Releases

Maintained by [roufsweb](https://github.com/roufsweb)

## Overview

Per our **Zero-Fork Upstream OS Mandate**, we do **not** distribute pre-modified Linux distro archives. Instead, you flash the small Odin **AP package (`Galaxy_S8_Linux_AP.tar`)** once, then use **S8 Imager** (`Launch_S8_Imager.bat`) to download and flash **unmodified official ARM64 distributions** directly from Canonical, Debian, Kali, Arch ARM, or Alpine mirrors, followed by installing `galaxy-s8-hw` hardware support cleanly post-boot.

## Included Odin Release Packages (`releases/`)

| File | Size | SHA-256 | Role |
| :--- | :--- | :--- | :--- |
| **`Galaxy_S8_Linux_AP.tar`** | `79,472,640` B | `9f1fa748a6901bee612274e47f6b5e7d74ab9f11751a97504fe7f4afcaf6b721` | Recommended Odin AP archive: DEFEX-free Linux `4.4.111` kernel on `BOOT` (`sda7`) + headless TWRP recovery on `RECOVERY` (`sda8`). |
| **`Galaxy_S8_Linux_AP_Proven.tar`** | `74,577,920` B | `4b5aec4221674b7e6dd6be7c2fe5f2b917b741d4158fe3ec1eca28343e2018d4` | Alternate baseline proven Odin AP archive. |

---

## Step 1: One-Time Odin Flash (`Galaxy_S8_Linux_AP.tar`)

### Enter Odin Download Mode
1. Connect the Galaxy S8 to your Windows PC with a USB-C data cable.
2. Hold **Volume Down + Bixby + Power** simultaneously for **11 to 13 seconds** until Download Mode (`PID_685D`) activates (no Volume Up press needed).
3. *Unresponsive recovery:* Hold all 3 buttons for 30 seconds to release the PMIC latch, pause 1 second, then hold all 3 buttons for 13 seconds.

### Flash the AP Package
1. Launch Odin 3.14+ on Windows and confirm `ID:COM` detects the device.
2. Click **AP** and select `releases/Galaxy_S8_Linux_AP.tar`.
3. Keep **Auto Reboot** and **F. Reset Time** checked, then click **Start**.
4. As soon as Odin displays green **PASS!**, unplug and immediately re-plug the USB-C cable so Windows enumerates ADB cleanly.

---

## Step 2: Deploy Unmodified Upstream OS via S8 Imager

1. Launch `Launch_S8_Imager.bat` from the repository root.
2. Open **Flash OS -> Catalog**, click **FETCH** on *Ubuntu 24.04.5 LTS Desktop (Official)* (or any listed upstream OS), wait for automatic SHA-256 verification, and select it.
3. Fill in **First-Boot Seed** (username, password, hostname, optional Wi-Fi) and UFS storage size (4-48 GB), then click **Flash Image**.
4. Click **Reboot Device**. The phone pulses haptics twice when USB RNDIS (`192.168.7.2`) and Dropbear SSH are online.

---

## Step 3: Install `galaxy-s8-hw` Hardware Pack

In **S8 Imager -> Device & Network Config**, click **INSTALL S8 PACK** (optionally check TigerVNC/noVNC if using headless over browser rather than a USB-C HDMI monitor).

Manual standalone installation packages are also built in [`packages/galaxy-s8-hw/`](file:///e:/rouf/galaxy-s8/packages/galaxy-s8-hw/) (`packages/dist/`):
* **Debian / Ubuntu / Kali:** `dpkg -i galaxy-s8-hw_1.0.0_arm64.deb`
* **Arch / Alpine / Other:** `tar -xzf galaxy-s8-hw-1.0.0-arm64.tar.gz && cd galaxy-s8-hw-1.0.0 && ./install.sh`

See [`TESTING_RUNBOOK.md`](file:///e:/rouf/galaxy-s8/releases/TESTING_RUNBOOK.md) for the end-to-end verification checklist.
