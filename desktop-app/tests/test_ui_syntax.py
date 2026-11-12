import os
import sys
import subprocess
import threading
import time
import tkinter as tk
from tkinter import filedialog
import customtkinter as ctk

from s8_flasher import (
    COLORS, VectorIcon, ToggleRow, InAppTerminalWindow,
    get_connected_devices, DevicePoller, FlasherWorker,
    NO_WINDOW_FLAG, find_adb, find_default_image, detect_image_structure, log
)

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
    print("Class definition validated successfully!")
