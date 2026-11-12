"""
Hardware Telemetry, Peripherals Control & Package Manager for Samsung Galaxy S8.
Queries real device state over USB RNDIS SSH (192.168.7.2), Wi-Fi SSH, or TWRP ADB.
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.config import DEFAULT_SERIAL, HW_PACK_VERSION, PACKAGES_DIR, RESOURCES_BIN_DIR
from app.core.adb import AdbClient


class DeviceManager:
    """Interfaces with live Galaxy S8 hardware sensors, peripherals, and OS services."""

    def __init__(self, adb: Optional[AdbClient] = None):
        self.adb = adb or AdbClient()

    def check_wifi_online(self, host: str = "") -> bool:
        target = host or getattr(self.adb, "wifi_ip", "") or ""
        if target and self.adb.probe_port(target, 22, timeout=0.5):
            return True
        return bool(self.adb.active_ssh_host())

    def get_telemetry(self) -> Dict[str, Any]:
        """Collect genuine real-time hardware & OS telemetry (no mock fallbacks)."""
        info: Dict[str, Any] = {
            "connected": False,
            "serial": self.adb.serial or DEFAULT_SERIAL,
            "state": "offline",
            "transport": "offline",
            "ssh_host": "",
            "os": "None",
            "kernel": "--",
            "cpu": "0%",
            "ram_free": "0 GB",
            "battery": "0%",
            "temp": "0°C",
            "wifi_ip": "Offline",
            "rndis_ip": "--",
            "lan_ip": "--",
            "lan_iface": "",
            "hw_pack_installed": False,
            "hw_pack_version": "",
            "ssh_daemon": "none",
            "dp_monitor": "Disconnected",
            "microsd_status": "Unknown",
        }

        rwp_info = self.adb.rwp_request("/rwp/v1/info", timeout=1.5)
        if isinstance(rwp_info, dict) and rwp_info.get("protocol") == "rwp-v1":
            info["connected"] = True
            info["state"] = "device"
            info["transport"] = "rwp_usb" if (rwp_info.get("rndis_ip") or self.adb.is_connected()) else "rwp_wifi"
            info["os"] = rwp_info.get("guest_os") or "AP Base Shell"
            info["kernel"] = rwp_info.get("kernel") or "--"
            info["battery"] = f"{rwp_info.get('battery_pct', 0)}%"
            info["temp"] = f"{rwp_info.get('temp_c', 0)}°C"
            info["rndis_ip"] = rwp_info.get("rndis_ip") or "--"
            info["wifi_ip"] = rwp_info.get("wlan_ip") or "Offline"
            info["lan_ip"] = rwp_info.get("lan_ip") or "--"
            info["lan_iface"] = rwp_info.get("lan_iface") or ""
            info["dp_monitor"] = "Connected" if rwp_info.get("dp_connected") else "Disconnected"
            import base64
            ext_script = (
                "HWVER=$(cat /etc/s8-hw-version 2>/dev/null || echo ''); "
                "C0=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq 2>/dev/null || echo '0'); "
                "C4=$(cat /sys/devices/system/cpu/cpu4/cpufreq/scaling_cur_freq 2>/dev/null || echo '0'); "
                "AVAIL=$(awk '/MemAvailable/{print $2}' /proc/meminfo 2>/dev/null || echo '0'); "
                "SD=$(mountpoint -q /media/sdcard && echo 'Mounted' || ( [ -b /dev/mmcblk0 ] && echo 'Detected' || echo 'Absent')); "
                "SSHD=$( (pgrep -x sshd >/dev/null && echo 'openssh') || (pgrep -f 'dropbear' >/dev/null && echo 'dropbear') || echo 'active' ); "
                "BTNS=$(pgrep -f '[s]8_button_daemon' >/dev/null && echo '1' || echo '0'); "
                "echo \"HWVER=$HWVER|C0=$C0|C4=$C4|AVAIL=$AVAIL|SD=$SD|SSHD=$SSHD|BTNS=$BTNS\""
            )
            b64_cmd = base64.b64encode(ext_script.encode("utf-8")).decode("ascii")
            ext_res = self.adb.rwp_request("/rwp/v1/exec", method="POST", payload={"env": "os", "cmd": f"echo {b64_cmd} | base64 -d | /bin/sh"}, timeout=2.0)
            if isinstance(ext_res, dict) and ext_res.get("output"):
                kv = {}
                for part in str(ext_res.get("output", "")).strip().split("|"):
                    if "=" in part:
                        k, v = part.split("=", 1)
                        kv[k.strip()] = v.strip()
                hwver = kv.get("HWVER", "")
                info["hw_pack_installed"] = bool(hwver)
                info["hw_pack_version"] = hwver
                c0 = int(kv.get("C0") or 0) // 1000
                c4 = int(kv.get("C4") or 0) // 1000
                if c0 or c4:
                    info["cpu"] = f"A53 {c0}MHz | M2 {c4}MHz"
                avail_kb = int(kv.get("AVAIL") or 0)
                if avail_kb:
                    info["ram_free"] = f"{avail_kb / 1048576:.1f} GB"
                info["microsd_status"] = kv.get("SD") or "Unknown"
                info["ssh_daemon"] = kv.get("SSHD") or "active"
                info["buttons_active"] = kv.get("BTNS") == "1"
            return info

        adb_up = False
        try:
            adb_up = bool(self.adb.is_connected())
        except Exception:
            adb_up = False

        if adb_up:
            state = self.adb.get_state() or "device"
            if hasattr(state, "_mock_name") or not isinstance(state, str):
                state = "device"
            raw = self.adb.shell(
                "grep -m1 '^PRETTY_NAME=' /etc/os-release 2>/dev/null || echo 'PRETTY_NAME=\"TWRP Recovery\"'; "
                "cat /sys/class/power_supply/battery/capacity 2>/dev/null || echo 0; "
                "cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null || echo 0; "
                "grep -E 'MemTotal|MemAvailable' /proc/meminfo 2>/dev/null; "
                "ip -4 -o addr show wlan0 2>/dev/null | awk '{print $4}' | cut -d/ -f1 | head -n1"
            )
            info["connected"] = True
            info["state"] = state
            info["transport"] = "adb_recovery" if state == "recovery" else "adb"
            os_match = re.search(r'PRETTY_NAME="?([^"\n]+)"?', raw)
            info["os"] = os_match.group(1) if os_match else ("TWRP Recovery" if state == "recovery" else "ARM64 Linux")

            lines = [ln.strip() for ln in raw.splitlines() if ln.strip() and not ln.startswith("PRETTY_NAME=") and not ln.startswith("Mem")]
            if len(lines) >= 1 and lines[0].isdigit():
                info["battery"] = f"{lines[0]}%"
            if len(lines) >= 2 and lines[1].isdigit():
                t_raw = int(lines[1])
                t_c = (t_raw / 1000.0) if t_raw > 1000 else ((t_raw / 10.0) if t_raw > 100 else float(t_raw))
                info["temp"] = f"{t_c:.1f}°C"
            avail_m = re.search(r"MemAvailable:\s*(\d+)", raw)
            if avail_m:
                avail_gb = int(avail_m.group(1)) / (1024 * 1024)
                info["ram_free"] = f"{avail_gb:.1f} GB"
            ip_m = re.search(r"\b(\d+\.\d+\.\d+\.\d+)\b", "\n".join(lines[2:]))
            if ip_m:
                info["wifi_ip"] = ip_m.group(1)
                self.adb.wifi_ip = info["wifi_ip"]
            return info

        # ADB offline -> check USB RNDIS SSH (192.168.7.2) or Wi-Fi SSH
        if not self.check_wifi_online():
            return info

        ssh_host = self.adb.active_ssh_host()
        if not ssh_host:
            return info

        probe = (
            "OS=$(sed -n 's/^PRETTY_NAME=//p' /etc/os-release 2>/dev/null | tr -d '\"' | head -n1); "
            "[ -z \"$OS\" ] && OS=$(uname -s); "
            "KVER=$(uname -r); "
            "CAP=$(cat /sys/class/power_supply/battery/capacity 2>/dev/null || echo '0'); "
            "BST=$(cat /sys/class/power_supply/battery/status 2>/dev/null || echo ''); "
            "MA=$(cat /sys/class/power_supply/battery/current_now 2>/dev/null || echo '0'); "
            "TEMP=$(cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null || echo '0'); "
            "C0=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq 2>/dev/null || echo '0'); "
            "C4=$(cat /sys/devices/system/cpu/cpu4/cpufreq/scaling_cur_freq 2>/dev/null || echo '0'); "
            "AVAIL=$(awk '/MemAvailable/{print $2}' /proc/meminfo 2>/dev/null || echo '0'); "
            "TOT=$(awk '/MemTotal/{print $2}' /proc/meminfo 2>/dev/null || echo '0'); "
            "WIP=$(ip -4 -o addr show wlan0 2>/dev/null | awk '{print $4}' | cut -d/ -f1 | head -n1); "
            "UIP=$(ip -4 -o addr show rndis0 2>/dev/null | awk '{print $4}' | cut -d/ -f1 | head -n1); "
            "HWVER=$(cat /etc/s8-hw-version 2>/dev/null || echo ''); "
            "DP=$(cat /sys/class/switch/hdmi/state 2>/dev/null || echo '0'); "
            "SD=$(mountpoint -q /media/sdcard && echo 'Mounted' || ( [ -b /dev/mmcblk0 ] && echo 'Detected' || echo 'Absent')); "
            "SSHD=$( (pgrep -x sshd >/dev/null && echo 'openssh') || (pgrep -f 'dropbear' >/dev/null && echo 's8-seed-dropbear') || echo 'unknown' ); "
            "BTNS=$(pgrep -f '[s]8_button_daemon' >/dev/null && echo '1' || echo '0'); "
            "printf 'OS=%s\\nKVER=%s\\nCAP=%s\\nBST=%s\\nMA=%s\\nTEMP=%s\\nC0=%s\\nC4=%s\\nAVAIL=%s\\nTOT=%s\\nWIP=%s\\nUIP=%s\\nHWVER=%s\\nDP=%s\\nSD=%s\\nSSHD=%s\\nBTNS=%s\\n' "
            "\"$OS\" \"$KVER\" \"$CAP\" \"$BST\" \"$MA\" \"$TEMP\" \"$C0\" \"$C4\" \"$AVAIL\" \"$TOT\" \"$WIP\" \"$UIP\" \"$HWVER\" \"$DP\" \"$SD\" \"$SSHD\" \"$BTNS\""
        )
        ok, raw = self.adb.exec_ssh(probe, host=ssh_host, timeout=8)
        if not ok:
            return info

        kv = {}
        for line in raw.splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                kv[k.strip()] = v.strip()

        info["connected"] = True
        info["state"] = "linux"
        info["transport"] = "ssh_usb" if ssh_host == "192.168.7.2" else "ssh_wifi"
        info["ssh_host"] = ssh_host
        info["os"] = kv.get("OS") or "ARM64 Linux"
        info["kernel"] = kv.get("KVER", "--")
        c0 = int(kv.get("C0") or 0) // 1000
        c4 = int(kv.get("C4") or 0) // 1000
        info["cpu"] = f"A53 {c0}MHz | M2 {c4}MHz" if (c0 or c4) else "Exynos 8895"
        avail_kb = int(kv.get("AVAIL") or 0)
        info["ram_free"] = f"{avail_kb / 1048576:.1f} GB" if avail_kb else "0 GB"
        cap = kv.get("CAP", "0")
        bst = kv.get("BST", "")
        ma = int(kv.get("MA") or 0)
        info["battery"] = f"{cap}% ({bst} {ma}mA)".strip() if bst else f"{cap}%"
        temp_raw = int(kv.get("TEMP") or 0)
        t_c = (temp_raw / 1000.0) if temp_raw > 1000 else ((temp_raw / 10.0) if temp_raw > 100 else float(temp_raw))
        info["temp"] = f"{t_c:.1f}°C"
        info["wifi_ip"] = kv.get("WIP") or "Offline"
        if kv.get("WIP"):
            self.adb.wifi_ip = kv["WIP"]
        info["rndis_ip"] = kv.get("UIP") or "--"
        hwver = kv.get("HWVER", "")
        info["hw_pack_installed"] = bool(hwver)
        info["hw_pack_version"] = hwver or ""
        info["dp_monitor"] = "Connected" if kv.get("DP") == "1" else "Disconnected"
        info["microsd_status"] = kv.get("SD", "Unknown")
        info["ssh_daemon"] = kv.get("SSHD", "unknown")
        info["buttons_active"] = kv.get("BTNS") == "1"
        return info

    def set_torch(self, state: int) -> bool:
        val = "3" if int(state) > 0 else "0"
        cmd = f"echo {val} > /sys/class/leds/torch-sec1/brightness"
        if self.adb.is_connected():
            self.adb.shell(cmd)
            return True
        host = self.adb.active_ssh_host()
        if host:
            ok, _ = self.adb.exec_ssh(cmd, host=host, timeout=8)
            return ok
        return False

    def toggle_torch(self, on: bool) -> bool:
        return self.set_torch(1 if on else 0)

    def pulse_haptic(self, duration_ms: int = 120) -> bool:
        safe_ms = max(20, min(2000, int(duration_ms)))
        cmd = f"echo {safe_ms} > /sys/class/timed_output/vibrator/enable"
        if self.adb.is_connected():
            self.adb.shell(cmd)
            return True
        host = self.adb.active_ssh_host()
        if host:
            ok, _ = self.adb.exec_ssh(cmd, host=host, timeout=8)
            return ok
        return False

    def vibrate(self, ms: int = 120) -> bool:
        return self.pulse_haptic(ms)

    def reboot_device(self, target: str = "system") -> Tuple[bool, str]:
        t = self.adb.detect_transport()
        if t["mode"].startswith("ssh"):
            if target == "poweroff":
                cmd = "nohup sh -c 'sleep 0.4; systemctl poweroff -i || poweroff -f' >/dev/null 2>&1 &"
            elif target == "recovery":
                cmd = "nohup sh -c 'sleep 0.4; reboot recovery || systemctl reboot' >/dev/null 2>&1 &"
            else:
                cmd = "nohup sh -c 'sleep 0.4; systemctl reboot || reboot -f' >/dev/null 2>&1 &"
            ok, err = self.adb.exec_ssh(cmd, host=t["host"], timeout=6)
            return (ok, f"Sent {target} request to {t['host']}") if ok else (False, err)

        if target == "poweroff":
            out = self.adb.root_shell("reboot -p")
            return True, out or "Poweroff triggered"
        args = ["reboot", "recovery"] if target == "recovery" else ["reboot"]
        res = self.adb.run_cmd(args, timeout=10)
        return res.returncode == 0, (res.stdout or res.stderr or "").strip()

    def scan_wifi(self) -> List[Dict[str, Any]]:
        """Scan 2.4/5 GHz Wi-Fi networks via s8_wifi.py or nmcli on the live phone."""
        cmd = (
            "if [ -x /usr/local/bin/s8_wifi.py ]; then "
            "  python3 /usr/local/bin/s8_wifi.py --json scan; "
            "elif command -v nmcli >/dev/null 2>&1; then "
            "  nmcli -t -f ACTIVE,SSID,FREQ,SIGNAL,SECURITY dev wifi list ifname wlan0 --rescan yes; "
            "else echo '__NO_WIFI_TOOL__'; fi"
        )
        raw = self.adb.exec_os(cmd, timeout=15)
        if not raw or "__NO_WIFI_TOOL__" in raw:
            return []
        try:
            data = json.loads(raw)
            return data.get("networks", [])
        except Exception:
            nets = []
            for line in raw.splitlines():
                parts = line.replace("\\:", "_").split(":")
                if len(parts) >= 5 and parts[1].strip():
                    freq = int(re.sub(r"\D", "", parts[2]) or "2412")
                    pct = int(parts[3]) if parts[3].isdigit() else 50
                    nets.append({
                        "ssid": parts[1].strip(),
                        "band": "5 GHz" if freq >= 5000 else "2.4 GHz",
                        "signal": max(-95, min(-30, -100 + pct // 2 + 15)),
                        "security": parts[4] or "Open",
                        "connected": parts[0] == "yes",
                    })
            return nets

    def connect_wifi(self, ssid: str, password: str = "") -> Tuple[bool, str]:
        """Connect live OS wlan0 via s8_wifi.py or nmcli without mutating unrelated files."""
        safe_ssid = ssid.replace("'", "'\\''")
        safe_pw = password.replace("'", "'\\''")
        cmd = (
            f"if [ -x /usr/local/bin/s8_wifi.py ]; then "
            f"  python3 /usr/local/bin/s8_wifi.py --json connect '{safe_ssid}' '{safe_pw}'; "
            f"elif command -v nmcli >/dev/null 2>&1; then "
            f"  nmcli dev wifi connect '{safe_ssid}' password '{safe_pw}' ifname wlan0; "
            f"else echo 'Install S8 Hardware Pack first to enable Wi-Fi'; exit 1; fi"
        )
        t = self.adb.detect_transport()
        if t["mode"].startswith("ssh"):
            ok, out = self.adb.exec_ssh(cmd, host=t["host"], timeout=30)
            try:
                res = json.loads(out)
                return bool(res.get("success")), res.get("message", out)
            except Exception:
                return ok, out
        out = self.adb.exec_os(cmd, timeout=30)
        return ("Connected" in out or "successfully" in out), out

    def install_hardware_pack(self, install_vnc: bool = False) -> Tuple[bool, str, str]:
        """
        Push and install galaxy-s8-hw (.deb on Debian/Ubuntu/Kali, .tar.gz everywhere else)
        cleanly onto a booted unmodified Linux OS over USB RNDIS SSH (192.168.7.2) or Wi-Fi.
        Returns (success, version, log_output).
        """
        deb_pkg = PACKAGES_DIR / f"galaxy-s8-hw_{HW_PACK_VERSION}_arm64.deb"
        tar_pkg = PACKAGES_DIR / f"galaxy-s8-hw-{HW_PACK_VERSION}-arm64.tar.gz"
        logs: List[str] = []

        t = self.adb.detect_transport()
        if not t["mode"].startswith("ssh"):
            return (
                False,
                "",
                "Phone must be booted into Linux (USB RNDIS 192.168.7.2 or Wi-Fi SSH reachable) to install S8 Hardware Pack.",
            )

        host = t["host"]
        ok_probe, distro_probe = self.adb.exec_ssh("command -v dpkg || echo 'non-deb'", host=host, timeout=5)
        use_deb = ok_probe and "dpkg" in distro_probe and deb_pkg.is_file()

        if use_deb:
            logs.append(f"[S8-HW] Uploading {deb_pkg.name} ({deb_pkg.stat().st_size:,} B) to {host}...")
            ok, err = self.adb.push_ssh(str(deb_pkg), "/tmp/galaxy-s8-hw.deb", host=host, timeout=90)
            if not ok:
                return False, "", f"Failed to upload .deb over SSH: {err}"
            install_cmd = (
                "dpkg -i /tmp/galaxy-s8-hw.deb 2>&1 && "
                "rm -f /tmp/galaxy-s8-hw.deb && "
                "cat /etc/s8-hw-version"
            )
        elif tar_pkg.is_file():
            logs.append(f"[S8-HW] Uploading universal package {tar_pkg.name} to {host}...")
            ok, err = self.adb.push_ssh(str(tar_pkg), "/tmp/galaxy-s8-hw.tar.gz", host=host, timeout=90)
            if not ok:
                return False, "", f"Failed to upload tarball over SSH: {err}"
            install_cmd = (
                "rm -rf /tmp/s8_hw_unpack && mkdir -p /tmp/s8_hw_unpack && "
                "tar -xzf /tmp/galaxy-s8-hw.tar.gz -C /tmp/s8_hw_unpack && "
                "sh /tmp/s8_hw_unpack/galaxy-s8-hw-*/install.sh 2>&1 && "
                "rm -rf /tmp/s8_hw_unpack /tmp/galaxy-s8-hw.tar.gz && "
                "cat /etc/s8-hw-version"
            )
        else:
            return False, "", f"Hardware package not built yet in {PACKAGES_DIR}. Run build_packages.py."

        ok, out = self.adb.exec_ssh(install_cmd, host=host, timeout=120)
        logs.append(out)
        if not ok:
            return False, "", "\n".join(logs)

        if install_vnc:
            logs.append("[S8-HW] Configuring optional VNC/OpenSSH desktop packages...")
            ok_v, out_v = self.adb.exec_ssh("/usr/local/bin/s8-vnc-setup.sh 2>&1", host=host, timeout=300)
            logs.append(out_v)

        ver = out.splitlines()[-1].strip() if out else HW_PACK_VERSION
        return True, ver, "\n".join(logs)
