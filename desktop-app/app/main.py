"""
S8 Imager - Master Desktop Application Entrypoint
by roufsweb
"""
from pathlib import Path
import argparse
import os
import sys
import threading
import time
import subprocess
import webbrowser

# Ensure stdio streams exist in windowed PyInstaller mode
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

from .config import APP_NAME, APP_VERSION, APP_AUTHOR, DEFAULT_HOST, DEFAULT_PORT, DEFAULT_SERIAL, UI_DIR
from .server.api import start_server

def launch_native_window(url: str):
    """Attempts to launch an ultra-clean frameless app window via Microsoft Edge or Chrome."""
    edge_paths = [
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
    ]
    for p in edge_paths:
        if p.exists():
            subprocess.Popen([str(p), f"--app={url}", "--window-size=1280,800"])
            return

    # Fallback to default system browser
    webbrowser.open(url)

def main():
    parser = argparse.ArgumentParser(description=f"{APP_NAME} v{APP_VERSION} by {APP_AUTHOR}")
    parser.add_argument("--serial", default=DEFAULT_SERIAL, help="Target device serial (default: ce10171ab3e9620804)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Server port (default: {DEFAULT_PORT})")
    parser.add_argument("--host", default=DEFAULT_HOST, help=f"Server host (default: {DEFAULT_HOST})")
    parser.add_argument("--serve-only", action="store_true", help="Run background server only without opening window")
    parser.add_argument("--legacy-gui", action="store_true", help="Launch fallback CustomTkinter GUI")
    args = parser.parse_args()

    if args.legacy_gui:
        try:
            from .gui_legacy import main as run_legacy_gui
            run_legacy_gui()
            return
        except ImportError as e:
            print(f"[!] Legacy GUI module error: {e}")
            sys.exit(1)

    # 1. Start Server
    server = start_server(host=args.host, port=args.port, serial=args.serial)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    app_url = f"http://{args.host}:{args.port}/"
    print(f"[*] {APP_NAME} v{APP_VERSION} running at {app_url}")

    # 2. Launch Native Window
    if not args.serve_only:
        launch_native_window(app_url)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[*] Shutting down...")
        server.shutdown()

if __name__ == "__main__":
    main()

