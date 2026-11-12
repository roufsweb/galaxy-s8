---
name: production-grade-vibe-coding
description: Elevate rapid AI-assisted coding ("vibe coding") into reliable, production-grade software engineering. Enforces automated verification, continuous integration, 4-layer testing (unit, integration, agentic E2E human-flow, performance), security guardrails, and real-human desktop app validation.
---

# Production-Grade Vibe Coding: Engineering Discipline for AI-Accelerated Software

> **Bridge the gap between rapid AI prototyping ("vibe coding") and disciplined, production-grade systems engineering.**
> This skill enforces automated verification, continuous integration, 4-layer test pyramids, security guardrails, and real-human simulation so you can ship AI-accelerated code at peak velocity with 100% operational confidence.

---

## 1. When to Use This Skill

Activate this skill whenever:
* Converting a fast prototype, UI mock, or "vibe-coded" feature into production-ready software.
* Building or auditing a CI/CD pipeline for an AI-accelerated desktop, systems, or web project.
* Authoring comprehensive multi-layer test coverage (Unit, Integration, Agentic E2E, and Performance).
* Simulating real-human user interaction on desktop and web interfaces using automated browser agents.
* Reviewing AI-generated code for hidden architectural debt, hallucinated APIs, security vulnerabilities, or tautological tests.

---

## 2. Core Engineering Workflow

```
   ┌────────────────────────────────────────────────────────┐
   │ 1. Establish CI/CD Foundation & Pre-Commit Gating     │
   │    • Linting & Strict Typing • Secret Sanitization    │
   └───────────────────────────┬────────────────────────────┘
                               │
   ┌───────────────────────────▼────────────────────────────┐
   │ 2. Enforce 4-Layer Test Pyramid                        │
   │    • Layer 1: Unit Tests (100% Logic Coverage)         │
   │    • Layer 2: Integration Tests (API & State)          │
   │    • Layer 3: Agentic E2E Human-Flow Tests             │
   │    • Layer 4: Aggressive Performance & Latency Budgets │
   └───────────────────────────┬────────────────────────────┘
                               │
   ┌───────────────────────────▼────────────────────────────┐
   │ 3. Close Gaps Typical of AI-Generated Code             │
   │    • Tautological Test Guards • Anti-Flaky Selectors   │
   │    • Reversible Rollbacks • Structured Telemetry       │
   └───────────────────────────┬────────────────────────────┘
                               │
   ┌───────────────────────────▼────────────────────────────┐
   │ 4. Autonomous Validation & Feedback Loop               │
   │    • Run ci_cd_validator.py • Block Merges on Failure  │
   └────────────────────────────────────────────────────────┘
```

---

## 3. The 4-Layer Testing Pyramid

Because AI makes authoring test suites fast and accessible, never settle for shallow testing. Enforce all four layers:

### Layer 1: Unit Tests (100% Logic & Boundary Coverage)
* **Scope:** Test every discrete function, class, and algorithm in strict isolation.
* **Requirements:**
  * Test expected inputs, boundary values, zero/empty states, and explicitly malformed inputs.
  * Mock external I/O (filesystems, network sockets, subshell processes like `adb`).
  * Verify explicit exception handling and graceful error propagation.

### Layer 2: Integration Tests (Contract & API Validation)
* **Scope:** Test communication between multiple components (e.g. REST API handler $\leftrightarrow$ domain manager $\leftrightarrow$ subprocess client).
* **Requirements:**
  * Spin up live test servers on dynamic/ephemeral ports.
  * Send genuine HTTP requests (`GET`, `POST`, query parameters, payloads) and validate response status codes, JSON schemas, headers, and CORS policies.
  * Validate contractual state transitions (e.g., toggling flashlight changes telemetry state).

### Layer 3: Agentic End-to-End (E2E) Real-Human Simulation
* **Scope:** Simulate an actual human engineer operating the application.
* **Tooling:** Automated browser drivers (Playwright / Puppeteer / Chrome DevTools).
* **Requirements:**
  * Launch the real desktop application window or web viewport (`1280x800` desktop resolution).
  * Real Human Interactions: Click navigation pills, type commands into interactive terminals, toggle switches, select dropdowns, drag sliders.
  * Dynamic DOM Assertions: Assert that clicking a tab actually changes visibility, mutates styling classes, updates text elements, and triggers background requests.
  * Visual Verification: Capture screenshot artifacts at key checkpoints (`artifacts/*.png`) to visually inspect styling, layouts, and modals.
  * Resilient Selectors: Strictly use accessible roles (`getByRole`, `getByLabelText`) or explicit `data-testid` attributes. Never use brittle generated CSS selectors (`div > div:nth-child(3)`).

