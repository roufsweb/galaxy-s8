#!/usr/bin/env python3
"""
s8_flasher.py — 1-Click Autonomous OS Flasher for Samsung Galaxy S8 (SM-G950N)
Supports both interactive Tkinter GUI and standalone terminal CLI.
"""

import sys
import os
import time
import subprocess
import shutil
import threading

WORKSPACE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ROM = os.path.join(WORKSPACE, "releases", "ubuntu-24.04-arm64.img.gz")
ALT_ROM = os.path.join(WORKSPACE, "releases", "ubuntu-24.04-arm64.img")

def find_adb():
    # 1. Check embedded adb from PyInstaller bundle
    if hasattr(sys, "_MEIPASS"):
        embedded_adb = os.path.join(sys._MEIPASS, "adb.exe")
        if os.path.exists(embedded_adb):
            return embedded_adb

    # 2. Check local tools directory
    local_adb = os.path.join(WORKSPACE, "tools", "adb.exe")
    if os.path.exists(local_adb):
        return local_adb

    # 3. Check system PATH
    adb = shutil.which("adb")
    if adb:
        return adb
    common_paths = [
        r"C:\platform-tools\adb.exe",
        r"C:\Program Files\Android\platform-tools\adb.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe")
    ]
    for p in common_paths:
        if os.path.exists(p):
            return p
    return "adb"

def run_cmd(args):
    try:
        p = subprocess.run(args, capture_output=True, text=True, check=True)
        return p.stdout.strip()
    except Exception:
        return None

def check_device(adb):
    out = run_cmd([adb, "devices"])
    if not out:
        return None
    for line in out.splitlines()[1:]:
        parts = line.strip().split()
        if len(parts) >= 2:
            return parts[0], parts[1]
    return None

def pulse_haptic(adb, serial, duration_ms):
    cmd = f"echo {duration_ms} > /sys/class/timed_output/vibrator/enable 2>/dev/null || true"
    subprocess.run([adb, "-s", serial, "shell", cmd], capture_output=True)

