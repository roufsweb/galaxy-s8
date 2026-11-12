"""
S8 Imager - Quick Launcher Entrypoint
by roufsweb
"""
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.main import main

if __name__ == "__main__":
    main()

