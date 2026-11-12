"""
Layer 2: Integration Test Suite for S8 Imager REST API Endpoints
Runs against an ephemeral live ThreadingHTTPServer instance to contractually
verify JSON schemas, status codes, CORS headers, and device control handlers.
"""
import unittest
from unittest.mock import patch, MagicMock
import urllib.request
import urllib.error
import json
import threading
import socket
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.server.api import start_server
from app.core.adb import AdbClient


def get_free_port() -> int:
    """Finds an available ephemeral port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class TestIntegrationApi(unittest.TestCase):
    """Integration tests running against live S8 Imager HTTP server."""

    @classmethod
    def setUpClass(cls):
        cls.port = get_free_port()
        cls.host = "127.0.0.1"
        cls.base_url = f"http://{cls.host}:{cls.port}"

        # Start live server on ephemeral port
        cls.server = start_server(host=cls.host, port=cls.port, serial="ce10171ab3e9620804")
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.server_thread.join(timeout=2)

    def fetch_json(self, path: str) -> tuple[int, dict]:
        """Helper to fetch and parse JSON from the live server."""
        url = f"{self.base_url}{path}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return resp.status, data

    def test_static_index_html(self):
        """Verifies serving of the main Bento grid HTML."""
        url = f"{self.base_url}/"
        with urllib.request.urlopen(url, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            self.assertIn("text/html", resp.headers.get("Content-Type", ""))
            content = resp.read().decode("utf-8")
            self.assertIn("S8 Imager", content)
            self.assertIn("roufsweb", content)

    def test_api_status_schema(self):
        """Verifies /api/status telemetry contract."""
        status, data = self.fetch_json("/api/status")
        self.assertEqual(status, 200)
        self.assertIn("connected", data)
        self.assertIn("serial", data)
        self.assertIn("state", data)
        self.assertIn("os", data)
        self.assertIn("cpu", data)
        self.assertIn("ram_free", data)
        self.assertIn("battery", data)
        self.assertIn("temp", data)
        self.assertIn("wifi_ip", data)

    def test_api_torch_toggle(self):
        """Verifies /api/torch turns on and off."""
        status, data = self.fetch_json("/api/torch?state=1")
        self.assertEqual(status, 200)
        self.assertEqual(data.get("torch"), 1)
        self.assertTrue(data.get("success"))

        status, data = self.fetch_json("/api/torch?state=0")
        self.assertEqual(status, 200)
        self.assertEqual(data.get("torch"), 0)
        self.assertTrue(data.get("success"))

    def test_api_haptic_pulse(self):
        """Verifies /api/haptic pulses for given duration."""
        status, data = self.fetch_json("/api/haptic?ms=100")
        self.assertEqual(status, 200)
        self.assertEqual(data.get("haptic"), "pulsed")
        self.assertEqual(data.get("ms"), 100)
        self.assertTrue(data.get("success"))

    def test_api_exec_ap_mode(self):
        """Verifies interactive command execution in AP mode."""
        status, data = self.fetch_json("/api/exec?cmd=echo+vibe_coding_test&env=ap")
        self.assertEqual(status, 200)
        self.assertIn("output", data)

    @patch.object(AdbClient, "exec_rwp", return_value="rwp_protocol_test\n")
    def test_api_exec_rwp_transport(self, mock_rwp):
        """Verifies command execution with RWP Wi-Fi transport."""
        status, data = self.fetch_json("/api/exec?cmd=echo+rwp_protocol_test&env=os&transport=rwp")
        self.assertEqual(status, 200)
        self.assertIn("output", data)
        self.assertEqual(data.get("transport"), "rwp")
        self.assertEqual(data.get("env"), "os")

    def test_api_wifi_scan(self):
        """Verifies /api/wifi/scan returns SSID list."""
        status, data = self.fetch_json("/api/wifi/scan")
        self.assertEqual(status, 200)
        self.assertIn("ssids", data)
        self.assertIsInstance(data["ssids"], list)

    def test_api_wifi_connect(self):
        """Verifies /api/wifi/connect initiates connection."""
        status, data = self.fetch_json("/api/wifi/connect?ssid=TestSSID&pass=TestPass")
        self.assertEqual(status, 200)
        self.assertEqual(data.get("status"), "connecting")
        self.assertEqual(data.get("ssid"), "TestSSID")

    @patch("webbrowser.open")
    def test_api_screen_launcher(self, mock_browser):
        """Verifies /api/screen opens virtual display."""
        status, data = self.fetch_json("/api/screen")
        self.assertEqual(status, 200)
        self.assertEqual(data.get("screen"), "opened")
        self.assertIn("url", data)

    def test_api_storage_info(self):
        """Verifies /api/storage/info contract and allocation math."""
        status, data = self.fetch_json("/api/storage/info?alloc=16")
        self.assertEqual(status, 200)
        self.assertEqual(data.get("rootfs_gb"), 16.0)
        self.assertEqual(data.get("free_data_gb"), 37.7)
        self.assertEqual(data.get("total_userdata_gb"), 53.7)
        self.assertTrue(data.get("clean_supported"))

    def test_api_flash_trigger(self):
        """Verifies /api/flash initiates pre-flight and validates parameters."""
        status, data = self.fetch_json("/api/flash?target=Ubuntu+24.04&alloc=32&clean=1")
        self.assertEqual(status, 200)
        self.assertEqual(data.get("status"), "ready")
        self.assertEqual(data.get("target"), "Ubuntu 24.04")
        self.assertEqual(data.get("alloc_gb"), 32)
        self.assertTrue(data.get("clean"))
        self.assertIn("pre_env", data)

    def test_api_flash_status_endpoint(self):
        """Verifies /api/flash/status returns execution telemetry and logs."""
        status, data = self.fetch_json("/api/flash/status")
        self.assertEqual(status, 200)
        self.assertIn("status", data)
        self.assertIn("progress", data)
        self.assertIn("logs", data)
        self.assertIsInstance(data["logs"], list)

    def test_api_distros_endpoint(self):
        """Verifies /api/distros returns scanned OS distribution images."""
        status, data = self.fetch_json("/api/distros")
        self.assertEqual(status, 200)
        self.assertIn("distros", data)
        self.assertIsInstance(data["distros"], list)


if __name__ == "__main__":
    unittest.main()

