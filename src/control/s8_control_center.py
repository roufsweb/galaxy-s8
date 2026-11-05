#!/usr/bin/env python3
"""
s8_control_center.py — Samsung Galaxy S8 Native macOS Sonoma Control Center
A beautiful, responsive GTK3 Quick Settings / Control Center window designed
for the top-right corner of the GNOME 46 macOS Sonoma desktop.
"""
import os
import sys
import subprocess
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, Gdk, GLib

CSS = b"""
window.control-center-win {
    background-color: rgba(30, 30, 34, 0.94);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 18px;
    box-shadow: 0 12px 36px rgba(0, 0, 0, 0.6);
}

.card {
    background-color: rgba(255, 255, 255, 0.07);
    border-radius: 14px;
    padding: 12px;
    border: 1px solid rgba(255, 255, 255, 0.05);
}

.card:hover {
    background-color: rgba(255, 255, 255, 0.09);
}

.card-title {
    font-size: 13px;
    font-weight: 700;
    color: #ffffff;
}

.card-subtitle {
    font-size: 11px;
    color: #a0a0aa;
}

.pill-button {
    border-radius: 12px;
    font-weight: 600;
    padding: 6px 12px;
    background-color: rgba(255, 255, 255, 0.1);
    color: #ffffff;
    border: none;
}

.pill-button:hover {
    background-color: rgba(0, 122, 255, 0.8);
    color: #ffffff;
}

.danger-button:hover {
    background-color: rgba(255, 59, 48, 0.8);
}

.active-toggle {
    background-color: #007aff;
    color: #ffffff;
}
"""

