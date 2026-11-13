#!/usr/bin/env python3
"""
s8_avatar_window.py — Full-Screen WebKitGTK Native Avatar Window for DisplayPort & Desktop.
Renders the 60 FPS Animoji Talking Face Avatar natively on Display :1.
Subscribes reactively to /tmp/s8_avatar_state.json for real-time state, text, and lip-sync amplitude.
"""

import os
import sys
import json

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

from gi.repository import Gtk, WebKit2, GLib

STATE_FILE = "/tmp/s8_avatar_state.json"

def main():
    target_url = sys.argv[1] if len(sys.argv) > 1 else "file:///mnt/android_data/s8-voice-assistant/ui/avatar.html"
    
    win = Gtk.Window()
    win.set_title("Galaxy S8 AI Assistant - Animoji Avatar")
    win.connect("destroy", Gtk.main_quit)
    
    # Configure borderless fullscreen window
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

    last_mtime = 0.0
    last_state = ""
    last_text = ""
    last_amp = 0.0

    def check_state():
        nonlocal last_mtime, last_state, last_text, last_amp
        try:
            if os.path.exists(STATE_FILE):
                mtime = os.path.getmtime(STATE_FILE)
                if mtime != last_mtime:
                    last_mtime = mtime
                    with open(STATE_FILE, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    
                    st = data.get("state", "IDLE")
                    txt = data.get("text", "")
                    spk = data.get("speaker", "GALAXY S8 ASSISTANT")
                    amp = float(data.get("amplitude", 0.0))

                    if st != last_state or txt != last_text:
                        last_state = st
                        last_text = txt
                        safe_txt = json.dumps(txt)
                        safe_spk = json.dumps(spk)
                        safe_st = json.dumps(st)
                        js = f"window.setAssistantState({safe_st}, {safe_txt}, {safe_spk});"
                        web_view.run_javascript(js, None, None, None)
                        print(f"[*] Updated avatar state: {st} | {spk}: {txt}", flush=True)

                    if abs(amp - last_amp) > 0.02:
                        last_amp = amp
                        js_amp = f"window.setAudioAmplitude({amp:.3f});"
                        web_view.run_javascript(js_amp, None, None, None)
        except Exception as e:
            print(f"[!] Avatar state error: {e}", flush=True)
        return True

    def on_load_changed(view, event):
        if event == WebKit2.LoadEvent.FINISHED:
            print("[*] Avatar HTML loaded successfully. Starting state sync timer...", flush=True)
            GLib.timeout_add(50, check_state)

    web_view.connect("load-changed", on_load_changed)
    
    print(f"[*] Native WebKitGTK Avatar window running on {os.environ.get('DISPLAY')}...")
    Gtk.main()

if __name__ == "__main__":
    main()
