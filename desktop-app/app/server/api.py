"""
HTTP REST & Static Asset Server for S8 Imager (`desktop-app`).
Zero external frameworks required (built on Python standard library http.server).
"""

import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.parse
import webbrowser
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import (
    AP_VERSION,
    APP_VERSION,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_SERIAL,
    DISTROS_DIR,
    HW_PACK_VERSION,
    KERNEL_VERSION,
    REPO_ROOT,
    RNDIS_DEFAULT_IP,
    UI_DIR,
)
from app.core.adb import AdbClient
from app.core.device import DeviceManager
from app.core.distros import DistroManager
from app.core.flasher import FlasherEngine
from app.core.injector import HardwareInjector


class S8ControllerState:
    """Shared singleton state across concurrent HTTP handler threads."""

    def __init__(self, serial: str = DEFAULT_SERIAL):
        self.adb = AdbClient(serial=serial)
        self.device = DeviceManager(self.adb)
        self.injector = HardwareInjector(self.adb)
        self.flasher = FlasherEngine(self.adb, self.injector)
        self.distros = DistroManager(DISTROS_DIR)
        self.lock = threading.Lock()
        self._telemetry_lock = threading.Lock()
        self._telemetry_cache: Optional[Dict[str, Any]] = None
        self._telemetry_ts: float = 0.0
        self._telemetry_refreshing: bool = False
        self.flash_state: Dict[str, Any] = {
            "active": False,
            "status": "IDLE",
            "progress": 0,
            "target": "",
            "error": "",
            "logs": [],
        }

    def get_cached_telemetry(self, max_age: float = 2.0) -> Dict[str, Any]:
        """Serve cached device telemetry immediately (<1ms) while refreshing asynchronously."""
        with self._telemetry_lock:
            cached = dict(self._telemetry_cache) if self._telemetry_cache is not None else None
            age = time.monotonic() - self._telemetry_ts
            should_refresh = (cached is None) or (age >= max_age)
            already_running = self._telemetry_refreshing

        if cached is None:
            # First cold call: populate synchronously once so initial response has live telemetry
            fresh = self.device.get_telemetry()
            with self._telemetry_lock:
                self._telemetry_cache = dict(fresh)
                self._telemetry_ts = time.monotonic()
            return fresh

        if should_refresh and not already_running:
            self.refresh_telemetry_async()

        return cached

    def refresh_telemetry_async(self):
        with self._telemetry_lock:
            if self._telemetry_refreshing:
                return
            self._telemetry_refreshing = True

        def _poll():
            try:
                fresh = self.device.get_telemetry()
                with self._telemetry_lock:
                    self._telemetry_cache = dict(fresh)
                    self._telemetry_ts = time.monotonic()
            finally:
                with self._telemetry_lock:
                    self._telemetry_refreshing = False

        threading.Thread(target=_poll, daemon=True).start()

    def append_flash_log(self, line: str):
        with self.lock:
            self.flash_state["logs"].append(line)
            if len(self.flash_state["logs"]) > 400:
                self.flash_state["logs"] = self.flash_state["logs"][-400:]


