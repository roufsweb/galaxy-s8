#!/usr/bin/env python3
"""
tests/services/test_virtual_environments.py -- Automated Unit & Live S8 Virtual Environment Test Suite
Verifies isolated multi-OS virtual environment capabilities (Kali Linux, OpenWrt, Alpine, Arch Linux)
running concurrently on the live Samsung Galaxy S8 without wiping the host Golden Ubuntu OS.
"""

import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
DESKTOP_APP_DIR = REPO_ROOT / "desktop-app"

import sys  # noqa: E402

sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(DESKTOP_APP_DIR))

from app.core.adb import AdbClient  # noqa: E402
from s8_venv_manager import S8VenvManager, get_distro_profiles  # noqa: E402


class TestVirtualEnvironments(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mgr = S8VenvManager()
        cls.adb = cls.mgr.adb
        cls.is_live = cls.adb.is_connected() or bool(cls.adb.active_ssh_host())

    def test_01_catalog_profiles(self):
        """Verify all 11 upstream OS profiles are cataloged with unique IDs and network indices."""
        profiles = get_distro_profiles()
        self.assertEqual(len(profiles), 11, "Must support all 11 upstream OS profiles")
        ids = [p.id for p in profiles]
        self.assertEqual(len(ids), len(set(ids)), "Distro profile IDs must be unique")
        net_indices = [p.net_idx for p in profiles]
        self.assertEqual(len(net_indices), len(set(net_indices)), "Virtual network indices must be unique")
        for p in profiles:
            self.assertTrue(p.filename, f"Profile {p.id} must define a source filename")
            self.assertIn(p.pkg_mgr, ("apt", "opkg", "apk", "pacman", "haos"))

    def test_02_s8_runner_script_installed(self):
        """Verify that the isolated namespace runner script is installed on the live Galaxy S8."""
        if not self.is_live:
            self.skipTest("Galaxy S8 offline")
        out = self.adb.exec_os("test -x /mnt/android_data/venvs/_bin/s8venv_run.sh && echo RUNNER_OK")
        self.assertIn("RUNNER_OK", out, "On-device namespace runner must be executable")

    def test_03_live_openwrt_venv(self):
        """Verify isolated OpenWrt virtual environment router execution, UCI, and s8ctl."""
        if not self.is_live:
            self.skipTest("Galaxy S8 offline")
        rc, out = self.mgr.exec_s8_venv(
            "openwrt-23.05",
            "which opkg uci procd; uci show dropbear | head -n 3; s8ctl --version"
        )
        self.assertEqual(rc, 0, f"OpenWrt venv command failed: {out}")
        self.assertIn("/bin/opkg", out)
        self.assertIn("/sbin/uci", out)
        self.assertIn("s8ctl v1.0.3", out)

    def test_04_live_kali_nethunter_venv(self):
        """Verify isolated Kali Linux virtual environment with raw packet socket permissions."""
        if not self.is_live:
            self.skipTest("Galaxy S8 offline")
        rc, out = self.mgr.exec_s8_venv(
            "kali-nethunter",
            "which apt-get dpkg; id; grep -q aid_net_raw /etc/group && echo RAW_SOCK_OK; s8ctl --version"
        )
        self.assertEqual(rc, 0, f"Kali venv command failed: {out}")
        self.assertIn("/usr/bin/apt-get", out)
        self.assertIn("RAW_SOCK_OK", out)
        self.assertIn("s8ctl v1.0.3", out)

    def test_05_live_alpine_venv(self):
        """Verify isolated Alpine Linux virtual environment with apk package manager."""
        if not self.is_live:
            self.skipTest("Galaxy S8 offline")
        rc, out = self.mgr.exec_s8_venv(
            "alpine-3.20",
            "which apk; apk info | wc -l; s8ctl --version"
        )
        self.assertEqual(rc, 0, f"Alpine venv command failed: {out}")
        self.assertIn("/sbin/apk", out)
        self.assertIn("s8ctl v1.0.3", out)

    def test_06_live_arch_venv(self):
        """Verify isolated Arch Linux ARM virtual environment with pacman package manager."""
        if not self.is_live:
            self.skipTest("Galaxy S8 offline")
        rc, out = self.mgr.exec_s8_venv(
            "arch-arm64",
            "which pacman; pacman -Q | wc -l; s8ctl --version"
        )
        self.assertEqual(rc, 0, f"Arch Linux venv command failed: {out}")
        self.assertIn("/usr/sbin/pacman", out)
        self.assertIn("s8ctl v1.0.3", out)


if __name__ == "__main__":
    unittest.main()

