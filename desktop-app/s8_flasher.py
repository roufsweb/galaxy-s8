import os
import sys
import time
import shutil
import subprocess
import threading
import json
import struct
import lzma
import gzip
import re
import tkinter as tk
from tkinter import filedialog
import customtkinter as ctk

ANSI_ESCAPE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

# Windows creation flag to completely suppress flashing console windows
NO_WINDOW_FLAG = 0x08000000 if sys.platform == "win32" else 0
WORKSPACE = os.path.dirname(os.path.abspath(__file__))

def get_app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return WORKSPACE

LOG_FILE = os.path.join(get_app_dir(), "flasher.log")

def log(msg: str):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

def detect_image_structure(filepath: str) -> dict:
    """
    Empirically inspects image headers (compressed or uncompressed) in milliseconds.
    Identifies tarballs, raw ext4 filesystems, MBR partition tables, and GPT partition tables,
    automatically resolving the rootfs partition offset and sector count.
    """
    fn_lower = os.path.basename(filepath).lower()
    is_tar = any(fn_lower.endswith(ext) for ext in [".tar.gz", ".tar.xz", ".tar", ".tgz", ".tar.bz2"])
    if is_tar:
        return {"is_tar": True, "format": "tar", "lba_start": 0, "sectors": 0, "size_mb": 0, "desc": "Tarball Archive"}

    header = b""
    try:
        if fn_lower.endswith(".xz") or ".xz." in fn_lower:
            with lzma.open(filepath, "rb") as f:
                header = f.read(65536)
        elif fn_lower.endswith(".gz") or ".gz." in fn_lower:
            with gzip.open(filepath, "rb") as f:
                header = f.read(65536)
        else:
            with open(filepath, "rb") as f:
                header = f.read(65536)
    except Exception as e:
        log(f"detect_image_structure error: {e}")
        return {"is_tar": False, "format": "unknown", "lba_start": 0, "sectors": 0, "size_mb": 0, "desc": "Unknown Image"}

    # 0. Check QCOW2 magic at offset 0
    if len(header) >= 4 and header[:4] == b"QFI\xfb":
        return {"is_tar": False, "format": "qcow2", "lba_start": 0, "sectors": 0, "size_mb": 0, "desc": "QCOW2 VM Image (Use .raw or .tar.xz)"}

    # 1. Check for pure raw ext4 filesystem (magic 0xEF53 at offset 1080)
    if len(header) >= 1082:
        if struct.unpack("<H", header[1080:1082])[0] == 0xef53:
            return {"is_tar": False, "format": "ext4_raw", "lba_start": 0, "sectors": 0, "size_mb": 0, "desc": "Raw ext4 Filesystem"}

    # 2. Check for MBR boot signature (0x55AA at offset 510)
    if len(header) >= 512 and header[510:512] == b"\x55\xaa":
        is_gpt = False
        for i in range(4):
            if header[446 + i*16 + 4] == 0xee:
                is_gpt = True
                break

        # Check GPT partition table
        if is_gpt and len(header) >= 1024:
            if header[512:520] == b"EFI PART":
                part_entry_lba, num_parts, part_entry_size = struct.unpack("<QQII", header[512+72:512+96])[:3]
                gpt_entries_offset = part_entry_lba * 512
                gpt_parts = []
                for p_idx in range(min(num_parts, 32)):
                    off = gpt_entries_offset + p_idx * part_entry_size
                    if off + part_entry_size <= len(header):
                        type_guid_raw = header[off:off+16]
                        if type_guid_raw == b"\x00" * 16:
                            continue
                        first_lba, last_lba = struct.unpack("<QQ", header[off+32:off+48])
                        sectors = last_lba - first_lba + 1
                        gpt_parts.append({"part": p_idx+1, "lba_start": first_lba, "sectors": sectors, "size_mb": sectors*512/(1024*1024)})
                if gpt_parts:
                    best = max(gpt_parts, key=lambda x: x["sectors"])
                    return {
                        "is_tar": False, "format": "gpt_disk",
                        "lba_start": best["lba_start"], "sectors": best["sectors"],
                        "size_mb": best["size_mb"],
                        "desc": f"GPT Disk (Part {best['part']} • {best['size_mb']:.0f} MB ext4)"
                    }

        # Standard MBR partition table
        mbr_parts = []
        for i in range(4):
            p = header[446 + i*16 : 446 + (i+1)*16]
            p_type, lba_start, sectors = struct.unpack("<4xB3xII", p)
            if p_type in (0x83, 0x8e) and sectors > 0:
                mbr_parts.append({"part": i+1, "type": hex(p_type), "lba_start": lba_start, "sectors": sectors, "size_mb": sectors*512/(1024*1024)})
        if mbr_parts:
            best = max(mbr_parts, key=lambda x: x["sectors"])
            return {
                "is_tar": False, "format": "mbr_disk",
                "lba_start": best["lba_start"], "sectors": best["sectors"],
                "size_mb": best["size_mb"],
                "desc": f"MBR Disk (Part {best['part']} • {best['size_mb']:.0f} MB ext4)"
            }

    return {"is_tar": False, "format": "raw_disk", "lba_start": 0, "sectors": 0, "size_mb": 0, "desc": "Raw Disk Image"}

def find_default_image():
    app_dir = get_app_dir()
    candidates = [
        os.path.join(app_dir, "ubuntu-24.04-arm64.img.gz"),
        os.path.join(app_dir, "ubuntu-24.04-arm64.img"),
        os.path.join(app_dir, "..", "releases", "ubuntu-24.04-arm64.img.gz"),
        os.path.join(app_dir, "..", "releases", "ubuntu-24.04-arm64.img"),
        os.path.join(WORKSPACE, "releases", "ubuntu-24.04-arm64.img.gz"),
        os.path.join(WORKSPACE, "releases", "ubuntu-24.04-arm64.img"),
        r"E:\rouf\galaxy-s8\releases\ubuntu-24.04-arm64.img.gz",
    ]
    for c in candidates:
        if os.path.isfile(c):
            return os.path.abspath(c)
    return ""

def get_bundle_dir():
    if hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS
    return WORKSPACE

def find_adb():
    bundle_dir = get_bundle_dir()
    embedded_adb = os.path.join(bundle_dir, "adb.exe")
    if os.path.exists(embedded_adb):
        return embedded_adb

    local_adb = os.path.join(WORKSPACE, "tools", "adb.exe")
    if os.path.exists(local_adb):
        return local_adb

    adb = shutil.which("adb")
    if adb:
        return adb

    for p in [
        r"C:\platform-tools\adb.exe",
        r"C:\Program Files\Android\platform-tools\adb.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe")
    ]:
        if os.path.exists(p):
            return p
    return "adb"

def get_supervisor_scripts_dir():
    bundle_dir = get_bundle_dir()
    scripts_in_bundle = os.path.join(bundle_dir, "scripts")
    if os.path.isdir(scripts_in_bundle):
        return scripts_in_bundle
    scripts_in_tools = os.path.join(WORKSPACE, "tools", "scripts")
    if os.path.isdir(scripts_in_tools):
        return scripts_in_tools
    scripts_in_scratch = os.path.join(WORKSPACE, "scratch")
    if os.path.isdir(scripts_in_scratch):
        return scripts_in_scratch
    return None


# Theme & Appearance Configuration
ctk.set_appearance_mode("Dark")

COLORS = {
    "bg": "#0B0F17",           # Deep obsidian background
    "surface": "#151C28",      # Primary card surface
    "surface_alt": "#1C2536",  # Inner container / toggle row surface
    "border": "#263248",       # Subtle hairline border
    "primary": "#2563EB",      # Samsung/Modern Blue accent
    "primary_hover": "#1D4ED8",
    "flash_btn": "#E11D48",    # Raspberry Pi Imager inspired crimson action accent
    "flash_hover": "#BE123C",
    "success": "#10B981",      # Connected emerald
    "success_bg": "#064E3B",
    "warning": "#F59E0B",
    "danger": "#EF4444",
    "text": "#F8FAFC",         # Primary crisp white
    "text_muted": "#94A3B8",   # Secondary slate label
    "text_dim": "#64748B"      # Placeholder / subtle metadata
}


class VectorIcon(tk.Canvas):
    """Lightweight dependency-free vector icon renderer for CustomTkinter."""
    def __init__(self, master, icon_type, size=20, bg=COLORS["surface"], color=COLORS["primary"], **kwargs):
        super().__init__(master, width=size, height=size, bg=bg, highlightthickness=0, **kwargs)
        self.size = size
        self.color = color
        self.draw_icon(icon_type)

    def draw_icon(self, icon_type):
        s = self.size
        c = self.color
        if icon_type == "phone":
            self.create_rectangle(s*0.25, s*0.1, s*0.75, s*0.9, outline=c, width=2)
            self.create_line(s*0.4, s*0.2, s*0.6, s*0.2, fill=c, width=1.5)
            self.create_oval(s*0.45, s*0.75, s*0.55, s*0.83, fill=c, outline="")
        elif icon_type == "disc":
            self.create_oval(s*0.12, s*0.12, s*0.88, s*0.88, outline=c, width=2)
            self.create_oval(s*0.38, s*0.38, s*0.62, s*0.62, outline=c, width=1.5)
        elif icon_type == "wifi":
            self.create_arc(s*0.1, s*0.2, s*0.9, s*0.9, start=45, extent=90, style=tk.ARC, outline=c, width=2)
            self.create_arc(s*0.25, s*0.38, s*0.75, s*0.88, start=45, extent=90, style=tk.ARC, outline=c, width=2)
            self.create_oval(s*0.44, s*0.72, s*0.56, s*0.84, fill=c, outline="")
        elif icon_type == "host":
            self.create_rectangle(s*0.15, s*0.2, s*0.85, s*0.5, outline=c, width=1.8)
            self.create_rectangle(s*0.15, s*0.55, s*0.85, s*0.85, outline=c, width=1.8)
            self.create_oval(s*0.25, s*0.3, s*0.33, s*0.38, fill=c, outline="")
            self.create_oval(s*0.25, s*0.65, s*0.33, s*0.73, fill=c, outline="")
        elif icon_type == "wipe":
            self.create_rectangle(s*0.28, s*0.3, s*0.72, s*0.85, outline=c, width=1.8)
            self.create_line(s*0.2, s*0.28, s*0.8, s*0.28, fill=c, width=2)
            self.create_line(s*0.42, s*0.42, s*0.42, s*0.72, fill=c, width=1.5)
            self.create_line(s*0.58, s*0.42, s*0.58, s*0.72, fill=c, width=1.5)
        elif icon_type == "ssh":
            self.create_rectangle(s*0.12, s*0.18, s*0.88, s*0.82, outline=c, width=1.8)
            self.create_line(s*0.26, s*0.38, s*0.42, s*0.5, fill=c, width=1.8)
            self.create_line(s*0.42, s*0.5, s*0.26, s*0.62, fill=c, width=1.8)
            self.create_line(s*0.48, s*0.62, s*0.68, s*0.62, fill=c, width=1.8)
        elif icon_type == "vnc":
            self.create_rectangle(s*0.12, s*0.18, s*0.88, s*0.72, outline=c, width=1.8)
            self.create_line(s*0.35, s*0.84, s*0.65, s*0.84, fill=c, width=2)
            self.create_line(s*0.5, s*0.72, s*0.5, s*0.84, fill=c, width=2)
        elif icon_type == "bolt":
            pts = [s*0.55, s*0.1, s*0.25, s*0.52, s*0.5, s*0.52, s*0.42, s*0.9, s*0.75, s*0.45, s*0.5, s*0.45]
            self.create_polygon(pts, fill=c, outline="")


