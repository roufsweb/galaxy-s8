"""
Dual-transport client for Samsung Galaxy S8:
1. Primary Native Linux Transport: USB RNDIS / Wi-Fi SSH (192.168.7.2 / wlan0)
2. Recovery / Staging Transport: Android Debug Bridge (ADB / TWRP)
"""

import json
import os
import shutil
import socket
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.config import ADB_PATH, DEFAULT_SERIAL, RNDIS_DEFAULT_IP


class AdbClient:
    """Manages ADB and Native SSH communication with Samsung Galaxy S8."""

    def __init__(self, serial: str = DEFAULT_SERIAL, adb_path: Path = ADB_PATH):
        self.serial = serial
        self.adb_path = str(adb_path)
        self.wifi_ip: str = os.environ.get("S8_SSH_IP", "").strip()
        self.ssh_bin = self._find_ssh_binary()
        self._cached_ssh_host: Optional[str] = None
        self._cached_ssh_ts: float = 0.0
        self._cached_rwp_url: Optional[str] = None
        self._cached_rwp_ts: float = 0.0

    @staticmethod
    def _find_ssh_binary() -> str:
        win_ssh = Path("C:/Windows/System32/OpenSSH/ssh.exe")
        if win_ssh.is_file():
            return str(win_ssh)
        found = shutil.which("ssh")
        return found or "ssh"

    @staticmethod
    def _no_window_flags() -> int:
        if os.name == "nt":
            return getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        return 0

    @staticmethod
    def ensure_ssh_keypair() -> Tuple[Optional[Path], Optional[Path]]:
        """Ensure the host user has an ed25519 or rsa SSH keypair for zero-prompt setup."""
        ssh_dir = Path.home() / ".ssh"
        ssh_dir.mkdir(parents=True, exist_ok=True)
        for name in ("id_ed25519", "id_rsa"):
            priv = ssh_dir / name
            pub = ssh_dir / f"{name}.pub"
            if priv.is_file() and pub.is_file():
                return priv, pub

        priv = ssh_dir / "id_ed25519"
        pub = ssh_dir / "id_ed25519.pub"
        keygen = shutil.which("ssh-keygen") or "C:/Windows/System32/OpenSSH/ssh-keygen.exe"
        if Path(keygen).is_file() or shutil.which(str(keygen)):
            try:
                subprocess.run(
                    [str(keygen), "-t", "ed25519", "-N", "", "-f", str(priv), "-C", "s8-imager"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    creationflags=AdbClient._no_window_flags(),
                )
                if priv.is_file() and pub.is_file():
                    return priv, pub
            except Exception:
                pass
        return None, None

    def get_ssh_hosts(self) -> List[str]:
        hosts = [RNDIS_DEFAULT_IP]
        if self.wifi_ip and self.wifi_ip not in hosts:
            hosts.append(self.wifi_ip)
        return hosts

    @staticmethod
    def probe_port(host: str, port: int = 22, timeout: float = 0.7) -> bool:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except Exception:
            return False

    def active_ssh_host(self, cache_ttl: float = 3.0) -> Optional[str]:
        now = time.monotonic()
        if self._cached_ssh_host and (now - self._cached_ssh_ts) < cache_ttl:
            return self._cached_ssh_host
        for host in self.get_ssh_hosts():
            if self.probe_port(host, 22, timeout=0.5):
                self._cached_ssh_host = host
                self._cached_ssh_ts = now
                return host
        self._cached_ssh_host = None
        self._cached_ssh_ts = now
        return None

    def exec_ssh(
        self,
        cmd: str,
        host: Optional[str] = None,
        user: str = "root",
        port: int = 22,
        timeout: int = 15,
    ) -> Tuple[bool, str]:
        target_host = host or self.active_ssh_host()
        if not target_host:
            return False, ""
        priv, _ = self.ensure_ssh_keypair()
        ssh_cmd = [
            self.ssh_bin,
            "-n",
            "-T",
            "-o", "BatchMode=yes",
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
            "-o", "LogLevel=ERROR",
            "-o", "ConnectTimeout=4",
            "-p", str(port),
        ]
        if priv:
            ssh_cmd.extend(["-i", str(priv)])
        ssh_cmd.extend([f"{user}@{target_host}", cmd])
        for attempt in range(2):
            try:
                res = subprocess.run(
                    ssh_cmd,
                    stdin=subprocess.DEVNULL,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    creationflags=self._no_window_flags(),
                )
                out = (res.stdout or "")
                if res.returncode != 0 and res.stderr and not out:
                    out = res.stderr
                if res.returncode == 0:
                    return True, out.strip()
                if res.returncode == 255 and attempt == 0:
                    self._cached_ssh_ts = 0.0
                    time.sleep(0.15)
                    continue
                return False, out.strip()
            except Exception as exc:
                if attempt == 0:
                    time.sleep(0.15)
                    continue
                return False, str(exc)
        return False, ""

    def push_ssh(
        self,
        local_path: str,
        remote_path: str,
        host: Optional[str] = None,
        user: str = "root",
        port: int = 22,
        timeout: int = 120,
    ) -> Tuple[bool, str]:
        """Stream a file to remote Linux over raw SSH stdin (works with Dropbear & OpenSSH)."""
        target_host = host or self.active_ssh_host()
        if not target_host:
            return False, "No SSH host reachable"
        p = Path(local_path)
        if not p.is_file():
            return False, f"Local file missing: {local_path}"
        priv, _ = self.ensure_ssh_keypair()
        ssh_cmd = [
            self.ssh_bin,
            "-o", "BatchMode=yes",
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
            "-o", "LogLevel=ERROR",
            "-o", "ConnectTimeout=5",
            "-p", str(port),
        ]
        if priv:
            ssh_cmd.extend(["-i", str(priv)])
        safe_remote = remote_path.replace("'", "'\\''")
        ssh_cmd.extend([f"{user}@{target_host}", f"mkdir -p \"$(dirname '{safe_remote}')\" && cat > '{safe_remote}'"])
        try:
            with open(p, "rb") as f:
                res = subprocess.run(
                    ssh_cmd,
                    stdin=f,
                    capture_output=True,
                    timeout=timeout,
                    creationflags=self._no_window_flags(),
                )
            err = res.stderr.decode("utf-8", errors="ignore").strip() if res.stderr else ""
            return (res.returncode == 0), err
        except Exception as exc:
            return False, str(exc)

    def run_cmd(self, args: List[str], timeout: int = 10) -> subprocess.CompletedProcess:
        cmd = [self.adb_path, "-s", self.serial] + args
        try:
            return subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                creationflags=self._no_window_flags(),
            )
        except subprocess.TimeoutExpired:
            return subprocess.CompletedProcess(args=cmd, returncode=124, stdout="", stderr="ERROR: Shell command timed out")

    def shell(self, command: str, timeout: int = 15) -> str:
        res = self.run_cmd(["shell", command], timeout=timeout)
        if res.returncode == 124 and "timed out" in res.stderr:
            return "ERROR: Shell command timed out"
        return res.stdout.strip() if res.returncode == 0 else ""

    def root_shell(self, command: str, timeout: int = 20) -> str:
        return self.shell(command, timeout=timeout)

    def is_connected(self) -> bool:
        try:
            res = subprocess.run(
                [self.adb_path, "devices"],
                capture_output=True,
                text=True,
                timeout=8,
                creationflags=self._no_window_flags(),
            )
            if res.returncode != 0:
                return False
            for line in res.stdout.splitlines():
                parts = line.split()
                if len(parts) >= 2 and parts[0] == self.serial and parts[1] in ("device", "recovery", "sideload"):
                    return True
            return False
        except Exception:
            return False

    def get_state(self) -> str:
        try:
            res = self.run_cmd(["get-state"], timeout=8)
            if res.returncode == 0 and res.stdout.strip():
                return res.stdout.strip()
        except Exception:
            pass
        try:
            res = subprocess.run(
                [self.adb_path, "devices"],
                capture_output=True,
                text=True,
                timeout=8,
                creationflags=self._no_window_flags(),
            )
            if res.returncode == 0:
                for line in res.stdout.splitlines():
                    parts = line.split()
                    if len(parts) >= 2 and parts[0] == self.serial:
                        return parts[1].strip()
        except Exception:
            pass
        return "offline"

    def detect_transport(self) -> Dict[str, str]:
        """Determine live active transport cleanly across USB RNDIS, Wi-Fi SSH, and TWRP ADB."""
        ssh_host = self.active_ssh_host()
        if ssh_host:
            mode = "ssh_usb" if ssh_host == RNDIS_DEFAULT_IP else "ssh_wifi"
            return {"mode": mode, "host": ssh_host, "state": "linux"}
        adb_state = self.get_state()
        if adb_state == "recovery":
            return {"mode": "adb_recovery", "host": self.serial, "state": "recovery"}
        if adb_state in ("device", "sideload"):
            return {"mode": "adb_linux", "host": self.serial, "state": adb_state}
        return {"mode": "offline", "host": "", "state": "offline"}

    def forward(self, local_port: int, remote_port: int) -> bool:
        res = self.run_cmd(["forward", f"tcp:{local_port}", f"tcp:{remote_port}"])
        return res.returncode == 0

    def push(self, local_path: str, remote_path: str, timeout: int = 60) -> bool:
        res = self.run_cmd(["push", str(local_path), remote_path], timeout=timeout)
        return res.returncode == 0

    def exec_rwp(self, cmd: str, ip: str = "192.168.0.232", port: int = 22, timeout: int = 15) -> str:
        ssh_cmd = [
            self.ssh_bin,
            "-n",
            "-T",
            "-o", "BatchMode=yes",
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
            "-o", "LogLevel=ERROR",
            "-o", "ConnectTimeout=4",
            "-p", str(port),
        ]
        priv, _ = self.ensure_ssh_keypair()
        if priv:
            ssh_cmd.extend(["-i", str(priv)])
        ssh_cmd.extend([f"root@{ip}", cmd])
        try:
            res = subprocess.run(
                ssh_cmd,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=timeout,
                creationflags=self._no_window_flags(),
            )
            return (res.stdout or "").strip() if res.returncode == 0 else ""
        except Exception:
            return ""

    def ensure_rwp_url(self, cache_ttl: float = 3.0) -> Optional[str]:
        """Auto-discover zero-config AP s8_usb_agentd (:7860) via ADB forward, USB RNDIS, or Wi-Fi."""
        now = time.monotonic()
        if self._cached_rwp_url and (now - self._cached_rwp_ts) < cache_ttl:
            return self._cached_rwp_url

        # 1. Zero-config USB ADB forward -> localhost:17860
        if self.is_connected():
            if self.probe_port("127.0.0.1", 17860, timeout=0.25):
                if self._probe_rwp_health("http://127.0.0.1:17860"):
                    self._cached_rwp_url = "http://127.0.0.1:17860"
                    self._cached_rwp_ts = now
                    return self._cached_rwp_url
            if self.forward(17860, 7860):
                if self._probe_rwp_health("http://127.0.0.1:17860"):
                    self._cached_rwp_url = "http://127.0.0.1:17860"
                    self._cached_rwp_ts = now
                    return self._cached_rwp_url

        # 2. Direct RNDIS or Wi-Fi RWP agent
        for host in self.get_ssh_hosts():
            if self.probe_port(host, 7860, timeout=0.35):
                url = f"http://{host}:7860"
                if self._probe_rwp_health(url):
                    self._cached_rwp_url = url
                    self._cached_rwp_ts = now
                    return url

        self._cached_rwp_url = None
        self._cached_rwp_ts = now
        return None

    @staticmethod
    def _probe_rwp_health(base_url: str) -> bool:
        try:
            with urllib.request.urlopen(f"{base_url}/rwp/v1/health", timeout=0.6) as resp:
                return resp.status == 200
        except Exception:
            return False

    def rwp_request(
        self,
        path: str,
        method: str = "GET",
        payload: Optional[Dict[str, Any]] = None,
        timeout: float = 10.0,
    ) -> Optional[Dict[str, Any]]:
        base_url = self.ensure_rwp_url()
        if not base_url:
            return None
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers = {"Content-Type": "application/json"} if data is not None else {}
        req = urllib.request.Request(f"{base_url}{path}", data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                return json.loads(raw)
        except Exception:
            self._cached_rwp_ts = 0.0
            return None

    def exec_env(self, cmd: str, env: str = "os", timeout: int = 15) -> str:
        """Execute inside AP base (`ap`) or installed guest rootfs (`os`) via RWP first, then SSH/ADB."""
        res = self.rwp_request("/rwp/v1/exec", method="POST", payload={"env": env, "cmd": cmd}, timeout=float(timeout))
        if isinstance(res, dict) and "output" in res:
            return str(res.get("output", "")).strip()

        if env == "ap":
            return self.shell(cmd, timeout=timeout)
        return self.exec_os(cmd, timeout=timeout)

    def exec_os(self, cmd: str, timeout: int = 15) -> str:
        """Execute inside the phone's Linux OS over RWP first, then SSH or ADB/chroot."""
        res = self.rwp_request("/rwp/v1/exec", method="POST", payload={"env": "os", "cmd": cmd}, timeout=float(timeout))
        if isinstance(res, dict) and "output" in res:
            return str(res.get("output", "")).strip()

        ok, out = self.exec_ssh(cmd, timeout=timeout)
        if ok or self.active_ssh_host():
            return out

        state = self.get_state()
        if state == "recovery":
            safe_cmd = cmd.replace("'", "'\\''")
            return self.root_shell(f"chroot /mnt/rootfs /bin/sh -c '{safe_cmd}' 2>/dev/null || chroot /mnt/ubuntu /bin/sh -c '{safe_cmd}'", timeout=timeout)
        if state in ("device", "sideload"):
            return self.root_shell(cmd, timeout=timeout)
        return ""
