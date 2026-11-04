---
name: project-findings-manager
description: Operational runbook and standards for documenting, verifying, and managing critical hardware, kernel, power management, and userland findings on the Samsung Galaxy S8 native Linux project.
---

# Project Findings Manager Skill

Use this skill continuously and proactively across the Samsung Galaxy S8 Native Linux project.

---

## 1. Autonomous Documentation Directive (Zero User Delay)

> [!IMPORTANT]
> **DO NOT wait for the user to request documentation.**  
> The moment a technical root cause, hardware mechanism, power modding trap, bootloop symptom, or tooling quirk is diagnosed or explained in the conversation, the agent **MUST immediately append it to [`FINDINGS.md`](file:///e:/rouf/galaxy-s8/FINDINGS.md) in that very same turn**.

---

## 2. Mandatory Trigger Criteria
A finding MUST be logged into [`FINDINGS.md`](file:///e:/rouf/galaxy-s8/FINDINGS.md) immediately whenever any of the following occur:
1. **Hardware & Power Management Traps:**
   - Any silicon, PMIC, or CCIC behavior (e.g., MAX77865 `CHGIN < CHGIN_UVLO`, A2N kernel `a2n_allow` killswitch).
   - Battery Eliminator / Dummy Battery dynamics (e.g., Coulomb counter depletion drift, NTC thermistor 10 kΩ spoofing, buffer capacitance requirements, low-voltage inrush brownout loops).
2. **Bootloader & Security Enforcement:**
   - S-Boot quirks, Download Mode protocol locks, Bootloader Control Block (`MISC` `/dev/block/sda5`).
   - Samsung Knox DEFEX, TIMA, and dm-verity panics on unlocked (`Knox 0x1`) bootloaders.
3. **Architecture & ABI Incompatibilities:**
   - Userland runtime traps on downstream kernels (e.g., glibc `AT_HWCAP` dynamic loader segfaults vs musl libc stability).
4. **Tooling & Flashing Specifications:**
   - Flasher strictness (e.g., Odin POSIX.1-1988 USTAR format vs PAX header rejections).
   - Ramdisk compression constraints (e.g., `lz4_legacy` vs standard gzip).

---

## 3. Standard Finding Schema
Always format new entries in [`FINDINGS.md`](file:///e:/rouf/galaxy-s8/FINDINGS.md) using this exact template:

```markdown
## [Number]. Finding: [Short Descriptive Title]
* **Severity:** [Critical | High | Medium | Low]
* **Discovery Date:** [YYYY-MM-DD]
* **Observed Symptom:** [Exact human or system symptom]
* **Kernel & Hardware Evidence:** [Code block with exact dmesg, console, register, or tool error lines]
* **Root Cause Analysis:** [Exhaustive technical explanation citing driver/source files]
* **Permanent Fix & Solution:** [Exact commands, patches, or procedures to resolve]
* **Future Prevention Rule:** [One-sentence directive added to project guidelines]
```

---

## 4. Evidence & Verification Standards
1. **Source Code & Register Cross-Reference:** Always cite exact line numbers and register names in `galaxy-s8-kvm-kernel/` (e.g., `drivers/battery_v2/`, `drivers/ccic/`, `include/linux/mfd/`).
2. **Direct Observation:** Quote exact `dmesg`, `/proc/last_kmsg`, serial/ADB output, or tool terminal strings. Never base findings on conjecture.
3. **Cross-Document Synchronization:**
   - If the finding introduces a permanent operational constraint, update [`GEMINI.md`](file:///e:/rouf/galaxy-s8/GEMINI.md).
   - If the finding alters firmware assets or project status, update [`SUMMARY.md`](file:///e:/rouf/galaxy-s8/SUMMARY.md).