class S8RequestHandler(SimpleHTTPRequestHandler):
    """REST + static UI request handler for S8 Imager."""

    state: S8ControllerState = None  # injected on server creation

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(UI_DIR), **kwargs)

    def setup(self):
        super().setup()
        try:
            self.connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except Exception:
            pass

    def log_message(self, format, *args):
        # Suppress verbose stdout access logging during UI polling
        return

    def _send_json(self, payload: Any, status: int = HTTPStatus.OK):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {}

    def _query_params(self) -> Dict[str, str]:
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)
        return {k: v[0] for k, v in qs.items() if v}

    def do_OPTIONS(self):
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        params = self._query_params()

        if path == "/api/status":
            tel = dict(self.state.get_cached_telemetry())
            tel["app_version"] = APP_VERSION
            tel["ap_version"] = AP_VERSION
            tel["repo_hw_pack_version"] = HW_PACK_VERSION
            tel["repo_kernel_version"] = KERNEL_VERSION
            self._send_json(tel)
            return

        if path == "/api/versions":
            manifest_path = REPO_ROOT / "VERSION_MANIFEST.json"
            if manifest_path.is_file():
                try:
                    self._send_json(json.loads(manifest_path.read_text(encoding="utf-8")))
                    return
                except Exception as exc:
                    self._send_json({"error": str(exc)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
                    return
            self._send_json({"error": "VERSION_MANIFEST.json not found"}, status=HTTPStatus.NOT_FOUND)
            return

        if path == "/api/distros":
            self._send_json({"distros": self._build_distro_list()})
            return

        if path == "/api/distros/download/status":
            self._send_json(self.state.distros.download_state)
            return

        if path == "/api/storage/info":
            alloc = float(params.get("alloc", "14"))
            calc = self.state.flasher.calculate_storage(alloc)
            live = self.state.flasher.get_storage_info()
            calc["free_gb"] = live["free_gb"]
            calc["recommended_max_gb"] = live["recommended_max_gb"]
            calc["clean_supported"] = True
            self._send_json(calc)
            return

        if path == "/api/flash/status":
            with self.state.lock:
                self._send_json(dict(self.state.flash_state))
            return

        if path == "/api/flash":
            target = params.get("target", "Ubuntu 24.04.5 Desktop")
            alloc = int(float(params.get("alloc", "14")))
            clean = params.get("clean", "1") in ("1", "true", "True")
            pre_env = self.state.flasher.verify_pre_flash_environment()
            self._send_json({
                "status": "ready",
                "target": target,
                "alloc_gb": alloc,
                "clean": clean,
                "pre_env": pre_env,
            })
            return

        if path == "/api/rwp/status":
            rwp_url = self.state.adb.ensure_rwp_url()
            info = self.state.adb.rwp_request("/rwp/v1/info") if rwp_url else None
            self._send_json({"available": bool(info), "url": rwp_url or "", "info": info or {}})
            return

        if path == "/api/hardware/status":
            tel = self.state.device.get_telemetry()
            self._send_json({
                "connected": tel["connected"],
                "transport": tel["transport"],
                "hw_pack_installed": tel.get("hw_pack_installed", False),
                "hw_pack_version": tel.get("hw_pack_version", ""),
                "ssh_daemon": tel.get("ssh_daemon", "none"),
                "buttons_active": tel.get("buttons_active", False),
                "dp_monitor": tel.get("dp_monitor", "Disconnected"),
            })
            return

        if path == "/api/torch":
            on = int(params.get("state", "0")) > 0
            ok = self.state.device.set_torch(1 if on else 0)
            self._send_json({"torch": 1 if on else 0, "success": bool(ok)})
            return

        if path == "/api/haptic":
            ms = int(params.get("ms", "120"))
            ok = self.state.device.pulse_haptic(ms)
            self._send_json({"haptic": "pulsed", "ms": ms, "success": bool(ok)})
            return

        if path == "/api/exec":
            self._handle_exec(params)
            return

        if path == "/api/wifi/scan":
            nets = self.state.device.scan_wifi()
            self._send_json({"ssids": nets, "networks": nets})
            return

        if path == "/api/wifi/connect":
            ssid = params.get("ssid", "")
            pw = params.get("pass", "") or params.get("password", "")
            self._send_json({"status": "connecting", "ssid": ssid, "has_pass": bool(pw)})
            return

        if path == "/api/screen":
            url = self._resolve_screen_url()
            try:
                webbrowser.open(url)
            except Exception:
                pass
            self._send_json({"screen": "opened", "url": url})
            return

        if path == "/" or path == "":
            self.path = "/index.html"
        super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        params = self._query_params()
        body = self._read_json_body()

        if path == "/api/distros/download":
            distro_id = body.get("id") or params.get("id", "")
            self._send_json(self.state.distros.start_download(distro_id))
            return

        if path == "/api/distros/verify":
            distro_id = body.get("id") or params.get("id", "")
            self._send_json(self.state.distros.verify_file(distro_id))
            return

        if path == "/api/flash":
            image_path = body.get("image_path") or params.get("image_path", "")
            alloc_gb = int(body.get("alloc_gb") or params.get("alloc", 14))
            wipe = bool(body.get("wipe", True))
            os_name = body.get("os_name") or Path(image_path).name or "Upstream Linux"
            username = body.get("username", "ubuntu")
            password = body.get("password", "ubuntu")
            hostname = body.get("hostname", "galaxy-s8")
            wifi_ssid = body.get("wifi_ssid", "")
            wifi_password = body.get("wifi_password", "")
            storage_target = body.get("storage_target") or params.get("storage_target", "internal")
            install_hw_pack = bool(body.get("install_hw_pack", True))
            res = self._start_flash_job(
                image_path=image_path,
                alloc_gb=alloc_gb,
                wipe=wipe,
                os_name=os_name,
                username=username,
                password=password,
                hostname=hostname,
                wifi_ssid=wifi_ssid,
                wifi_password=wifi_password,
                storage_target=storage_target,
                install_hw_pack=install_hw_pack,
            )
            self._send_json(res)
            return

        if path == "/api/flash/cancel":
            self.state.flasher.cancel()
            with self.state.lock:
                self.state.flash_state["status"] = "CANCELLED"
                self.state.flash_state["active"] = False
            self._send_json({"cancelled": True})
            return

        if path in ("/api/hardware/install", "/api/hardware/inject"):
            install_vnc = bool(body.get("install_vnc", False))
            ok, version, log_out = self.state.device.install_hardware_pack(install_vnc=install_vnc)
            self.state.refresh_telemetry_async()
            self._send_json({
                "success": ok,
                "hw_pack_installed": ok,
                "version": version,
                "log": log_out,
            })
            return

        if path == "/api/hardware/vnc_setup":
            ok, out = self.state.adb.exec_ssh("/usr/local/bin/s8-vnc-setup.sh 2>&1", timeout=300)
            self._send_json({"success": ok, "log": out})
            return

        if path == "/api/wifi/connect":
            ssid = body.get("ssid") or params.get("ssid", "")
            pw = body.get("password") or body.get("pass") or params.get("pass", "")
            if not ssid:
                self._send_json({"success": False, "message": "SSID is required"})
                return
            ok, msg = self.state.device.connect_wifi(ssid, pw)
            self.state.refresh_telemetry_async()
            self._send_json({"success": ok, "status": "connected" if ok else "failed", "ssid": ssid, "message": msg})
            return

        if path == "/api/config/apply":
            hostname = (body.get("hostname") or "").strip()
            if not hostname:
                self._send_json({"success": False, "message": "Hostname required"})
                return
            safe_host = "".join(c for c in hostname if c.isalnum() or c in "-.") or "galaxy-s8"
            out = self.state.adb.exec_os(f"hostnamectl set-hostname '{safe_host}' 2>/dev/null || echo '{safe_host}' > /etc/hostname")
            self._send_json({"success": True, "hostname": safe_host, "output": out})
            return

        if path == "/api/exec":
            merged = dict(params)
            merged.update({k: str(v) for k, v in body.items()})
            self._handle_exec(merged)
            return

        if path == "/api/reboot":
            target = body.get("target") or params.get("target", "system")
            ok, msg = self.state.device.reboot_device(target)
            self._send_json({"success": ok, "target": target, "message": msg})
            return

        if path == "/api/torch":
            on = int(body.get("state", params.get("state", 0))) > 0
            ok = self.state.device.set_torch(1 if on else 0)
            self._send_json({"torch": 1 if on else 0, "success": bool(ok)})
            return

        if path == "/api/haptic":
            ms = int(body.get("ms", params.get("ms", 120)))
            ok = self.state.device.pulse_haptic(ms)
            self._send_json({"haptic": "pulsed", "ms": ms, "success": bool(ok)})
            return

        if path == "/api/versions/rollback":
            target_type = body.get("target_type") or params.get("target_type", "ap")
            ver = body.get("version") or params.get("version", "")
            live = bool(body.get("live", False))
            if not ver:
                self._send_json({"success": False, "error": "Version is required"}, status=HTTPStatus.BAD_REQUEST)
                return
            flag = "--rollback-ap" if target_type == "ap" else "--rollback-hw"
            cmd = [sys.executable, str(REPO_ROOT / "scripts" / "version_manager.py"), flag, str(ver)]
            if live:
                cmd.append("--live")
            res = subprocess.run(cmd, capture_output=True, text=True)
            self._send_json({
                "success": res.returncode == 0,
                "target_type": target_type,
                "version": ver,
                "live": live,
                "output": (res.stdout + "\n" + res.stderr).strip(),
            })
            return

        self._send_json({"error": f"Unknown endpoint: {path}"}, status=HTTPStatus.NOT_FOUND)

    def _build_distro_list(self) -> List[Dict[str, Any]]:
        catalog = self.state.distros.list_catalog()
        seen_paths = {Path(c["local_path"]).resolve() for c in catalog}
        items: List[Dict[str, Any]] = []
        for entry in catalog:
            items.append({
                "id": entry["id"],
                "name": entry["name"],
                "vendor": entry["vendor"],
                "version": entry.get("version", "latest"),
                "verification_status": entry.get("verification_status", "READY_TO_TEST"),
                "verified_with_ap": entry.get("verified_with_ap", AP_VERSION),
                "verified_with_hw_pack": entry.get("verified_with_hw_pack", HW_PACK_VERSION),
                "verification_notes": entry.get("verification_notes", ""),
                "filename": entry["filename"],
                "path": entry["local_path"],
                "size_mb": round(entry["local_bytes"] / (1024 * 1024), 1),
                "type": entry["format"].upper(),
                "downloaded": entry["downloaded"],
                "verified": entry["downloaded"] and bool(entry.get("sha256")),
                "sha256": entry.get("sha256", ""),
                "url": entry["url"],
                "recommended_gb": entry["recommended_gb"],
                "desktop": entry["desktop"],
                "description": entry["description"],
            })

        # Discover any user-provided valid upstream images in distros/
        if DISTROS_DIR.is_dir():
            for p in sorted(DISTROS_DIR.iterdir()):
                if not p.is_file() or p.resolve() in seen_paths:
                    continue
                lower = p.name.lower()
                if any(lower.endswith(ext) for ext in (".img.xz", ".img", ".raw", ".tar.xz", ".tar.gz", ".tgz")):
                    items.append({
                        "id": p.stem,
                        "name": f"{p.name} (Local Image)",
                        "vendor": "Local",
                        "filename": p.name,
                        "path": str(p),
                        "size_mb": round(p.stat().st_size / (1024 * 1024), 1),
                        "type": "RAW ROOTFS" if (".img" in lower or ".raw" in lower) else "ROOTFS TARBALL",
                        "downloaded": True,
                        "verified": False,
                        "sha256": "",
                        "url": "",
                        "recommended_gb": 10,
                        "desktop": "desktop" in lower,
                        "description": "Local user image in distros/.",
                    })
        return items

    def _handle_exec(self, params: Dict[str, str]):
        cmd = params.get("cmd", "").strip()
        env = params.get("env", "os")
        transport = params.get("transport", "auto")
        if not cmd:
            self._send_json({"output": "", "transport": transport, "env": env})
            return

        if transport == "rwp":
            ip = params.get("ip") or getattr(self.state.adb, "wifi_ip", "") or "192.168.0.232"
            out = self.state.adb.exec_rwp(cmd, ip=ip)
        elif transport == "ssh":
            _, out = self.state.adb.exec_ssh(cmd)
        else:
            out = self.state.adb.exec_env(cmd, env=env)
        self._send_json({"output": out, "transport": transport, "env": env})

    def _resolve_screen_url(self) -> str:
        t = self.state.adb.detect_transport()
        if t["mode"] == "ssh_usb":
            return f"http://{RNDIS_DEFAULT_IP}:6080/vnc.html?autoconnect=1&password=ubuntu"
        if t["mode"] == "ssh_wifi" and t["host"]:
            return f"http://{t['host']}:6080/vnc.html?autoconnect=1&password=ubuntu"
        if self.state.adb.is_connected():
            self.state.adb.forward(6080, 6080)
        return "http://127.0.0.1:6080/vnc.html?autoconnect=1&password=ubuntu"

    def _start_flash_job(
        self,
        image_path: str,
        alloc_gb: int,
        wipe: bool,
        os_name: str,
        username: str,
        password: str,
        hostname: str,
        wifi_ssid: str,
        wifi_password: str,
        storage_target: str = "internal",
        install_hw_pack: bool = True,
    ) -> Dict[str, Any]:
        with self.state.lock:
            if self.state.flash_state["active"]:
                return {"started": False, "error": "Flash job already in progress."}
            self.state.flash_state.update({
                "active": True,
                "status": "FLASHING",
                "progress": 1,
                "target": os_name,
                "error": "",
                "logs": [f"[INIT] Preparing unmodified {os_name} -> {alloc_gb} GB ({storage_target})..."],
            })

        def _worker():
            def on_log(msg: str):
                self.state.append_flash_log(msg)

            def on_prog(pct: int):
                with self.state.lock:
                    self.state.flash_state["progress"] = pct

            ok, msg = self.state.flasher.flash(
                image_path=image_path,
                alloc_gb=alloc_gb,
                wipe=wipe,
                os_name=os_name,
                username=username,
                password=password,
                hostname=hostname,
                wifi_ssid=wifi_ssid,
                wifi_password=wifi_password,
                storage_target=storage_target,
                install_hw_pack=install_hw_pack,
                log_callback=on_log,
                progress_callback=on_prog,
            )
            with self.state.lock:
                self.state.flash_state["active"] = False
                self.state.flash_state["status"] = "COMPLETE" if ok else "ERROR"
                self.state.flash_state["progress"] = 100 if ok else self.state.flash_state["progress"]
                self.state.flash_state["error"] = "" if ok else msg
                self.state.flash_state["logs"].append(f"[{'DONE' if ok else 'FAIL'}] {msg}")

        threading.Thread(target=_worker, daemon=True).start()
        return {"started": True, "target": os_name, "alloc_gb": alloc_gb}


class S8HttpServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    request_queue_size = 64


def start_server(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    serial: str = DEFAULT_SERIAL,
) -> ThreadingHTTPServer:
    """Create and run the multi-threaded S8 Imager HTTP server."""
    shared_state = S8ControllerState(serial=serial)
    shared_state.refresh_telemetry_async()
    S8RequestHandler.adb_client = shared_state.adb
    S8RequestHandler.device_manager = shared_state.device
    S8RequestHandler.flasher = shared_state.flasher

    class BoundHandler(S8RequestHandler):
        state = shared_state
        adb_client = shared_state.adb
        device_manager = shared_state.device
        flasher = shared_state.flasher

    server = S8HttpServer((host, port), BoundHandler)
    return server


S8ApiHandler = S8RequestHandler
