"""
Layer 1: Unit Test Suite for S8 Imager Core Logic
Validates AdbClient, DeviceManager, FlasherEngine, and config path resolution
with pure logic isolation, mocks, boundary values, and error handling.
"""
import unittest
from unittest.mock import MagicMock, patch
import hashlib
import struct
import subprocess
import tempfile
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.config import (
    BASE_DIR as CFG_BASE,
    BIN_DIR,
    UI_DIR,
    RESOURCES_DIR,
    ADB_PATH,
    DEFAULT_SERIAL,
    USERDATA_TOTAL_GB
)
from app.core.adb import AdbClient
from app.core.device import DeviceManager
from app.core.distros import DistroManager
from app.core.flasher import EXT4_SUPER_MAGIC, FlasherEngine, LINUX_GPT_GUID, detect_linux_partition
from app.core.injector import HardwareInjector


class TestConfigUnit(unittest.TestCase):
    """Verifies directory structures and path resolution."""

    def test_paths_integrity(self):
        self.assertTrue(UI_DIR.exists())
        self.assertTrue((UI_DIR / "index.html").exists())
        self.assertEqual(DEFAULT_SERIAL, "ce10171ab3e9620804")
        self.assertEqual(USERDATA_TOTAL_GB, 53.7)


class TestAdbClientUnit(unittest.TestCase):
    """Tests AdbClient command construction and error handling."""

    def setUp(self):
        self.adb = AdbClient(serial="test_serial_123", adb_path="adb")

    @patch("subprocess.run")
    def test_run_cmd_structure(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=["adb", "-s", "test_serial_123", "get-state"],
            returncode=0,
            stdout="recovery\n",
            stderr=""
        )
        res = self.adb.run_cmd(["get-state"])
        mock_run.assert_called_once()
        called_args = mock_run.call_args[0][0]
        self.assertEqual(called_args, ["adb", "-s", "test_serial_123", "get-state"])
        self.assertEqual(res.stdout.strip(), "recovery")

    @patch("subprocess.run")
    def test_is_connected_matching_serial(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=["adb", "devices"],
            returncode=0,
            stdout="List of devices attached\ntest_serial_123\trecovery\nother_serial\toffline\n",
            stderr=""
        )
        self.assertTrue(self.adb.is_connected())

    @patch("subprocess.run")
    def test_is_connected_missing_serial(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=["adb", "devices"],
            returncode=0,
            stdout="List of devices attached\nsome_other_phone\tdevice\n",
            stderr=""
        )
        self.assertFalse(self.adb.is_connected())

    @patch("subprocess.run")
    def test_shell_timeout_graceful(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["adb", "shell"], timeout=5)
        out = self.adb.shell("sleep 10", timeout=5)
        self.assertIn("ERROR: Shell command timed out", out)

    @patch("subprocess.run")
    def test_exec_rwp_command(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=["ssh", "root@192.168.0.232", "uname -a"],
            returncode=0,
            stdout="Linux Galaxy-S8 4.4.111\n",
            stderr=""
        )
        out = self.adb.exec_rwp("uname -a", ip="192.168.0.232")
        self.assertEqual(out, "Linux Galaxy-S8 4.4.111")
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        self.assertIn("root@192.168.0.232", args)


class TestDeviceManagerUnit(unittest.TestCase):
    """Tests DeviceManager telemetry collection and peripheral controls."""

    def setUp(self):
        self.mock_adb = MagicMock(spec=AdbClient)
        self.mock_adb.serial = "ce10171ab3e9620804"
        self.device = DeviceManager(self.mock_adb)

    def test_offline_telemetry_schema(self):
        self.mock_adb.is_connected.return_value = False
        with patch.object(DeviceManager, "check_wifi_online", return_value=False):
            data = self.device.get_telemetry()
            self.assertFalse(data["connected"])
            self.assertEqual(data["state"], "offline")
            self.assertEqual(data["os"], "None")
            self.assertEqual(data["battery"], "0%")
            self.assertEqual(data["wifi_ip"], "Offline")

    def test_online_telemetry_parser(self):
        self.mock_adb.is_connected.return_value = True
        self.mock_adb.get_state.return_value = "recovery"
        self.mock_adb.shell.return_value = (
            'PRETTY_NAME="Ubuntu 24.04.5 LTS"\n'
            '88\n'
            '412\n'
            'MemTotal: 3670016 kB\n'
            'MemAvailable: 2500000 kB\n'
            '192.168.0.227\n'
        )
        data = self.device.get_telemetry()
        self.assertTrue(data["connected"])
        self.assertEqual(data["state"], "recovery")
        self.assertEqual(data["os"], "Ubuntu 24.04.5 LTS")
        self.assertEqual(data["battery"], "88%")
        self.assertEqual(data["temp"], "41.2°C")
        self.assertIn("GB", data["ram_free"])
        self.assertEqual(data["wifi_ip"], "192.168.0.227")

    def test_torch_control(self):
        self.mock_adb.shell.return_value = ""
        self.assertTrue(self.device.set_torch(1))
        self.assertTrue(self.device.set_torch(0))

    def test_haptic_control(self):
        self.mock_adb.shell.return_value = ""
        self.assertTrue(self.device.pulse_haptic(150))


