# Galaxy S8 Native Linux & Docker Project Rules

These rules apply to all tasks and agent interactions in this workspace (`e:\rouf\galaxy-s8`).

> [!CRITICAL]
> **STRICT HEADLESS DIRECTIVE — NO INTERNAL DISPLAY:**
> The phone's internal OLED display is **COMPLETELY ABSENT / DISCONNECTED** (`lcdtype=-1`).
> **NEVER** give instructions referencing on-screen visual feedback (e.g., "watch for screen to go black", "when you see the Samsung logo", "tap confirmation on display", "look at the splash screen"). The user CANNOT see anything on the phone!
> **ALWAYS** design and communicate physical procedures using ONLY:
> 1. **Haptic Feedback:** The internal vibration motor pulses (single buzz on reset, boot vibrations).
> 2. **Strict Time Counting:** Explicit seconds count (e.g. "count to 7 seconds").
> 3. **Host PC USB Status:** Windows Device Manager / Odin / ADB status (`PID_685D` for Download Mode, `PID_6860` on COM11 for Android, `recovery` in `adb devices`).

## 1. Hardware & Variant Profile
* **Target Device:** Samsung Galaxy S8 (Exynos 8895) - Korean Variant (`SM-G950N`, codenames: `dreamlteks`, `dreamltekor`).
* **Bootloader State:** **Unlocked** (Knox state `0x1`). Never suggest Qualcomm/US-locked (`SM-G950U`) bootloader workarounds.
* **Bootloader Rev:** Binary Version 5 (`U5` / `G950NKSU5DVG2`). Do not attempt to flash bootloaders older than Rev 5 to prevent rollback bricking.
* **Internal Screen:** **ABSENT / DISCONNECTED**. Always design procedures for **headless** operation (USB-C DisplayPort Alt Mode / DeX, ADB, scrcpy, SSH, or hardware UART).

## 2. Kernel Compilation & Virtualization Rules
* **Baseline Kernel:** The device was running the **A2N Kernel (Linux 4.4.302)**, which contains a proprietary trial lock (`[set_a2n_allow] a2n: bye bye!`) that disables battery charging at the PMIC level when unlicensed. Use the clean Samsung stock kernel (`boot_stock.tar`) or our custom compiled kernel without trial killswitches.
* **KVM Prohibition:** NEVER enable `CONFIG_KVM=y` on downstream kernels. Samsung S-Boot boots in Non-Secure EL1 and reserves EL2 (Hypervisor) in TrustZone; executing `hvc` instructions causes an instant `sec_debug` kernel panic. Docker does NOT need KVM—focus exclusively on cgroups, namespaces, and overlayfs.
* **Ramdisk Packaging:** Samsung downstream kernels use standard **`gzip`** compression for internal ramdisks (`1f 8b 08 00`). `lz4_legacy` is only used for packaging `.img.lz4` archives in official firmware tars. Always compress boot ramdisks with `gzip`.
* **Odin TAR Packaging:** All Odin flashable `.tar` archives MUST be created strictly in POSIX.1-1988 `USTAR` format (`format=tarfile.USTAR_FORMAT`). Never use Python's default PAX format, which injects `./@PaxHeader` and causes Odin to abort with "Unassigned file".

## 3. Storage & Partitioning Safety
* **Storage Type:** 64 GB UFS 2.1 (`/dev/block/platform/11120000.ufs/by-name/*`).
* **Protected Partitions:** NEVER modify, wipe, or overwrite `efs`, `nvdata`, `param`, or `sboot`.
* **Safe Target Partitions:** 
  - `boot` (kernel / initramfs for primary OS)
  - `recovery` (kernel / initramfs for secondary dual-boot OS or TWRP)
  - `userdata` (contains rootfs, loopback images, Docker storage)

## 4. Headless & Screenless Operating Principles
* **Never assume physical touch or display interaction:** Internal display does not exist. Never refer to on-screen visuals. Bypass Google/Samsung setup wizards in Android, disable screen locks, and enable persistent ADB by default (`persist.sys.usb.config=mtp,adb`).
* **Hardware Button Timing:** Because there is no screen, button press combinations must be described with exact time durations in seconds and vibration motor sensations.
* **Video Output:** The device supports native DisplayPort 1.2 Alternate Mode over USB Type-C. Guide the user to use a powered USB-C hub with HDMI out and keyboard/mouse.
* **Emergency Shell:** TWRP must always have insecure `adbd` active on boot as a rescue environment.

## 5. Hardware Modding Directives
* **Battery Safety & Eliminator (Dummy Battery):** Advise against running the device 24/7 on an aging lithium battery. Use a 4.10V DC buck converter with a 10 kΩ NTC thermistor to ground on the battery connector and a 470–1000 µF low-ESR buffer capacitor.
* **Coulomb Counter Drift Prevention:** When running without a battery on Android, provide dual-feed (4.10V VBAT + 5V USB-C VBUS) or patch `max77865_fg_read_soc()` in the kernel to prevent the fuel gauge from counting down to 0% and triggering artificial shutdowns.
* **Low-Voltage Recovery Protocol:** If battery voltage drops below 3.4V, do not attempt booting normal OS (which triggers brownout reboot loops and Knox DEFEX panics). Hold the device in Download Mode to safely trickle-charge past 3.65V.
* **Thermal Management:** With the screen removed, recommend mounting a heatsink + fan directly to the midframe shield over the Exynos 8895 SoC to prevent thermal throttling.

