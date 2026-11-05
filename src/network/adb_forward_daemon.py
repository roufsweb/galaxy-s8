import subprocess
import time
import sys

print("ADB_FORWARD_DAEMON_STARTING")
sys.stdout.flush()

while True:
    try:
        # Check if forwards are present
        out = subprocess.check_output(['adb', 'forward', '--list'], stderr=subprocess.STDOUT, timeout=5).decode('utf-8', errors='ignore')
        if 'tcp:6080' not in out or 'tcp:5901' not in out:
            print("Re-establishing ADB forwards (6080, 5901, 2222)...")
            subprocess.call(['adb', 'forward', 'tcp:6080', 'tcp:6080'], timeout=5)
            subprocess.call(['adb', 'forward', 'tcp:5901', 'tcp:5901'], timeout=5)
            subprocess.call(['adb', 'forward', 'tcp:2222', 'tcp:22'], timeout=5)
            print("ADB forwards established successfully!")
            sys.stdout.flush()
    except Exception as e:
        print(f"Error checking/restoring forwards: {e}")
        sys.stdout.flush()
    time.sleep(2)

