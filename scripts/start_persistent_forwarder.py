import subprocess
import sys
import time

cmd = [
    "powershell.exe",
    "-WindowStyle", "Hidden",
    "-NoProfile",
    "-Command",
    "while($true) { adb forward tcp:2323 tcp:2323; adb forward tcp:6080 tcp:6080; adb forward tcp:5901 tcp:5901; adb forward tcp:2222 tcp:22; Start-Sleep -Seconds 3 }"
]

subprocess.Popen(cmd, creationflags=0x08000000 if sys.platform == "win32" else 0)
print("Persistent forwarder process spawned in background.")

