import subprocess

for d in [0, 1, 2, 3, 4, 6, 7, 22]:
    cmd = ['speaker-test', '-D', f'hw:0,{d}', '-c', '2', '-r', '48000', '-t', 'sine', '-f', '1000', '-l', '1']
    res = subprocess.run(cmd, capture_output=True, text=True)
    out = res.stderr or res.stdout
    lines = [l.strip() for l in out.splitlines() if 'error' in l.lower() or 'busy' in l.lower() or '0 -' in l.lower()]
    print(f"hw:0,{d}: {lines[:2] if lines else 'OK'}")

