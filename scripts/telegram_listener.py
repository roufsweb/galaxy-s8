#!/usr/bin/env python3
"""
telegram_listener.py — Reactive Bi-Directional Telegram Listener with Priority Preemption.
Listens for incoming messages from the authorized Telegram user.
Detects priority interrupts (e.g. "stop", "abort", "cancel", "switch to", "halt").
When an interrupt is detected:
  1. Writes scratch/telegram_interrupt.json
  2. Dispatches an immediate high-priority [ACK] receipt indicating task termination
  3. Outputs structured [PRIORITY INTERRUPT] block to stdout
  4. Exits with code 0 to immediately wake up Antigravity to kill active workers and switch tasks.
"""

import os
import sys
import json
import time
import re
import urllib.request
import urllib.parse
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE))

try:
    from scripts.send_telegram import send_telegram_message
except ImportError:
    send_telegram_message = None

INTERRUPT_KEYWORDS = [
    r"\bstop\b", r"\babort\b", r"\bcancel\b", r"\bkill\b", r"\bhalt\b",
    r"\bterminate\b", r"\bswitch to\b", r"\binstead\b", r"\bdon't do that\b",
    r"\bwait stop\b", r"\bhold on\b"
]

def load_env():
    env_file = WORKSPACE / ".env"
    env_vars = {}
    if env_file.exists():
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    env_vars[k.strip()] = v.strip().strip('"').strip("'")
    return env_vars

def get_state_file():
    scratch_dir = WORKSPACE / "scratch"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    return scratch_dir / "telegram_listener_state.json"

def get_interrupt_file():
    scratch_dir = WORKSPACE / "scratch"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    return scratch_dir / "telegram_interrupt.json"

def get_active_tasks_file():
    scratch_dir = WORKSPACE / "scratch"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    return scratch_dir / "active_tasks.json"

def get_pending_prompt_file():
    scratch_dir = WORKSPACE / "scratch"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    return scratch_dir / "pending_telegram_prompt.json"

def get_active_tasks():
    path = get_active_tasks_file()
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except Exception:
            pass
    return []

def register_active_task(task_id: str, name: str):
    tasks = [t for t in get_active_tasks() if t.get("id") != task_id]
    tasks.append({"id": task_id, "name": name, "started_at": time.time()})
    with open(get_active_tasks_file(), "w", encoding="utf-8") as f:
        json.dump(tasks, f, indent=2)

def clear_active_task(task_id: str):
    path = get_active_tasks_file()
    if task_id == "ALL":
        if path.exists():
            path.unlink()
        return
    tasks = [t for t in get_active_tasks() if t.get("id") != task_id]
    if tasks:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(tasks, f, indent=2)
    elif path.exists():
        path.unlink()

def load_pending_prompt():
    path = get_pending_prompt_file()
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return None

def save_pending_prompt(data: dict):
    with open(get_pending_prompt_file(), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def clear_pending_prompt():
    path = get_pending_prompt_file()
    if path.exists():
        try:
            path.unlink()
        except Exception:
            pass

def write_interrupt_file(text: str, sender_name: str, from_id: int):
    interrupt_data = {
        "timestamp": time.time(),
        "action": "INTERRUPT_AND_SWITCH",
        "instruction": text,
        "sender": sender_name,
        "sender_id": from_id,
    }
    try:
        with open(get_interrupt_file(), "w", encoding="utf-8") as f:
            json.dump(interrupt_data, f, indent=2)
    except Exception as e:
        print(f"[!] Warning: Failed to write interrupt file: {e}", file=sys.stderr)

def _post_bot_api(token: str, method: str, payload: dict):
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/{method}",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            resp.read()
    except Exception as e:
        print(f"[!] Warning: {method} failed: {e}", file=sys.stderr)

def answer_callback_query(token: str, callback_query_id: str, text: str = ""):
    if not callback_query_id:
        return
    _post_bot_api(token, "answerCallbackQuery", {"callback_query_id": callback_query_id, "text": text})

def mark_callback_message_resolved(token: str, cb: dict, status_label: str):
    """Remove inline buttons and stamp confirmation onto the clicked option card."""
    msg = cb.get("message") or {}
    chat_id = (msg.get("chat") or {}).get("id")
    message_id = msg.get("message_id")
    if not chat_id or not message_id:
        return
    orig_text = msg.get("text") or "Task Control Options"
    if "[CONFIRMED]" not in orig_text:
        _post_bot_api(token, "editMessageText", {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": f"{orig_text}\n\n[CONFIRMED] {status_label}",
            "reply_markup": {"inline_keyboard": []},
        })
    else:
        _post_bot_api(token, "editMessageReplyMarkup", {
            "chat_id": chat_id,
            "message_id": message_id,
            "reply_markup": {"inline_keyboard": []},
        })

def build_task_control_markup() -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": "[1] Keep Running & Execute Prompt", "callback_data": "task_continue"},
                {"text": "[2] Pause/Kill Task & Switch", "callback_data": "task_preempt"},
            ]
        ]
    }

