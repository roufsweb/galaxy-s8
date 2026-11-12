#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import re
import sys
import json
import time
import shutil
import socket
import random
import subprocess


def ensure_wifi_firmware():
    """Populate Broadcom BCM4361 module paths before scanning or associating."""
    params_dir = "/sys/module/dhd/parameters"
    mapping = {
        "firmware_path": "/vendor/etc/wifi/bcmdhd_sta.bin",
        "nvram_path": "/vendor/etc/wifi/nvram.txt",
        "clm_path": "/vendor/etc/wifi/bcmdhd_clm.blob",
    }
    if os.path.isdir(params_dir):
        for name, val in mapping.items():
            p = os.path.join(params_dir, name)
            try:
                with open(p, "r") as f:
                    cur = f.read().strip()
            except Exception:
                cur = ""
            if cur != val:
                try:
                    with open(p, "w") as f:
                        f.write(val)
                except Exception:
                    pass
    subprocess.run(["ip", "link", "set", "wlan0", "up"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _has_nm():
    if not shutil.which("nmcli"):
        return False
    r = subprocess.run(["nmcli", "-t", "-f", "RUNNING", "general"], capture_output=True, text=True, timeout=3)
    return r.returncode == 0 and "running" in r.stdout.lower()


def wpa_request(cmd_str):
    client_sock = f"/tmp/wpa_ctrl_{os.getpid()}_{int(time.time()*1000)%1000000}_{random.randint(100,999)}"
    try:
        if os.path.exists(client_sock):
            try:
                os.unlink(client_sock)
            except Exception:
                pass
        s = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        s.bind(client_sock)
        s.settimeout(2.5)
        target = "/run/wpa_supplicant/wlan0"
        if not os.path.exists(target):
            target = "/var/run/wpa_supplicant/wlan0"
        s.connect(target)
        s.send((cmd_str + "\n").encode("utf-8"))
        data = s.recv(8192)
        s.close()
        return data.decode("utf-8", errors="ignore").strip()
    except Exception:
        try:
            p = subprocess.run(f"wpa_cli -i wlan0 {cmd_str}", shell=True, capture_output=True, text=True, timeout=3)
            return p.stdout.strip()
        except Exception:
            return ""
    finally:
        if os.path.exists(client_sock):
            try:
                os.unlink(client_sock)
            except Exception:
                pass

def get_wifi_status():
    ensure_wifi_firmware()
    status = {
        "connected": False,
        "ssid": "Not Connected",
        "bssid": "",
        "ip": "",
        "freq": 0,
        "band": "Unknown",
        "signal": -100,
        "security": "None",
        "wpa_state": "DISCONNECTED",
        "backend": "wpa_supplicant",
    }

    if _has_nm():
        status["backend"] = "networkmanager"
        p = subprocess.run(
            ["nmcli", "-t", "-f", "ACTIVE,SSID,BSSID,FREQ,SIGNAL,SECURITY", "dev", "wifi", "list", "ifname", "wlan0"],
            capture_output=True, text=True, timeout=5
        )
        for line in p.stdout.splitlines():
            if line.startswith("yes:"):
                parts = line.replace("\\:", "__COL__").split(":")
                if len(parts) >= 6:
                    status["connected"] = True
                    status["wpa_state"] = "COMPLETED"
                    status["ssid"] = parts[1].replace("__COL__", ":")
                    status["bssid"] = parts[2].replace("__COL__", ":")
                    try:
                        f = int(re.sub(r"\D", "", parts[3]) or "0")
                        status["freq"] = f
                        status["band"] = "5 GHz" if f >= 5000 else "2.4 GHz"
                    except Exception:
                        pass
                    try:
                        pct = int(parts[4])
                        status["signal"] = max(-95, min(-30, -100 + pct // 2 + 15))
                    except Exception:
                        pass
                    status["security"] = parts[5] or "None"
                    break
        ip_p = subprocess.run(["ip", "-4", "-o", "addr", "show", "wlan0"], capture_output=True, text=True, timeout=3)
        m = re.search(r"inet\s+(\d+\.\d+\.\d+\.\d+)", ip_p.stdout)
        if m:
            status["ip"] = m.group(1)
        if status["connected"]:
            return status

    raw = wpa_request("STATUS")
    if not raw:
        return status

    for line in raw.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip()
            if k == "wpa_state":
                status["wpa_state"] = v
                if v == "COMPLETED":
                    status["connected"] = True
            elif k == "ssid":
                status["ssid"] = v
            elif k == "bssid":
                status["bssid"] = v
            elif k == "ip_address":
                status["ip"] = v
            elif k == "freq":
                try:
                    f = int(v)
                    status["freq"] = f
                    status["band"] = "5 GHz" if f >= 5000 else "2.4 GHz"
                except Exception:
                    pass
            elif k == "key_mgmt":
                status["security"] = v

    if status["connected"]:
        sig_raw = wpa_request("SIGNAL_POLL")
        for line in sig_raw.splitlines():
            if line.startswith("RSSI="):
                try:
                    status["signal"] = int(line.split("=")[1])
                except Exception:
                    pass
    return status


def scan_networks():
    ensure_wifi_firmware()
    current = get_wifi_status()
    seen = {}

    if _has_nm():
        subprocess.run(["nmcli", "dev", "wifi", "rescan", "ifname", "wlan0"], capture_output=True, timeout=8)
        time.sleep(1.0)
        p = subprocess.run(
            ["nmcli", "-t", "-f", "ACTIVE,SSID,BSSID,FREQ,SIGNAL,SECURITY", "dev", "wifi", "list", "ifname", "wlan0"],
            capture_output=True, text=True, timeout=8
        )
        for line in p.stdout.splitlines():
            parts = line.replace("\\:", "__COL__").split(":")
            if len(parts) < 6:
                continue
            ssid = parts[1].replace("__COL__", ":").strip()
            if not ssid:
                continue
            bssid = parts[2].replace("__COL__", ":").strip()
            try:
                freq = int(re.sub(r"\D", "", parts[3]) or "2412")
            except Exception:
                freq = 2412
            try:
                pct = int(parts[4])
                sig = max(-95, min(-30, -100 + pct // 2 + 15))
            except Exception:
                sig = -80
            sec = parts[5].strip() or "Open"
            band = "5 GHz" if freq >= 5000 else "2.4 GHz"
            key = (ssid, band)
            item = {
                "ssid": ssid,
                "bssid": bssid,
                "freq": freq,
                "band": band,
                "signal": sig,
                "security": sec,
                "flags": sec,
                "connected": (parts[0] == "yes"),
            }
            if key not in seen or sig > seen[key]["signal"]:
                seen[key] = item
        if seen:
            networks = list(seen.values())
            networks.sort(key=lambda x: (not x["connected"], -x["signal"]))
            return networks

    wpa_request("SCAN")
    time.sleep(1.5)
    raw = wpa_request("SCAN_RESULTS")
    for line in raw.splitlines():
        parts = line.split("\t")
        if len(parts) >= 5:
            bssid, freq_str, sig_str, flags, ssid = parts[0], parts[1], parts[2], parts[3], parts[4]
            if not ssid:
                continue
            try:
                freq = int(freq_str)
                sig = int(sig_str)
            except Exception:
                continue

            band = "5 GHz" if freq >= 5000 else "2.4 GHz"
            sec = "Open"
            if "WPA3" in flags or "SAE" in flags:
                sec = "WPA3"
            elif "WPA2" in flags:
                sec = "WPA2"
            elif "WPA" in flags:
                sec = "WPA"
            elif "WEP" in flags:
                sec = "WEP"

            key = (ssid, band)
            is_active = (current["connected"]) and (ssid == current["ssid"]) and (band == current["band"])
            item = {
                "ssid": ssid,
                "bssid": bssid,
                "freq": freq,
                "band": band,
                "signal": sig,
                "security": sec,
                "flags": flags,
                "connected": is_active,
            }
            if key not in seen or sig > seen[key]["signal"]:
                seen[key] = item

    networks = list(seen.values())
    networks.sort(key=lambda x: (not x["connected"], -x["signal"]))
    return networks


def connect_network(ssid, password=None):
    ensure_wifi_firmware()
    if _has_nm():
        cmd = ["nmcli", "dev", "wifi", "connect", ssid, "ifname", "wlan0"]
        if password:
            cmd += ["password", password]
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
        if p.returncode == 0:
            stat = get_wifi_status()
            return True, f"Connected to {ssid} (IP: {stat.get('ip', '')})"
        err = (p.stderr or p.stdout or "").strip()
        return False, err or "nmcli association failed."

    list_raw = wpa_request("LIST_NETWORKS")
    net_id = None
    for line in list_raw.splitlines()[1:]:
        parts = line.split("\t")
        if len(parts) >= 2 and parts[1] == ssid:
            net_id = parts[0]
            break

    if net_id is None:
        net_id = wpa_request("ADD_NETWORK")
        if not net_id.isdigit():
            return False, f"Failed to add network: {net_id}"

    wpa_request(f'SET_NETWORK {net_id} ssid "{ssid}"')
    if password:
        wpa_request(f'SET_NETWORK {net_id} psk "{password}"')
        wpa_request(f'SET_NETWORK {net_id} key_mgmt WPA-PSK')
    else:
        wpa_request(f'SET_NETWORK {net_id} key_mgmt NONE')

    wpa_request(f"ENABLE_NETWORK {net_id}")
    wpa_request(f"SELECT_NETWORK {net_id}")
    wpa_request("SAVE_CONFIG")

    connected = False
    for _ in range(12):
        time.sleep(1)
        stat = get_wifi_status()
        if stat["connected"] and stat["ssid"] == ssid:
            connected = True
            break

    if not connected:
        return False, "Association timed out."

    if shutil.which("dhclient"):
        subprocess.run("killall dhclient 2>/dev/null; dhclient -v wlan0 >/tmp/dhclient_gui.log 2>&1", shell=True)
    elif shutil.which("udhcpc"):
        subprocess.run("udhcpc -n -q -i wlan0 >/tmp/udhcpc_gui.log 2>&1", shell=True)
    time.sleep(1)
    stat = get_wifi_status()
    return True, f"Connected to {ssid} (IP: {stat['ip']})"


def disconnect_wifi():
    if _has_nm():
        subprocess.run(["nmcli", "dev", "disconnect", "wlan0"], capture_output=True, timeout=5)
    wpa_request("DISCONNECT")
    return True


if __name__ == "__main__":
    args = sys.argv[1:]
    as_json = False
    if "--json" in args:
        as_json = True
        args.remove("--json")

    cmd = args[0] if args else ""
    if cmd == "scan":
        nets = scan_networks()
        if as_json:
            print(json.dumps({"networks": nets, "status": get_wifi_status()}))
        else:
            for n in nets:
                active = " [*ACTIVE*]" if n["connected"] else ""
                print(f"  [{n['band']:>7}] {n['ssid']:<24} {n['signal']:>4} dBm  ({n['security']}){active}")
    elif cmd == "connect" and len(args) >= 2:
        ok, msg = connect_network(args[1], args[2] if len(args) > 2 else None)
        if as_json:
            print(json.dumps({"success": ok, "message": msg, "status": get_wifi_status()}))
        else:
            print(("[+] " if ok else "[!] ") + msg)
        sys.exit(0 if ok else 1)
    elif cmd == "status":
        st = get_wifi_status()
        if as_json:
            print(json.dumps(st))
        else:
            for k, v in st.items():
                print(f"  {k}: {v}")
    else:
        status = get_wifi_status()
        if as_json:
            print(json.dumps({"status": status, "networks": scan_networks()}))
        else:
            print("=== LIVE WI-FI STATUS ===")
            for k, v in status.items():
                print(f"  {k}: {v}")
            print("\n=== SCANNING WI-FI NETWORKS (2.4 GHz & 5 GHz) ===")
            for n in scan_networks():
                active = " [*ACTIVE*]" if n["connected"] else ""
                print(f"  [{n['band']:>7}] {n['ssid']:<24} {n['signal']:>4} dBm  ({n['security']}){active}")