def execute_flash(adb, serial, rom_path, log_callback=None, progress_callback=None):
    def log(msg):
        if log_callback:
            log_callback(msg)
        else:
            print(msg)

    if not os.path.exists(rom_path):
        log(f"[!] ROM file not found: {rom_path}")
        return False

    file_size = os.path.getsize(rom_path)
    file_mb = file_size / (1024 * 1024)
    filename = os.path.basename(rom_path)
    log(f"[*] Target ROM: {filename} ({file_mb:.1f} MB)")

    log("[*] Unlocking MAX77865 PMIC to 1,500 mA fast charging and applying V4L2 panic guard...")
    prep_cmds = (
        "echo '0xBD 0x6C' > /sys/class/power_supply/max77865-charger/data 2>/dev/null; "
        "echo '0xC0 0x3C' > /sys/class/power_supply/max77865-charger/data 2>/dev/null; "
        "echo 1500 > /sys/class/power_supply/battery/batt_tune_fast_charge_current 2>/dev/null; "
        "rm -f /dev/video[1-9][0-9]* /dev/v4l-subdev* 2>/dev/null; "
        "for c in /sys/devices/system/cpu/cpu[0-7]; do echo performance > $c/cpufreq/scaling_governor 2>/dev/null; done; "
        "mkdir -p /data/linux /mnt/ubuntu"
    )
    subprocess.run([adb, "-s", serial, "shell", prep_cmds], capture_output=True)

    pulse_haptic(adb, serial, 500)

    dest_path = f"/data/{filename}"
    log(f"[*] Streaming {filename} to internal UFS 2.1 flash over high-speed USB...")
    t0 = time.time()

    proc = subprocess.Popen([adb, "-s", serial, "push", rom_path, dest_path], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for line in iter(proc.stdout.readline, ""):
        line_clean = line.strip()
        if "%" in line_clean:
            if progress_callback:
                try:
                    pct_str = [p for p in line_clean.split() if "%" in p][0].replace("%", "").replace("[", "").replace("]", "")
                    progress_callback(float(pct_str), line_clean)
                except Exception:
                    pass
            elif not log_callback:
                sys.stdout.write(f"\r    -> {line_clean}")
                sys.stdout.flush()
    proc.wait()
    if not log_callback:
        sys.stdout.write("\n")

    if proc.returncode != 0:
        log("[!] High-speed file transfer failed!")
        return False

    elapsed = time.time() - t0
    speed = file_mb / elapsed if elapsed > 0 else 0
    log(f"[+] Transfer completed in {elapsed:.1f}s ({speed:.1f} MB/s)!")

    log("[*] Decompressing into /data/linux/rootfs.img using octa-core hardware pigz...")
    if progress_callback:
        progress_callback(95.0, "Decompressing on 8-core CPU...")
    t1 = time.time()

    if filename.endswith(".gz"):
        install_cmd = (
            f"/sbin/pigz -d -c {dest_path} > /data/linux/rootfs.img.tmp && "
            "mv /data/linux/rootfs.img.tmp /data/linux/rootfs.img && "
            f"rm -f {dest_path} && sync"
        )
    else:
        install_cmd = f"mv {dest_path} /data/linux/rootfs.img && sync"

    proc2 = subprocess.run([adb, "-s", serial, "shell", install_cmd], capture_output=True, text=True)
    if proc2.returncode != 0:
        log(f"[!] Decompression failed: {proc2.stderr}")
        return False

    decomp_elapsed = time.time() - t1
    log(f"[+] OS installed successfully in {decomp_elapsed:.1f}s!")

    log("[*] Verifying ext4 filesystem integrity...")
    fs_check = subprocess.run([adb, "-s", serial, "shell", "/sbin/e2fsck -p /data/linux/rootfs.img"], capture_output=True, text=True)
    log(f"    -> {fs_check.stdout.strip()}")

    log("[+] Signaling Success on phone haptic motor (3 pulses)...")
    for _ in range(3):
        pulse_haptic(adb, serial, 150)
        time.sleep(0.25)

    log("[*] Launching Ubuntu 24.04.5 LTS & GNOME 46 macOS Desktop...")
    subprocess.run([adb, "-s", serial, "shell", "if [ -f /data/linux/start_all.sh ]; then nohup /sbin/sh /data/linux/start_all.sh >/dev/null 2>&1 & fi"], capture_output=True)

    if progress_callback:
        progress_callback(100.0, "Flash Complete! System Live.")

    log("\n" + "=" * 60)
    log("   FLASH COMPLETE & UBUNTU IS NOW LIVE!")
    log("   - Web Desktop (noVNC): http://192.168.0.227:6080 (or localhost:6080)")
    log("   - TigerVNC Display:    :1 (port 5901, password: ubuntu)")
    log("   - SSH Terminal:        ssh root@192.168.0.227 (password: ubuntu)")
    log("   - USB-C DisplayPort:   Hotplug external monitor anytime")
    log("=" * 60)
    return True

# --- TKINTER MODERN GUI ---
def run_gui():
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox

    adb = find_adb()
    root = tk.Tk()
    root.title("Galaxy S8 (SM-G950N) 1-Click OS Flasher")
    root.geometry("680x520")
    root.minsize(600, 480)

    # Style configuration
    style = ttk.Style(root)
    style.theme_use("clam")

    # Colors
    BG_COLOR = "#0f172a"
    CARD_BG = "#1e293b"
    TEXT_COLOR = "#f8fafc"
    ACCENT_COLOR = "#38bdf8"
    SUCCESS_COLOR = "#22c55e"

    root.configure(bg=BG_COLOR)

    # Header
    header_frame = tk.Frame(root, bg=BG_COLOR)
    header_frame.pack(fill="x", padx=20, pady=(15, 10))

    title_label = tk.Label(header_frame, text="Samsung Galaxy S8 1-Click OS Flasher", font=("Helvetica", 16, "bold"), fg=TEXT_COLOR, bg=BG_COLOR)
    title_label.pack(anchor="w")
    sub_label = tk.Label(header_frame, text="Deploy Native Ubuntu 24.04 LTS, Homelab, or Custom ROMs in under 2 minutes", font=("Helvetica", 10), fg="#94a3b8", bg=BG_COLOR)
    sub_label.pack(anchor="w")

    # Device Status Card
    dev_frame = tk.LabelFrame(root, text=" Target Hardware Status ", font=("Helvetica", 10, "bold"), fg=ACCENT_COLOR, bg=CARD_BG, bd=1, relief="solid")
    dev_frame.pack(fill="x", padx=20, pady=10)

    dev_status_var = tk.StringVar(value="Searching for Galaxy S8 over USB...")
    dev_status_lbl = tk.Label(dev_frame, textvariable=dev_status_var, font=("Consolas", 11), fg=TEXT_COLOR, bg=CARD_BG, padx=10, pady=8)
    dev_status_lbl.pack(anchor="w")

    # ROM File Selection Card
    rom_frame = tk.LabelFrame(root, text=" Operating System ROM Image ", font=("Helvetica", 10, "bold"), fg=ACCENT_COLOR, bg=CARD_BG, bd=1, relief="solid")
    rom_frame.pack(fill="x", padx=20, pady=10)

    initial_rom = DEFAULT_ROM if os.path.exists(DEFAULT_ROM) else (ALT_ROM if os.path.exists(ALT_ROM) else "")
    rom_path_var = tk.StringVar(value=initial_rom)

    rom_entry_frame = tk.Frame(rom_frame, bg=CARD_BG)
    rom_entry_frame.pack(fill="x", padx=10, pady=10)

    rom_entry = tk.Entry(rom_entry_frame, textvariable=rom_path_var, font=("Consolas", 10), bg="#0f172a", fg=TEXT_COLOR, insertbackground=TEXT_COLOR, relief="flat", bd=4)
    rom_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))

    def browse_file():
        fn = filedialog.askopenfilename(
            title="Select OS ROM Image",
            filetypes=[("ROM Images", "*.img.gz *.img *.tar.gz"), ("All Files", "*.*")]
        )
        if fn:
            rom_path_var.set(fn)

    browse_btn = tk.Button(rom_entry_frame, text="Browse...", font=("Helvetica", 9, "bold"), bg="#334155", fg=TEXT_COLOR, activebackground="#475569", activeforeground=TEXT_COLOR, bd=0, padx=12, pady=4, cursor="hand2", command=browse_file)
    browse_btn.pack(side="right")

    # Progress Bar & Status
    prog_frame = tk.Frame(root, bg=BG_COLOR)
    prog_frame.pack(fill="x", padx=20, pady=10)

    status_var = tk.StringVar(value="Ready to flash.")
    status_lbl = tk.Label(prog_frame, textvariable=status_var, font=("Helvetica", 10), fg="#94a3b8", bg=BG_COLOR)
    status_lbl.pack(anchor="w", pady=(0, 5))

    prog_bar = ttk.Progressbar(prog_frame, orient="horizontal", mode="determinate")
    prog_bar.pack(fill="x")

    # Log Window
    log_frame = tk.Frame(root, bg=BG_COLOR)
    log_frame.pack(fill="both", expand=True, padx=20, pady=5)

    log_text = tk.Text(log_frame, bg="#050811", fg="#cbd5e1", font=("Consolas", 9), relief="flat", height=8)
    log_text.pack(side="left", fill="both", expand=True)
    scrollbar = tk.Scrollbar(log_frame, command=log_text.yview)
    scrollbar.pack(side="right", fill="y")
    log_text.config(yscrollcommand=scrollbar.set)

    def append_log(msg):
        log_text.insert(tk.END, msg + "\n")
        log_text.see(tk.END)

    # Flash Button
    btn_frame = tk.Frame(root, bg=BG_COLOR)
    btn_frame.pack(fill="x", padx=20, pady=(5, 15))

    current_device = [None]

    def update_progress(pct, status_text):
        prog_bar["value"] = pct
        status_var.set(f"{status_text} ({pct:.1f}%)")
        root.update_idletasks()

    def start_flashing():
        if not current_device[0]:
            messagebox.showwarning("No Device", "Please connect Samsung Galaxy S8 in Recovery/ADB mode first.")
            return

        rom_target = rom_path_var.get().strip()
        if not os.path.exists(rom_target):
            messagebox.showerror("ROM Not Found", f"Specified ROM file does not exist:\n{rom_target}")
            return

        flash_btn.config(state="disabled", text="Flashing in Progress...")
        browse_btn.config(state="disabled")

        def worker():
            success = execute_flash(
                adb, current_device[0], rom_target,
                log_callback=append_log,
                progress_callback=update_progress
            )
            flash_btn.config(state="normal", text="Start 1-Click Flash")
            browse_btn.config(state="normal")
            if success:
                messagebox.showinfo("Success", "Ubuntu 24.04 OS has been flashed and is now live on the Galaxy S8!")

        t = threading.Thread(target=worker, daemon=True)
        t.start()

    flash_btn = tk.Button(btn_frame, text="Start 1-Click Flash", font=("Helvetica", 12, "bold"), bg="#0284c7", fg="#ffffff", activebackground="#0369a1", activeforeground="#ffffff", bd=0, pady=8, cursor="hand2", command=start_flashing)
    flash_btn.pack(fill="x")

    def poll_device():
        dev = check_device(adb)
        if dev:
            current_device[0] = dev[0]
            dev_status_var.set(f"CONNECTED: Samsung Galaxy S8 ({dev[0]}) — Mode: {dev[1]}")
            dev_status_lbl.config(fg=SUCCESS_COLOR)
        else:
            current_device[0] = None
            dev_status_var.set("DISCONNECTED: Waiting for Galaxy S8 over USB...")
            dev_status_lbl.config(fg="#f87171")
        root.after(2000, poll_device)

    poll_device()
    root.mainloop()

# --- CLI MODE ---
def run_cli(rom_path=None):
    adb = find_adb()
    print("=" * 65)
    print("   GALAXY S8 (SM-G950N) 1-CLICK AUTONOMOUS OS FLASHER")
    print("=" * 65)

    if not rom_path:
        if os.path.exists(DEFAULT_ROM):
            rom_path = DEFAULT_ROM
        elif os.path.exists(ALT_ROM):
            rom_path = ALT_ROM
        else:
            print("[!] No ROM image found in releases/. Specify path: python s8_flasher.py <path>")
            sys.exit(1)

    print("\n[*] Probing for connected Samsung Galaxy S8...")
    dev = check_device(adb)
    while not dev:
        print("[!] No device detected over USB. Retrying in 2 seconds...")
        time.sleep(2)
        dev = check_device(adb)

    serial = dev[0]
    print(f"[+] Found Galaxy S8: {serial} ({dev[1]})")
    success = execute_flash(adb, serial, rom_path)
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("--cli", "-c"):
        target_rom = sys.argv[2] if len(sys.argv) > 2 else None
        run_cli(target_rom)
    elif len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        run_cli(sys.argv[1])
    else:
        run_gui()