def resolve_pending_choice(text: str):
    """Map manual text replies (1/2) to interactive task control actions."""
    norm = text.strip().lower()
    if norm in {"1", "keep", "continue", "keep running", "option 1"}:
        return "KEEP_RUNNING_AND_EXECUTE"
    if norm in {"2", "pause", "kill", "stop task", "switch", "abort task", "option 2"}:
        return "PREEMPT_AND_SWITCH"
    return None

def emit_wake_event(header: str, action: str, text: str, sender_name: str, username: str, from_id: int, date_str: str, active_tasks=None):
    print("\n============================================================")
    print(header)
    print(f"Sender: {sender_name} (@{username}) [ID: {from_id}]")
    print(f"Time:   {date_str}")
    print(f"Action: {action}")
    if active_tasks:
        names = ", ".join(t.get("name", t.get("id", "task")) for t in active_tasks)
        print(f"Active: {names}")
    print("------------------------------------------------------------")
    print(text)
    print("============================================================\n")
    sys.stdout.flush()
    sys.exit(0)

def load_last_offset():
    state_file = get_state_file()
    if state_file.exists():
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("offset", 0)
        except Exception:
            pass
    return 0

def save_last_offset(offset):
    state_file = get_state_file()
    try:
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump({"offset": offset, "updated_at": time.time()}, f)
    except Exception:
        pass

def get_quick_telemetry() -> str:
    import subprocess
    try:
        res = subprocess.run(["adb", "get-state"], capture_output=True, text=True, timeout=2)
        dev_state = res.stdout.strip() or "OFFLINE"
    except Exception:
        dev_state = "UNKNOWN"
    return dev_state

def is_quick_ping(text: str) -> bool:
    """Match pure health/status pings answered directly in Python using 0 AI tokens."""
    norm = text.strip().lower().rstrip("?!.")
    return norm in {
        "ping", "/ping", "alive", "are you up", "are you alive",
        "status", "/status", "progress", "update", "updates",
        "any update", "any updates", "check status", "hello", "hi", "/start"
    }

is_status_query = is_quick_ping

def check_is_interrupt(text: str) -> bool:
    lower_text = text.lower()
    for kw in INTERRUPT_KEYWORDS:
        if re.search(kw, lower_text):
            return True
    return False

def handle_task_decision(action: str, pending: dict, from_id: int, sender_name: str, username: str, auto_ack: bool):
    """Finalize an interactive Keep-Running vs Pause-Switch choice and wake Antigravity."""
    instruction = pending.get("instruction", "")
    active_tasks = pending.get("active_tasks", [])
    date_str = pending.get("date_str") or time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())

    if action == "PREEMPT_AND_SWITCH":
        write_interrupt_file(instruction, sender_name, from_id)
        ack_msg = f"[ACK: PAUSE & SWITCH] Confirmed! Pausing active background task(s) and switching to:\n\"{instruction}\""
    else:
        ack_msg = f"[ACK: KEEP RUNNING] Confirmed! Keeping background task(s) running and executing:\n\"{instruction}\""

    if auto_ack and send_telegram_message:
        try:
            send_telegram_message(ack_msg, chat_id=str(from_id), parse_mode="Markdown")
        except Exception as ack_err:
            print(f"[!] Warning: Auto-ack failed: {ack_err}", file=sys.stderr)

    clear_pending_prompt()
    emit_wake_event(
        "[TELEGRAM TASK CONTROL DECISION]",
        action,
        instruction,
        sender_name,
        username,
        from_id,
        date_str,
        active_tasks=active_tasks,
    )

