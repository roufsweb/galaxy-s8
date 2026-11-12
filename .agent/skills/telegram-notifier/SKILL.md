---
name: telegram-notifier
description: Autonomous Bi-Directional Telegram dispatcher & reactive message listener for Antigravity with priority task preemption, conversational mobile summaries, and instant task switching.
---

# Telegram Notifier & Reactive Preemptive Bridge Skill (`telegram-notifier`)

This skill enables complete bi-directional interaction between Antigravity and the user's mobile Telegram (`@roufsantigravitybot` -> `<TELEGRAM_CHAT_ID>` configured in `.env`).

## 1. Capabilities

1. **Instant Outbound Notifications:** Dispatches real-time milestone alerts, build progress, and visual verification screenshots directly to Telegram.
2. **Bi-Directional Reactive Listener:** Sits in a zero-token, non-polling long-wait task (`scripts/telegram_listener.py`). When the user sends a message on Telegram from their phone:
   - Dispatches an **instant [ACK] receipt** in < 0.5s: `[ACK] Received: "<text>". Antigravity has been woken up...`
   - Immediately terminates with code 0, reactively waking up Antigravity.
   - Antigravity ingests the user's message, announces its plan (`[STAGE]`), executes commands/tests, and sends the completion status (`[PASS]`).
   - Automatically re-arms the listener to wait for the next instruction.
3. **Priority Task Preemption & Interactive Task Control (`/abort`, `1` / `2`, Inline Buttons):**
   - Automatically detects explicit interrupt keywords (`stop`, `abort`, `cancel`, `kill`, `switch to`, `instead`) and immediately dispatches `[ACK: PRIORITY INTERRUPT]` with `Action: PREEMPT_AND_SWITCH`.
   - **Interactive Options When Tasks Are Active:** When a long-running background task is registered in `scratch/active_tasks.json` and a new prompt arrives, `scripts/telegram_listener.py` holds the prompt in `scratch/pending_telegram_prompt.json` and sends inline Telegram buttons (`[1] Keep Running & Execute Prompt` / `[2] Pause/Kill Task & Switch`) while continuing to wait for a `callback_query` tap or text reply (`1` / `2`).
   - Based on the user's choice, wakes Antigravity with `Action: KEEP_RUNNING_AND_EXECUTE` (leave background worker active and handle the new prompt concurrently) or `Action: PREEMPT_AND_SWITCH` (terminate active worker via `manage_task(Action='kill')` and clear it from `scratch/active_tasks.json` before switching).
4. **Autonomous Background Progress Heartbeat Protocol:**
   - Long-running scripts (`scripts/download_steamos.py`, builds, extractions, flashes) MUST import `send_telegram_message` directly to dispatch `[STAGE]` start alerts, periodic `[PROGRESS]` heartbeats (every ~20% or 3 minutes), and `[PASS]` / `[FAIL]` completion notifications—even while Antigravity is idle.
   - Scripts should also register themselves via `telegram_listener.py --register-task` and clear on exit so Telegram prompts offer safe Keep/Switch options.
5. **Zero-Token Live Status Responder:**
   - Pure status/liveness pings (`status`, `/status`, `ping`, `/ping`, `alive`, `are you up`, `progress`, `update`, `hi`, `hello`) are answered directly by Python (`[LIVE STATUS | 0 AI TOKENS]`) with live `adb get-state` telemetry and active task names, **without waking Antigravity** (consuming 0 AI tokens). Send `full status` or any concrete instruction to wake the AI.
6. **Conversational Mobile Summary Protocol:**
   - Avoids dumping massive multi-page desktop markdown reports into the Telegram window.
   - Delivers crisp, natural, conversational executive summaries tailored for mobile reading (key highlights, hardware status, actions taken, and next steps).
7. **Zero-Token Idle Listener:** `scripts/telegram_listener.py` runs as a local OS Python subprocess; while waiting or handling background progress/status updates, the AI model is dormant and consumes zero tokens.

## 2. Credentials & Configuration
- Stored exclusively in `.env` at workspace root:
  - `TELEGRAM_BOT_TOKEN`
  - `TELEGRAM_ALLOWED_USER_IDS`
- **Rule 16 Compliance**: `.env` is permanently excluded via `.gitignore` and sanitized by `scripts/sanitize_repo.py`.

## 3. Mobile Telegram Conversational Format Standard