class S8ControlCenter(Gtk.Window):
    def __init__(self):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.set_title("Control Center")
        self.set_wmclass("s8-control-center", "S8ControlCenter")
        self.set_decorated(False)
        self.set_resizable(False)
        self.set_keep_above(True)
        self.set_default_size(360, 520)
        self.get_style_context().add_class("control-center-win")

        # Position in top right corner (x=1540 on 1920x1080 display)
        self.set_position(Gtk.WindowPosition.NONE)
        self.move(1540, 36)

        # Allow closing on Escape key
        self.connect("key-press-event", self.on_key_press)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        main_box.set_margin_top(14)
        main_box.set_margin_bottom(14)
        main_box.set_margin_start(14)
        main_box.set_margin_end(14)
        self.add(main_box)

        # Header with title and close button
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        title_lbl = Gtk.Label(label="Control Center")
        title_lbl.get_style_context().add_class("card-title")
        title_lbl.set_halign(Gtk.Align.START)
        header_box.pack_start(title_lbl, True, True, 0)

        close_btn = Gtk.Button(label="✕")
        close_btn.get_style_context().add_class("pill-button")
        close_btn.connect("clicked", lambda b: self.close_window())
        header_box.pack_end(close_btn, False, False, 0)
        main_box.pack_start(header_box, False, False, 0)

        # 1. Wi-Fi Card
        wifi_card = self.create_wifi_card()
        main_box.pack_start(wifi_card, False, False, 0)

        # 2. Sound Volume Card
        sound_card = self.create_sound_card()
        main_box.pack_start(sound_card, False, False, 0)

        # 3. Battery & Power Card
        batt_card = self.create_battery_card()
        main_box.pack_start(batt_card, False, False, 0)

        # 4. Performance & Quick Hardware Boost
        perf_card = self.create_perf_card()
        main_box.pack_start(perf_card, False, False, 0)

        # 5. Session Actions (Reboot / Shutdown)
        session_card = self.create_session_card()
        main_box.pack_start(session_card, False, False, 0)

        self.show_all()

    def on_key_press(self, widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self.close_window()
            return True
        return False

    def close_window(self):
        self.destroy()
        Gtk.main_quit()

    def create_wifi_card(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.get_style_context().add_class("card")

        top_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        icon = Gtk.Image.new_from_icon_name("network-wireless-signal-excellent-symbolic", Gtk.IconSize.BUTTON)
        top_row.pack_start(icon, False, False, 0)

        title = Gtk.Label(label="Wi-Fi")
        title.get_style_context().add_class("card-title")
        title.set_halign(Gtk.Align.START)
        top_row.pack_start(title, True, True, 0)

        manager_btn = Gtk.Button(label="Networks")
        manager_btn.get_style_context().add_class("pill-button")
        manager_btn.connect("clicked", lambda b: subprocess.Popen(["/usr/local/bin/s8-wifi-gui"]))
        top_row.pack_end(manager_btn, False, False, 0)
        box.pack_start(top_row, False, False, 0)

        # Info row
        ssid = "Unknown"
        ip = "192.168.0.227"
        try:
            res = subprocess.check_output("iw dev wlan0 link 2>/dev/null", shell=True).decode()
            for line in res.splitlines():
                if "SSID:" in line:
                    ssid = line.split("SSID:")[1].strip()
            ip_res = subprocess.check_output("ip -4 addr show wlan0 2>/dev/null | grep 'inet '", shell=True).decode()
            if ip_res:
                ip = ip_res.strip().split()[1].split("/")[0]
        except Exception:
            pass

        info_lbl = Gtk.Label(label=f"Connected to {ssid}  ({ip})")
        info_lbl.get_style_context().add_class("card-subtitle")
        info_lbl.set_halign(Gtk.Align.START)
        box.pack_start(info_lbl, False, False, 0)

        return box

    def create_sound_card(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.get_style_context().add_class("card")

        top_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        icon = Gtk.Image.new_from_icon_name("audio-volume-high-symbolic", Gtk.IconSize.BUTTON)
        top_row.pack_start(icon, False, False, 0)

        title = Gtk.Label(label="Sound & Volume")
        title.get_style_context().add_class("card-title")
        title.set_halign(Gtk.Align.START)
        top_row.pack_start(title, True, True, 0)

        test_btn = Gtk.Button(label="Test Audio")
        test_btn.get_style_context().add_class("pill-button")
        test_btn.connect("clicked", lambda b: subprocess.Popen(["s8ctl", "audio", "test"]))
        top_row.pack_end(test_btn, False, False, 0)
        box.pack_start(top_row, False, False, 0)

        # Volume slider
        slider_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        vol_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 5)
        vol_scale.set_value(80)

        def on_vol_change(scale):
            val = int(scale.get_value())
            subprocess.run(f"amixer set Master {val}% >/dev/null 2>&1", shell=True)

        vol_scale.connect("value-changed", on_vol_change)
        slider_row.pack_start(vol_scale, True, True, 0)
        box.pack_start(slider_row, False, False, 0)

        sub = Gtk.Label(label="Maxim MAX98506 Speaker • CS47L92 DMIC1")
        sub.get_style_context().add_class("card-subtitle")
        sub.set_halign(Gtk.Align.START)
        box.pack_start(sub, False, False, 0)

        return box

    def create_battery_card(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.get_style_context().add_class("card")

        cap = "100"
        status = "Charging"
        curr = "1500"
        try:
            with open("/sys/class/power_supply/battery/capacity", "r") as f:
                cap = f.read().strip()
            with open("/sys/class/power_supply/battery/status", "r") as f:
                status = f.read().strip()
            with open("/sys/class/power_supply/battery/current_now", "r") as f:
                curr = str(abs(int(f.read().strip())) // 1000)
        except Exception:
            pass

        top_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        icon = Gtk.Image.new_from_icon_name("battery-full-charging-symbolic", Gtk.IconSize.BUTTON)
        top_row.pack_start(icon, False, False, 0)

        title = Gtk.Label(label=f"Battery: {cap}%")
        title.get_style_context().add_class("card-title")
        title.set_halign(Gtk.Align.START)
        top_row.pack_start(title, True, True, 0)

        fast_btn = Gtk.Button(label="1500mA Boost")
        fast_btn.get_style_context().add_class("pill-button")
        fast_btn.connect("clicked", lambda b: subprocess.run("s8ctl charge-limit 100", shell=True))
        top_row.pack_end(fast_btn, False, False, 0)
        box.pack_start(top_row, False, False, 0)

        sub = Gtk.Label(label=f"{status} • Input Current: {curr} mA • MAX77865 PMIC")
        sub.get_style_context().add_class("card-subtitle")
        sub.set_halign(Gtk.Align.START)
        box.pack_start(sub, False, False, 0)

        return box

    def create_perf_card(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.get_style_context().add_class("card")

        title = Gtk.Label(label="Hardware & Performance")
        title.get_style_context().add_class("card-title")
        title.set_halign(Gtk.Align.START)
        box.pack_start(title, False, False, 0)

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        cpu_btn = Gtk.Button(label="CPU Boost (2.3GHz)")
        cpu_btn.get_style_context().add_class("pill-button")
        cpu_btn.connect("clicked", lambda b: subprocess.run("s8ctl cpu-profile max", shell=True))
        btn_row.pack_start(cpu_btn, True, True, 0)

        torch_btn = Gtk.Button(label="Torch")
        torch_btn.get_style_context().add_class("pill-button")
        torch_btn.connect("clicked", lambda b: subprocess.run("s8ctl torch toggle", shell=True))
        btn_row.pack_start(torch_btn, True, True, 0)

        vib_btn = Gtk.Button(label="Vibrate")
        vib_btn.get_style_context().add_class("pill-button")
        vib_btn.connect("clicked", lambda b: subprocess.run("s8ctl vibrate 150", shell=True))
        btn_row.pack_start(vib_btn, True, True, 0)

        box.pack_start(btn_row, False, False, 0)
        return box

    def create_session_card(self):
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        box.get_style_context().add_class("card")

        reboot_btn = Gtk.Button(label="Reboot Phone")
        reboot_btn.get_style_context().add_class("pill-button")
        reboot_btn.connect("clicked", lambda b: subprocess.Popen(["reboot"]))
        box.pack_start(reboot_btn, True, True, 0)

        term_btn = Gtk.Button(label="Open Console")
        term_btn.get_style_context().add_class("pill-button")
        term_btn.connect("clicked", lambda b: subprocess.Popen(["kgx"]))
        box.pack_start(term_btn, True, True, 0)

        return box

def main():
    if "DISPLAY" not in os.environ:
        os.environ["DISPLAY"] = ":1"

    css_provider = Gtk.CssProvider()
    css_provider.load_from_data(CSS)
    Gtk.StyleContext.add_provider_for_screen(
        Gdk.Screen.get_default(),
        css_provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )

    app = S8ControlCenter()
    Gtk.main()

if __name__ == "__main__":
    main()