class ToggleRow(ctk.CTkFrame):
    """Modern container row with icon, title, subtle port/meta badge, and switch."""
    def __init__(self, master, icon_type, title, meta_text, default_on=True, icon_color=COLORS["primary"]):
        super().__init__(
            master,
            fg_color=COLORS["surface_alt"],
            corner_radius=10,
            border_width=1,
            border_color=COLORS["border"]
        )
        self.grid_columnconfigure(1, weight=1)

        # Icon container
        icon_canvas = VectorIcon(self, icon_type, size=22, bg=COLORS["surface_alt"], color=icon_color)
        icon_canvas.grid(row=0, column=0, padx=(14, 10), pady=14)

        # Label stack
        text_frame = ctk.CTkFrame(self, fg_color="transparent")
        text_frame.grid(row=0, column=1, sticky="w", pady=10)

        self.title_lbl = ctk.CTkLabel(
            text_frame, text=title,
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=COLORS["text"]
        )
        self.title_lbl.pack(anchor="w")

        self.meta_lbl = ctk.CTkLabel(
            text_frame, text=meta_text,
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color=COLORS["text_dim"]
        )
        self.meta_lbl.pack(anchor="w")

        # Modern Pill Switch
        self.switch_var = ctk.BooleanVar(value=default_on)
        self.switch = ctk.CTkSwitch(
            self, text="", variable=self.switch_var,
            width=44, height=22, switch_width=40, switch_height=20,
            progress_color=COLORS["primary"],
            button_color=COLORS["text"],
            fg_color=COLORS["border"]
        )
        self.switch.grid(row=0, column=2, padx=(10, 14), pady=14)

    def get(self) -> bool:
        return self.switch_var.get()

    def set(self, val: bool):
        self.switch_var.set(val)


class InAppTerminalWindow(ctk.CTkToplevel):
    """
    Genuine In-App Interactive Root Terminal for Samsung Galaxy S8.
    Direct bidirectional interactive I/O with ADB root shell pipe.
    Supports Dual Environment Modes:
      1. Linux OS Userland (chroot /mnt/ubuntu with full Linux PATH & environment)
      2. Base AP Hardware Recovery (/sbin/sh ADB root pipe)
    """
    def __init__(self, parent, adb_path, serial, model="Galaxy S8", is_installed=False):
        super().__init__(parent)
        self.adb = adb_path
        self.serial = serial
        self.model = model
        self.is_installed = is_installed
        self.current_env = "os" if is_installed else "recovery"
        self.title(f"{model} Console — In-App Terminal ({serial})")
        self.geometry("920x560")
        self.minsize(760, 440)
        self.configure(fg_color=COLORS["bg"])

        self.history = []
        self.hist_idx = -1
        self.proc = None
        self.running = True

        self._build_ui()
        self._start_shell()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # 1. Header Toolbar
        header = ctk.CTkFrame(self, fg_color=COLORS["surface"], corner_radius=10, border_width=1, border_color=COLORS["border"])
        header.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 6))
        header.grid_columnconfigure(1, weight=1)

        left_f = ctk.CTkFrame(header, fg_color="transparent")
        left_f.grid(row=0, column=0, padx=12, pady=8, sticky="w")

        dot = ctk.CTkLabel(left_f, text="●", font=ctk.CTkFont(size=14), text_color=COLORS["success"])
        dot.pack(side="left", padx=(0, 6))

        t_lbl = ctk.CTkLabel(left_f, text="TERMINAL", font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"), text_color=COLORS["text"])
        t_lbl.pack(side="left", padx=(0, 10))

        # Dual Environment Segmented Switcher
        self.env_seg = ctk.CTkSegmentedButton(
            left_f,
            values=["Linux OS (Ubuntu)", "Recovery AP (ADB)"],
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            selected_color=COLORS["primary"],
            selected_hover_color=COLORS["primary_hover"],
            command=self._on_env_changed
        )
        self.env_seg.set("Linux OS (Ubuntu)" if self.current_env == "os" else "Recovery AP (ADB)")
        self.env_seg.pack(side="left", padx=(0, 10))

        badge = ctk.CTkLabel(left_f, text=f"{self.model} • {self.serial}", font=ctk.CTkFont(family="Consolas", size=11), fg_color=COLORS["surface_alt"], text_color=COLORS["text_muted"], corner_radius=6, padx=8, pady=2)
        badge.pack(side="left")

        # Quick command pills on the right
        btn_bar = ctk.CTkFrame(header, fg_color="transparent")
        btn_bar.grid(row=0, column=2, padx=12, pady=8, sticky="e")

        for label, cmd in [
            ("Status", "s8ctl status"),
            ("Storage", "df -h"),
            ("Memory", "free -m"),
            ("Processes", "ps aux | head -n 15"),
            ("Clear", "__clear__"),
        ]:
            if label == "Clear":
                b = ctk.CTkButton(btn_bar, text=label, width=54, height=26, font=ctk.CTkFont(family="Segoe UI", size=11), fg_color=COLORS["surface_alt"], hover_color=COLORS["border"], command=self._clear_screen)
            else:
                b = ctk.CTkButton(btn_bar, text=label, width=64 if len(label) < 8 else 85, height=26, font=ctk.CTkFont(family="Segoe UI", size=11), fg_color=COLORS["surface_alt"], hover_color=COLORS["primary"], command=lambda c=cmd: self._send_raw(c))
            b.pack(side="left", padx=3)

        # 2. Main Terminal Output Area
        term_frame = ctk.CTkFrame(self, fg_color="#070A0F", corner_radius=10, border_width=1, border_color=COLORS["border"])
        term_frame.grid(row=1, column=0, sticky="nsew", padx=14, pady=6)
        term_frame.grid_columnconfigure(0, weight=1)
        term_frame.grid_rowconfigure(0, weight=1)

        self.term_box = ctk.CTkTextbox(
            term_frame,
            fg_color="#070A0F",
            text_color="#38BDF8",
            font=ctk.CTkFont(family="Consolas", size=12),
            wrap="char",
            corner_radius=8
        )
        self.term_box.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)

        # 3. Input Command Prompt Line
        input_frame = ctk.CTkFrame(self, fg_color=COLORS["surface"], corner_radius=10, border_width=1, border_color=COLORS["border"])
        input_frame.grid(row=2, column=0, sticky="ew", padx=14, pady=(6, 12))
        input_frame.grid_columnconfigure(1, weight=1)

        self.prompt_lbl = ctk.CTkLabel(input_frame, text="root@Galaxy-S8-Ubuntu:~# ", font=ctk.CTkFont(family="Consolas", size=12, weight="bold"), text_color=COLORS["success"])
        self.prompt_lbl.grid(row=0, column=0, padx=(14, 6), pady=10)

        self.cmd_entry = ctk.CTkEntry(
            input_frame,
            height=36,
            fg_color=COLORS["surface_alt"],
            border_color=COLORS["border"],
            text_color=COLORS["text"],
            font=ctk.CTkFont(family="Consolas", size=12),
            placeholder_text="Enter Linux command (e.g. apt, python3, s8ctl, ls)..."
        )
        self.cmd_entry.grid(row=0, column=1, sticky="ew", padx=(0, 8), pady=10)
        self.cmd_entry.bind("<Return>", lambda e: self._on_send_clicked())
        self.cmd_entry.bind("<Up>", self._hist_prev)
        self.cmd_entry.bind("<Down>", self._hist_next)

        send_btn = ctk.CTkButton(
            input_frame, text="SEND", width=70, height=36,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"],
            command=self._on_send_clicked
        )
        send_btn.grid(row=0, column=2, padx=(0, 14), pady=10)
        self.cmd_entry.focus_set()

    def _on_env_changed(self, choice: str):
        target_env = "os" if "Linux" in choice else "recovery"
        if target_env == self.current_env:
            return
        self.current_env = target_env
        if self.proc:
            try:
                self.proc.terminate()
            except Exception:
                pass
        self._clear_screen()
        self._start_shell()

    def _start_shell(self):
        try:
            if self.current_env == "os":
                shell_cmd = "chroot /mnt/ubuntu /usr/bin/env -i HOME=/root TERM=xterm-256color PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin LANG=C.UTF-8 /bin/bash -i"
                args = [self.adb, "-s", self.serial, "shell", shell_cmd]
                banner = (
                    f"=================================================================\n"
                    f"  Connected to Linux OS (Ubuntu 24.04 LTS Noble) on {self.model}\n"
                    f"  Environment: Full GNU Root Userland (glibc 2.39, apt, systemd)\n"
                    f"=================================================================\n\n"
                )
                self.prompt_lbl.configure(text="root@Galaxy-S8-Ubuntu:~# ")
            else:
                args = [self.adb, "-s", self.serial, "shell"]
                banner = (
                    f"=================================================================\n"
                    f"  Connected to Base AP Hardware Recovery Shell on {self.model}\n"
                    f"  Environment: In-Memory CPIO Ramdisk (/sbin/sh, PMIC, Partitions)\n"
                    f"=================================================================\n\n"
                )
                self.prompt_lbl.configure(text="root@Galaxy-S8-Recovery:~# ")

            self.proc = subprocess.Popen(
                args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                creationflags=NO_WINDOW_FLAG
            )
            self._append_text(banner)
            threading.Thread(target=self._reader_loop, daemon=True).start()
        except Exception as e:
            self._append_text(f"Error launching shell: {e}\n")

    def _reader_loop(self):
        try:
            while self.running and self.proc and self.proc.stdout:
                line = self.proc.stdout.readline()
                if not line:
                    break
                clean_line = ANSI_ESCAPE.sub('', line)
                self.after(0, lambda t=clean_line: self._append_text(t))
        except Exception:
            pass

    def _append_text(self, text: str):
        self.term_box.insert(tk.END, text)
        self.term_box.see(tk.END)

    def _on_send_clicked(self):
        cmd = self.cmd_entry.get().strip()
        if not cmd:
            return
        self.history.append(cmd)
        self.hist_idx = len(self.history)
        self.cmd_entry.delete(0, tk.END)
        self._send_raw(cmd)

    def _send_raw(self, cmd: str):
        if not self.proc or not self.proc.stdin:
            self._append_text("Error: Terminal pipe is not active.\n")
            return
        try:
            self.proc.stdin.write(cmd + "\n")
            self.proc.stdin.flush()
        except Exception as e:
            self._append_text(f"Write error: {e}\n")

    def _clear_screen(self):
        self.term_box.delete("1.0", tk.END)

    def _hist_prev(self, event):
        if self.history and self.hist_idx > 0:
            self.hist_idx -= 1
            self.cmd_entry.delete(0, tk.END)
            self.cmd_entry.insert(0, self.history[self.hist_idx])
        return "break"

    def _hist_next(self, event):
        if self.history and self.hist_idx < len(self.history) - 1:
            self.hist_idx += 1
            self.cmd_entry.delete(0, tk.END)
            self.cmd_entry.insert(0, self.history[self.hist_idx])
        elif self.hist_idx >= len(self.history) - 1:
            self.hist_idx = len(self.history)
            self.cmd_entry.delete(0, tk.END)
        return "break"

    def _on_close(self):
        self.running = False
        if self.proc:
            try:
                self.proc.stdin.write("exit\n")
                self.proc.stdin.flush()
                self.proc.terminate()
            except Exception:
                pass
        self.destroy()


