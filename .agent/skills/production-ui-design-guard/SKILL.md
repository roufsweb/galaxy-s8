---
name: production-ui-design-guard
description: Enforce clean, restrained, production-grade UI design across desktop and web applications. Eliminates AI prompt leakage, redundant status pills, hallucinated helper microcopy, Windows/Linux terminology mismatches, and bloated card heights. Use whenever designing, generating, refactoring, or reviewing frontend UI, desktop apps (PyQt/PySide/Electron/Tauri), dashboards, or system utilities.
---

# Production UI Design Guard: Standards for Restrained, Production-Ready Interfaces

> **Eliminates AI prompt leakage, redundant status pills, hallucinated helper microcopy, Windows/Linux terminology mismatches, and bloated card heights.**
> Prevents AI-generated UI antipatterns to produce clean, high-density, production-ready interfaces across web, desktop, and administrative utilities.

---

## 1. When to Use This Skill

Activate this skill whenever:
* **Designing or generating** new application screens, dashboards, or desktop utilities.
* **Refactoring AI-generated UI code** that looks cluttered, "vibe-coded," or overloaded with badges and helper text.
* **Auditing UI layouts** before shipping to production or packaging standalone executables.
* **Building** hardware flashing tools, system monitors, developer consoles, or administrative interfaces.

---

## 2. Core UI Guardrails

### Guardrail 1: Zero Prompt-to-UI Leakage
Users often describe how a feature works in their prompt (e.g., *"make it always clean ext4 with auto-wipe"*, *"use dual-drive partitioning"*, *"real hardware streaming logs"*). **Do NOT copy conversational prompt descriptions directly into UI labels, badges, or subtitles.**

* ❌ **Bad:** A static green box inside a card reading `Always Clean Ext4 (Auto-Wipe)` or subtitle `Real hardware streaming & execution logs`.
* ✅ **Good:** A clean toggle/checkbox `[x] Format as ext4 before flashing`, or omitting static architectural facts from the UI entirely.

### Guardrail 2: Eliminate Decorative Pill & Badge Bloat
AI models frequently invent non-functional pills (e.g., `Ready to Flash`, `16 GB System (C:) • 29.8%`, `GNOME 46 GUI`) that look like interactive buttons.

* **Rule:** If an element is not clickable, it must not have a button border, hover state, or pill container unless it is the single primary connection/process state in the header.
* **Limit:** Maximum 1 status badge per card header. Never place decorative status boxes side-by-side with action buttons.

### Guardrail 3: Strip Redundant Subtitles & Microcopy
Do not explain standard UI controls to the user. Every text node must earn its pixels.

* **Cut:** Card subtitles that just restate the title (e.g., Title: `Live Deployment Console`, Subtitle: `Real hardware streaming & execution logs`).
* **Cut:** Speculative use-case examples inside storage or config cards (e.g., `Rootfs, packages & desktop apps` or `Docker, Home Assistant & storage`). Show only the partition name, mount point, and size.
* **Cut:** Instructional filler inside buttons (e.g., `Select OS Image (File Explorer)` with two folder icons $\rightarrow$ change to `Select Image...` with a single leading icon).

### Guardrail 4: Enforce Strict Domain & OS Terminology
Never mix operating system paradigms within the same interface.

* **Linux / Android / Embedded targets:** Use block devices and mount paths (`/`, `/data`, `sda24`, `ext4`, `rootfs`). Never label Linux partitions as `(C:)` or `(D:)`.
* **Windows targets:** Use drive letters (`C:`, `D:`) and NTFS/exFAT terminology.

### Guardrail 5: Layout Density & Flex Stretching
Prevent cards from stretching vertically to fill window height when their internal content is short, which creates massive empty black voids.

* **Left / Config Column:** Cards must hug their content height (`height: auto` / `QSizePolicy.Preferred`), stacked from the top with a consistent gap (12px to 16px).
* **Right / Console Column:** Only log views, terminals, or data tables should expand to fill vertical space (`flex: 1` / `QSizePolicy.Expanding`).
* **Slider & Preset Alignment:** When pairing a range slider with quick-select preset pills (`10 GB`, `16 GB`, `32 GB`), either use tick marks on the slider or preset pills below it—never render both a text scale and duplicate buttons underneath.

### Guardrail 6: Action & State Hierarchy
Maintain a strict visual hierarchy so the user knows immediately where to click:

