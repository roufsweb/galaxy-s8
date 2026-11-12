"""
S8 Imager - Local Development Server Launcher
by roufsweb
"""
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.server.api import start_server
from app.config import DEFAULT_HOST, DEFAULT_PORT, DEFAULT_SERIAL

if __name__ == "__main__":
    server = start_server(host=DEFAULT_HOST, port=DEFAULT_PORT, serial=DEFAULT_SERIAL)
    print(f"[*] S8 Imager Development Server active at http://{DEFAULT_HOST}:{DEFAULT_PORT}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Server stopped.")
        server.shutdown()
