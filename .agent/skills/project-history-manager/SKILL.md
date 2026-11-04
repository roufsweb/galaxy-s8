---
name: project-history-manager
description: Operational runbook and query tool for logging, searching, and reviewing the chronological execution history, verified working procedures, and past failures on the Samsung Galaxy S8 native Linux project.
---

# Project History Manager Skill

Use this skill continuously to maintain total visibility over all past actions, prevent repeating failed experiments, and search project history instantly.

---

## 1. Fast History Search Tool

Before proposing ANY flashing, rebooting, kernel compilation, or configuration changes, run the search tool to review previous attempts and known pitfalls:

```powershell
python e:\rouf\galaxy-s8\scripts\search_history.py "<keyword>"
```
*Or via PowerShell wrapper:*
```powershell
powershell -ExecutionPolicy Bypass -File e:\rouf\galaxy-s8\scripts\search_history.ps1 "<keyword>"
```

---

## 2. Mandatory Pre-Flight Audit Rule

> [!CRITICAL]
> **No guessing / No throwing rocks in the air:**  
> Before formulating any technical plan or recommending a firmware flash, you MUST:
> 1. Query [`HISTORY.md`](file:///e:/rouf/galaxy-s8/HISTORY.md) to check if the action was attempted before and what its outcome was.
> 2. Query [`FINDINGS.md`](file:///e:/rouf/galaxy-s8/FINDINGS.md) to check if any hardware/PMIC locks apply.
> 3. Verify the live hardware state via USB PID (`PID_685D` for Download Mode, `PID_6860` for Android) before giving instructions.
> 4. **HEADLESS ENFORCEMENT:** Remember the device has NO INTERNAL DISPLAY. Never tell the user to watch the screen, look for logos, or tap prompts. Guide only with vibration cues, countdown timers in seconds, and PC USB logs.

---

## 3. Mandatory Post-Action Ledger Update

Immediately after completing a test, flash, script execution, or recovery sequence, update [`HISTORY.md`](file:///e:/rouf/galaxy-s8/HISTORY.md) with:
* **Task Title & Number:** Incremented sequential task ID.
* **Timestamp & Files Touched:** Exact files, images, or partitions modified.
* **What Worked:** Verified successes backed by log/hardware proof.
* **What Failed:** Exact failure modes and technical root causes.
* **Current Status Matrix:** Update the high-level matrix at the top of [`HISTORY.md`](file:///e:/rouf/galaxy-s8/HISTORY.md).

---

## 4. Maintenance Standards

* Keep entries strictly factual. Never omit failed steps.
* Maintain the Asset & Partition Inventory at the bottom of [`HISTORY.md`](file:///e:/rouf/galaxy-s8/HISTORY.md) whenever new images (`.tar`, `.img`) are generated.