* **Primary CTA:** Maximum one solid high-contrast button per view (e.g., `Flash Image`). Use a single clean icon, Title Case (avoid screaming ALL CAPS unless styled with tiny tracking), and disable it clearly when the target device is Disconnected.
* **Secondary Actions:** Outlined or subtle surface buttons (`Select Image...`, `Browse Library`, `Copy Logs`).
* **State Consistency:** Never display `Ready to Flash` or `[STANDBY] Ready to deploy` inside the UI while the top-right hardware indicator says `Disconnected`. Tie all readiness text and CTA enabled states directly to the actual device connection state.

---

## 3. Step-by-Step UI Audit Workflow

Before outputting or updating any UI code, run this 5-point verification pass:

```
┌────────────────────────────────────────────────────────┐
│ 1. Prompt Echo Check                                   │
│    Scan all string literals; delete prompt phrases.    │
└───────────────────────────┬────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────┐
│ 2. Clickability Test                                   │
│    Strip borders/fills from non-interactive pills.     │
└───────────────────────────┬────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────┐
│ 3. Icon & Emoji Purge                                  │
│    Remove emojis (⚡, 📁, 🧹); enforce unified SVGs.    │
└───────────────────────────┬────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────┐
│ 4. Dead Space Collapse                                 │
│    Remove flex-grow from short configuration cards.    │
└───────────────────────────┬────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────┐
│ 5. State Synchronization                               │
│    Disable actions & align readiness with device state.│
└────────────────────────────────────────────────────────┘
```

1. **Prompt Echo Check:** Scan all string literals in the component. Delete any string that sounds like a prompt instruction, marketing tagline, or technical spec sheet.
2. **Clickability Test:** Inspect every bordered box or rounded pill. If it has no `onClick` / `clicked.connect` handler, remove the border and background fill and render it as plain muted metadata text.
3. **Icon & Emoji Purge:** Remove decorative emojis (`⚡`, `📁`, `🧹`) from production buttons and terminal output. Use a single consistent SVG/icon pack (e.g., Lucide, Phosphor, Material) at 16px–18px.
4. **Dead Space Collapse:** Check flex/grid containers. Ensure configuration cards do not have `flex-grow: 1` or forced heights that leave empty gaps between controls and summary footers.
5. **State Synchronization:** Verify that disconnected/idle states disable destructive actions and do not show contradictory "Ready" statuses in the console or cards.

---

## 4. Consolidated Design Tokens & Component Specifications

### 4.1 Token Architecture (Three-Layer Structure)
1. **Primitive Tokens:** Raw color palettes and geometry values (`gray-900: #0f172a`, `emerald-500: #10b981`, `sky-500: #0ea5e9`, `amber-500: #f59e0b`, `rose-500: #ef4444`).
2. **Semantic Tokens:** Purpose-bound variables:
   * Background: `--surface-app: #0b0f19`, `--surface-card: #111827`, `--surface-card-hover: #1f2937`
   * Borders: `--border-subtle: #1f2937`, `--border-active: #374151`
   * Text: `--text-primary: #f9fafb`, `--text-secondary: #9ca3af`, `--text-muted: #6b7280`
   * Accents: `--accent-blue: #38bdf8`, `--accent-green: #34d399`, `--accent-amber: #fbbf24`, `--accent-red: #f87171`
3. **Component Tokens:** Scoped elements (`--btn-primary-bg: #2563eb`, `--badge-dot-radius: 4px`, `--terminal-font-family: 'JetBrains Mono', monospace`).

### 4.2 Bento Grid Layout Specifications
* **Desktop Shell:** Fixed navigation sidebar (220px–240px) + fluid Bento content area with 16px (`1rem`) gap.
* **Card Geometry:** Border radius `0.75rem` (`rounded-xl`), background `rgb(17, 24, 39)` (`bg-gray-900/90`), border `1px solid rgb(31, 41, 55)` (`border-gray-800`), backdrop-blur for glassmorphism headers.
* **Typography Scale:**
   * Page Title: `1.25rem` (`text-xl`), font-semibold, tracking-tight.
   * Card Header: `0.875rem` (`text-sm`), font-semibold, uppercase tracking-wider, text-gray-400.
   * Primary Metric/Value: `1.125rem` (`text-lg`), font-bold, mono for numbers.
   * Body/Labels: `0.8125rem` (`text-xs` to `text-sm`), text-gray-300.

### 4.3 Production Component Checklist
* **Buttons:** Standard height 36px–40px, rounded-lg, focus-visible outline (2px accent).
* **Sliders:** Sleek 4px–6px track with accent-colored thumb and inline numerical readout.
* **Terminal Emulators (`xterm.js`):** JetBrains Mono / Fira Code font, dark surface (`#0d1117`), high-contrast ANSI green/cyan prompt, native scrollbars.
* **Status Indicators:** Glowing 6px pulse dot + single word state (`Online`, `Offline`, `Flashing`).