def get_connected_devices(adb_path) -> list:
    """
    Scans all devices via `adb devices -l` and dynamically probes hardware properties.
    Returns a sorted list of device dicts (Exynos 8895 Galaxy S8/S8+ ranked highest).
    Zero hardcoded serial numbers.
    """
    devices = []
    try:
        p = subprocess.run(
            [adb_path, "devices", "-l"],
            capture_output=True,
            text=True,
            creationflags=NO_WINDOW_FLAG,
            timeout=3
        )
        if not p.stdout:
            return []

        lines = [line.strip() for line in p.stdout.splitlines()[1:] if line.strip()]
        for line in lines:
            parts = line.split()
            if len(parts) < 2:
                continue
            serial = parts[0]
            mode = parts[1]  # 'device', 'recovery', 'unauthorized', 'offline'

            props = {}
            for token in parts[2:]:
                if ":" in token:
                    k, v = token.split(":", 1)
                    props[k] = v

            raw_model = props.get("model", "")
            raw_device = props.get("device", "")
            raw_product = props.get("product", "")

            model_name = raw_model.replace("_", " ") if raw_model else "Android Device"
            is_s8 = False
            score = 10

            s8_tokens = ["DREAMLTE", "DREAM2LTE", "SM-G950", "SM-G955", "GALAXY_S8", "GALAXY S8"]
            combined = f"{raw_model} {raw_device} {raw_product}".upper()
            if any(t in combined for t in s8_tokens):
                is_s8 = True
                score = 100
                if "G950" in combined:
                    model_name = "Galaxy S8"
                elif "G955" in combined:
                    model_name = "Galaxy S8+"
                elif "GALAXY_S8" in combined or "GALAXY S8" in combined:
                    model_name = "Galaxy S8"

            if mode in ("recovery", "device") and not is_s8:
                try:
                    q = subprocess.run(
                        [adb_path, "-s", serial, "shell", "getprop ro.product.model; getprop ro.product.device; getprop ro.hardware"],
                        capture_output=True, text=True, creationflags=NO_WINDOW_FLAG, timeout=2
                    )
                    if q.stdout:
                        q_lines = [l.strip() for l in q.stdout.splitlines() if l.strip()]
                        if len(q_lines) >= 1 and q_lines[0]:
                            model_name = q_lines[0]
                        q_combined = " ".join(q_lines).upper()
                        if any(t in q_combined for t in s8_tokens) or "8895" in q_combined:
                            is_s8 = True
                            score = 100
                except Exception:
                    pass

            devices.append({
                "serial": serial,
                "mode": mode,
                "model": model_name,
                "device": raw_device,
                "product": raw_product,
                "is_s8": is_s8,
                "score": score
            })
    except Exception as e:
        log(f"get_connected_devices error: {e}")

    devices.sort(key=lambda d: d["score"], reverse=True)
    return devices


class DevicePoller(threading.Thread):
    """Zero-sluggishness background daemon thread for dynamic non-blocking device detection."""
    def __init__(self, app, adb_path):
        super().__init__(daemon=True)
        self.app = app
        self.adb = adb_path
        self.running = True
        self.last_state = None
        self.last_serial = None
        self.last_model = None

    def run(self):
        while self.running:
            try:
                devices = get_connected_devices(self.adb)
                serial, mode, model = None, None, "Galaxy S8"
                if devices:
                    user_ser = getattr(self.app, "user_selected_serial", None)
                    matched_dev = None
                    if user_ser:
                        for d in devices:
                            if d["serial"] == user_ser:
                                matched_dev = d
                                break
                    if not matched_dev:
                        matched_dev = devices[0]

                    serial = matched_dev["serial"]
                    mode = matched_dev["mode"]
                    model = matched_dev["model"]

                self.last_serial = serial
                self.last_model = model
                installed = False
                detected_os = "Base AP Recovery (Kernel #14 Active)"
                vitals = {
                    "battery_pct": "---",
                    "battery_temp": "---",
                    "mem_free_gb": 0.0,
                    "mem_total_gb": 0.0,
                    "wifi_ip": "Disconnected",
                }

                if serial and mode in ("device", "recovery"):
                    cmd = (
                        '[ -f /data/linux/.installed ] && echo "INSTALLED=1" || echo "INSTALLED=0"; '
                        'grep PRETTY_NAME /mnt/ubuntu/etc/os-release 2>/dev/null || echo "PRETTY_NAME=Base AP Recovery (Kernel #14 Active)"; '
                        'cat /sys/class/power_supply/battery/capacity 2>/dev/null || echo "0"; '
                        'cat /sys/devices/virtual/sec/sec-ap-thermistor/temperature 2>/dev/null || echo "0"; '
                        'grep MemTotal /proc/meminfo 2>/dev/null || echo "MemTotal: 0 kB"; '
                        'grep MemAvailable /proc/meminfo 2>/dev/null || echo "MemAvailable: 0 kB"; '
                        'ip -4 addr show wlan0 2>/dev/null | grep "inet " | awk \'{print $2}\' || echo ""'
                    )
                    try:
                        res = subprocess.run(
                            [self.adb, "-s", serial, "shell", cmd],
                            capture_output=True, text=True, creationflags=NO_WINDOW_FLAG, timeout=3
                        )
                        if res.stdout:
                            lines = [l.strip() for l in res.stdout.splitlines() if l.strip()]
                            for line in lines:
                                if line.startswith("INSTALLED="):
                                    installed = (line.split("=")[1] == "1")
                                elif line.startswith("PRETTY_NAME="):
                                    val = line.split("=", 1)[1].strip('"\'')
                                    if val:
                                        detected_os = val
                                elif line.isdigit() and len(line) <= 3 and vitals["battery_pct"] == "---":
                                    vitals["battery_pct"] = line
                                elif line.isdigit() and vitals["battery_temp"] == "---":
                                    vitals["battery_temp"] = f"{int(line)/10:.1f}°C"
                                elif "MemTotal:" in line:
                                    try:
                                        kb = int(line.split(":")[1].replace("kB", "").strip())
                                        vitals["mem_total_gb"] = kb / (1024 * 1024)
                                    except Exception:
                                        pass
                                elif "MemAvailable:" in line:
                                    try:
                                        kb = int(line.split(":")[1].replace("kB", "").strip())
                                        vitals["mem_free_gb"] = kb / (1024 * 1024)
                                    except Exception:
                                        pass
                                elif "/" in line and line[0].isdigit():
                                    vitals["wifi_ip"] = line.split("/")[0].strip()
                    except Exception:
                        pass

                curr_state = (serial is not None, len(devices), serial, mode, model, installed, detected_os, vitals["battery_pct"], vitals["wifi_ip"])
                if curr_state != self.last_state:
                    self.last_state = curr_state
                    connected = serial is not None
                    s_ser = serial if serial else "---"
                    s_mode = mode if mode else "none"
                    s_model = model if model else "Galaxy S8"
                    self.app.after(0, lambda c=connected, devs=devices, s=s_ser, mod=s_model, m=s_mode, inst=installed, dos=detected_os, vit=vitals: self.app.set_device_state(c, devs, s, mod, m, inst, dos, vit))
            except Exception as e:
                log(f"DevicePoller exception: {e}")
                if self.last_state is not None:
                    self.last_state = None
                    empty_vit = {"battery_pct": "---", "battery_temp": "---", "mem_free_gb": 0.0, "mem_total_gb": 0.0, "wifi_ip": "Disconnected"}
                    self.app.after(0, lambda: self.app.set_device_state(False, [], "---", "Galaxy S8", "none", False, "No Device Connected", empty_vit))
            time.sleep(2.0)