class TestFlasherEngineUnit(unittest.TestCase):
    """Tests partition mathematics and pre-flash checks."""

    def setUp(self):
        self.mock_adb = MagicMock(spec=AdbClient)
        self.flasher = FlasherEngine(self.mock_adb)

    def test_calculate_storage_tiers(self):
        tier10 = self.flasher.calculate_storage(10)
        self.assertEqual(tier10["rootfs_gb"], 10.0)
        self.assertEqual(tier10["free_data_gb"], 43.7)

        tier16 = self.flasher.calculate_storage(16)
        self.assertEqual(tier16["rootfs_gb"], 16.0)
        self.assertEqual(tier16["free_data_gb"], 37.7)

        tier53 = self.flasher.calculate_storage(53)
        self.assertEqual(tier53["rootfs_gb"], 53.0)
        self.assertEqual(tier53["free_data_gb"], 0.7)

    def test_calculate_storage_boundaries(self):
        min_tier = self.flasher.calculate_storage(4)
        self.assertEqual(min_tier["rootfs_gb"], 4.0)
        self.assertEqual(min_tier["free_data_gb"], 49.7)

        max_tier = self.flasher.calculate_storage(48)
        self.assertEqual(max_tier["rootfs_gb"], 48.0)
        self.assertEqual(max_tier["free_data_gb"], 5.7)

        over_tier = self.flasher.calculate_storage(60)
        self.assertEqual(over_tier["free_data_gb"], 0.0)

    def test_calculate_storage_128gb_variant(self):
        # 128 GB UFS model (~112.5 GB Userdata)
        tier32 = self.flasher.calculate_storage(32, total_gb=112.5)
        self.assertEqual(tier32["rootfs_gb"], 32.0)
        self.assertEqual(tier32["free_data_gb"], 80.5)
        self.assertEqual(tier32["total_userdata_gb"], 112.5)

        tier108 = self.flasher.calculate_storage(108, total_gb=112.5)
        self.assertEqual(tier108["rootfs_gb"], 108.0)
        self.assertEqual(tier108["free_data_gb"], 4.5)

    def test_pre_flash_environment_connected(self):
        self.mock_adb.is_connected.return_value = True
        self.mock_adb.shell.side_effect = ["1", "0", ""]
        env = self.flasher.verify_pre_flash_environment()
        self.assertTrue(env["connected"])
        self.assertTrue(env["partition_ready"])
        self.assertTrue(env["root_ready"])


