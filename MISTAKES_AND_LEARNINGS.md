# Mistakes, Pitfalls & Learned Lessons

This document tracks known traps, debugging revelations, and solutions for the Samsung Galaxy S8 (`SM-G950N`) Exynos project.

---

## 1. Bootloader & Flashing Pitfalls

### Trap 1: Anti-Rollback Protection (SW REV CHECK FAIL)
* **Symptom:** Odin flashing fails with error: `SW REV. CHECK FAIL : [boot]Fused 5 > Binary 4`.
* **Cause:** Samsung S-Boot enforces monotonic counter security fuses. Once updated to Bootloader Revision 5 (`U5` / `DVG2`), the device will permanently reject any firmware or boot image with Revision 4 or lower.
* **Lesson/Rule:** Always use base binaries, kernels, and DTBs built against REV 5 (e.g. `G950NKSU5DVG2`). Never attempt to flash older Android 8/7 Odin tarballs.

### Trap 2: FRP / OEM Lock Blocking Custom Binaries
* **Symptom:** Odin errors with `Custom Binary (BOOT) Blocked By OEM Lock` or `FRP Lock`.
* **Cause:** The "OEM Unlocking" option was disabled in Developer Options, or Google Factory Reset Protection was active.
* **Lesson/Rule:** Ensure OEM unlocking is enabled. In screenless situations where the system has been wiped, flash full stock AP/BL/CP/CSC first, bypass setup, and ensure OEM unlocking is toggled.

---

## 2. Kernel Compilation & Toolchain Pitfalls

### Trap 3: Modern GCC / Clang Build Failures
* **Symptom:** Compiling Samsung 4.4 kernel on modern Linux (Ubuntu 22.04+ with GCC 11/12) throws hundreds of errors regarding VLA (Variable Length Arrays), inline assembly constraints, and `-Werror`.
* **Cause:** The downstream 4.4 Samsung BSP code uses GCC 4.9-era C dialects and compiler extensions.
* **Lesson/Rule:** NEVER use system GCC. Always use the bundled `aarch64-linux-android-4.9` toolchain located in `scripts/toolchain/` or compile within an Ubuntu 18.04/20.04 container.

### Trap 4: The KVM Trap & Repack Compression Failure
* **Symptom:** Flashing `boot_kvm_fixed.tar` or any kernel with `CONFIG_KVM=y` triggers an immediate Samsung Debugger panic / Upload Mode crash on boot.
* **Root Causes:**
  1. **ARM EL2 Lock:** Samsung's S-Boot bootloader boots the Exynos 8895 in Non-Secure EL1 and reserves EL2 (Hypervisor) in TrustZone. When `CONFIG_KVM=y` executes hypervisor mode setup (`hvc` instructions) from EL1, the CPU throws an undefined instruction exception.
  2. **Ramdisk Compression Mismatch:** Android Image Kitchen was repacking ramdisks as `gzip`. Samsung S-Boot on Android 9 REV 5 strictly expects `lz4_legacy` compressed ramdisks.
* **Lesson/Rule:** 
  - Do NOT enable `CONFIG_KVM=y` on downstream kernels without an EL2 hypervisor shim.
  - Docker does NOT require KVM; Docker relies strictly on kernel cgroups, namespaces, and overlayfs.
  - Always use `lz4_legacy` compression for ramdisk images (as handled natively by `magiskboot`).
  - Active verified working kernel baseline: **A2N Kernel 4.4.302** (backed up directly from the running device as `boot_backup_live.img`).

---

## 3. Screenless / Headless Operation Pitfalls

### Trap 5: Android Setup Wizard Blocking USB Debugging
* **Symptom:** Device boots stock Android, but PC cannot connect via `adb` or `scrcpy` because the initial Setup Wizard is waiting for on-screen touch input.
* **Cause:** Clean stock flashes force the initial setup wizard and require manual USB authorization on screen.
* **Lesson/Rule:** 
  1. Boot into TWRP and disable the setup wizard via shell:
     ```bash
     pm disable-user com.google.android.setupwizard
     pm disable-user com.sec.android.app.SecSetupWizard
     settings put global setup_wizard_has_run 1
     settings put secure user_setup_complete 1
     ```
  2. Pre-inject your PC's `adbkey.pub` into `/data/misc/adb/adb_keys` to bypass the authorization popup.

### Trap 6: Blind Odin Download Mode Misses
* **Symptom:** Phone vibrates or boot loops instead of entering Download Mode.
* **Cause:** Missing the exact button timing without visual screen confirmation.
* **Lesson/Rule:**
  1. Ensure complete power-off (hold Power + Vol Down 12 seconds with USB unplugged).
  2. Hold **Volume Down + Bixby**.
  3. While holding, plug in the USB cable connected to PC.
  4. Wait 2 seconds, release buttons, and press **Volume Up** once.
  5. Check Windows Device Manager / Odin log for `Added! [COMx]`.

---

## 4. Power & Hardware Modding Pitfalls

### Trap 7: High-Load Power Cutoff (Brownout)
* **Symptom:** S8 suddenly powers off during high multi-core compilation or container load while connected to a PC USB port.
* **Cause:** PC USB 2.0/3.0 ports only supply 0.5A to 0.9A. When all 8 Exynos cores hit 2.3 GHz turbo, peak power consumption exceeds 6W–8W (~1.5A–2.0A at battery voltage).
* **Lesson/Rule:** Never power high-load tests from a low-power USB port alone. Use a 15W+ Samsung AFC/PD fast charger, or perform the battery eliminator mod using a 4.10V high-current DC buck converter.

### Trap 8: Battery Elimination Thermistor Cutoff
* **Symptom:** Phone refuses to boot or immediately shuts down when the battery is removed and external voltage is applied.
* **Cause:** The S8's fuel gauge IC (Maxim PMIC) monitors the `THM` (thermistor) line. If open circuit, the PMIC assumes battery temperature is -20°C or +80°C and halts boot.
* **Lesson/Rule:** Always bridge the `THM` pad to `GND` with a **10 kΩ resistor** to simulate a healthy 25°C battery condition.

### Trap 9: glibc 2.35 (Ubuntu 22.04) vs. Linux 4.4 Syscall Traps
* **Symptom:** Sub-processes in Ubuntu 22.04 (such as `apt` http methods or complex bash forks) fail with Segmentation Faults. Register `x8` in dmesg shows syscall `0x1b2` (434 = `pidfd_open`).
* **Cause:** Ubuntu 22.04 uses glibc 2.35+, which introduces unconditional calls to Linux 5.3+ syscalls (`pidfd_open` #434, `clone3` #435). Downstream Android 4.4 kernels trap unknown syscalls under SECCOMP/defex and send `SIGSYS`/`SIGSEGV`.
* **Lesson/Rule:** For downstream Linux 4.4 kernels, use **Ubuntu 20.04 LTS (Focal Fossa)** or **Debian 11 (Bullseye)**. Both use **glibc 2.31**, which was architected natively for Linux 4.4 kernels without `pidfd_open` dependencies, providing full stability for systemd and Docker CE.

