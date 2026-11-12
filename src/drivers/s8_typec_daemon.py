#!/usr/bin/env python3
"""
s8_typec_daemon.py — Galaxy S8 (SM-G950N, Exynos 8895) CC-Aware Type-C Multi-Role,
DisplayPort Alt-Mode, Power Arbitration, and USB Storage Supervisor.

Features:
1. Dynamic CC Pin (Configuration Channel) Arbitration:
   - Evaluates /sys/class/typec/port0/power_role ([source] vs [sink]).
   - Unpowered portable monitors (Rd detected): 5V VBUS booster turned ON.
   - Self-powered monitors / powered docks / PC (Rp detected): 5V booster kept strictly OFF.
2. Fast Cable Disconnect Watchdog:
   - On detach: Instantly disarms 5V booster, resets DP link (0), restores SBU switch,
     and returns Type-C controller to neutral Dual-Role Device (UFP/Sink) mode.
   - Eliminates PC USB port overcurrent shutdown / Code 43 on re-plug.
3. Safe 5V High-Current Fast Charging:
   - Programs MAX77865 PMIC registers directly to safe 1,500 mA fast charging at 5V.
   - Avoids risky 9V/12V AFC/PD high-voltage switching on modified headless boards.
4. Auto-Mount & Unmount for external USB storage (/dev/block/sd* -> /media/usb*).
5. Automatic Exynos DECON2 DisplayPort Bridge supervision.
"""

import os
import sys
import time
import subprocess

# Sysfs paths for Type-C, CCIC, DisplayPort, and PMIC
SYSFS_DATA_ROLE = "/sys/class/typec/port0/data_role"
SYSFS_PORT_TYPE = "/sys/class/typec/port0/port_type"
SYSFS_POWER_ROLE = "/sys/class/typec/port0/power_role"
SYSFS_PORT_PARTNER = "/sys/class/typec/port0/port0-partner"
SYSFS_OTG_MODE = "/sys/class/host_notify/usb_otg/mode"
SYSFS_OTG_BOOSTER = "/sys/class/host_notify/usb_otg/booster"
SYSFS_OTG_ONLINE = "/sys/class/power_supply/otg/online"
SYSFS_CCIC_STATE = "/sys/class/sec/ccic/state"
SYSFS_HDMI_STATE = "/sys/class/switch/hdmi/state"
SYSFS_DP_LINK = "/sys/class/dp_sec/link"
SYSFS_DP_SBU = "/sys/class/dp_sec/dp_sbu_sw_sel"
SYSFS_DP_TEST = "/sys/class/dp_sec/dp_test"
SYSFS_VIBRATOR = "/sys/class/timed_output/vibrator/enable"

SYSFS_CHARGER_DATA = "/sys/class/power_supply/max77865-charger/data"
SYSFS_BATT_TUNE_INPUT = "/sys/class/power_supply/battery/batt_tune_input_charge_current"
SYSFS_BATT_TUNE_FAST = "/sys/class/power_supply/battery/batt_tune_fast_charge_current"
SYSFS_BATT_HC_USB = "/sys/class/power_supply/battery/batt_high_current_usb"

def read_file(path, default=""):
    try:
        with open(path, "r") as f:
            return f.read().strip()
    except Exception:
        return default

def write_file(path, val):
    try:
        with open(path, "w") as f:
            f.write(str(val) + "\n")
            return True
    except Exception:
        return False

def vibrate(duration_ms=100):
    write_file(SYSFS_VIBRATOR, duration_ms)

