#!/usr/bin/env python3
import email.utils
import os
import socket
import struct
import time
import urllib.request

STATE_FILE = "/etc/s8_saved_epoch"


def set_system_time(unix_ts: float, source: str):
    if unix_ts < 1767225600:  # sanity >= 2026-01-01
        return False
    os.system(f"date -u -s @{int(unix_ts)} >/dev/null 2>&1")
    with open(STATE_FILE, "w") as f:
        f.write(str(int(unix_ts)) + "\n")
    print(f"[s8-time-sync] Synced UTC time from {source}: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime(unix_ts))}")
    return True


def sync_sntp(host="pool.ntp.org") -> float:
    addr = socket.getaddrinfo(host, 123, socket.AF_INET, socket.SOCK_DGRAM)[0][4]
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(3.0)
    try:
        s.sendto(b"\x1b" + 47 * b"\0", addr)
        data, _ = s.recvfrom(1024)
        if len(data) >= 48:
            t = struct.unpack("!12I", data[:48])[10]
            return float(t - 2208988800)
    finally:
        s.close()
    return 0.0


def sync_http(url="http://archive.ubuntu.com") -> float:
    req = urllib.request.Request(url, method="HEAD")
    with urllib.request.urlopen(req, timeout=4.0) as resp:
        hdr = resp.headers.get("Date")
        if hdr:
            dt = email.utils.parsedate_to_datetime(hdr)
            return dt.timestamp()
    return 0.0


def main():
    if os.path.exists(STATE_FILE):
        try:
            saved = int(open(STATE_FILE).read().strip())
            if time.time() < saved:
                os.system(f"date -u -s @{saved} >/dev/null 2>&1")
        except Exception:
            pass

    for _ in range(20):
        for host in ("time.google.com", "pool.ntp.org", "time.cloudflare.com"):
            try:
                ts = sync_sntp(host)
                if set_system_time(ts, f"SNTP:{host}"):
                    return 0
            except Exception:
                pass
        for url in ("http://archive.ubuntu.com", "http://detectportal.firefox.com/success.txt"):
            try:
                ts = sync_http(url)
                if set_system_time(ts, f"HTTP:{url}"):
                    return 0
            except Exception:
                pass
        time.sleep(3)
    print("[s8-time-sync] Warning: could not reach NTP/HTTP yet.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

