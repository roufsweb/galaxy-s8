"""
Layer 4: Aggressive Performance & Latency Budget Test Suite
Enforces strict response time budgets on S8 Imager REST API endpoints,
static asset serving, and telemetry parsing logic to prevent performance regressions.
"""
import unittest
import urllib.request
import time
import statistics
import threading
import socket
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.server.api import start_server


def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class TestPerformanceBudget(unittest.TestCase):
    """Enforces strict latency and throughput budgets."""

    @classmethod
    def setUpClass(cls):
        cls.port = get_free_port()
        cls.host = "127.0.0.1"
        cls.base_url = f"http://{cls.host}:{cls.port}"

        cls.server = start_server(host=cls.host, port=cls.port, serial="ce10171ab3e9620804")
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.server_thread.join(timeout=2)

    def test_static_asset_latency_budget(self):
        """Budget: Static index.html must be served in under 30ms."""
        url = f"{self.base_url}/"
        latencies = []
        for _ in range(15):
            t0 = time.perf_counter()
            with urllib.request.urlopen(url, timeout=3) as resp:
                resp.read()
            latencies.append((time.perf_counter() - t0) * 1000.0)

        p95 = statistics.quantiles(latencies, n=20)[18]
        avg = statistics.mean(latencies)
        print(f"\n[PERF] Static Asset Delivery: Avg={avg:.2f}ms, p95={p95:.2f}ms")
        self.assertLess(avg, 30.0, f"Average static asset latency exceeded 30ms budget: {avg:.2f}ms")

    def test_api_status_latency_budget(self):
        """Budget: /api/status telemetry responses must be under 100ms p95."""
        url = f"{self.base_url}/api/status"
        # Warm-up request to prime the background cache
        with urllib.request.urlopen(url, timeout=3) as resp:
            resp.read()

        latencies = []
        for _ in range(25):
            t0 = time.perf_counter()
            with urllib.request.urlopen(url, timeout=3) as resp:
                resp.read()
            latencies.append((time.perf_counter() - t0) * 1000.0)

        p95 = statistics.quantiles(latencies, n=20)[18]
        avg = statistics.mean(latencies)
        print(f"[PERF] /api/status Telemetry: Avg={avg:.2f}ms, p95={p95:.2f}ms")
        self.assertLess(avg, 25.0, f"Average /api/status latency exceeded 25ms budget: {avg:.2f}ms")
        self.assertLess(p95, 50.0, f"p95 /api/status latency exceeded 50ms budget: {p95:.2f}ms")


if __name__ == "__main__":
    unittest.main()