When sending completion updates to Telegram via `scripts/send_telegram.py`:
- **Keep it Conversational:** Write naturally as a direct engineering peer in Telegram chat.
- **Concise & Punchy (Mobile-Optimized):** Limit to 4–8 bullet points or short paragraphs. Never flood mobile with 200-line desktop tables or raw logs.
- **Key Telemetry First:** Hardware health, test verdict, and status.
- **Reference Deep Artifacts:** If full forensic logs or broad reports exist, reference their report name so the user can inspect them on their PC.
- **Strict Rule 22 Compliance:** Use bracketed ASCII tags (`[PASS]`, `[STAGE]`, `[INFO]`, `[ALERT]`). Zero unicode emojis.

## 4. Usage Instructions

### Outbound Notifications
```bash
python scripts/send_telegram.py "[STAGE] Custom kernel build reached 90%."
python scripts/send_telegram.py --photo "path/to/screenshot.png" "[VISUAL PROOF] Hardware Center UI Verified"
```

### Preemptive Telegram Listener & Task Registry
Launch listener in background:
```python
run_command(CommandLine="python scripts/telegram_listener.py", WaitMsBeforeAsync=500, toolSummary="Arm reactive Telegram listener")
```
Register / clear long-running background tasks so Telegram offers Keep-Running vs Pause/Switch inline buttons when a new prompt arrives:
```bash
python scripts/telegram_listener.py --register-task task-123 "SteamOS Rootfs Extract"
python scripts/telegram_listener.py --list-tasks
python scripts/telegram_listener.py --clear-task task-123   # or ALL
```

### Handling Priority Interrupts & Interactive Task Choices in Agent Execution
When `[TELEGRAM PRIORITY INTERRUPT RECEIVED]` or `[TELEGRAM TASK CONTROL DECISION]` (`Action: PREEMPT_AND_SWITCH`) arrives:
1. List running tasks via `manage_task(Action='list')`.
2. Terminate running worker tasks with `manage_task(Action='kill', TaskId=...)` and run `python scripts/telegram_listener.py --clear-task ALL`.
3. Dispatch `[STAGE] Stopped previous task. Immediately executing: <new instruction>` to Telegram.
4. Execute the new instruction.

When `[TELEGRAM TASK CONTROL DECISION]` arrives with `Action: KEEP_RUNNING_AND_EXECUTE`:
1. Leave running background tasks active (`manage_task(Action='list')` to verify).
2. Handle the user's new prompt concurrently without killing the active worker.

## 5. Status Indicator Standard (Rule 22 Compliance)
Strict ban on unicode emojis. Use clean bracketed ASCII indicators:
- `[ACK]` Instant receipt acknowledgment of normal user message
- `[ACK: SYSTEM LIVE]` Instant device/task status reply
- `[ACK: PRIORITY INTERRUPT]` Instant receipt acknowledgment of a stop/switch command
- `[ACK: KEEP RUNNING]` / `[ACK: PAUSE & SWITCH]` Confirmation of inline button or 1/2 choice
- `[OPTIONS]` Interactive task control prompt with inline Keep/Switch buttons
- `[STAGE]` Action plan / progress checkpoint / preemption notice
- `[PROGRESS]` Periodic background worker heartbeat
- `[PASS]` / `[OK]` Successful completion
- `[VISUAL PROOF]` Screenshot artifact
- `[ALERT]` / `[WARN]` Warning / diagnostic notice
- `[FAIL]` / `[ERR]` Error state

## 6. Zero-Token & Minimal-Token Rule (Mandatory)
1. **No Extra Tokens / No External LLM API Keys:** Telegram listener and notification scripts MUST NEVER request or call external LLM APIs (`GEMINI_API_KEY`, etc.). All background listening, ACKs, status checks, progress heartbeats, and inline button prompts execute in pure local Python with **0 AI tokens**.
2. **Do Not Wake AI for Routine Checks:** Pure status/health pings (`ping`, `status`, `/status`, `alive`, `are you up`, `progress`, `update`, `hello`) and interactive Keep/Switch prompt delivery (`[OPTIONS]`) MUST be handled directly by `scripts/telegram_listener.py` while keeping the listener running (`continue`). Only wake the active Antigravity session when concrete execution, interrupts, task choices, or deep analysis (`full status`) are required.
3. **Zero-Token Background Updates:** Long-running workers push `[STAGE]`, `[PROGRESS]`, and `[PASS]` messages directly via `scripts/send_telegram.py` without invoking the AI model.
4. **Minimal-Token AI Turns:** When woken up, keep reasoning tight, execute the action, send a concise 4-8 line summary to Telegram, and immediately re-arm `scripts/telegram_listener.py` so the session returns to 0-token idle sleep.