class FlasherWorker(threading.Thread):
    """Background worker thread executing storage wipe, provisioning, push, extraction, and boot."""
    def __init__(self, app, adb_path, config, on_complete):
        super().__init__(daemon=True)
        self.app = app
        self.adb = adb_path
        self.cfg = config
        self.on_complete = on_complete

    def update_progress(self, ratio: float, msg: str):
        self.app.after(0, lambda: self.app.set_progress(ratio, msg))

    def pulse_haptic(self, serial, duration_ms):
        cmd = f"echo {duration_ms} > /sys/class/timed_output/vibrator/enable 2>/dev/null || true"
        subprocess.run([self.adb, "-s", serial, "shell", cmd], capture_output=True, creationflags=NO_WINDOW_FLAG)

    def get_serial(self):
        devices = get_connected_devices(self.adb)
        if devices:
            return devices[0]["serial"]
        return None

    def run(self):
        success = False
        try:
            log("FlasherWorker started")
            serial = self.get_serial()
            log(f"FlasherWorker: Target serial = {serial}")
            if not serial:
                raise RuntimeError("No Galaxy S8 device detected via USB")

            image_path = self.cfg["image_path"]
            log(f"FlasherWorker: Image path = {image_path}")
            if not os.path.exists(image_path):
                raise RuntimeError(f"Image not found: {image_path}")

            filename = os.path.basename(image_path)
            file_size = os.path.getsize(image_path)
            file_mb = file_size / (1024 * 1024)
            log(f"FlasherWorker: File size = {file_mb:.1f} MB ({file_size} bytes)")

            # Step 1: Storage & Clean Wipe (5% -> 15%)
            log("FlasherWorker: Step 1 Storage & Clean Wipe...")
            self.update_progress(0.05, "Preparing storage subsystem...")
            if self.cfg.get("clean_wipe", True):
                self.update_progress(0.08, "Wiping /data (USERDATA) to clean ext4...")
                storage_cmd = (
                    "killall -9 Xtigervnc sshd nginx dbus-daemon metacity gnome-panel wpa_supplicant dhclient bluetoothd s8_input_bridge s8_button_daemon casaos casaos-gateway 2>/dev/null || true; "
                    "umount -f -l /mnt/ubuntu/mnt/android_data 2>/dev/null || true; "
                    "umount -f -l /mnt/ubuntu 2>/dev/null || true; "
                    "losetup -D 2>/dev/null || losetup -d /dev/block/loop0 2>/dev/null || true; "
                    "if mountpoint -q /data; then "
                    "  rm -rf /data/linux /data/docker /data/local /data/* 2>/dev/null || true; "
                    "else "
                    "  mount -t ext4 /dev/block/sda24 /data 2>/dev/null || (mke2fs -F -t ext4 /dev/block/sda24 && mount -t ext4 /dev/block/sda24 /data); "
                    "  rm -rf /data/linux /data/docker /data/local /data/* 2>/dev/null || true; "
                    "fi; "
                    "mkdir -p /data/linux /mnt/ubuntu"
                )
            else:
                storage_cmd = (
                    "if ! mountpoint -q /data; then "
                    "  mount /data 2>/dev/null || "
                    "  (mke2fs -F -t ext4 /dev/block/sda24 && mount /data); "
                    "fi; "
                    "mkdir -p /data/linux /mnt/ubuntu"
                )
            subprocess.run([self.adb, "-s", serial, "shell", storage_cmd], capture_output=True, creationflags=NO_WINDOW_FLAG, check=True)
            log("FlasherWorker: Step 1 complete")

            # Step 2: PMIC Fast Charge & Performance (15% -> 20%)
            self.update_progress(0.15, "Configuring PMIC fast charge & performance governor...")
            prep = [
                "rm -f /dev/video[1-9][0-9]* /dev/v4l-subdev* 2>/dev/null",
                "echo 1 > /proc/sys/net/ipv4/ip_forward 2>/dev/null",
                "for c in /sys/devices/system/cpu/cpu[0-7]; do echo performance > $c/cpufreq/scaling_governor 2>/dev/null; done"
            ]
            if self.cfg.get("fast_charge_1500ma", True):
                prep.extend([
                    "echo '0xBD 0x6C' > /sys/class/power_supply/max77865-charger/data 2>/dev/null",
                    "echo '0xC0 0x3C' > /sys/class/power_supply/max77865-charger/data 2>/dev/null",
                    "echo 1500 > /sys/class/power_supply/battery/batt_tune_fast_charge_current 2>/dev/null"
                ])
            subprocess.run([self.adb, "-s", serial, "shell", "; ".join(prep)], capture_output=True, creationflags=NO_WINDOW_FLAG)
            self.pulse_haptic(serial, 150)

            # Step 3: Deploy Supervisor Scripts (20% -> 25%)
            self.update_progress(0.20, "Deploying boot supervisor & hardware daemons...")
            scripts_dir = get_supervisor_scripts_dir()
            if scripts_dir:
                for s in [
                    "start_all.sh", "start_ubuntu_desktop.sh", "connect_wifi.sh",
                    "init_audio.sh", "s8ctl.py", "asound.conf",
                    "s8_typec_daemon.py", "vnc_lite.html", "bixby.sh"
                ]:
                    sp = os.path.join(scripts_dir, s)
                    if os.path.exists(sp):
                        subprocess.run([self.adb, "-s", serial, "push", sp, f"/data/linux/{s}"], capture_output=True, creationflags=NO_WINDOW_FLAG)
                        subprocess.run([self.adb, "-s", serial, "shell", f"chmod 755 /data/linux/{s}"], capture_output=True, creationflags=NO_WINDOW_FLAG)

            # Step 4: Stream OS Image over High-Speed USB (25% -> 75%)
            dest_path = f"/data/{filename}"
            self.update_progress(0.25, f"Streaming {filename} ({file_mb:.0f} MB)...")
            start_time = time.time()
            proc = subprocess.Popen(
                [self.adb, "-s", serial, "push", image_path, dest_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=NO_WINDOW_FLAG
            )

            while proc.poll() is None:
                time.sleep(0.5)
                try:
                    res = subprocess.run(
                        [self.adb, "-s", serial, "shell", f"ls -l {dest_path} 2>/dev/null"],
                        capture_output=True,
                        text=True,
                        creationflags=NO_WINDOW_FLAG,
                        timeout=2
                    )
                    parts = res.stdout.strip().split()
                    if len(parts) >= 5 and parts[4].isdigit():
                        curr_bytes = int(parts[4])
                        elapsed = max(time.time() - start_time, 0.1)
                        speed_mb = (curr_bytes / (1024 * 1024)) / elapsed
                        pct = (curr_bytes / file_size) * 100.0
                        ratio = 0.25 + (curr_bytes / file_size) * 0.50
                        self.update_progress(
                            ratio,
                            f"Transferring {filename}: {curr_bytes / (1024*1024):.0f}/{file_mb:.0f} MB ({pct:.0f}%) - {speed_mb:.1f} MB/s"
                        )
                except Exception:
                    pass

            proc.wait()
            if proc.returncode != 0:
                raise RuntimeError("USB file transfer failed")
            self.update_progress(0.75, f"Transferred {filename} successfully ({file_mb:.0f} MB)")

            # Step 5: Extract / Decompress rootfs according to file format (75% -> 90%)
            fn_lower = filename.lower()
            img_info = detect_image_structure(image_path)
            log(f"FlasherWorker: Image structure = {img_info}")

            is_tar = img_info["is_tar"]
            is_xz = fn_lower.endswith(".xz") or ".xz." in fn_lower
            is_gz = fn_lower.endswith(".gz") or ".gz." in fn_lower
            fmt = img_info["format"]
            lba_start = img_info["lba_start"]
            sectors = img_info["sectors"]

            if is_tar:
                self.update_progress(0.76, "Creating 12 GB ext4 rootfs container on UFS flash...")
                prep_rootfs_cmd = (
                    "rm -f /data/linux/rootfs.img && "
                    "truncate -s 12G /data/linux/rootfs.img && "
                    "mke2fs -F -t ext4 /data/linux/rootfs.img && "
                    "mkdir -p /mnt/ubuntu && "
                    "mount -t ext4 -o loop /data/linux/rootfs.img /mnt/ubuntu"
                )
                subprocess.run([self.adb, "-s", serial, "shell", prep_rootfs_cmd], capture_output=True, creationflags=NO_WINDOW_FLAG, check=True)

                self.update_progress(0.80, f"Extracting {filename} into rootfs...")
                if fn_lower.endswith(".tar.xz"):
                    extract_cmd = f"tar -Jxf {dest_path} -C /mnt/ubuntu && rm -f {dest_path} && sync"
                elif fn_lower.endswith(".tar.gz") or fn_lower.endswith(".tgz"):
                    extract_cmd = f"tar -zxf {dest_path} -C /mnt/ubuntu && rm -f {dest_path} && sync"
                elif fn_lower.endswith(".tar.bz2"):
                    extract_cmd = f"tar -jxf {dest_path} -C /mnt/ubuntu && rm -f {dest_path} && sync"
                else:
                    extract_cmd = f"tar -xf {dest_path} -C /mnt/ubuntu && rm -f {dest_path} && sync"
                res = subprocess.run([self.adb, "-s", serial, "shell", extract_cmd], capture_output=True, text=True, creationflags=NO_WINDOW_FLAG)
                if res.returncode != 0:
                    raise RuntimeError(f"Tar extraction failed: {res.stderr}")

            elif fmt in ("mbr_disk", "gpt_disk") and lba_start > 0 and sectors > 0:
                self.update_progress(0.76, f"Extracting root partition (LBA {lba_start}, {img_info['size_mb']:.0f} MB)...")
                if is_xz:
                    decomp_cmd = f"/sbin/unxz -c {dest_path} | /sbin/dd bs=512 skip={lba_start} count={sectors} of=/data/linux/rootfs.img && rm -f {dest_path} && sync"
                elif is_gz:
                    decomp_cmd = f"/sbin/pigz -d -c {dest_path} | /sbin/dd bs=512 skip={lba_start} count={sectors} of=/data/linux/rootfs.img && rm -f {dest_path} && sync"
                else:
                    decomp_cmd = f"/sbin/dd if={dest_path} of=/data/linux/rootfs.img bs=512 skip={lba_start} count={sectors} && rm -f {dest_path} && sync"
                res = subprocess.run([self.adb, "-s", serial, "shell", decomp_cmd], capture_output=True, text=True, creationflags=NO_WINDOW_FLAG)
                if res.returncode != 0:
                    raise RuntimeError(f"Partition extraction failed: {res.stderr}")
                self.update_progress(0.85, "Checking & expanding filesystem to full capacity...")
                subprocess.run([self.adb, "-s", serial, "shell", "/sbin/e2fsck -fy /data/linux/rootfs.img 2>/dev/null || true"], capture_output=True, creationflags=NO_WINDOW_FLAG)
                subprocess.run([self.adb, "-s", serial, "shell", "/sbin/resize2fs /data/linux/rootfs.img 2>/dev/null || true"], capture_output=True, creationflags=NO_WINDOW_FLAG)

            elif is_xz:
                self.update_progress(0.76, "Decompressing XZ image on octa-core CPU...")
                decomp_cmd = f"/sbin/unxz -c {dest_path} > /data/linux/rootfs.img && rm -f {dest_path} && sync"
                res = subprocess.run([self.adb, "-s", serial, "shell", decomp_cmd], capture_output=True, text=True, creationflags=NO_WINDOW_FLAG)
                if res.returncode != 0:
                    raise RuntimeError(f"unxz failed: {res.stderr}")
                subprocess.run([self.adb, "-s", serial, "shell", "/sbin/e2fsck -fy /data/linux/rootfs.img 2>/dev/null || true"], capture_output=True, creationflags=NO_WINDOW_FLAG)
                subprocess.run([self.adb, "-s", serial, "shell", "/sbin/resize2fs /data/linux/rootfs.img 2>/dev/null || true"], capture_output=True, creationflags=NO_WINDOW_FLAG)

            elif is_gz:
                self.update_progress(0.76, "Decompressing GZ image on octa-core CPU...")
                decomp_cmd = f"/sbin/pigz -d -c {dest_path} > /data/linux/rootfs.img && rm -f {dest_path} && sync"
                res = subprocess.run([self.adb, "-s", serial, "shell", decomp_cmd], capture_output=True, text=True, creationflags=NO_WINDOW_FLAG)
                if res.returncode != 0:
                    raise RuntimeError(f"pigz failed: {res.stderr}")
                subprocess.run([self.adb, "-s", serial, "shell", "/sbin/e2fsck -fy /data/linux/rootfs.img 2>/dev/null || true"], capture_output=True, creationflags=NO_WINDOW_FLAG)
                subprocess.run([self.adb, "-s", serial, "shell", "/sbin/resize2fs /data/linux/rootfs.img 2>/dev/null || true"], capture_output=True, creationflags=NO_WINDOW_FLAG)

            else:
                self.update_progress(0.76, "Moving raw image to rootfs...")
                install_cmd = f"mv {dest_path} /data/linux/rootfs.img && sync"
                res = subprocess.run([self.adb, "-s", serial, "shell", install_cmd], capture_output=True, text=True, creationflags=NO_WINDOW_FLAG)
                if res.returncode != 0:
                    raise RuntimeError(f"Move failed: {res.stderr}")
                subprocess.run([self.adb, "-s", serial, "shell", "/sbin/e2fsck -fy /data/linux/rootfs.img 2>/dev/null || true"], capture_output=True, creationflags=NO_WINDOW_FLAG)
                subprocess.run([self.adb, "-s", serial, "shell", "/sbin/resize2fs /data/linux/rootfs.img 2>/dev/null || true"], capture_output=True, creationflags=NO_WINDOW_FLAG)

            # Step 6: Inject Universal Galaxy S8 Hardware Foundation (90% -> 95%)
            self.update_progress(0.90, "Injecting S8 hardware shims, GIDs & audio firmwares...")
            ssid = self.cfg.get("wifi_ssid", "").strip()
            psk = self.cfg.get("wifi_password", "").strip()
            host = self.cfg.get("hostname", "").strip() or "Galaxy-S8-Linux"
            user_pass = self.cfg.get("user_password", "").strip() or "ubuntu"

            if ssid:
                if psk:
                    wpa = f'ctrl_interface=/var/run/wpa_supplicant\nupdate_config=1\n\nnetwork={{\n    ssid="{ssid}"\n    psk="{psk}"\n    key_mgmt=WPA-PSK\n}}\n'
                else:
                    wpa = f'ctrl_interface=/var/run/wpa_supplicant\nupdate_config=1\n\nnetwork={{\n    ssid="{ssid}"\n    key_mgmt=NONE\n}}\n'
                wpa_cmd = f"cat << 'EOF' > /data/linux/wpa_ubuntu.conf\n{wpa}\nEOF\nchmod 600 /data/linux/wpa_ubuntu.conf"
                subprocess.run([self.adb, "-s", serial, "shell", wpa_cmd], capture_output=True, creationflags=NO_WINDOW_FLAG)

            subprocess.run([self.adb, "-s", serial, "shell", f"echo '{host}' > /data/linux/hostname"], capture_output=True, creationflags=NO_WINDOW_FLAG)

            inject_script = (
                "mkdir -p /mnt/ubuntu && "
                "mountpoint -q /mnt/ubuntu || mount -t ext4 -o rw,noatime /data/linux/rootfs.img /mnt/ubuntu 2>/dev/null || true; "
                "mkdir -p /mnt/ubuntu/etc /mnt/ubuntu/usr/local/bin /mnt/ubuntu/usr/local/src /mnt/ubuntu/lib/modules /mnt/ubuntu/etc/firmware /mnt/ubuntu/vendor/firmware /mnt/ubuntu/var/log /mnt/ubuntu/etc/apt/apt.conf.d /mnt/ubuntu/mnt/android_data; "
                "for g in 'aid_graphics:x:1004:' 'aid_audio:x:1005:' 'aid_input:x:1005:' 'aid_camera:x:1006:' 'aid_inet:x:3003:' 'aid_net_raw:x:3004:' 'aid_sdcard_rw:x:1015:'; do "
                "  grep -q \"^${g%%:*}\" /mnt/ubuntu/etc/group 2>/dev/null || echo \"$g\" >> /mnt/ubuntu/etc/group 2>/dev/null; "
                "done; "
                "for grp in aid_graphics aid_audio aid_inet aid_net_raw aid_sdcard_rw; do "
                "  sed -i \"s/^$grp:x:[0-9]*:/&root,/\" /mnt/ubuntu/etc/group 2>/dev/null || true; "
                "done; "
                "echo -e 'nameserver 1.1.1.1\\nnameserver 8.8.8.8' > /mnt/ubuntu/etc/resolv.conf 2>/dev/null; "
                f"echo '{host}' > /mnt/ubuntu/etc/hostname 2>/dev/null; "
                f"echo '127.0.0.1 localhost {host}' > /mnt/ubuntu/etc/hosts 2>/dev/null; "
                "echo 'APT::Sandbox::User \"root\"; APT::Sandbox::Seccomp \"false\";' > /mnt/ubuntu/etc/apt/apt.conf.d/99sandbox 2>/dev/null || true; "
                "cp -r /etc/firmware/* /mnt/ubuntu/etc/firmware/ 2>/dev/null || true; "
                "cp -r /etc/firmware/* /mnt/ubuntu/vendor/firmware/ 2>/dev/null || true; "
                "if [ -d /data/linux ]; then "
                "  cp /data/linux/s8ctl.py /mnt/ubuntu/usr/local/bin/s8ctl 2>/dev/null || true; "
                "  cp /data/linux/s8_typec_daemon.py /mnt/ubuntu/usr/local/bin/s8_typec_daemon.py 2>/dev/null || true; "
                "  cp /data/linux/init_audio.sh /mnt/ubuntu/usr/local/bin/init_audio.sh 2>/dev/null || true; "
                "  cp /data/linux/asound.conf /mnt/ubuntu/etc/asound.conf 2>/dev/null || true; "
                "  cp /data/linux/start_ubuntu_desktop.sh /mnt/ubuntu/usr/local/bin/start_ubuntu_desktop.sh 2>/dev/null || true; "
                "  chmod +x /mnt/ubuntu/usr/local/bin/* 2>/dev/null || true; "
                "  if [ -f /data/linux/wpa_ubuntu.conf ]; then "
                "    cp /data/linux/wpa_ubuntu.conf /mnt/ubuntu/etc/wpa_ubuntu.conf 2>/dev/null || true; "
                "    mkdir -p /mnt/ubuntu/etc/wpa_supplicant 2>/dev/null || true; "
                "    cp /data/linux/wpa_ubuntu.conf /mnt/ubuntu/etc/wpa_supplicant/wpa_supplicant.conf 2>/dev/null || true; "
                "  fi; "
                "fi; "
                f"echo 'root:{user_pass}' | chroot /mnt/ubuntu chpasswd 2>/dev/null || true; "
                "sync; "
                "umount -l /mnt/ubuntu 2>/dev/null || true"
            )
            subprocess.run([self.adb, "-s", serial, "shell", inject_script], capture_output=True, creationflags=NO_WINDOW_FLAG)

            manifest = json.dumps(self.cfg, indent=2)
            subprocess.run([self.adb, "-s", serial, "shell", f"cat << 'EOF' > /data/linux/os_config.json\n{manifest}\nEOF"], capture_output=True, creationflags=NO_WINDOW_FLAG)
            subprocess.run([self.adb, "-s", serial, "shell", "touch /data/linux/.installed && sync"], capture_output=True, creationflags=NO_WINDOW_FLAG)

            # Step 7: Launch System & Complete (95% -> 100%)
            self.update_progress(0.95, "Validating ext4 & launching services...")
            subprocess.run([self.adb, "-s", serial, "shell", "/sbin/e2fsck -p /data/linux/rootfs.img"], capture_output=True, creationflags=NO_WINDOW_FLAG)
            subprocess.run(
                [self.adb, "-s", serial, "shell", "if [ -f /data/linux/start_all.sh ]; then nohup /sbin/sh /data/linux/start_all.sh >/dev/null 2>&1 & fi"],
                capture_output=True,
                creationflags=NO_WINDOW_FLAG
            )
            for _ in range(3):
                self.pulse_haptic(serial, 150)
                time.sleep(0.25)

            self.update_progress(1.0, "Flash Complete — OS Booted & Active")
            log("FlasherWorker completed successfully!")
            success = True
        except Exception as e:
            log(f"FlasherWorker ERROR: {e}")
            self.update_progress(0.0, f"Error: {e}")
            success = False
        finally:
            log(f"FlasherWorker finished (success={success})")
            self.app.after(0, lambda: self.on_complete(success))


class GalaxyS8FlasherUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("S8 Imager — Universal Linux Installer & Device Manager")
        self.geometry("960x650")
        self.minsize(920, 600)
        self.configure(fg_color=COLORS["bg"])

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)  # Row 2 contains the active page

        self.selected_image_path = ""
        self.adb_path = find_adb()
        self.is_flashing = False
        self.is_installed = False
        self.is_connected = False
        self.terminal_window = None
        self.user_selected_serial = None
        self.current_serial = ""
        self.cached_devices = []
        self.torch_state = False
        self.has_auto_switched_to_manager = False

        self._build_header()
        self._build_navigation()
        self._build_flasher_page()
        self._build_manager_page()

        # Default to Flasher view initially
        self._show_flasher_page()

        # Check for default ROM
        default_img = find_default_image()
        if default_img:
            self.selected_image_path = default_img
            self.path_entry.delete(0, tk.END)
            self.path_entry.insert(0, default_img)
            filename = os.path.basename(default_img)
            size_mb = os.path.getsize(default_img) / (1024 * 1024)
            st = detect_image_structure(default_img)
            self.img_status_lbl.configure(text=f"Ready: {filename} ({size_mb:.0f} MB • {st['desc']})", text_color=COLORS["success"])

        # Start non-blocking background device poller
        self.poller = DevicePoller(self, self.adb_path)
        self.poller.start()

    # ------------------------------------------------------------------
    # 1. TOP BAR (Identity + Dynamic Device Dropdown + Status Pill)
    # ------------------------------------------------------------------
    def _build_header(self):
        header = ctk.CTkFrame(
            self, fg_color=COLORS["surface"], corner_radius=12,
            border_width=1, border_color=COLORS["border"]
        )
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(16, 8))
        header.grid_columnconfigure(1, weight=1)

        # Left Brand & SoC Badge
        brand_frame = ctk.CTkFrame(header, fg_color="transparent")
        brand_frame.grid(row=0, column=0, padx=16, pady=10, sticky="w")

        phone_icon = VectorIcon(brand_frame, "phone", size=24, bg=COLORS["surface"], color=COLORS["primary"])
        phone_icon.pack(side="left", padx=(0, 10))

        title_lbl = ctk.CTkLabel(
            brand_frame, text="Galaxy S8 Imager",
            font=ctk.CTkFont(family="Segoe UI", size=17, weight="bold"),
            text_color=COLORS["text"]
        )
        title_lbl.pack(side="left", padx=(0, 10))

        soc_badge = ctk.CTkLabel(
            brand_frame, text="EXYNOS 8895",
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
            fg_color=COLORS["surface_alt"], text_color=COLORS["text_muted"],
            corner_radius=6, padx=8, pady=2
        )
        soc_badge.pack(side="left")

        # Right Hardware Selector Dropdown + Status Pill
        status_frame = ctk.CTkFrame(header, fg_color="transparent")
        status_frame.grid(row=0, column=2, padx=16, pady=10, sticky="e")

        self.device_combo = ctk.CTkComboBox(
            status_frame,
            values=["Scanning for USB devices..."],
            width=310,
            height=30,
            font=ctk.CTkFont(family="Consolas", size=11),
            dropdown_font=ctk.CTkFont(family="Consolas", size=11),
            fg_color=COLORS["surface_alt"],
            border_color=COLORS["border"],
            button_color=COLORS["primary"],
            text_color=COLORS["text"],
            command=self._on_device_selected
        )
        self.device_combo.pack(side="left", padx=(0, 10))

        self.status_pill = ctk.CTkLabel(
            status_frame, text="● CONNECTED",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color=COLORS["success_bg"], text_color=COLORS["success"],
            corner_radius=14, padx=12, pady=4
        )
        self.status_pill.pack(side="left")

    # ------------------------------------------------------------------
    # 2. NAVIGATION SEGMENTED SWITCHER (Multi-Page Switcher)
    # ------------------------------------------------------------------
    def _build_navigation(self):
        nav_frame = ctk.CTkFrame(self, fg_color="transparent")
        nav_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 10))
        nav_frame.grid_columnconfigure(0, weight=1)

        self.nav_seg = ctk.CTkSegmentedButton(
            nav_frame,
            values=["⚡ OS FLASHER", "🖥️ DEVICE MANAGER"],
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            selected_color=COLORS["primary"],
            selected_hover_color=COLORS["primary_hover"],
            command=self._on_nav_changed,
            height=36
        )
        self.nav_seg.set("⚡ OS FLASHER")
        self.nav_seg.pack(fill="x")

    def _on_nav_changed(self, choice: str):
        if "FLASHER" in choice:
            self._show_flasher_page()
        else:
            self._show_manager_page()

    def _show_flasher_page(self):
        self.page_manager.grid_remove()
        self.page_flasher.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0, 14))
        self.nav_seg.set("⚡ OS FLASHER")

    def _show_manager_page(self):
        self.page_flasher.grid_remove()
        self.page_manager.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0, 14))
        self.nav_seg.set("🖥️ DEVICE MANAGER")

    # ------------------------------------------------------------------
    # 3. PAGE 1: OS FLASHER & PROVISIONING VIEW
    # ------------------------------------------------------------------
    def _build_flasher_page(self):
        self.page_flasher = ctk.CTkFrame(self, fg_color="transparent")
        self.page_flasher.grid_columnconfigure(0, weight=1)
        self.page_flasher.grid_rowconfigure(2, weight=1)

        # Card A: OS Image Selection
        img_card = ctk.CTkFrame(
            self.page_flasher, fg_color=COLORS["surface"], corner_radius=12,
            border_width=1, border_color=COLORS["border"]
        )
        img_card.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        img_card.grid_columnconfigure(1, weight=1)

        disc_icon = VectorIcon(img_card, "disc", size=22, bg=COLORS["surface"], color=COLORS["primary"])
        disc_icon.grid(row=0, column=0, padx=(16, 10), pady=(12, 6), sticky="w")

        ctk.CTkLabel(
            img_card, text="OS IMAGE & DISTRIBUTION",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=COLORS["text_muted"]
        ).grid(row=0, column=1, pady=(12, 6), sticky="w")

        self.img_status_lbl = ctk.CTkLabel(
            img_card, text="No package selected",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=COLORS["danger"]
        )
        self.img_status_lbl.grid(row=0, column=2, padx=16, pady=(12, 6), sticky="e")

        self.path_entry = ctk.CTkEntry(
            img_card, placeholder_text="Select Ubuntu, Raspberry Pi OS, Debian 12, or Arch rootfs / .img...",
            height=36, fg_color=COLORS["surface_alt"], border_color=COLORS["border"],
            text_color=COLORS["text"], font=ctk.CTkFont(family="Consolas", size=11)
        )
        self.path_entry.grid(row=1, column=0, columnspan=2, sticky="ew", padx=(16, 8), pady=(0, 14))

        self.browse_btn = ctk.CTkButton(
            img_card, text="Choose OS", width=110, height=36,
            fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"],
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=self._on_browse
        )
        self.browse_btn.grid(row=1, column=2, padx=(0, 16), pady=(0, 14))

        # Card B: Storage Provisioning & Flash Settings
        prov_card = ctk.CTkFrame(
            self.page_flasher, fg_color=COLORS["surface"], corner_radius=12,
            border_width=1, border_color=COLORS["border"]
        )
        prov_card.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        prov_card.grid_columnconfigure((0, 1), weight=1)

        p_header = ctk.CTkFrame(prov_card, fg_color="transparent")
        p_header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=16, pady=(12, 6))

        host_icon = VectorIcon(p_header, "host", size=20, bg=COLORS["surface"], color=COLORS["primary"])
        host_icon.pack(side="left", padx=(0, 8))

        ctk.CTkLabel(
            p_header, text="STORAGE & PROVISIONING SETTINGS",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=COLORS["text_muted"]
        ).pack(side="left")

        # Storage allocation segmented selector
        alloc_f = ctk.CTkFrame(prov_card, fg_color="transparent")
        alloc_f.grid(row=1, column=0, columnspan=2, sticky="ew", padx=16, pady=(0, 8))
        alloc_f.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            alloc_f, text="Userdata Allocation:",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=COLORS["text"]
        ).grid(row=0, column=0, padx=(0, 10), sticky="w")

        self.size_seg = ctk.CTkSegmentedButton(
            alloc_f,
            values=["10 GB (Standard)", "16 GB (Recommended)", "32 GB (Large)", "53 GB (Full Storage)"],
            font=ctk.CTkFont(family="Segoe UI", size=11),
            selected_color=COLORS["primary"],
            selected_hover_color=COLORS["primary_hover"],
            height=28
        )
        self.size_seg.set("10 GB (Standard)")
        self.size_seg.grid(row=0, column=1, sticky="ew")

        # Toggles row (Clean Wipe & Fast Charge)
        toggles_f = ctk.CTkFrame(prov_card, fg_color="transparent")
        toggles_f.grid(row=2, column=0, columnspan=2, sticky="ew", padx=14, pady=(0, 10))
        toggles_f.grid_columnconfigure((0, 1), weight=1)

        self.toggle_wipe = ToggleRow(
            toggles_f, "wipe", "Clean Install", "Format /data partition ext4",
            default_on=True, icon_color=COLORS["warning"]
        )
        self.toggle_wipe.grid(row=0, column=0, sticky="ew", padx=4, pady=2)

        self.toggle_charge = ToggleRow(
            toggles_f, "bolt", "1,500 mA Fast Charge", "Unlock MAX77865 PMIC current limit",
            default_on=True, icon_color=COLORS["success"]
        )
        self.toggle_charge.grid(row=0, column=1, sticky="ew", padx=4, pady=2)

        # Hidden default toggles for backend compatibility
        self.toggle_ssh = ToggleRow(self, "ssh", "SSH", "SSH", default_on=True)
        self.toggle_vnc = ToggleRow(self, "vnc", "VNC", "VNC", default_on=True)

        # Card C / Footer: Progress & Action Execution
        flasher_footer = ctk.CTkFrame(
            self.page_flasher, fg_color=COLORS["surface"], corner_radius=12,
            border_width=1, border_color=COLORS["border"]
        )
        flasher_footer.grid(row=2, column=0, sticky="ew", pady=(0, 4))
        flasher_footer.grid_columnconfigure(0, weight=1)

        prog_box = ctk.CTkFrame(flasher_footer, fg_color="transparent")
        prog_box.grid(row=0, column=0, sticky="ew", padx=16, pady=12)
        prog_box.grid_columnconfigure(0, weight=1)

        self.status_lbl = ctk.CTkLabel(
            prog_box, text="Ready to write image",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=COLORS["text_muted"]
        )
        self.status_lbl.grid(row=0, column=0, sticky="w", pady=(0, 6))

        self.percent_lbl = ctk.CTkLabel(
            prog_box, text="0%",
            font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
            text_color=COLORS["primary"]
        )
        self.percent_lbl.grid(row=0, column=1, sticky="e", pady=(0, 6))

        self.progress_bar = ctk.CTkProgressBar(
            prog_box, height=8, corner_radius=4,
            fg_color=COLORS["surface_alt"], progress_color=COLORS["primary"]
        )
        self.progress_bar.grid(row=1, column=0, columnspan=2, sticky="ew")
        self.progress_bar.set(0)

        self.flash_btn = ctk.CTkButton(
            flasher_footer, text="WRITE OS", width=140, height=42,
            fg_color=COLORS["flash_btn"], hover_color=COLORS["flash_hover"],
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            corner_radius=8, command=self._on_flash_clicked
        )
        self.flash_btn.grid(row=0, column=1, padx=(4, 16), pady=12)

    # ------------------------------------------------------------------
    # 4. PAGE 2: OS & DEVICE MANAGER VIEW
    # ------------------------------------------------------------------
    def _build_manager_page(self):
        self.page_manager = ctk.CTkFrame(self, fg_color="transparent")
        self.page_manager.grid_columnconfigure(0, weight=1)
        self.page_manager.grid_rowconfigure(1, weight=1)

        # Card A: Dynamic Detected OS Banner
        os_banner = ctk.CTkFrame(
            self.page_manager, fg_color=COLORS["surface"], corner_radius=12,
            border_width=1, border_color=COLORS["border"]
        )
        os_banner.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        os_banner.grid_columnconfigure(1, weight=1)

        os_icon = VectorIcon(os_banner, "host", size=24, bg=COLORS["surface"], color=COLORS["success"])
        os_icon.grid(row=0, column=0, rowspan=2, padx=(16, 12), pady=12, sticky="w")

        self.os_title_lbl = ctk.CTkLabel(
            os_banner, text="● OS ACTIVE: Detecting distribution...",
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            text_color=COLORS["success"]
        )
        self.os_title_lbl.grid(row=0, column=1, sticky="w", pady=(10, 0))

        self.os_sub_lbl = ctk.CTkLabel(
            os_banner, text="Kernel 4.4.111 #14 aarch64 • USB ADB Active • Port Forwarding Ready",
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color=COLORS["text_muted"]
        )
        self.os_sub_lbl.grid(row=1, column=1, sticky="w", pady=(0, 10))

        ref_btn = ctk.CTkButton(
            os_banner, text="Refresh", width=70, height=28,
            fg_color=COLORS["surface_alt"], hover_color=COLORS["primary"],
            font=ctk.CTkFont(family="Segoe UI", size=11),
            command=self._refresh_manager_state
        )
        ref_btn.grid(row=0, column=2, rowspan=2, padx=16, pady=12, sticky="e")

        # 2-Column Split Body (Left: Vitals & Controls | Right: Wi-Fi & Access)
        split_body = ctk.CTkFrame(self.page_manager, fg_color="transparent")
        split_body.grid(row=1, column=0, sticky="nsew")
        split_body.grid_columnconfigure((0, 1), weight=1)
        split_body.grid_rowconfigure(0, weight=1)

        # === LEFT COLUMN: Hardware Vitals + Controls ===
        left_m = ctk.CTkFrame(split_body, fg_color="transparent")
        left_m.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        left_m.grid_columnconfigure(0, weight=1)

        # Card 1: Hardware Vitals
        vitals_card = ctk.CTkFrame(
            left_m, fg_color=COLORS["surface"], corner_radius=12,
            border_width=1, border_color=COLORS["border"]
        )
        vitals_card.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        vitals_card.grid_columnconfigure(0, weight=1)

        v_head = ctk.CTkFrame(vitals_card, fg_color="transparent")
        v_head.pack(fill="x", padx=14, pady=(10, 6))
        VectorIcon(v_head, "phone", size=18, bg=COLORS["surface"], color=COLORS["primary"]).pack(side="left", padx=(0, 6))
        ctk.CTkLabel(v_head, text="HARDWARE VITALS", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color=COLORS["text_muted"]).pack(side="left")

        self.cpu_lbl = ctk.CTkLabel(vitals_card, text="CPU: Exynos 8895 (4x M2 @ 2.3 GHz + 4x A53 @ 1.7 GHz)", font=ctk.CTkFont(family="Consolas", size=11), text_color=COLORS["text"], anchor="w")
        self.cpu_lbl.pack(fill="x", padx=16, pady=2)

        self.ram_lbl = ctk.CTkLabel(vitals_card, text="RAM: Detecting memory...", font=ctk.CTkFont(family="Consolas", size=11), text_color=COLORS["text"], anchor="w")
        self.ram_lbl.pack(fill="x", padx=16, pady=2)

        self.batt_lbl = ctk.CTkLabel(vitals_card, text="Battery: Detecting power...", font=ctk.CTkFont(family="Consolas", size=11), text_color=COLORS["text"], anchor="w")
        self.batt_lbl.pack(fill="x", padx=16, pady=2)

        self.kernel_lbl = ctk.CTkLabel(vitals_card, text="Kernel: Linux localhost 4.4.111 #14 SMP PREEMPT", font=ctk.CTkFont(family="Consolas", size=11), text_color=COLORS["text_muted"], anchor="w")
        self.kernel_lbl.pack(fill="x", padx=16, pady=(2, 10))

        # Card 2: Hardware Quick Controls
        ctrl_card = ctk.CTkFrame(
            left_m, fg_color=COLORS["surface"], corner_radius=12,
            border_width=1, border_color=COLORS["border"]
        )
        ctrl_card.grid(row=1, column=0, sticky="ew")
        ctrl_card.grid_columnconfigure((0, 1), weight=1)

        c_head = ctk.CTkFrame(ctrl_card, fg_color="transparent")
        c_head.grid(row=0, column=0, columnspan=2, sticky="ew", padx=14, pady=(10, 6))
        VectorIcon(c_head, "bolt", size=18, bg=COLORS["surface"], color=COLORS["primary"]).pack(side="left", padx=(0, 6))
        ctk.CTkLabel(c_head, text="HARDWARE CONTROLS", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color=COLORS["text_muted"]).pack(side="left")

        self.torch_btn = ctk.CTkButton(
            ctrl_card, text="🔦 Flashlight: OFF", height=32,
            fg_color=COLORS["surface_alt"], hover_color=COLORS["primary"],
            font=ctk.CTkFont(family="Segoe UI", size=11),
            command=self._on_torch_toggle
        )
        self.torch_btn.grid(row=1, column=0, padx=(14, 4), pady=(0, 6), sticky="ew")

        haptic_btn = ctk.CTkButton(
            ctrl_card, text="📳 Pulse Haptic", height=32,
            fg_color=COLORS["surface_alt"], hover_color=COLORS["primary"],
            font=ctk.CTkFont(family="Segoe UI", size=11),
            command=self._on_haptic_pulse
        )
        haptic_btn.grid(row=1, column=1, padx=(4, 14), pady=(0, 6), sticky="ew")

        reboot_down_btn = ctk.CTkButton(
            ctrl_card, text="⬇️ Reboot Odin", height=32,
            fg_color=COLORS["surface_alt"], hover_color=COLORS["warning"],
            font=ctk.CTkFont(family="Segoe UI", size=11),
            command=self._on_reboot_download
        )
        reboot_down_btn.grid(row=2, column=0, padx=(14, 4), pady=(0, 10), sticky="ew")

        reboot_rec_btn = ctk.CTkButton(
            ctrl_card, text="🔄 Reboot Device", height=32,
            fg_color=COLORS["surface_alt"], hover_color=COLORS["danger"],
            font=ctk.CTkFont(family="Segoe UI", size=11),
            command=self._on_reboot_device
        )
        reboot_rec_btn.grid(row=2, column=1, padx=(4, 14), pady=(0, 10), sticky="ew")

        # === RIGHT COLUMN: Universal Wi-Fi + Remote Consoles ===
        right_m = ctk.CTkFrame(split_body, fg_color="transparent")
        right_m.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        right_m.grid_columnconfigure(0, weight=1)

        # Card 3: Universal Hardware Wi-Fi Manager
        wifi_card = ctk.CTkFrame(
            right_m, fg_color=COLORS["surface"], corner_radius=12,
            border_width=1, border_color=COLORS["border"]
        )
        wifi_card.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        wifi_card.grid_columnconfigure(1, weight=1)

        w_head = ctk.CTkFrame(wifi_card, fg_color="transparent")
        w_head.grid(row=0, column=0, columnspan=2, sticky="ew", padx=14, pady=(10, 6))
        VectorIcon(w_head, "wifi", size=18, bg=COLORS["surface"], color=COLORS["primary"]).pack(side="left", padx=(0, 6))
        ctk.CTkLabel(w_head, text="WI-FI MANAGER (Dual-Band 2.4 / 5 GHz)", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color=COLORS["text_muted"]).pack(side="left")

        self.wifi_ip_badge = ctk.CTkLabel(
            w_head, text="Disconnected", font=ctk.CTkFont(family="Consolas", size=11),
            fg_color=COLORS["surface_alt"], text_color=COLORS["text_muted"], corner_radius=6, padx=8, pady=2
        )
        self.wifi_ip_badge.pack(side="right")

        # SSID Dropdown + Scan Button
        ssid_f = ctk.CTkFrame(wifi_card, fg_color="transparent")
        ssid_f.grid(row=1, column=0, columnspan=2, sticky="ew", padx=14, pady=(0, 6))
        ssid_f.grid_columnconfigure(0, weight=1)

        self.ssid_entry = ctk.CTkComboBox(
            ssid_f, values=["(Click Scan for Wi-Fi)"], height=32,
            fg_color=COLORS["surface_alt"], border_color=COLORS["border"],
            text_color=COLORS["text"], font=ctk.CTkFont(family="Consolas", size=11)
        )
        self.ssid_entry.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        self.scan_btn = ctk.CTkButton(
            ssid_f, text="SCAN", width=55, height=32,
            fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"],
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            command=self._on_scan_wifi
        )
        self.scan_btn.grid(row=0, column=1)

        # Password + Connect Button
        pass_f = ctk.CTkFrame(wifi_card, fg_color="transparent")
        pass_f.grid(row=2, column=0, columnspan=2, sticky="ew", padx=14, pady=(0, 10))
        pass_f.grid_columnconfigure(0, weight=1)

        self.wifi_pass_entry = ctk.CTkEntry(
            pass_f, placeholder_text="Enter Wi-Fi Password...", height=32,
            show="•", fg_color=COLORS["surface_alt"], border_color=COLORS["border"],
            text_color=COLORS["text"], font=ctk.CTkFont(family="Consolas", size=11)
        )
        self.wifi_pass_entry.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        self.wifi_conn_btn = ctk.CTkButton(
            pass_f, text="CONNECT", width=75, height=32,
            fg_color=COLORS["success"], hover_color="#059669",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            command=self._on_connect_wifi
        )
        self.wifi_conn_btn.grid(row=0, column=1)

        # Card 4: Access Consoles & Dedicated Virtual Screen
        access_card = ctk.CTkFrame(
            right_m, fg_color=COLORS["surface"], corner_radius=12,
            border_width=1, border_color=COLORS["border"]
        )
        access_card.grid(row=1, column=0, sticky="ew")
        access_card.grid_columnconfigure((0, 1), weight=1)

        a_head = ctk.CTkFrame(access_card, fg_color="transparent")
        a_head.grid(row=0, column=0, columnspan=2, sticky="ew", padx=14, pady=(10, 6))
        VectorIcon(a_head, "host", size=18, bg=COLORS["surface"], color=COLORS["primary"]).pack(side="left", padx=(0, 6))
        ctk.CTkLabel(a_head, text="REMOTE CONSOLE & VIRTUAL DISPLAY", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color=COLORS["text_muted"]).pack(side="left")

        self.terminal_btn = ctk.CTkButton(
            access_card, text="ROOT TERMINAL", height=38,
            fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"],
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=self._open_terminal
        )
        self.terminal_btn.grid(row=1, column=0, padx=(14, 4), pady=(0, 6), sticky="ew")

        self.desktop_btn = ctk.CTkButton(
            access_card, text="DEVICE SCREEN", height=38,
            fg_color=COLORS["success"], hover_color="#059669",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=self._open_desktop
        )
        self.desktop_btn.grid(row=1, column=1, padx=(4, 14), pady=(0, 6), sticky="ew")

        wire_lbl = ctk.CTkLabel(
            access_card, text="⚡ USB Wire Port Relay: :6080 (noVNC) • :5901 (RFB) • :2222 (SSH)",
            font=ctk.CTkFont(family="Consolas", size=10), text_color=COLORS["text_muted"]
        )
        wire_lbl.grid(row=2, column=0, columnspan=2, pady=(0, 8))

    # ------------------------------------------------------------------
    # 5. HARDWARE CONTROLS CALLBACKS
    # ------------------------------------------------------------------
    def _on_torch_toggle(self):
        serial = self.get_active_serial()
        if not serial: return
        self.torch_state = not getattr(self, "torch_state", False)
        val = "1" if self.torch_state else "0"
        subprocess.run([self.adb_path, "-s", serial, "shell", f"echo {val} > /sys/class/leds/torch-sec1/brightness"], creationflags=NO_WINDOW_FLAG)
        self.torch_btn.configure(
            text=f"🔦 Flashlight: {'ON' if self.torch_state else 'OFF'}",
            fg_color=COLORS["primary"] if self.torch_state else COLORS["surface_alt"]
        )

    def _on_haptic_pulse(self):
        serial = self.get_active_serial()
        if not serial: return
        subprocess.run([self.adb_path, "-s", serial, "shell", "echo 150 > /sys/class/timed_output/vibrator/enable"], creationflags=NO_WINDOW_FLAG)

    def _on_reboot_download(self):
        serial = self.get_active_serial()
        if not serial: return
        subprocess.run([self.adb_path, "-s", serial, "reboot", "download"], creationflags=NO_WINDOW_FLAG)

    def _on_reboot_device(self):
        serial = self.get_active_serial()
        if not serial: return
        subprocess.run([self.adb_path, "-s", serial, "reboot"], creationflags=NO_WINDOW_FLAG)

    def _refresh_manager_state(self):
        if hasattr(self, "poller"):
            self.poller.last_state = None

    # ------------------------------------------------------------------
    # 6. UNIVERSAL WI-FI MANAGER LOGIC (Distro-Agnostic)
    # ------------------------------------------------------------------
    def _on_scan_wifi(self):
        if not self.is_connected:
            self.status_lbl.configure(text="Cannot scan: Galaxy S8 not connected")
            return
        self.scan_btn.configure(text="...", state="disabled")
        self.status_lbl.configure(text="Scanning dual-band 2.4 GHz & 5 GHz networks...")

        def worker():
            serial = self.get_active_serial()
            if not serial:
                return
            subprocess.run([self.adb_path, "-s", serial, "shell", "ip link set wlan0 up 2>/dev/null"], creationflags=NO_WINDOW_FLAG)
            scan_cmd = (
                "pgrep -f wpa_supplicant >/dev/null || { "
                "mkdir -p /mnt/ubuntu/var/run/wpa_supplicant /mnt/ubuntu/run/wpa_supplicant; "
                "echo 'ctrl_interface=/var/run/wpa_supplicant' > /mnt/ubuntu/etc/wpa_scan.conf; "
                "chroot /mnt/ubuntu /usr/sbin/wpa_supplicant -B -i wlan0 -c /etc/wpa_scan.conf 2>/dev/null || true; "
                "sleep 1; }; "
                "chroot /mnt/ubuntu wpa_cli -i wlan0 scan >/dev/null 2>&1; "
                "sleep 4; "
                "chroot /mnt/ubuntu wpa_cli -i wlan0 scan_results 2>/dev/null || wpa_cli -i wlan0 scan_results 2>/dev/null"
            )
            res = subprocess.run([self.adb_path, "-s", serial, "shell", scan_cmd], capture_output=True, text=True, creationflags=NO_WINDOW_FLAG, timeout=12)
            parsed_entries = []
            if res.stdout:
                for line in res.stdout.splitlines():
                    parts = line.strip().split("\t")
                    if len(parts) >= 5 and parts[4].strip():
                        s = parts[4].strip()
                        if s != "ssid":
                            try:
                                freq = int(parts[1])
                                sig = int(parts[2])
                            except Exception:
                                freq, sig = 2400, -100
                            parsed_entries.append({"ssid": s, "freq": freq, "sig": sig})

            parsed_entries.sort(key=lambda x: x["sig"], reverse=True)
            ssids = []
            for item in parsed_entries:
                if item["ssid"] not in ssids:
                    ssids.append(item["ssid"])

            def update():
                self.scan_btn.configure(text="SCAN", state="normal")
                if ssids:
                    self.ssid_entry.configure(values=ssids)
                    self.ssid_entry.set(ssids[0])
                    num_5g = sum(1 for item in parsed_entries if item["freq"] >= 5000)
                    self.status_lbl.configure(text=f"Found {len(ssids)} Wi-Fi networks (2.4 GHz + 5 GHz dual-band) • Selected: {ssids[0]}")
                else:
                    self.status_lbl.configure(text="Scan complete • No Wi-Fi SSIDs detected over the air")
            self.after(0, update)

        threading.Thread(target=worker, daemon=True).start()

    def _on_connect_wifi(self):
        serial = self.get_active_serial()
        ssid = self.ssid_entry.get().strip()
        psk = self.wifi_pass_entry.get().strip()
        if not serial or not ssid or ssid == "(Click Scan for Wi-Fi)":
            return
        self.wifi_conn_btn.configure(text="CONNECTING...", state="disabled")
        self.status_lbl.configure(text=f"Connecting to {ssid}...")

        def worker():
            if psk:
                wpa = f'ctrl_interface=/var/run/wpa_supplicant\nupdate_config=1\n\nnetwork={{\n    ssid="{ssid}"\n    psk="{psk}"\n    key_mgmt=WPA-PSK\n}}\n'
            else:
                wpa = f'ctrl_interface=/var/run/wpa_supplicant\nupdate_config=1\n\nnetwork={{\n    ssid="{ssid}"\n    key_mgmt=NONE\n}}\n'

            subprocess.run([self.adb_path, "-s", serial, "shell", f"cat << 'EOF' > /data/linux/wpa_supplicant.conf\n{wpa}\nEOF\nchmod 600 /data/linux/wpa_supplicant.conf"], creationflags=NO_WINDOW_FLAG)
            subprocess.run([self.adb_path, "-s", serial, "shell", "cp /data/linux/wpa_supplicant.conf /mnt/ubuntu/etc/wpa_ubuntu.conf 2>/dev/null; cp /data/linux/wpa_supplicant.conf /mnt/ubuntu/etc/wpa_supplicant/wpa_supplicant.conf 2>/dev/null"], creationflags=NO_WINDOW_FLAG)

            conn_cmd = (
                "killall wpa_supplicant 2>/dev/null || true; "
                "sleep 1; "
                "chroot /mnt/ubuntu /usr/sbin/wpa_supplicant -B -i wlan0 -c /etc/wpa_ubuntu.conf 2>/dev/null || true; "
                "for i in 1 2 3 4 5 6 7 8; do "
                "  sleep 1; "
                "  if chroot /mnt/ubuntu wpa_cli -i wlan0 status 2>/dev/null | grep -q 'wpa_state=COMPLETED'; then "
                "    chroot /mnt/ubuntu /usr/sbin/dhclient -v wlan0 2>/dev/null || true; "
                "    echo 'nameserver 1.1.1.1' > /mnt/ubuntu/etc/resolv.conf 2>/dev/null; "
                "    echo 'nameserver 8.8.8.8' >> /mnt/ubuntu/etc/resolv.conf 2>/dev/null; "
                "    break; "
                "  fi; "
                "done; "
                "ip -4 addr show wlan0 2>/dev/null | grep 'inet ' | awk '{print $2}'"
            )
            res = subprocess.run([self.adb_path, "-s", serial, "shell", conn_cmd], capture_output=True, text=True, creationflags=NO_WINDOW_FLAG, timeout=16)
            ip = ""
            if res.stdout:
                for line in res.stdout.splitlines():
                    if "/" in line and line.strip()[0].isdigit():
                        ip = line.strip().split("/")[0]

            def update():
                self.wifi_conn_btn.configure(text="CONNECT", state="normal")
                if ip:
                    self.wifi_ip_badge.configure(text=f"● IP: {ip}", fg_color=COLORS["success_bg"], text_color=COLORS["success"])
                    self.status_lbl.configure(text=f"Connected to {ssid} • Assigned IP: {ip}")
                else:
                    self.status_lbl.configure(text=f"Wi-Fi configuration applied for {ssid}")
                if hasattr(self, "poller"):
                    self.poller.last_state = None
            self.after(0, update)

        threading.Thread(target=worker, daemon=True).start()

    # ------------------------------------------------------------------
    # 7. TERMINAL & VIRTUAL DISPLAY LAUNCHERS
    # ------------------------------------------------------------------
    def _open_terminal(self):
        """Opens genuine in-app interactive root terminal directly inside the app."""
        log("Opening in-app interactive root terminal via ADB")
        serial = self.get_active_serial()
        model = self.poller.last_model if hasattr(self.poller, "last_model") and self.poller.last_model else "Galaxy S8"
        if not serial:
            self.status_lbl.configure(text="Cannot open terminal: No device connected via USB")
            return
        if self.terminal_window is not None and self.terminal_window.winfo_exists():
            self.terminal_window.focus()
            self.terminal_window.lift()
        else:
            self.terminal_window = InAppTerminalWindow(self, self.adb_path, serial, model, is_installed=self.is_installed)

    def _open_desktop(self):
        """Relays the default OS display stream over the dedicated USB wire."""
        import webbrowser
        log("Opening desktop stream over USB wire")
        target_ser = self.get_active_serial()
        if target_ser:
            try:
                subprocess.run([self.adb_path, "-s", target_ser, "forward", "tcp:6080", "tcp:6080"], creationflags=NO_WINDOW_FLAG)
                subprocess.run([self.adb_path, "-s", target_ser, "forward", "tcp:5901", "tcp:5901"], creationflags=NO_WINDOW_FLAG)
                subprocess.run([self.adb_path, "-s", target_ser, "forward", "tcp:2222", "tcp:22"], creationflags=NO_WINDOW_FLAG)
            except Exception as e:
                log(f"Desktop port forward error: {e}")
        self.status_lbl.configure(text="Desktop active at http://localhost:6080/ (VNC Lite • Password: ubuntu)")
        webbrowser.open("http://localhost:6080/vnc_lite.html?password=ubuntu&scale=true")

    # ------------------------------------------------------------------
    # 8. STATE UPDATER & DYNAMIC HARDWARE TELEMETRY
    # ------------------------------------------------------------------
    def set_device_state(self, connected: bool, devices=None, serial="---", model="Galaxy S8", mode="none", installed=False, detected_os="", vitals=None):
        """Updates top bar hardware dropdown and status pill dynamically across pages."""
        self.is_connected = connected
        self.is_installed = installed
        self.current_serial = serial if connected else ""

        if connected and devices:
            self.cached_devices = devices
            options = []
            selected_option = ""
            for d in devices:
                opt = f"{d['model']} ({d['serial']} • {d['mode']})"
                options.append(opt)
                if d['serial'] == serial:
                    selected_option = opt

            if not selected_option and options:
                selected_option = options[0]

            self.device_combo.configure(values=options)
            if self.device_combo.get() != selected_option:
                self.device_combo.set(selected_option)

            self.terminal_btn.configure(state="normal", fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"])
            self.desktop_btn.configure(state="normal", fg_color=COLORS["success"], hover_color="#059669")

            if installed:
                self.status_pill.configure(
                    text="● OS ACTIVE", fg_color=COLORS["success_bg"], text_color=COLORS["success"]
                )
                self.os_title_lbl.configure(
                    text=f"● OS ACTIVE: {detected_os or 'Linux OS'}",
                    text_color=COLORS["success"]
                )
                if not self.has_auto_switched_to_manager and not self.is_flashing:
                    self.has_auto_switched_to_manager = True
                    self._show_manager_page()
            else:
                self.status_pill.configure(
                    text="● BASE AP READY", fg_color=COLORS["success_bg"], text_color=COLORS["success"]
                )
                self.os_title_lbl.configure(
                    text="● BASE AP READY: Samsung Galaxy S8 (Kernel #14 Active)",
                    text_color=COLORS["primary"]
                )

            # Update vitals
            if vitals:
                if vitals.get("mem_total_gb"):
                    self.ram_lbl.configure(text=f"RAM: {vitals['mem_free_gb']:.1f} GB Free / {vitals['mem_total_gb']:.1f} GB Total")
                if vitals.get("battery_pct") != "---":
                    self.batt_lbl.configure(text=f"Battery: {vitals['battery_pct']}% • {vitals.get('battery_temp', '')} • 1,500 mA Fast Charge")
                if vitals.get("wifi_ip") and vitals["wifi_ip"] != "Disconnected":
                    self.wifi_ip_badge.configure(text=f"● IP: {vitals['wifi_ip']}", fg_color=COLORS["success_bg"], text_color=COLORS["success"])
                else:
                    self.wifi_ip_badge.configure(text="Disconnected", fg_color=COLORS["surface_alt"], text_color=COLORS["text_muted"])
        else:
            self.cached_devices = []
            self.device_combo.configure(values=["No Device Connected"])
            self.device_combo.set("No Device Connected")
            self.status_pill.configure(
                text="○ DISCONNECTED", fg_color="#3F1D24", text_color=COLORS["danger"]
            )
            self.os_title_lbl.configure(
                text="○ No Device Connected via USB", text_color=COLORS["danger"]
            )
            self.terminal_btn.configure(state="disabled", fg_color=COLORS["surface_alt"])
            self.desktop_btn.configure(state="disabled", fg_color=COLORS["surface_alt"])

    def get_active_serial(self) -> str:
        if hasattr(self, "user_selected_serial") and self.user_selected_serial:
            return self.user_selected_serial
        if hasattr(self, "current_serial") and self.current_serial:
            return self.current_serial
        if hasattr(self, "poller") and self.poller.last_serial:
            return self.poller.last_serial
        devs = get_connected_devices(self.adb_path)
        if devs:
            return devs[0]["serial"]
        return ""

    def _on_device_selected(self, choice: str):
        log(f"User selected device choice: {choice}")
        for d in getattr(self, "cached_devices", []):
            if d["serial"] in choice:
                self.user_selected_serial = d["serial"]
                self.current_serial = d["serial"]
                if hasattr(self, "poller"):
                    self.poller.last_state = None
                break

    def _on_browse(self):
        file_path = filedialog.askopenfilename(
            title="Select Galaxy S8 OS Image",
            filetypes=[("OS Images & Archives", "*.img.gz *.img.xz *.img *.raw *.raw.xz *.tar.gz *.tar.xz *.tar *.tgz *.zip"), ("All Files", "*.*")]
        )
        if file_path:
            self.selected_image_path = file_path
            self.path_entry.delete(0, tk.END)
            self.path_entry.insert(0, file_path)
            filename = os.path.basename(file_path)
            size_mb = os.path.getsize(file_path) / (1024 * 1024)
            self.img_status_lbl.configure(text=f"Analyzing {filename}...", text_color=COLORS["primary"])
            def check():
                st = detect_image_structure(file_path)
                lbl = f"Ready: {filename} ({size_mb:.0f} MB • {st['desc']})"
                self.after(0, lambda: self.img_status_lbl.configure(text=lbl, text_color=COLORS["success"]))
            threading.Thread(target=check, daemon=True).start()

    def get_configuration(self) -> dict:
        return {
            "image_path": self.path_entry.get().strip(),
            "wifi_ssid": self.ssid_entry.get().strip(),
            "wifi_password": self.wifi_pass_entry.get(),
            "hostname": "Galaxy-S8-Linux",
            "user_password": "ubuntu",
            "clean_wipe": self.toggle_wipe.get(),
            "enable_ssh": True,
            "enable_vnc": True,
            "fast_charge_1500ma": self.toggle_charge.get(),
        }

    def set_progress(self, ratio: float, status_text: str):
        self.progress_bar.set(ratio)
        self.percent_lbl.configure(text=f"{int(ratio * 100)}%")
        self.status_lbl.configure(text=status_text)

    def _on_flash_clicked(self):
        log("User clicked WRITE OS")
        cfg = self.get_configuration()
        if not cfg["image_path"] or not os.path.exists(cfg["image_path"]):
            self.img_status_lbl.configure(text="Please choose a valid OS image first", text_color=COLORS["danger"])
            self.status_lbl.configure(text="Cannot write: No valid image file selected")
            return

        if not self.is_connected:
            self.status_lbl.configure(text="Cannot write: Galaxy S8 not detected via USB")
            return

        self.is_flashing = True
        self.flash_btn.configure(state="disabled", text="WRITING...", fg_color=COLORS["surface_alt"])
        self.browse_btn.configure(state="disabled")

        def on_worker_complete(success: bool):
            self.is_flashing = False
            self.browse_btn.configure(state="normal")
            self.flash_btn.configure(state="normal", text="WRITE OS", fg_color=COLORS["flash_btn"])
            if success:
                self.is_installed = True
                self.img_status_lbl.configure(text="Installed Successfully", text_color=COLORS["success"])
                self.status_lbl.configure(text="Flash Complete! Forwarding ports & opening Device Manager...")
                try:
                    target_ser = self.get_active_serial()
                    if target_ser:
                        subprocess.run([self.adb_path, "-s", target_ser, "forward", "tcp:6080", "tcp:6080"], creationflags=NO_WINDOW_FLAG)
                        subprocess.run([self.adb_path, "-s", target_ser, "forward", "tcp:5901", "tcp:5901"], creationflags=NO_WINDOW_FLAG)
                        subprocess.run([self.adb_path, "-s", target_ser, "forward", "tcp:2222", "tcp:22"], creationflags=NO_WINDOW_FLAG)
                except Exception as e:
                    log(f"Port forward error: {e}")

                self._show_manager_page()
                if hasattr(self, "poller"):
                    self.poller.last_state = None
            else:
                self.img_status_lbl.configure(text="Deployment Failed", text_color=COLORS["danger"])

        log(f"Starting FlasherWorker with image: {cfg['image_path']}")
        worker = FlasherWorker(self, self.adb_path, cfg, on_worker_complete)
        worker.start()



if __name__ == "__main__":
    log("Galaxy S8 Flasher launched")
    app = GalaxyS8FlasherUI()
    app.mainloop()