class TestDistroPartitionAndSeedUnit(unittest.TestCase):
    """Tests MBR/GPT ext4 partition extraction logic, upstream catalog, and Rule 27 seed."""

    def test_detect_linux_partition_raw_ext4(self):
        buf = bytearray(2048)
        struct.pack_into("<H", buf, 1080, EXT4_SUPER_MAGIC)
        offset, size = detect_linux_partition(bytes(buf), total_size=4096)
        self.assertEqual(offset, 0)
        self.assertEqual(size, 4096)

    def test_detect_linux_partition_mbr(self):
        buf = bytearray(2048)
        buf[510:512] = b"\x55\xAA"
        # Entry 0: vfat boot (0x0C) at LBA 2048, 1024 sectors
        buf[446 + 4] = 0x0C
        struct.pack_into("<II", buf, 446 + 8, 2048, 1024)
        # Entry 1: Linux ext4 (0x83) at LBA 4096, 8192 sectors
        buf[462 + 4] = 0x83
        struct.pack_into("<II", buf, 462 + 8, 4096, 8192)
        offset, size = detect_linux_partition(bytes(buf))
        self.assertEqual(offset, 4096 * 512)
        self.assertEqual(size, 8192 * 512)

    def test_detect_linux_partition_gpt(self):
        buf = bytearray(16384)
        buf[512:520] = b"EFI PART"
        struct.pack_into("<Q", buf, 512 + 72, 2)      # part_lba = 2 (offset 1024)
        struct.pack_into("<I", buf, 512 + 80, 4)      # num_entries
        struct.pack_into("<I", buf, 512 + 84, 128)    # entry_size
        entry_pos = 1024
        buf[entry_pos : entry_pos + 16] = LINUX_GPT_GUID
        struct.pack_into("<QQ", buf, entry_pos + 32, 8192, 16383)
        offset, size = detect_linux_partition(bytes(buf))
        self.assertEqual(offset, 8192 * 512)
        self.assertEqual(size, 8192 * 512)

    def test_distro_catalog_and_verify(self):
        with tempfile.TemporaryDirectory() as tmp:
            dm = DistroManager(Path(tmp))
            catalog = dm.list_catalog()
            ubuntu = [d for d in catalog if d["id"] == "ubuntu-desktop-24.04"]
            self.assertEqual(len(ubuntu), 1)
            expected_ubuntu = "f4a333eccfda8f1ae01a03da5ba6effb52fe32becc7dde27dc9a269200ac823a"
            self.assertEqual(ubuntu[0]["sha256"], expected_ubuntu)

            # Corrupt/mismatch check against known Ubuntu SHA-256 (offline safe)
            bad_file = Path(tmp) / ubuntu[0]["filename"]
            bad_file.write_bytes(b"corrupted-sample")
            res_bad = dm.verify_file("ubuntu-desktop-24.04")
            self.assertFalse(res_bad["ok"])
            self.assertFalse(res_bad["verified"])

            # Local-only hash verification (no upstream manifest) + mocked match verification
            sample = Path(tmp) / "ArchLinuxARM-aarch64-latest.tar.gz"
            sample.write_bytes(b"test-arch-payload")
            res_ok = dm.verify_file("arch-arm64")
            self.assertTrue(res_ok["ok"])
            self.assertEqual(res_ok["sha256"], hashlib.sha256(b"test-arch-payload").hexdigest())

            with patch.object(DistroManager, "fetch_expected_sha256", return_value=res_ok["sha256"]):
                res_verified = dm.verify_file("arch-arm64")
                self.assertTrue(res_verified["ok"])
                self.assertTrue(res_verified["verified"])

    def test_minimal_seed_shell_generation(self):
        script = HardwareInjector._build_seed_shell(
            target_root="/mnt/ubuntu",
            username="alice",
            password="secret",
            hostname="s8-box",
            wifi_ssid="MyWiFi",
            wifi_password="wifi_pass_change_me",
        )
        self.assertIn("99-s8-no-fimc.rules", script)
        self.assertIn("system-boot", script)
        self.assertIn("aid_inet:x:3003:", script)
        self.assertIn("192.168.7.2", script)
        self.assertIn("99-s8-rndis-unmanaged.conf", script)
        self.assertIn("graphical.target", script)
        self.assertIn("alice", script)
        self.assertIn("s8-box", script)
        self.assertIn("ffs.adb", script)

    def test_rwp_exec_env_and_telemetry(self):
        client = AdbClient()
        with patch.object(client, "rwp_request", return_value={"output": "ap-ok", "exit_code": 0}) as mock_rwp:
            self.assertEqual(client.exec_env("uname -r", env="ap"), "ap-ok")
            mock_rwp.assert_called_once()

        with patch.object(client, "rwp_request", return_value=None), \
             patch.object(client, "shell", return_value="adb-ok") as mock_sh:
            self.assertEqual(client.exec_env("id", env="ap"), "adb-ok")
            mock_sh.assert_called_once()

        dm = DeviceManager(client)
        rwp_payload = {
            "protocol": "rwp-v1",
            "kernel": "4.4.111-s8-universal-v2",
            "temp_c": 41.2,
            "battery_pct": 88,
            "dp_connected": True,
            "rndis_ip": "192.168.7.2",
            "wlan_ip": "192.168.0.227",
            "lan_iface": "eth0",
            "lan_ip": "192.168.1.55",
            "guest_os": "Alpine Linux 3.20",
        }
        with patch.object(client, "rwp_request", return_value=rwp_payload), \
             patch.object(client, "is_connected", return_value=True):
            tel = dm.get_telemetry()
            self.assertTrue(tel["connected"])
            self.assertEqual(tel["transport"], "rwp_usb")
            self.assertEqual(tel["kernel"], "4.4.111-s8-universal-v2")
            self.assertEqual(tel["lan_ip"], "192.168.1.55")
            self.assertEqual(tel["dp_monitor"], "Connected")


if __name__ == "__main__":
    unittest.main()

