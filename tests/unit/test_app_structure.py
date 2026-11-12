"""
Unit tests for S8 Imager application architecture and path resolution
"""
import unittest
import sys
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.config import BASE_DIR as CFG_BASE, BIN_DIR, UI_DIR, RESOURCES_DIR, ADB_PATH
from app.core.adb import AdbClient
from app.core.device import DeviceManager
from app.core.flasher import FlasherEngine

class TestAppStructure(unittest.TestCase):

    def test_paths_exist(self):
        self.assertTrue(BIN_DIR.exists(), f"BIN_DIR missing: {BIN_DIR}")
        self.assertTrue(UI_DIR.exists(), f"UI_DIR missing: {UI_DIR}")
        self.assertTrue((UI_DIR / "index.html").exists(), "index.html missing")
        self.assertTrue(RESOURCES_DIR.exists(), f"RESOURCES_DIR missing: {RESOURCES_DIR}")
        self.assertTrue(ADB_PATH.exists(), f"ADB binary missing: {ADB_PATH}")

    def test_adb_client_initialization(self):
        client = AdbClient(serial="ce10171ab3e9620804", adb_path=ADB_PATH)
        self.assertEqual(client.serial, "ce10171ab3e9620804")
        self.assertEqual(client.adb_path, str(ADB_PATH))

    def test_storage_calculation(self):
        adb = AdbClient()
        engine = FlasherEngine(adb)
        calc = engine.calculate_storage(10)
        self.assertEqual(calc["rootfs_gb"], 10.0)
        self.assertEqual(calc["free_data_gb"], 43.7)
        self.assertEqual(calc["total_userdata_gb"], 53.7)

    def test_ui_index_content(self):
        index_html = (UI_DIR / "index.html").read_text(encoding="utf-8")
        self.assertIn("S8 Imager", index_html)
        self.assertIn("roufsweb", index_html)
        self.assertNotIn("CONNECTED:", index_html)
        self.assertNotIn("DISCONNECTED", index_html)

if __name__ == "__main__":
    unittest.main()

