"""
Official unmodified upstream ARM64 Linux catalog, downloader, and SHA-256 verifier.
All images listed here come strictly from official upstream release mirrors.
"""

import hashlib
import threading
import time
import urllib.request
from pathlib import Path
from typing import Callable, Dict, List, Optional

from app.config import DISTROS_DIR

UPSTREAM_DISTROS: List[Dict] = [
    {
        "id": "ubuntu-desktop-24.04",
        "name": "Ubuntu 24.04.5 LTS Desktop (Official Upstream)",
        "vendor": "Canonical",
        "filename": "ubuntu-24.04.5-preinstalled-desktop-arm64.img.xz",
        "url": "https://cdimage.ubuntu.com/releases/24.04/release/ubuntu-24.04.5-preinstalled-desktop-arm64+raspi.img.xz",
        "sha256_url": "https://cdimage.ubuntu.com/releases/24.04/release/SHA256SUMS",
        "sha256_match_name": "ubuntu-24.04.5-preinstalled-desktop-arm64+raspi.img.xz",
        "sha256": "f4a333eccfda8f1ae01a03da5ba6effb52fe32becc7dde27dc9a269200ac823a",
        "format": "img.xz",
        "recommended_gb": 14,
        "desktop": True,
        "description": "Unmodified official Canonical Ubuntu 24.04.5 ARM64 GNOME Desktop image.",
    },
    {
        "id": "ubuntu-server-24.04",
        "name": "Ubuntu 24.04 Server Rootfs (Official Upstream)",
        "vendor": "Canonical",
        "filename": "ubuntu-24.04-server-rootfs-arm64.tar.xz",
        "url": "https://cloud-images.ubuntu.com/releases/noble/release/ubuntu-24.04-server-cloudimg-arm64-root.tar.xz",
        "sha256_url": "https://cloud-images.ubuntu.com/releases/noble/release/SHA256SUMS",
        "sha256_match_name": "ubuntu-24.04-server-cloudimg-arm64-root.tar.xz",
        "sha256": "",
        "format": "tar.xz",
        "recommended_gb": 8,
        "desktop": False,
        "description": "Clean official Ubuntu Server 24.04 rootfs archive with full apt & systemd.",
    },
    {
        "id": "ubuntu-base-24.04",
        "name": "Ubuntu 24.04.5 Minimal Base (Official Upstream)",
        "vendor": "Canonical",
        "filename": "ubuntu-base-24.04.5-base-arm64.tar.gz",
        "url": "https://cdimage.ubuntu.com/ubuntu-base/releases/24.04/release/ubuntu-base-24.04.5-base-arm64.tar.gz",
        "sha256_url": "https://cdimage.ubuntu.com/ubuntu-base/releases/24.04/release/SHA256SUMS",
        "sha256_match_name": "ubuntu-base-24.04.5-base-arm64.tar.gz",
        "sha256": "",
        "format": "tar.gz",
        "recommended_gb": 4,
        "desktop": False,
        "description": "Ultra-light 30 MB official Ubuntu base rootfs for custom CLI setups.",
    },
    {
        "id": "debian-12",
        "name": "Debian 12 Bookworm Generic (Official Upstream)",
        "vendor": "Debian",
        "filename": "debian-12-generic-arm64.tar.xz",
        "url": "https://cloud.debian.org/images/cloud/bookworm/latest/debian-12-generic-arm64.tar.xz",
        "sha256_url": "https://cloud.debian.org/images/cloud/bookworm/latest/SHA256SUMS",
        "sha256_match_name": "debian-12-generic-arm64.tar.xz",
        "sha256": "",
        "format": "tar.xz",
        "recommended_gb": 6,
        "desktop": False,
        "description": "Official unmodified Debian 12 Bookworm ARM64 tarball.",
    },
    {
        "id": "kali-nethunter",
        "name": "Kali Linux ARM64 Minimal (Official Upstream)",
        "vendor": "Offensive Security",
        "filename": "kali-nethunter-rootfs-minimal-arm64.tar.xz",
        "url": "https://kali.download/nethunter-images/current/rootfs/kali-nethunter-rootfs-minimal-arm64.tar.xz",
        "sha256_url": "",
        "sha256_match_name": "",
        "sha256": "",
        "format": "tar.xz",
        "recommended_gb": 8,
        "desktop": False,
        "description": "Official upstream Kali Linux ARM64 minimal rootfs.",
    },
    {
        "id": "alpine-3.20",
        "name": "Alpine Linux 3.20 Minirootfs (Official Upstream)",
        "vendor": "Alpine",
        "filename": "alpine-minirootfs-3.20.3-aarch64.tar.gz",
        "url": "https://dl-cdn.alpinelinux.org/alpine/v3.20/releases/aarch64/alpine-minirootfs-3.20.3-aarch64.tar.gz",
        "sha256_url": "https://dl-cdn.alpinelinux.org/alpine/v3.20/releases/aarch64/alpine-minirootfs-3.20.3-aarch64.tar.gz.sha256",
        "sha256_match_name": "alpine-minirootfs-3.20.3-aarch64.tar.gz",
        "sha256": "",
        "format": "tar.gz",
        "recommended_gb": 2,
        "desktop": False,
        "description": "Ultra-fast ~4 MB official Alpine Linux musl/OpenRC rootfs.",
    },
    {
        "id": "arch-arm64",
        "name": "Arch Linux ARM (Official Upstream)",
        "vendor": "Arch Linux ARM",
        "filename": "ArchLinuxARM-aarch64-latest.tar.gz",
        "url": "http://os.archlinuxarm.org/os/ArchLinuxARM-aarch64-latest.tar.gz",
        "sha256_url": "",
        "sha256_match_name": "",
        "sha256": "",
        "format": "tar.gz",
        "recommended_gb": 6,
        "desktop": False,
        "description": "Official rolling-release Arch Linux ARM generic aarch64 rootfs.",
    },
]


