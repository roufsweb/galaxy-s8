#!/usr/bin/env python3
"""
deploy_steamos.py — Streams SteamOS p2 (root 14.24 GiB) & p3 (home 3.41 GiB) directly
over USB ADB TCP forwarding into S8 /data/linux/ with zero-token Telegram progress
heartbeats, mounts /mnt/steamos cleanly alongside Kali, starts SteamOS TigerVNC :2
(port 5902), and executes initial SteamOS chroot verification tests.
"""

import json
import socket
import sys
import time
import subprocess
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE))

from scripts.send_telegram import send_telegram_message
from scripts.telegram_listener import register_active_task, clear_active_task

TASK_ID = "steamos-deploy"
TASK_NAME = "SteamOS Stream Push & Initial S8 Chroot Test"
RECV_PORT = 19001

SRC_IMG = WORKSPACE / "distros" / "steamos" / "extracted" / "steamos-arm-port-sm8550-v1.4.img"
RECV_LOCAL = WORKSPACE / "scratch" / "s8_recv.py"
RECV_REMOTE = "/data/linux/s8_recv.py"
INIT_LOCAL = WORKSPACE / "scratch" / "init_steamos_s8.sh"
INIT_REMOTE = "/data/linux/init_steamos_s8.sh"

PARTS = [
    {
        "name": "steamos_root.img",
        "offset": 537919488,
        "size": 15289286656,
        "chroot_path": "/mnt/linux_data/steamos_root.img",
        "remote": "/data/linux/steamos_root.img",
    },
    {
        "name": "steamos_home.img",
        "offset": 15827206144,
        "size": 3665821696,
        "chroot_path": "/mnt/linux_data/steamos_home.img",
        "remote": "/data/linux/steamos_home.img",
    },
]


def read_json_line(sock: socket.socket) -> dict:
    buf = bytearray()
    while True:
        b = sock.recv(1)
        if not b or b == b"\n":
            return json.loads(buf.decode("utf-8")) if buf else {}
        buf.extend(b)


def start_receiver_on_s8():
    subprocess.run(["adb", "push", str(RECV_LOCAL), RECV_REMOTE], check=True)
    launcher = WORKSPACE / "scratch" / "start_recv_s8.sh"
    launcher.write_text(
        "#!/sbin/sh\n"
        "pkill -f 's8_recv.py 1900[1]' 2>/dev/null || true\n"
        "mkdir -p /mnt/ubuntu/mnt/linux_data\n"
        "grep -q '/mnt/ubuntu/mnt/linux_data ' /proc/mounts || mount -o bind /data/linux /mnt/ubuntu/mnt/linux_data\n"
        f"chroot /mnt/ubuntu /usr/bin/python3 /mnt/linux_data/s8_recv.py {RECV_PORT} </dev/null >/data/linux/s8_recv.log 2>&1 &\n"
        "sleep 1\n",
        encoding="utf-8",
        newline="\n",
    )
    subprocess.run(["adb", "push", str(launcher), "/data/linux/start_recv_s8.sh"], check=True)
    subprocess.run(["adb", "shell", "sh /data/linux/start_recv_s8.sh"], check=True)
    subprocess.run(["adb", "forward", f"tcp:{RECV_PORT}", f"tcp:{RECV_PORT}"], check=True)
    time.sleep(1.0)


def stop_receiver_on_s8():
    try:
        with socket.create_connection(("127.0.0.1", RECV_PORT), timeout=5) as s:
            s.sendall(b'{"cmd":"quit"}\n')
            read_json_line(s)
    except Exception:
        pass


