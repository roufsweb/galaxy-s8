import os
import sys
import time
import shutil
import subprocess
import threading
import json
import tkinter as tk
from tkinter import filedialog
import customtkinter as ctk

# Windows creation flag to completely suppress flashing console windows
NO_WINDOW_FLAG = 0x08000000 if sys.platform == "win32" else 0
WORKSPACE = os.path.dirname(os.path.abspath(__file__))

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


class DevicePoller(threading.Thread):
    """Zero-sluggishness background daemon thread for non-blocking ADB polling."""
    def __init__(self, app, adb_path):
        super().__init__(daemon=True)
        self.app = app
        self.adb = adb_path
        self.running = True
        self.last_state = None

    def run(self):
        while self.running:
            try:
                p = subprocess.run(
                    [self.adb, "devices"],
                    capture_output=True,
                    text=True,
                    creationflags=NO_WINDOW_FLAG,
                    timeout=3
                )
                serial, mode = None, None
                if p.stdout:
                    for line in p.stdout.splitlines()[1:]:
                        parts = line.strip().split()
                        if len(parts) >= 2:
                            serial, mode = parts[0], parts[1]
                            break

                curr_state = (serial is not None, serial, mode)
                if curr_state != self.last_state:
                    self.last_state = curr_state
                    connected = serial is not None
                    s_ser = serial if serial else "---"
                    s_mode = mode if mode else "none"
                    self.app.after(0, lambda c=connected, s=s_ser, m=s_mode: self.app.set_device_state(c, "SM-G950N", s, m))
            except Exception:
                if self.last_state != (False, None, None):
                    self.last_state = (False, None, None)
                    self.app.after(0, lambda: self.app.set_device_state(False, "SM-G950N", "---", "none"))
            time.sleep(1.5)