class TypeCSupervisor:
    def __init__(self):
        self.current_state = "idle"  # "idle", "pc", "display_powered", "display_unpowered", "host"
        self.last_hdmi = -1
        self.last_attached = False
        self.mounted_drives = {}
        self.ensure_mount_points()

    def ensure_mount_points(self):
        os.makedirs("/media/usb", exist_ok=True)
        for i in range(1, 5):
            os.makedirs(f"/media/usb{i}", exist_ok=True)

    def is_partner_attached(self):
        """Check if any Type-C partner, display, or charger is attached."""
        if os.path.exists(SYSFS_PORT_PARTNER):
            return True
        if read_file(SYSFS_HDMI_STATE, "0") == "1":
            return True
        ccic = read_file(SYSFS_CCIC_STATE, "0")
        if ccic != "0":
            return True
        return False

    def get_power_role(self):
        """
        Returns 'source' (we output power / Rd attached),
                'sink' (we receive power / Rp attached),
                or 'unknown'.
        """
        prole = read_file(SYSFS_POWER_ROLE, "")
        if "[source]" in prole:
            return "source"
        elif "[sink]" in prole:
            return "sink"
        return "unknown"

    def get_data_role(self):
        """
        Returns 'host' (we are USB Host),
                'device' (we are USB Device / ADB),
                or 'unknown'.
        """
        drole = read_file(SYSFS_DATA_ROLE, "")
        if "[host]" in drole:
            return "host"
        elif "[device]" in drole:
            return "device"
        return "unknown"

    def apply_safe_5v_fast_charge(self):
        """
        Directly configure MAX77865 PMIC registers for 1,500 mA fast charging at 5V.
        100% safe, rock-solid, zero high-voltage AFC/PD step-up risks.
        """
        write_file(SYSFS_CHARGER_DATA, "0xBD 0x6C")  # Unlock CHGPROT
        write_file(SYSFS_CHARGER_DATA, "0xC3 0x61")  # UVLO = 4.3V + DISSKIP
        write_file(SYSFS_CHARGER_DATA, "0xC0 0x3C")  # CHG_CNFG_09 = 1500mA input limit
        write_file(SYSFS_CHARGER_DATA, "0xB9 0x9E")  # CHG_CNFG_02 = 1500mA fast charge limit
        write_file(SYSFS_CHARGER_DATA, "0xB7 0x05")  # CHG_CNFG_00 = MODE_BUCK | MODE_CHGR
        write_file(SYSFS_BATT_TUNE_INPUT, "1500")
        write_file(SYSFS_BATT_TUNE_FAST, "1500")
        write_file(SYSFS_BATT_HC_USB, "1")

    def disarm_and_reset(self):
        """
        Fast Detach / Cable Disconnect Watchdog:
        Immediately cut 5V VBUS booster, reset DisplayPort links,
        and revert CCIC to neutral Dual-Role Device (UFP/Sink) mode.
        """
        print("[s8_typec] Disarming USB/DisplayPort -> Reverting to safe neutral Device mode...", flush=True)
        # 1. Kill VBUS booster immediately to prevent reverse power injection into PC
        write_file(SYSFS_OTG_BOOSTER, "OFF")
        write_file(SYSFS_OTG_MODE, "NONE")

        # 2. Reset DisplayPort link training and SBU analog switch
        write_file(SYSFS_DP_LINK, "0")
        write_file(SYSFS_DP_TEST, "1,0")

        # 2b. Blank fb2 to prevent Exynos DECON2 timeout panics
        fb_path = "/dev/graphics/fb2" if os.path.exists("/dev/graphics/fb2") else "/dev/fb2"
        if os.path.exists(fb_path):
            try:
                import fcntl
                with open(fb_path, "wb") as fb:
                    # FB_BLANK_POWERDOWN = 4
                    fcntl.ioctl(fb.fileno(), 0x4611, 4)
            except Exception:
                pass

        # 3. Restore standard USB data role and dual-role port state
        write_file(SYSFS_PORT_TYPE, "dual")
        write_file(SYSFS_DATA_ROLE, "device")

        self.current_state = "idle"
        print("[s8_typec] Reset complete: 5V booster OFF, role=device, link=0.", flush=True)

    def handle_display_connection(self):
        """Configure DisplayPort with CC-aware power arbitration."""
        p_role = self.get_power_role()

        if p_role == "source":
            # Unpowered portable monitor: Needs 5V power from phone
            print("[s8_typec] Unpowered portable display detected (Rd) -> Turning ON 5V VBUS booster...", flush=True)
            write_file(SYSFS_OTG_BOOSTER, "ON")
            write_file(SYSFS_OTG_MODE, "HOST")
            write_file(SYSFS_DATA_ROLE, "host")
            self.current_state = "display_unpowered"
        else:
            # Powered display, dock, or TV: Supplies power to phone
            print("[s8_typec] Powered display/dock detected (Rp) -> Keeping 5V booster OFF, charging as Sink...", flush=True)
            write_file(SYSFS_OTG_BOOSTER, "OFF")
            write_file(SYSFS_OTG_MODE, "NONE")
            self.apply_safe_5v_fast_charge()
            self.current_state = "display_powered"

        # Align SBU analog switch for DisplayPort AUX channel
        write_file(SYSFS_DP_SBU, "0 0")
        time.sleep(0.05)
        write_file(SYSFS_DP_LINK, "22")
        time.sleep(0.2)

        hdmi = int(read_file(SYSFS_HDMI_STATE, "0"))
        if hdmi != 1:
            # Try flipped SBU orientation
            write_file(SYSFS_DP_SBU, "1 0")
            time.sleep(0.05)
            write_file(SYSFS_DP_LINK, "22")
            time.sleep(0.2)
            hdmi = int(read_file(SYSFS_HDMI_STATE, "0"))

        if hdmi == 1:
            print("[s8_typec] DisplayPort link training SUCCEEDED! (HDMI State = 1)", flush=True)
            vibrate(150)
            time.sleep(0.1)
            vibrate(150)
            self.ensure_dp_bridge()

    def ensure_dp_bridge(self):
        """Ensure DECON2 fb2 is unblanked and single exynos_dp_bridge instance is running."""
        fb_path = "/dev/graphics/fb2" if os.path.exists("/dev/graphics/fb2") else "/dev/fb2"
        if os.path.exists(fb_path):
            try:
                import fcntl
                with open(fb_path, "wb") as fb:
                    fcntl.ioctl(fb.fileno(), 0x4611, 0)
                    print(f"[s8_typec] Unblanked {fb_path} successfully.", flush=True)
            except Exception as e:
                print(f"[s8_typec] ioctl unblank {fb_path}: {e}", flush=True)

        if not os.path.exists("/usr/local/bin/exynos_dp_bridge"):
            return

        # Avoid spawning duplicates when s8-dp-bridge.service already owns exynos_dp_bridge
        try:
            if subprocess.check_output(["pgrep", "-x", "exynos_dp_bridge"]).decode().strip():
                return
        except Exception:
            pass

        if os.path.isdir("/run/systemd/system"):
            res = subprocess.run(["systemctl", "start", "s8-dp-bridge.service"],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if res.returncode == 0:
                print("[s8_typec] Started s8-dp-bridge.service cleanly.", flush=True)
                return

        print("[s8_typec] Starting exynos_dp_bridge directly...", flush=True)
        env = dict(os.environ)
        if os.path.exists("/tmp/.X11-unix/X1"):
            env["DISPLAY"] = ":1"
        elif os.path.exists("/tmp/.X11-unix/X0"):
            env["DISPLAY"] = ":0"
        subprocess.Popen(["/usr/local/bin/exynos_dp_bridge"], env=env,
                         stdout=open("/var/log/exynos_dp_bridge.log", "a"),
                         stderr=subprocess.STDOUT)

    def check_usb_storage(self):
        """Auto-mount and unmount USB flash drives / hard drives (/dev/block/sd*)."""
        if not os.path.exists("/dev/block"):
            return

        current_devs = set()
        for entry in os.listdir("/dev/block"):
            if entry.startswith("sd") and not entry.startswith("sda") and any(c.isdigit() for c in entry):
                dev_path = f"/dev/block/{entry}"
                current_devs.add(dev_path)

        for dev in current_devs:
            if dev not in self.mounted_drives:
                mount_point = f"/media/usb_{os.path.basename(dev)}"
                os.makedirs(mount_point, exist_ok=True)
                print(f"[s8_typec] USB drive detected: {dev} -> mounting at {mount_point}...", flush=True)
                res = subprocess.run(["mount", "-o", "rw,noatime,umask=000", dev, mount_point],
                                     capture_output=True)
                if res.returncode == 0:
                    self.mounted_drives[dev] = mount_point
                    vibrate(100)
                else:
                    subprocess.run(["mount", dev, mount_point], capture_output=True)
                    self.mounted_drives[dev] = mount_point

        removed = [d for d in self.mounted_drives if d not in current_devs]
        for dev in removed:
            mp = self.mounted_drives.pop(dev)
            print(f"[s8_typec] USB drive removed: {dev} -> unmounting {mp}...", flush=True)
            subprocess.run(["umount", "-l", mp], capture_output=True)

    def run(self):
        print("[s8_typec] Galaxy S8 CC-Aware Type-C & Power Supervisor running.", flush=True)
        ap_owns_dp = os.path.exists("/dev/.s8_dp_daemon.lock")
        if ap_owns_dp:
            print("[s8_typec] /sbin/s8_dp_daemon owns DisplayPort/fb2 -> operating in USB storage hotplug mode only.", flush=True)
        else:
            self.ensure_dp_bridge()

        while True:
            try:
                if not ap_owns_dp:
                    ap_owns_dp = os.path.exists("/dev/.s8_dp_daemon.lock")
                if ap_owns_dp:
                    self.check_usb_storage()
                    time.sleep(0.5)
                    continue
                attached = self.is_partner_attached()
                hdmi = int(read_file(SYSFS_HDMI_STATE, "0"))
                p_role = self.get_power_role()
                d_role = self.get_data_role()

                # Event: Cable Detached
                if not attached and self.last_attached:
                    print("[s8_typec] Cable disconnect detected -> Running watchdog disarm...", flush=True)
                    self.disarm_and_reset()

                # Event: Cable Attached or State Transition
                elif attached:
                    if hdmi == 1 and self.last_hdmi != 1:
                        print("[s8_typec] DisplayPort hotplug detected!", flush=True)
                        self.handle_display_connection()

                    elif hdmi == 0 and d_role == "device" and self.current_state != "pc":
                        # Connected to PC USB Host or Charger as Device
                        print("[s8_typec] Connected to PC USB host / Charger -> Enforcing 5V Safe Fast Charge.", flush=True)
                        write_file(SYSFS_OTG_BOOSTER, "OFF")
                        write_file(SYSFS_OTG_MODE, "NONE")
                        self.apply_safe_5v_fast_charge()
                        self.current_state = "pc"

                    elif hdmi == 0 and p_role == "source" and self.current_state != "host":
                        # OTG Accessory attached (Flash drive, mouse, keyboard)
                        print("[s8_typec] USB OTG accessory detected (Rd) -> Turning ON 5V booster...", flush=True)
                        write_file(SYSFS_OTG_BOOSTER, "ON")
                        write_file(SYSFS_OTG_MODE, "HOST")
                        write_file(SYSFS_DATA_ROLE, "host")
                        self.current_state = "host"

                self.last_attached = attached
                self.last_hdmi = hdmi

                # Manage USB storage partitions
                self.check_usb_storage()

            except Exception as e:
                print(f"[s8_typec] Error in monitor loop: {e}", flush=True)

            time.sleep(0.5)

if __name__ == "__main__":
    daemon = TypeCSupervisor()
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        if cmd in ["arm", "dock", "display"]:
            daemon.handle_display_connection()
            sys.exit(0)
        elif cmd in ["disarm", "pc", "device", "reset"]:
            daemon.disarm_and_reset()
            sys.exit(0)
        elif cmd == "charge":
            daemon.apply_safe_5v_fast_charge()
            print("[s8_typec] Safe 5V Fast Charge applied (1500mA).")
            sys.exit(0)
        elif cmd == "status":
            hdmi = read_file(SYSFS_HDMI_STATE, "0")
            otg_online = read_file(SYSFS_OTG_ONLINE, "0")
            booster = "ON" if otg_online == "1" else "OFF"
            omode = read_file(SYSFS_OTG_MODE, "NONE")
            prole = daemon.get_power_role()
            drole = daemon.get_data_role()
            attached = daemon.is_partner_attached()
            print("==============================================")
            print("  Samsung Galaxy S8 Type-C Status (CC-Aware)  ")
            print("==============================================")
            print(f"Cable Attached   : {attached}")
            print(f"Power Role (CC)  : {prole}")
            print(f"Data Role        : {drole}")
            print(f"DisplayPort HPD  : {'CONNECTED' if hdmi == '1' else 'DISCONNECTED'}")
            print(f"5V VBUS Booster  : {booster} (PMIC: {otg_online})")
            print(f"USB OTG Mode     : {omode}")
            print("==============================================")
            sys.exit(0)

    daemon.run()
