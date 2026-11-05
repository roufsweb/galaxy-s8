#!/usr/bin/env python3
"""
s8_wifi_portal.py — Captive Web Configuration Portal for Galaxy S8 Native Linux
Serves a clean, responsive Wi-Fi setup page on port 8080 during SoftAP mode.
Maintained by roufsweb (https://github.com/roufsweb)
"""
import os
import sys
import json
import time
import subprocess
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Galaxy S8 Linux — Wi-Fi Setup</title>
    <style>
        :root {
            --bg: #0f172a;
            --surface: #1e293b;
            --primary: #38bdf8;
            --text: #f8fafc;
            --text-dim: #94a3b8;
            --border: #334155;
            --btn: #0284c7;
            --btn-hover: #0369a1;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background: var(--bg);
            color: var(--text);
            margin: 0;
            padding: 24px;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            box-sizing: border-box;
        }
        .card {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 32px;
            max-width: 440px;
            width: 100%;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.4);
        }
        h1 {
            font-size: 1.35rem;
            margin-top: 0;
            margin-bottom: 8px;
            color: var(--text);
        }
        .subtitle {
            color: var(--text-dim);
            font-size: 0.88rem;
            margin-bottom: 24px;
        }
        label {
            display: block;
            font-size: 0.82rem;
            font-weight: 600;
            color: var(--text-dim);
            margin-bottom: 6px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        select, input[type="text"], input[type="password"] {
            width: 100%;
            padding: 10px 12px;
            background: #0f172a;
            border: 1px solid var(--border);
            border-radius: 6px;
            color: var(--text);
            font-size: 0.95rem;
            margin-bottom: 18px;
            box-sizing: border-box;
        }
        select:focus, input:focus {
            outline: none;
            border-color: var(--primary);
        }
        button {
            width: 100%;
            padding: 12px;
            background: var(--btn);
            color: #fff;
            border: none;
            border-radius: 6px;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            transition: background 0.15s;
        }
        button:hover {
            background: var(--btn-hover);
        }
        .footer {
            margin-top: 24px;
            text-align: center;
            font-size: 0.8rem;
            color: var(--text-dim);
        }
        .footer a {
            color: var(--primary);
            text-decoration: none;
        }
        .net-item {
            display: flex;
            justify-content: space-between;
            padding: 4px 0;
        }
    </style>
</head>
<body>
    <div class="card">
        <h1>Galaxy S8 Wi-Fi Setup</h1>
        <div class="subtitle">Select your local wireless network to connect this device.</div>
        <form method="POST" action="/connect">
            <label for="ssid">Wireless Network (SSID)</label>
            <select id="ssid" name="ssid" required>
                __NETWORK_OPTIONS__
            </select>

            <label for="password">Wi-Fi Password</label>
            <input type="password" id="password" name="password" placeholder="Leave empty for open networks">

            <button type="submit">Save and Connect</button>
        </form>
        <div class="footer">
            Maintained by <a href="https://github.com/roufsweb" target="_blank">roufsweb</a>
        </div>
    </div>
</body>
</html>
"""

def scan_ssids():
    networks = []
    seen = set()
    try:
        cmd = ["wpa_cli", "-i", "wlan0", "scan"]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2)
        time.sleep(1.2)
        res = subprocess.run(["wpa_cli", "-i", "wlan0", "scan_results"],
                             capture_output=True, text=True, timeout=3)
        for line in res.stdout.splitlines()[1:]:
            parts = line.split("\t")
            if len(parts) >= 5:
                ssid = parts[4].strip()
                if ssid and ssid not in seen:
                    freq = int(parts[1]) if parts[1].isdigit() else 2412
                    band = "5G" if freq >= 5000 else "2.4G"
                    signal = parts[2]
                    networks.append((ssid, band, signal))
                    seen.add(ssid)
    except Exception as e:
        print(f"[!] Scan error: {e}")
    return networks

class WifiPortalHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Quiet logging

    def do_GET(self):
        if self.path in ("/", "/index.html", "/hotspot-detect.html", "/generate_204"):
            networks = scan_ssids()
            options_html = ""
            if networks:
                for ssid, band, sig in networks:
                    options_html += f'<option value="{ssid}">{ssid} ({band}, {sig} dBm)</option>\n'
            else:
                options_html = '<option value="">No networks found — enter manually</option>\n'

            content = HTML_TEMPLATE.replace("__NETWORK_OPTIONS__", options_html)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content.encode("utf-8"))))
            self.end_headers()
            self.wfile.write(content.encode("utf-8"))
        else:
            # Captive portal redirection
            self.send_response(302)
            self.send_header("Location", "http://192.168.4.1:8080/")
            self.end_headers()

    def do_POST(self):
        if self.path == "/connect":
            content_len = int(self.headers.get("Content-Length", 0))
            post_body = self.rfile.read(content_len).decode("utf-8", errors="ignore")
            params = urllib.parse.parse_qs(post_body)

            ssid = params.get("ssid", [""])[0].strip()
            password = params.get("password", [""])[0].strip()

            if ssid:
                resp = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Connecting...</title>
<style>body{{font-family:sans-serif;background:#0f172a;color:#f8fafc;padding:32px;text-align:center;}}
.card{{background:#1e293b;border-radius:12px;padding:32px;max-width:440px;margin:40px auto;border:1px solid #334155;}}
h2{{color:#38bdf8;}}p{{color:#94a3b8;font-size:0.95rem;line-height:1.5;}}</style></head>
<body><div class="card">
<h2>Connecting to {ssid}...</h2>
<p>The device is applying your credentials and connecting to your local network.</p>
<p>Once connected, reconnect your phone or laptop to your home Wi-Fi and access:</p>
<p><strong>Web Desktop:</strong> http://&lt;phone-ip&gt;:6080/vnc.html<br>
<strong>SSH Console:</strong> ssh root@&lt;phone-ip&gt; (Port 22)</p>
</div></body></html>"""
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(resp.encode("utf-8"))))
                self.end_headers()
                self.wfile.write(resp.encode("utf-8"))

                # Write credentials to wpa_ubuntu.conf
                conf_data = f"""ctrl_interface=/var/run/wpa_supplicant
update_config=1

network={{
    ssid="{ssid}"
"""
                if password:
                    conf_data += f'    psk="{password}"\n    key_mgmt=WPA-PSK\n}}\n'
                else:
                    conf_data += '    key_mgmt=NONE\n}\n'

                with open("/data/linux/wpa_ubuntu.conf", "w") as f:
                    f.write(conf_data)
                with open("/etc/wpa_ubuntu.conf", "w") as f:
                    f.write(conf_data)

                print(f"[+] Saved Wi-Fi credentials for: {ssid}")

                # Trigger connection asynchronously in 1 second
                def trigger():
                    time.sleep(1)
                    subprocess.run(["/sbin/sh", "/data/linux/connect_wifi.sh"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                import threading
                threading.Thread(target=trigger, daemon=True).start()
            else:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"SSID is required.")

def run_portal(port=8080):
    server_address = ("0.0.0.0", port)
    httpd = HTTPServer(server_address, WifiPortalHandler)
    print(f"[*] Galaxy S8 Wi-Fi Setup Portal active on http://0.0.0.0:{port}")
    httpd.serve_forever()

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    run_portal(port)