class FlasherWorker(threading.Thread):
    """Background worker thread executing storage wipe, provisioning, push, and boot."""
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
        p = subprocess.run([self.adb, "devices"], capture_output=True, text=True, creationflags=NO_WINDOW_FLAG)
        if p.stdout:
            for line in p.stdout.splitlines()[1:]:
                parts = line.strip().split()
                if len(parts) >= 2:
                    return parts[0]
        return None

    def run(self):
        success = False
        try:
            serial = self.get_serial()
            if not serial:
                raise RuntimeError("No Galaxy S8 device detected via USB")

            image_path = self.cfg["image_path"]
            if not os.path.exists(image_path):
                raise RuntimeError(f"Image not found: {image_path}")

            filename = os.path.basename(image_path)
            file_size = os.path.getsize(image_path)
            file_mb = file_size / (1024 * 1024)

            # Step 1: Storage & Clean Wipe (5% -> 15%)
            self.update_progress(0.05, "Preparing storage subsystem...")
            if self.cfg.get("clean_wipe", True):
                self.update_progress(0.08, "Wiping /data (USERDATA) to clean ext4...")
                storage_cmd = (
                    "umount -l /mnt/ubuntu 2>/dev/null || true; "
                    "umount -l /data 2>/dev/null || true; "
                    "mke2fs -F -t ext4 /dev/block/platform/11120000.ufs/by-name/USERDATA && "
                    "mount -t ext4 /dev/block/platform/11120000.ufs/by-name/USERDATA /data && "
                    "mkdir -p /data/linux /mnt/ubuntu"
                )
            else:
                storage_cmd = (
                    "if ! mountpoint -q /data; then "
                    "  mount /data 2>/dev/null || "
                    "  (mke2fs -F -t ext4 /dev/block/platform/11120000.ufs/by-name/USERDATA && mount /data); "
                    "fi; "
                    "mkdir -p /data/linux /mnt/ubuntu"
                )
            subprocess.run([self.adb, "-s", serial, "shell", storage_cmd], capture_output=True, creationflags=NO_WINDOW_FLAG, check=True)

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
                for s in ["start_all.sh", "start_ubuntu_desktop.sh", "connect_wifi.sh", "init_audio.sh", "s8ctl.py", "asound.conf"]:
                    sp = os.path.join(scripts_dir, s)
                    if os.path.exists(sp):
                        subprocess.run([self.adb, "-s", serial, "push", sp, f"/data/linux/{s}"], capture_output=True, creationflags=NO_WINDOW_FLAG)
                        subprocess.run([self.adb, "-s", serial, "shell", f"chmod 755 /data/linux/{s}"], capture_output=True, creationflags=NO_WINDOW_FLAG)

            # Step 4: Stream OS Image over High-Speed USB (25% -> 75%)
            dest_path = f"/data/{filename}"
            self.update_progress(0.25, f"Streaming {filename} ({file_mb:.0f} MB)...")
            proc = subprocess.Popen(
                [self.adb, "-s", serial, "push", image_path, dest_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=NO_WINDOW_FLAG
            )

            last_update_time = 0
            for line in iter(proc.stdout.readline, ""):
                if "%" in line:
                    now = time.time()
                    if now - last_update_time >= 0.08:
                        last_update_time = now
                        try:
                            pct_str = [p for p in line.split() if "%" in p][0].replace("%", "").replace("[", "").replace("]", "")
                            ratio = 0.25 + (float(pct_str) / 100.0) * 0.50
                            self.update_progress(ratio, f"Transferring {filename}: {line.strip()}")
                        except Exception:
                            pass
            proc.wait()
            if proc.returncode != 0:
                raise RuntimeError("USB file transfer failed")

            # Step 5: Decompress rootfs image (75% -> 90%)
            self.update_progress(0.75, "Extracting rootfs image on octa-core CPU...")
            if filename.endswith(".gz"):
                install_cmd = (
                    f"/sbin/pigz -d -c {dest_path} > /data/linux/rootfs.img.tmp && "
                    "mv /data/linux/rootfs.img.tmp /data/linux/rootfs.img && "
                    f"rm -f {dest_path} && sync"
                )
            else:
                install_cmd = f"mv {dest_path} /data/linux/rootfs.img && sync"

            res = subprocess.run([self.adb, "-s", serial, "shell", install_cmd], capture_output=True, text=True, creationflags=NO_WINDOW_FLAG)
            if res.returncode != 0:
                raise RuntimeError(f"Extraction failed: {res.stderr}")

            # Step 6: Apply Pre-Flash Customizations (90% -> 95%)
            self.update_progress(0.90, "Applying network credentials & hostname...")
            ssid = self.cfg.get("wifi_ssid", "").strip()
            psk = self.cfg.get("wifi_password", "").strip()
            if ssid:
                if psk:
                    wpa = f'ctrl_interface=/var/run/wpa_supplicant\nupdate_config=1\n\nnetwork={{\n    ssid="{ssid}"\n    psk="{psk}"\n    key_mgmt=WPA-PSK\n}}\n'
                else:
                    wpa = f'ctrl_interface=/var/run/wpa_supplicant\nupdate_config=1\n\nnetwork={{\n    ssid="{ssid}"\n    key_mgmt=NONE\n}}\n'
                wpa_cmd = f"cat << 'EOF' > /data/linux/wpa_ubuntu.conf\n{wpa}\nEOF\nchmod 600 /data/linux/wpa_ubuntu.conf"
                subprocess.run([self.adb, "-s", serial, "shell", wpa_cmd], capture_output=True, creationflags=NO_WINDOW_FLAG)

            host = self.cfg.get("hostname", "").strip()
            if host:
                subprocess.run([self.adb, "-s", serial, "shell", f"echo '{host}' > /data/linux/hostname"], capture_output=True, creationflags=NO_WINDOW_FLAG)

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

            self.update_progress(1.0, "Flash Complete — Ubuntu Active")
            success = True
        except Exception as e:
            self.update_progress(0.0, f"Error: {e}")
            success = False
        finally:
            self.app.after(0, lambda: self.on_complete(success))


class GalaxyS8FlasherUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("S8 Imager — SM-G950N")
        self.geometry("940x580")
        self.minsize(880, 540)
        self.configure(fg_color=COLORS["bg"])

        # Main layout grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.selected_image_path = ""
        self.adb_path = find_adb()

        self._build_header()
        self._build_body()
        self._build_footer()

        # Check for default ROM
        for candidate in [
            os.path.join(WORKSPACE, "releases", "ubuntu-24.04-arm64.img.gz"),
            os.path.join(WORKSPACE, "releases", "ubuntu-24.04-arm64.img"),
        ]:
            if os.path.exists(candidate):
                self.selected_image_path = candidate
                self.path_entry.delete(0, tk.END)
                self.path_entry.insert(0, candidate)
                filename = os.path.basename(candidate)
                self.img_status_lbl.configure(text=f"Ready: {filename}", text_color=COLORS["success"])
                break

        # Start non-blocking background device poller
        self.poller = DevicePoller(self, self.adb_path)
        self.poller.start()

    # ------------------------------------------------------------------
    # 1. COMPACT TOP BAR (Identity + Live Device Status Pill)
    # ------------------------------------------------------------------
    def _build_header(self):
        header = ctk.CTkFrame(
            self, fg_color=COLORS["surface"], corner_radius=12,
            border_width=1, border_color=COLORS["border"]
        )
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(18, 10))
        header.grid_columnconfigure(1, weight=1)

        # Left Brand & SoC Badge
        brand_frame = ctk.CTkFrame(header, fg_color="transparent")
        brand_frame.grid(row=0, column=0, padx=16, pady=12, sticky="w")

        phone_icon = VectorIcon(brand_frame, "phone", size=26, bg=COLORS["surface"], color=COLORS["primary"])
        phone_icon.pack(side="left", padx=(0, 10))

        title_lbl = ctk.CTkLabel(
            brand_frame, text="Galaxy S8 Imager",
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
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

        # Right Hardware Telemetry + Status Pill
        status_frame = ctk.CTkFrame(header, fg_color="transparent")
        status_frame.grid(row=0, column=2, padx=16, pady=12, sticky="e")

        self.device_meta_lbl = ctk.CTkLabel(
            status_frame,
            text="SM-G950N  •  ce10171ab3e9620804  •  recovery",
            font=ctk.CTkFont(family="Consolas", size=12),
            text_color=COLORS["text_muted"]
        )
        self.device_meta_lbl.pack(side="left", padx=(0, 12))

        self.status_pill = ctk.CTkLabel(
            status_frame, text="● CONNECTED",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color=COLORS["success_bg"], text_color=COLORS["success"],
            corner_radius=14, padx=12, pady=4
        )
        self.status_pill.pack(side="left")

    # ------------------------------------------------------------------
    # 2. SPLIT 2-COLUMN BODY (Left: Image + Config | Right: Toggles)
    # ------------------------------------------------------------------
    def _build_body(self):
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=20, pady=6)
        body.grid_columnconfigure(0, weight=3)  # Left column wider
        body.grid_columnconfigure(1, weight=2)  # Right column compact
        body.grid_rowconfigure(0, weight=1)

        # === LEFT COLUMN ===
        left_col = ctk.CTkFrame(body, fg_color="transparent")
        left_col.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        left_col.grid_columnconfigure(0, weight=1)
        left_col.grid_rowconfigure(1, weight=1)

        # Card A: OS Image Selector (Raspberry Pi Imager Style)
        img_card = ctk.CTkFrame(
            left_col, fg_color=COLORS["surface"], corner_radius=12,
            border_width=1, border_color=COLORS["border"]
        )
        img_card.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        img_card.grid_columnconfigure(1, weight=1)

        disc_icon = VectorIcon(img_card, "disc", size=24, bg=COLORS["surface"], color=COLORS["primary"])
        disc_icon.grid(row=0, column=0, padx=(16, 10), pady=(14, 6), sticky="w")

        ctk.CTkLabel(
            img_card, text="OS IMAGE",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=COLORS["text_muted"]
        ).grid(row=0, column=1, pady=(14, 6), sticky="w")

        self.img_status_lbl = ctk.CTkLabel(
            img_card, text="No package selected",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=COLORS["danger"]
        )
        self.img_status_lbl.grid(row=0, column=2, padx=16, pady=(14, 6), sticky="e")

        self.path_entry = ctk.CTkEntry(
            img_card, placeholder_text="Select Ubuntu 24.04 rootfs / tar.lz4 / .img...",
            height=38, fg_color=COLORS["surface_alt"], border_color=COLORS["border"],
            text_color=COLORS["text"], font=ctk.CTkFont(family="Consolas", size=12)
        )
        self.path_entry.grid(row=1, column=0, columnspan=2, sticky="ew", padx=(16, 8), pady=(0, 16))

        self.browse_btn = ctk.CTkButton(
            img_card, text="Choose OS", width=110, height=38,
            fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"],
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=self._on_browse
        )
        self.browse_btn.grid(row=1, column=2, padx=(0, 16), pady=(0, 16))

        # Card B: Pre-Flash Network & System Identity
        net_card = ctk.CTkFrame(
            left_col, fg_color=COLORS["surface"], corner_radius=12,
            border_width=1, border_color=COLORS["border"]
        )
        net_card.grid(row=1, column=0, sticky="nsew")
        net_card.grid_columnconfigure((0, 1), weight=1)

        header_row = ctk.CTkFrame(net_card, fg_color="transparent")
        header_row.grid(row=0, column=0, columnspan=2, sticky="ew", padx=16, pady=(14, 8))

        wifi_icon = VectorIcon(header_row, "wifi", size=22, bg=COLORS["surface"], color=COLORS["primary"])
        wifi_icon.pack(side="left", padx=(0, 8))

        ctk.CTkLabel(
            header_row, text="NETWORK & CREDENTIALS",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=COLORS["text_muted"]
        ).pack(side="left")

        # 2x2 Compact Input Grid
        self.ssid_entry = self._create_field(net_card, 1, 0, "Wi-Fi SSID", "")
        self.wifi_pass_entry = self._create_field(net_card, 1, 1, "Wi-Fi Password", "", show="•")
        self.hostname_entry = self._create_field(net_card, 3, 0, "Hostname", "Galaxy-S8-Ubuntu")
        self.user_pass_entry = self._create_field(net_card, 3, 1, "Root / Ubuntu Password", "ubuntu", show="•")

        # === RIGHT COLUMN (Hardware & Service Toggles) ===
        right_col = ctk.CTkFrame(
            body, fg_color=COLORS["surface"], corner_radius=12,
            border_width=1, border_color=COLORS["border"]
        )
        right_col.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        right_col.grid_columnconfigure(0, weight=1)

        r_header = ctk.CTkFrame(right_col, fg_color="transparent")
        r_header.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 10))

        host_icon = VectorIcon(r_header, "host", size=22, bg=COLORS["surface"], color=COLORS["primary"])
        host_icon.pack(side="left", padx=(0, 8))

        ctk.CTkLabel(
            r_header, text="FEATURES & SERVICES",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=COLORS["text_muted"]
        ).pack(side="left")

        # Toggle Containers
        self.toggle_wipe = ToggleRow(
            right_col, "wipe", "Clean Install", "Wipe /data & format ext4",
            default_on=True, icon_color=COLORS["warning"]
        )
        self.toggle_wipe.grid(row=1, column=0, sticky="ew", padx=14, pady=5)

        self.toggle_ssh = ToggleRow(
            right_col, "ssh", "OpenSSH Server", "Port :22 • root & ubuntu",
            default_on=True, icon_color=COLORS["primary"]
        )
        self.toggle_ssh.grid(row=2, column=0, sticky="ew", padx=14, pady=5)

        self.toggle_vnc = ToggleRow(
            right_col, "vnc", "Web Desktop (noVNC)", "Port :6080 • X11 Session",
            default_on=True, icon_color=COLORS["primary"]
        )
        self.toggle_vnc.grid(row=3, column=0, sticky="ew", padx=14, pady=5)

        self.toggle_charge = ToggleRow(
            right_col, "bolt", "1,500 mA Fast Charge", "Unlock USB current limit",
            default_on=True, icon_color=COLORS["success"]
        )
        self.toggle_charge.grid(row=4, column=0, sticky="ew", padx=14, pady=5)

    def _create_field(self, parent, row, col, label, default_val="", show=None):
        pad_x = (16, 8) if col == 0 else (8, 16)
        ctk.CTkLabel(
            parent, text=label,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=COLORS["text"]
        ).grid(row=row, column=col, sticky="w", padx=pad_x, pady=(8, 4))

        entry = ctk.CTkEntry(
            parent, height=36, fg_color=COLORS["surface_alt"],
            border_color=COLORS["border"], text_color=COLORS["text"],
            font=ctk.CTkFont(family="Consolas", size=12), show=show
        )
        entry.grid(row=row + 1, column=col, sticky="ew", padx=pad_x, pady=(0, 8))
        if default_val:
            entry.insert(0, default_val)
        return entry

    # ------------------------------------------------------------------
    # 3. ACTION FOOTER (Telemetry Progress + Primary Flash Trigger)
    # ------------------------------------------------------------------
    def _build_footer(self):
        footer = ctk.CTkFrame(
            self, fg_color=COLORS["surface"], corner_radius=12,
            border_width=1, border_color=COLORS["border"]
        )
        footer.grid(row=2, column=0, sticky="ew", padx=20, pady=(10, 18))
        footer.grid_columnconfigure(0, weight=1)

        prog_box = ctk.CTkFrame(footer, fg_color="transparent")
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
            footer, text="WRITE OS", width=150, height=42,
            fg_color=COLORS["flash_btn"], hover_color=COLORS["flash_hover"],
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            corner_radius=8, command=self._on_flash_clicked
        )
        self.flash_btn.grid(row=0, column=1, padx=(4, 16), pady=12)

    # ------------------------------------------------------------------
    # 4. HOOKS FOR ANTIGRAVITY BACKEND LOGIC
    # ------------------------------------------------------------------
    def _on_browse(self):
        file_path = filedialog.askopenfilename(
            title="Select Galaxy S8 OS Image",
            filetypes=[("OS Archives & Images", "*.img.gz *.tar.gz *.tar.lz4 *.img *.zip"), ("All Files", "*.*")]
        )
        if file_path:
            self.selected_image_path = file_path
            self.path_entry.delete(0, tk.END)
            self.path_entry.insert(0, file_path)
            filename = os.path.basename(file_path)
            self.img_status_lbl.configure(text=f"Ready: {filename}", text_color=COLORS["success"])

    def get_configuration(self) -> dict:
        """Returns pre-flash configuration dictionary for the flashing worker."""
        return {
            "image_path": self.path_entry.get().strip(),
            "wifi_ssid": self.ssid_entry.get().strip(),
            "wifi_password": self.wifi_pass_entry.get(),
            "hostname": self.hostname_entry.get().strip(),
            "user_password": self.user_pass_entry.get(),
            "clean_wipe": self.toggle_wipe.get(),
            "enable_ssh": self.toggle_ssh.get(),
            "enable_vnc": self.toggle_vnc.get(),
            "fast_charge_1500ma": self.toggle_charge.get(),
        }

    def set_progress(self, ratio: float, status_text: str):
        """Thread-safe UI updater for flashing progress (ratio: 0.0 to 1.0)."""
        self.progress_bar.set(ratio)
        self.percent_lbl.configure(text=f"{int(ratio * 100)}%")
        self.status_lbl.configure(text=status_text)

    def set_device_state(self, connected: bool, model="SM-G950N", serial="---", mode="none"):
        """Updates top bar hardware pill dynamically."""
        self.device_meta_lbl.configure(text=f"{model}  •  {serial}  •  {mode}")
        if connected:
            self.status_pill.configure(
                text="● CONNECTED", fg_color=COLORS["success_bg"], text_color=COLORS["success"]
            )
        else:
            self.status_pill.configure(
                text="○ DISCONNECTED", fg_color="#3F1D24", text_color=COLORS["danger"]
            )

    def _on_flash_clicked(self):
        cfg = self.get_configuration()
        if not cfg["image_path"] or not os.path.exists(cfg["image_path"]):
            self.img_status_lbl.configure(text="Select a valid file first", text_color=COLORS["danger"])
            return

        # Lock UI buttons during flash
        self.flash_btn.configure(state="disabled", text="WRITING...", fg_color=COLORS["surface_alt"])
        self.browse_btn.configure(state="disabled")

        def on_worker_complete(success: bool):
            self.flash_btn.configure(state="normal", text="WRITE OS", fg_color=COLORS["flash_btn"])
            self.browse_btn.configure(state="normal")
            if success:
                self.img_status_lbl.configure(text="Installed Successfully", text_color=COLORS["success"])
            else:
                self.img_status_lbl.configure(text="Deployment Failed", text_color=COLORS["danger"])

        worker = FlasherWorker(self, self.adb_path, cfg, on_worker_complete)
        worker.start()


if __name__ == "__main__":
    app = GalaxyS8FlasherUI()
    app.mainloop()