class DistroManager:
    """Manages listing, downloading, and SHA-256 verification of upstream OS images."""

    def __init__(self, distros_dir: Optional[Path] = None):
        self.distros_dir = Path(distros_dir or DISTROS_DIR)
        self.distros_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self.download_state: Dict = {
            "active": False,
            "id": "",
            "filename": "",
            "bytes_done": 0,
            "bytes_total": 0,
            "percent": 0,
            "status": "IDLE",
            "verified": False,
            "error": "",
        }

    def list_catalog(self) -> List[Dict]:
        items = []
        for entry in UPSTREAM_DISTROS:
            local_path = self.distros_dir / entry["filename"]
            item = dict(entry)
            item["local_path"] = str(local_path)
            item["downloaded"] = local_path.is_file()
            item["local_bytes"] = local_path.stat().st_size if item["downloaded"] else 0
            items.append(item)
        return items

    def get_entry(self, distro_id: str) -> Optional[Dict]:
        for entry in UPSTREAM_DISTROS:
            if entry["id"] == distro_id or entry["filename"] == distro_id:
                return dict(entry)
        return None

    @staticmethod
    def compute_sha256(path: Path) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            while True:
                chunk = f.read(1024 * 1024)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def fetch_expected_sha256(entry: Dict) -> str:
        if entry.get("sha256"):
            return entry["sha256"].strip().lower()
        sha_url = entry.get("sha256_url", "")
        if not sha_url:
            return ""
        try:
            with urllib.request.urlopen(sha_url, timeout=15) as resp:
                body = resp.read().decode("utf-8", errors="ignore")
            target = entry.get("sha256_match_name") or entry["filename"]
            for line in body.splitlines():
                if target in line:
                    token = line.strip().split()[0].lower()
                    if len(token) == 64:
                        return token
        except Exception:
            pass
        return ""

    def verify_file(self, distro_id: str) -> Dict:
        entry = self.get_entry(distro_id)
        if not entry:
            return {"ok": False, "error": f"Unknown distro: {distro_id}"}
        local_path = self.distros_dir / entry["filename"]
        if not local_path.is_file():
            return {"ok": False, "error": f"File not downloaded: {local_path}"}
        actual = self.compute_sha256(local_path)
        expected = self.fetch_expected_sha256(entry)
        matched = (actual == expected) if expected else True
        return {
            "ok": matched,
            "id": entry["id"],
            "filename": entry["filename"],
            "sha256": actual,
            "expected_sha256": expected or "not-published-upstream",
            "verified": bool(expected and actual == expected),
            "bytes": local_path.stat().st_size,
        }

    def start_download(self, distro_id: str, on_done: Optional[Callable[[Dict], None]] = None) -> Dict:
        entry = self.get_entry(distro_id)
        if not entry:
            return {"started": False, "error": f"Unknown upstream image: {distro_id}"}
        with self._lock:
            if self.download_state["active"]:
                return {"started": False, "error": f"Download already in progress: {self.download_state['filename']}"}
            self.download_state.update({
                "active": True,
                "id": entry["id"],
                "filename": entry["filename"],
                "bytes_done": 0,
                "bytes_total": 0,
                "percent": 0,
                "status": "DOWNLOADING",
                "verified": False,
                "error": "",
            })

        def _worker():
            part_path = self.distros_dir / (entry["filename"] + ".part")
            final_path = self.distros_dir / entry["filename"]
            try:
                req = urllib.request.Request(entry["url"], headers={"User-Agent": "S8-Imager/1.0"})
                with urllib.request.urlopen(req, timeout=30) as resp:
                    total = int(resp.headers.get("Content-Length") or 0)
                    with self._lock:
                        self.download_state["bytes_total"] = total
                    done = 0
                    h = hashlib.sha256()
                    with open(part_path, "wb") as out:
                        while True:
                            chunk = resp.read(512 * 1024)
                            if not chunk:
                                break
                            out.write(chunk)
                            h.update(chunk)
                            done += len(chunk)
                            with self._lock:
                                self.download_state["bytes_done"] = done
                                self.download_state["percent"] = int((done / total) * 100) if total > 0 else 0
                actual_sha = h.hexdigest()
                with self._lock:
                    self.download_state["status"] = "VERIFYING_SHA256"
                expected_sha = self.fetch_expected_sha256(entry)
                if expected_sha and actual_sha != expected_sha:
                    part_path.unlink(missing_ok=True)
                    raise ValueError(f"SHA-256 mismatch (got {actual_sha[:12]}, expected {expected_sha[:12]})")
                part_path.replace(final_path)
                with self._lock:
                    self.download_state.update({
                        "active": False,
                        "status": "COMPLETE",
                        "percent": 100,
                        "verified": bool(expected_sha),
                        "error": "",
                    })
                if on_done:
                    on_done(dict(self.download_state))
            except Exception as exc:
                part_path.unlink(missing_ok=True)
                with self._lock:
                    self.download_state.update({
                        "active": False,
                        "status": "ERROR",
                        "error": str(exc),
                    })

        threading.Thread(target=_worker, daemon=True).start()
        return {"started": True, "id": entry["id"], "filename": entry["filename"]}

