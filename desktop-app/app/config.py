"""
S8 Imager - Central Configuration & Dynamic Path Resolution
Author: roufsweb
"""
from pathlib import Path
import os
import sys

def get_base_dir() -> Path:
    """Resolves the application root directory in both source and frozen PyInstaller modes."""
    if getattr(sys, "frozen", False):
        # Frozen executable (PyInstaller)
        if hasattr(sys, "_MEIPASS"):
            return Path(sys._MEIPASS)
        return Path(sys.executable).resolve().parent
    # Standard Python source module (desktop-app/app/config.py -> desktop-app/)
    return Path(__file__).resolve().parent.parent

BASE_DIR = get_base_dir()
REPO_ROOT = BASE_DIR.parent if (BASE_DIR.parent / "packages").exists() else BASE_DIR
BIN_DIR = BASE_DIR / "bin"
ADB_PATH = BIN_DIR / ("adb.exe" if sys.platform == "win32" else "adb")
UI_DIR = BASE_DIR / "ui"
RESOURCES_DIR = BASE_DIR / "resources" / "scripts"
RESOURCES_BIN_DIR = BASE_DIR / "resources" / "bin"
DISTROS_DIR = REPO_ROOT / "distros"
PACKAGES_DIR = REPO_ROOT / "packages" / "dist"
if not PACKAGES_DIR.exists():
    PACKAGES_DIR = BASE_DIR / "resources" / "packages"
RNDIS_DEFAULT_IP = os.environ.get("S8_RNDIS_IP", "192.168.7.2")

# Default Target Device Configuration
DEFAULT_SERIAL = os.environ.get("S8_SERIAL", "ce10171ab3e9620804")
DEFAULT_PORT = int(os.environ.get("S8_PORT", 8999))
DEFAULT_HOST = "127.0.0.1"
HW_PACK_VERSION = "1.0.2"
AP_VERSION = "3.0.0"
KERNEL_VERSION = "4.4.111-s8-universal-v3"

# Metadata
APP_NAME = "S8 Imager"
APP_SUBTITLE = "Universal OS Flasher & Hardware Manager"
APP_AUTHOR = "roufsweb"
APP_VERSION = "2.6.0"

# Target Hardware Specs
TARGET_SOC = "Samsung Exynos 8895 Octa"
TARGET_MODEL = "Galaxy S8 (SM-G950N)"
USERDATA_PARTITION = "/dev/block/sda24"
USERDATA_TOTAL_GB = 53.7

# Ensure ADB path fallback to system PATH if binary not found in bin/
if not ADB_PATH.exists():
    system_adb = os.popen("where adb" if sys.platform == "win32" else "which adb").read().strip().splitlines()
    if system_adb:
        ADB_PATH = Path(system_adb[0])