### Layer 4: Aggressive Performance & Load Budgets
* **Scope:** Ensure velocity does not sacrifice speed, responsiveness, or resource efficiency.
* **Requirements:**
  * **API Latency Budget:** p95 responses under **100ms** for local telemetry endpoints (`/api/status`).
  * **UI Interaction Budget:** View transitions and modal openings under **50ms**.
  * **Memory Stability:** Zero memory leaks over continuous polling loops (e.g., 60 cycles over 30 seconds).

---

## 4. Closing the Gaps of AI-Generated Code

AI code assistants optimize for immediate superficial functionality ("making it look like it works"). The following rigorous checks must be applied:

| AI Vulnerability / Gap | Engineering Failure Mode | Mandatory Defense |
| :--- | :--- | :--- |
| **Tautological Tests** | Tests that assert `1 == 1` or mock out the code under test, always passing even if buggy. | Introduce intentional mutant faults into the code and verify the test fails with a meaningful error message. |
| **Hallucinated APIs** | Calling non-existent methods or assuming third-party libraries have methods they lack. | Enforce strict static analysis (`mypy --strict`, TypeScript `tsc --noEmit`) and run full build checks. |
| **Credential / Secret Leaks** | Hardcoding tokens, API keys, or private bot IDs directly in source files. | Automated pre-commit scanning with `sanitize_repo.py` blocking any commits containing sensitive patterns. |
| **Flaky UI Selectors** | Tests breaking whenever a Tailwind class or div layout is slightly adjusted. | Mandate `data-testid="..."` attributes on all interactive controls (buttons, inputs, status pills). |
| **Silent Swallowed Errors** | Catching `except Exception: pass` and hiding real hardware or network failures. | Enforce structured logging with correlation IDs and return explicit JSON error payloads (`{"error": "...", "code": 500}`). |

---

## 5. Desktop Application Real-Human Testing Guide

To test desktop applications (like `S8 Imager`) like a real human, leverage:

### 1. Python Playwright Test Engine
```python
from playwright.sync_api import sync_playwright

def test_human_desktop_journey():
    with sync_playwright() as p:
        # Launch Chromium or MS Edge with exact desktop window sizing
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()
        
        # 1. Load Desktop Web Dashboard
        page.goto("http://localhost:8000/")
        page.wait_for_selector("[data-testid='app-sidebar']")
        
        # 2. Simulate Human Navigation
        page.click("[data-testid='nav-btn-dashboard']")
        assert page.is_visible("[data-testid='page-dashboard']")
        
        # 3. Simulate Terminal Interaction
        page.click("[data-testid='nav-btn-terminal']")
        page.fill("[data-testid='terminal-input']", "uname -a")
        page.press("[data-testid='terminal-input']", "Enter")
        page.wait_for_selector("[data-testid='terminal-output']")
        
        # 4. Capture Visual Artifact
        page.screenshot(path="artifacts/desktop_human_test.png")
        browser.close()
```

### 2. Available Antigravity & AI Permissions
* **Powershell / Bash Execution (`run_command`):** Allows launching headless or headful Playwright processes, test runners, and dev servers.
* **Chrome DevTools Plugin (`antigravity-plugins-official/plugin/chrome-devtools-plugin`):** Connects to running Chrome/Edge instances via CDP for real-time DOM inspection and performance profiling.
* **REA MCP Reverse-Engineering & Native UI Suite:**
  * `observe_web_execution`: Analyzes web application events and network traffic.
  * `capture_browser_scenario`: Captures complete interaction traces and screenshots.
  * `inspect_electron_page`: Directly inspects DOM trees inside running desktop application shells.

---

## 6. Pre-Flight Verification Checklist

Before approving or releasing any desktop feature:

- [ ] **CI/CD Validation Passes:** Run `python scripts/ci_cd_validator.py` with 100% green exit code.
- [ ] **Zero Tautological Tests:** All unit and integration assertions strictly verify actual functional logic.
- [ ] **All 4 Layers Green:** Unit (100%), Integration (APIs), E2E (Playwright human flow), Performance (latency budgets met).
- [ ] **Zero Hardcoded Secrets:** `python scripts/sanitize_repo.py` passes with zero credential alerts.
- [ ] **Visual Proof Captured:** E2E human test generated clean screenshot artifacts in the designated directory.
- [ ] **Rollback Safety:** Verified that turning off feature flags or issuing a single git revert cleanly restores stability.