def listen_for_message(timeout_sec=25, max_wait_sec=None, auto_ack=True):
    env_vars = load_env()
    token = os.environ.get("TELEGRAM_BOT_TOKEN") or env_vars.get("TELEGRAM_BOT_TOKEN")
    allowed_id_str = os.environ.get("TELEGRAM_ALLOWED_USER_IDS") or env_vars.get("TELEGRAM_ALLOWED_USER_IDS") or ""
    
    allowed_ids = set()
    for uid in allowed_id_str.split(","):
        uid = uid.strip()
        if uid.isdigit():
            allowed_ids.add(int(uid))

    if not token:
        print("[!] ERROR: TELEGRAM_BOT_TOKEN not found in .env or environment.", file=sys.stderr)
        sys.exit(1)

    offset = load_last_offset()
    start_time = time.time()

    # If offset is 0, fetch current updates to initialize offset to latest
    if offset == 0:
        init_url = f"https://api.telegram.org/bot{token}/getUpdates?offset=-1"
        try:
            with urllib.request.urlopen(init_url, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                results = data.get("result", [])
                if results:
                    offset = results[-1]["update_id"] + 1
                    save_last_offset(offset)
        except Exception as e:
            print(f"[!] Warning: Initializing offset failed: {e}", file=sys.stderr)

    print(f"[*] Telegram listener armed. Waiting for user message (offset={offset})...")
    sys.stdout.flush()

    while True:
        elapsed = time.time() - start_time
        if max_wait_sec:
            remaining = max_wait_sec - elapsed
            if remaining <= 0:
                print("[*] Listener timeout reached without new message.")
                sys.exit(0)
            current_timeout = max(1, min(timeout_sec, int(remaining)))
        else:
            current_timeout = timeout_sec

        params = urllib.parse.urlencode({
            "offset": offset,
            "timeout": current_timeout,
            "allowed_updates": json.dumps(["message", "edited_message", "callback_query"]),
        })
        url = f"https://api.telegram.org/bot{token}/getUpdates?{params}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "AntigravityTelegramListener/1.0"})
            with urllib.request.urlopen(req, timeout=current_timeout + 5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if not data.get("ok"):
                    time.sleep(2)
                    continue

                updates = data.get("result", [])
                for u in updates:
                    u_id = u.get("update_id", 0)
                    if u_id >= offset:
                        offset = u_id + 1
                        save_last_offset(offset)

                    cb = u.get("callback_query")
                    if cb:
                        from_user = cb.get("from", {})
                        from_id = from_user.get("id")
                        if allowed_ids and from_id not in allowed_ids:
                            print(f"[!] Ignoring callback from unauthorized user ID: {from_id}")
                            continue
                        cb_id = cb.get("id", "")
                        cb_data = cb.get("data", "")
                        action = "PREEMPT_AND_SWITCH" if cb_data == "task_preempt" else "KEEP_RUNNING_AND_EXECUTE"
                        label = "Pause Task & Switch" if action == "PREEMPT_AND_SWITCH" else "Keep Running Task"
                        pending = load_pending_prompt()
                        if not pending:
                            answer_callback_query(token, cb_id, f"{label}: Prompt already handled or expired.")
                            mark_callback_message_resolved(token, cb, f"Expired / Already Handled ({label})")
                            if send_telegram_message:
                                send_telegram_message(
                                    f"[INFO] You tapped '{label}', but no active prompt is waiting right now. (0 AI tokens used)",
                                    chat_id=str(from_id),
                                    parse_mode="Markdown",
                                )
                            continue
                        answer_callback_query(token, cb_id, f"Confirmed: {label}")
                        mark_callback_message_resolved(token, cb, f"Selected: {label}")
                        sender_name = from_user.get("first_name", "User")
                        username = from_user.get("username", "")
                        handle_task_decision(action, pending, from_id, sender_name, username, auto_ack)
                        continue

                    msg = u.get("message") or u.get("edited_message")
                    if not msg:
                        continue

                    from_user = msg.get("from", {})
                    from_id = from_user.get("id")
                    
                    # Verify user ID if restricted
                    if allowed_ids and from_id not in allowed_ids:
                        print(f"[!] Ignoring message from unauthorized user ID: {from_id}")
                        continue

                    sender_name = from_user.get("first_name", "User")
                    username = from_user.get("username", "")
                    text = (msg.get("text") or "").strip()
                    if not text:
                        continue
                    date_ts = msg.get("date", int(time.time()))
                    date_str = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(date_ts))

                    pending = load_pending_prompt()
                    if pending:
                        choice_action = resolve_pending_choice(text)
                        if choice_action:
                            handle_task_decision(choice_action, pending, from_id, sender_name, username, auto_ack)
                            continue
                        clear_pending_prompt()

                    is_interrupt = check_is_interrupt(text)
                    if is_interrupt:
                        write_interrupt_file(text, sender_name, from_id)
                        if auto_ack and send_telegram_message:
                            try:
                                ack_msg = f"[ACK: PRIORITY INTERRUPT] Received: \"{text}\"\n\nStopping active task immediately and switching to your new instruction..."
                                send_telegram_message(ack_msg, chat_id=str(from_id), parse_mode="Markdown")
                            except Exception as ack_err:
                                print(f"[!] Warning: Auto-ack failed: {ack_err}", file=sys.stderr)
                        emit_wake_event("[TELEGRAM PRIORITY INTERRUPT RECEIVED]", "PREEMPT_AND_SWITCH", text, sender_name, username, from_id, date_str)

                    active_tasks = get_active_tasks()
                    if is_quick_ping(text):
                        if send_telegram_message:
                            try:
                                dev_state = get_quick_telemetry()
                                tasks_str = ", ".join(t.get("name", t.get("id", "task")) for t in active_tasks) if active_tasks else "None (Idle)"
                                live_msg = (
                                    f"[LIVE STATUS | 0 AI TOKENS]\n"
                                    f"- ADB Device: {dev_state}\n"
                                    f"- Active Task(s): {tasks_str}\n"
                                    f"- Listener: ARMED\n"
                                    f"(Send 'full status' or any instruction to wake AI)"
                                )
                                send_telegram_message(live_msg, chat_id=str(from_id), parse_mode="Markdown")
                            except Exception as ack_err:
                                print(f"[!] Warning: Quick status reply failed: {ack_err}", file=sys.stderr)
                        print(f"[0-TOKEN STATUS] Replied directly to '{text}' without waking AI.")
                        sys.stdout.flush()
                        continue

                    if active_tasks:
                        save_pending_prompt({
                            "timestamp": time.time(),
                            "instruction": text,
                            "sender": sender_name,
                            "username": username,
                            "sender_id": from_id,
                            "date_str": date_str,
                            "active_tasks": active_tasks,
                        })
                        if send_telegram_message:
                            task_desc = ", ".join(t.get("name", t.get("id", "task")) for t in active_tasks)
                            opt_msg = (
                                f"[OPTIONS] Active background task running: {task_desc}\n\n"
                                f"New prompt: \"{text}\"\n\n"
                                f"Choose how to proceed (tap a button or reply 1 / 2):\n"
                                f"1 - Keep running background task and execute this prompt\n"
                                f"2 - Pause/kill active task and switch exclusively"
                            )
                            send_telegram_message(
                                opt_msg,
                                chat_id=str(from_id),
                                parse_mode="Markdown",
                                reply_markup=build_task_control_markup(),
                            )
                        print(f"[*] Sent interactive Keep/Switch options for prompt: {text}")
                        sys.stdout.flush()
                        continue

                    if auto_ack and send_telegram_message:
                        try:
                            ack_msg = f"[ACK] Received: \"{text}\"\n\nAntigravity has been woken up and is actively executing your request..."
                            send_telegram_message(ack_msg, chat_id=str(from_id), parse_mode="Markdown")
                        except Exception as ack_err:
                            print(f"[!] Warning: Auto-ack failed: {ack_err}", file=sys.stderr)

                    emit_wake_event("[TELEGRAM USER MESSAGE RECEIVED]", "NORMAL_TASK", text, sender_name, username, from_id, date_str)

        except urllib.error.URLError:
            time.sleep(2)
        except Exception:
            time.sleep(2)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Reactive Bi-Directional Telegram Listener")
    parser.add_argument("max_wait", nargs="?", type=int, default=None, help="Optional max listen duration in seconds")
    parser.add_argument("--register-task", nargs=2, metavar=("TASK_ID", "NAME"), help="Register an active background task")
    parser.add_argument("--clear-task", metavar="TASK_ID", help="Clear a task ID (or ALL)")
    parser.add_argument("--list-tasks", action="store_true", help="Print registered active tasks")
    args = parser.parse_args()

    if args.register_task:
        register_active_task(args.register_task[0], args.register_task[1])
        print(f"[+] Registered active task: {args.register_task[0]} ({args.register_task[1]})")
        sys.exit(0)
    if args.clear_task:
        clear_active_task(args.clear_task)
        print(f"[+] Cleared active task: {args.clear_task}")
        sys.exit(0)
    if args.list_tasks:
        print(json.dumps(get_active_tasks(), indent=2))
        sys.exit(0)

    listen_for_message(timeout_sec=25, max_wait_sec=args.max_wait, auto_ack=True)
