"""
Unit test for telemetry polling parsing logic
"""
import unittest

class TestDevicePoller(unittest.TestCase):

    def test_telemetry_parser_sample_data(self):
        sample_output = """
INSTALLED=1
PRETTY_NAME="Ubuntu 24.04.5 LTS"
99
392
MemTotal:        3670016 kB
MemAvailable:    2988440 kB
192.168.0.227/24
"""
        lines = [l.strip() for l in sample_output.splitlines() if l.strip()]
        
        installed = False
        os_name = "Base AP Recovery"
        batt_pct = "---"
        batt_temp = "---"
        mem_free_gb = 0.0
        wifi_ip = "Offline"

        for line in lines:
            if line.startswith("INSTALLED="):
                installed = (line.split("=")[1] == "1")
            elif line.startswith("PRETTY_NAME="):
                val = line.split("=", 1)[1].strip('"\'')
                if val:
                    os_name = val
            elif line.isdigit() and len(line) <= 3 and batt_pct == "---":
                batt_pct = f"{line}%"
            elif line.isdigit() and batt_temp == "---":
                batt_temp = f"{int(line)/10:.1f}°C"
            elif "MemAvailable:" in line:
                kb = int(line.split(":")[1].replace("kB", "").strip())
                mem_free_gb = round(kb / (1024 * 1024), 2)
            elif "/" in line and line[0].isdigit():
                wifi_ip = line.split("/")[0]

        self.assertTrue(installed)
        self.assertEqual(os_name, "Ubuntu 24.04.5 LTS")
        self.assertEqual(batt_pct, "99%")
        self.assertEqual(batt_temp, "39.2°C")
        self.assertEqual(mem_free_gb, 2.85)
        self.assertEqual(wifi_ip, "192.168.0.227")

if __name__ == "__main__":
    unittest.main()
