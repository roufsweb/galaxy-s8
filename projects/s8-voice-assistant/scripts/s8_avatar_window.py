#!/usr/bin/env python3
"""
s8_avatar_window.py — Full-Screen WebKitGTK Native Avatar Window for DisplayPort & Desktop.
Renders the 60 FPS Animoji Talking Face Avatar natively on Display :1.
Supports automatic portrait and landscape scaling.
"""

import os
import sys

# Antigravity Rule 7 environment guards for Exynos 8895 / X11
os.environ["GSK_RENDERER"] = "cairo"
os.environ["GDK_BACKEND"] = "x11"
os.environ["GTK_USE_PORTAL"] = "0"
os.environ["GDK_DEBUG"] = "no-portals"
os.environ["GTK_A11Y"] = "none"
os.environ["WEBKIT_DISABLE_SANDBOX_THIS_IS_DANGEROUS"] = "1"
os.environ["WEBKIT_DISABLE_DMABUF_RENDERER"] = "1"
os.environ["WEBKIT_DISABLE_COMPOSITING_MODE"] = "1"

if "DISPLAY" not in os.environ:
    os.environ["DISPLAY"] = ":1"

import gi
gi.require_version("Gtk", "3.0")
try:
    gi.require_version("WebKit2", "4.1")
except ValueError:
    gi.require_version("WebKit2", "4.0")

from gi.repository import Gtk, WebKit2

def main():
    target_url = sys.argv[1] if len(sys.argv) > 1 else "file:///mnt/android_data/s8-voice-assistant/ui/avatar.html"
    
    win = Gtk.Window()
    win.set_title("Galaxy S8 AI Assistant - Animoji Avatar")
    win.connect("destroy", Gtk.main_quit)
    
    # Configure borderless window sized to current screen
    win.fullscreen()
    
    settings = WebKit2.Settings()
    settings.set_enable_javascript(True)
    settings.set_enable_webgl(True)
    settings.set_allow_file_access_from_file_urls(True)
    settings.set_allow_universal_access_from_file_urls(True)
    
    web_view = WebKit2.WebView.new_with_settings(settings)
    web_view.load_uri(target_url)
    
    win.add(web_view)
    win.show_all()
    
    print(f"[*] Native WebKitGTK Avatar window running on {os.environ.get('DISPLAY')}...")
    Gtk.main()

if __name__ == "__main__":
    main()