def stream_all_parts():
    total_bytes = sum(p["size"] for p in PARTS)
    bytes_done_before = 0
    start_ts = time.time()
    last_bucket = -1
    last_notify_ts = start_ts

    for part in PARTS:
        print(f"[STAGE] Streaming {part['name']} ({part['size'] / (1024**3):.2f} GiB) over USB TCP...")
        sys.stdout.flush()

        with socket.create_connection(("127.0.0.1", RECV_PORT), timeout=30) as sock:
            hdr = json.dumps({"cmd": "put", "path": part["chroot_path"], "size": part["size"]}).encode("utf-8") + b"\n"
            sock.sendall(hdr)
            resp = read_json_line(sock)
            resume_from = int(resp.get("resume_from", 0))
            if resume_from > 0:
                print(f"[*] Resuming {part['name']} from {resume_from / (1024**3):.2f} GiB")

            sent_this_part = resume_from
            if resume_from < part["size"]:
                chunk_size = 2 * 1024 * 1024
                with open(SRC_IMG, "rb") as fin:
                    fin.seek(part["offset"] + resume_from)
                    remaining = part["size"] - resume_from
                    while remaining > 0:
                        data = fin.read(min(chunk_size, remaining))
                        if not data:
                            raise RuntimeError(f"Unexpected EOF reading {part['name']}")
                        sock.sendall(data)
                        n = len(data)
                        remaining -= n
                        sent_this_part += n

                        cur_total = bytes_done_before + sent_this_part
                        pct = min(100.0, (cur_total / total_bytes) * 100.0)
                        bucket = int(pct // 20)
                        now = time.time()
                        if (bucket > last_bucket and pct >= 5.0) or (now - last_notify_ts >= 120):
                            last_bucket = max(last_bucket, bucket)
                            last_notify_ts = now
                            speed_mb = (cur_total / (1024 * 1024)) / max(now - start_ts, 0.1)
                            msg = (
                                f"[PROGRESS] Streaming SteamOS to Galaxy S8\n"
                                f"- Progress: {cur_total / (1024**3):.2f} / {total_bytes / (1024**3):.2f} GiB ({pct:.1f}%)\n"
                                f"- Avg Speed: {speed_mb:.1f} MB/s"
                            )
                            print(msg)
                            sys.stdout.flush()
                            send_telegram_message(msg, parse_mode=None)

            sock.settimeout(60)
            ack = read_json_line(sock)
            if not ack.get("ok") or int(ack.get("size", 0)) != part["size"]:
                raise RuntimeError(f"Receiver verification failed for {part['name']}: {ack}")
            print(f"[OK] Verified {part['name']} on S8 ({ack['size']} bytes)")

        bytes_done_before += part["size"]


def main():
    if not SRC_IMG.exists():
        print(f"[FAIL] Missing source image: {SRC_IMG}", file=sys.stderr)
        sys.exit(1)

    register_active_task(TASK_ID, TASK_NAME)
    t0 = time.time()
    try:
        send_telegram_message(
            "[STAGE] Streaming SteamOS Partitions to Galaxy S8\n"
            "- Source: p2 root (14.24 GiB) + p3 home (3.41 GiB) = 17.65 GiB\n"
            "- Target: /data/linux/steamos_root.img + steamos_home.img (Kali untouched)\n"
            "- Sending live zero-token progress updates every ~20% or 2 min.",
            parse_mode=None,
        )

        start_receiver_on_s8()
        try:
            stream_all_parts()
        finally:
            stop_receiver_on_s8()

        print("[STAGE] Running SteamOS mount, TigerVNC :2 (:5902), and chroot tests...")
        sys.stdout.flush()
        subprocess.run(["adb", "push", str(INIT_LOCAL), INIT_REMOTE], check=True)
        res = subprocess.run(
            ["adb", "shell", f"chmod +x {INIT_REMOTE} && sh {INIT_REMOTE}"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        print(res.stdout)
        if res.stderr:
            print(res.stderr, file=sys.stderr)
        if res.returncode != 0:
            raise RuntimeError(f"init_steamos_s8.sh exited {res.returncode}")

        elapsed = time.time() - t0
        send_telegram_message(
            f"[PASS] SteamOS Deployed & Initial Chroot Verified ({elapsed:.0f}s)\n"
            f"- Mounted at /mnt/steamos (+ /home)\n"
            f"- SteamOS Xtigervnc :2 armed on port 5902 (1280x720)\n"
            f"- Waking Antigravity to launch Plasma/Steam & spin up your VNC viewer!",
            parse_mode=None,
        )
    except Exception as exc:
        err = f"[FAIL] SteamOS deployment error: {exc}"
        print(err, file=sys.stderr)
        send_telegram_message(err, parse_mode=None)
        sys.exit(1)
    finally:
        clear_active_task(TASK_ID)


if __name__ == "__main__":
    main()
