# Samsung Galaxy S8 (SM-G950N, Exynos 8895) Hardware Sensors & Native Linux Telemetry Guide

> **Authoritative Operational Manual for Native Ubuntu 24.04 LTS & Custom Linux Kernel 4.4.111**  
> Empirically verified on physical hardware (`SM-G950N`, Serial `ce10171ab3e9620804`, headless `lcdtype=-1`).

---

## 1. Executive Summary & Hardware Topology

The Samsung Galaxy S8 features an enterprise-grade sensor array spanning silicon on-chip telemetry, multi-channel analog thermistors, an optical pulse oximeter, and an integrated Broadcom sensor hub MCU.

Under standard Android, these sensors are gated behind proprietary Samsung Sensor Service Provider (SSP) daemons and Broadcom Location Hub Daemons (`lhd`/`gpsd`). Under our native Linux architecture, all sensors are exposed via **standard Industrial I/O (IIO)**, **hwmon (`/sys/class/hwmon`)**, **thermal zones (`/sys/class/thermal`)**, **sysfs**, and a unified **Linux Emulation Daemon (`s8_sensor_daemon`)**.

```
+-----------------------------------------------------------------------------------+
|                            Samsung Galaxy S8 Sensor Fabric                        |
+-----------------------------------------------------------------------------------+
                                         |
     +-----------------------------------+-----------------------------------+
     |                                   |                                   |
[On-Chip & Direct I2C/SPI]     [12-Bit Hardware ADC]           [Broadcom BCM4774 MCU]
     |                                   |                                   |
     +-- 6x Thermal Zones                +-- CH0: AP Board Thermistor        +-- ST LSM6DSL IMU (Accel+Gyro)
     +-- Maxim MAX86907E PPG / SpO2      +-- CH1: Battery Pack NTC           +-- AKM AK09916C Compass
     +-- MAX77865 Battery Fuel Gauge     +-- CH3: Charger IC NTC             +-- ST LPS22H Barometer
     +-- Immersion Haptic Actuator       +-- CH4: Wireless VBUS Sense        +-- AMS TMD4906 Light & Prox
     +-- S2MPB02 Rear Torch LED          +-- CH8: 3.5mm Headphone Jack Sense +-- Samsung Context Hub
     +-- 4x Chassis Button GPIO Keys     +-- CH10: RF PA Thermistor          +-- Dual IIO (/dev/iio:device1..24)
                                         +-- CH11: Battery Sense Voltage
```

---

## 2. Sensor Mapping Reference Table

| Subsystem / Sensor | Hardware Chip Model | Manufacturer | Physical Bus / Node | Linux Sysfs / IIO Path | Output Unit & Native Range |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Big CPU Cores** | Mongoose M2 TMU | Samsung S.LSI | Internal Thermal Sensor | `/sys/class/thermal/thermal_zone0/temp` | millidegrees C ($30,000 - 85,000$ m°C) |
| **Little CPU Cores** | Cortex-A53 TMU | ARM / Samsung | Internal Thermal Sensor | `/sys/class/thermal/thermal_zone1/temp` | millidegrees C ($30,000 - 85,000$ m°C) |
| **GPU Cores** | Mali-G71 MP20 TMU | ARM / Samsung | Internal Thermal Sensor | `/sys/class/thermal/thermal_zone2/temp` | millidegrees C ($30,000 - 85,000$ m°C) |
| **Camera ISP** | Exynos FIMC-IS TMU | Samsung S.LSI | Internal Thermal Sensor | `/sys/class/thermal/thermal_zone3/temp` | millidegrees C ($30,000 - 85,000$ m°C) |
| **Chassis Ambient** | Motherboard NTC | Samsung | Internal Thermal Sensor | `/sys/class/thermal/thermal_zone4/temp` | millidegrees C ($20,000 - 60,000$ m°C) |
| **AP Board Thermistor** | Murata NCP15XH103F | Murata / Samsung | `15b70000.adc` CH0 | `/sys/devices/virtual/sec/sec-ap-thermistor/temperature` | Tenths of °C ($350 = 35.0$ °C) |
| **RF PA Thermistor** | Murata NCP15XH103F | Murata / Samsung | `15b70000.adc` CH10 | `/sys/devices/virtual/sec/sec-pa-thermistor/temperature` | Tenths of °C ($335 = 33.5$ °C) |
| **Battery Voltage** | MAX77865 Fuel Gauge | Maxim Integrated | PMIC I2C Bus | `/sys/class/power_supply/battery/voltage_now` | Microvolts ($3,500,000 - 4,400,000$ µV) |
| **Battery Current** | MAX77865 Current Sense | Maxim Integrated | PMIC I2C Bus | `/sys/class/power_supply/battery/current_now` | Milliamps ($-2500$ to $+1500$ mA) |
| **Battery SoC %** | MAX77865 ModelGauge | Maxim Integrated | PMIC I2C Bus | `/sys/class/power_supply/battery/capacity` | Percentage ($0 - 100$ %) |
| **Optical PPG / SpO2** | MAX86907E Pulse Oximeter | Maxim Integrated | I2C Bus (`hrm_sensor`) | `/sys/class/sensors/hrm_sensor/curr_adc` | Photoplethysmogram Red/IR Amplitudes |
| **Hardware ADC** | S5N5C10 12-Bit ADC | Samsung S.LSI | `/dev/iio:device0` | `/sys/bus/iio/devices/iio:device0/in_voltage*_raw` | 12-Bit raw count ($0 - 4095$, 1.8V ref) |
| **Haptic Actuator** | TouchSense ERM Motor | Immersion Corp | Timed Output Driver | `/sys/class/timed_output/vibrator/enable` | Milliseconds duration ($0 - 10,000$ ms) |
| **Chassis Buttons** | Power, Vol+, Vol-, Bixby | Samsung Physical | `/dev/input/event3` | Linux `evdev` interface | Key events (Codes: 116, 115, 114, 528) |
| **Sensor Hub MCU** | BCM4774IUB2G | Broadcom | `108c0000.spi` | `/sys/class/sensors/ssp_sensor/` | Multi-sensor aggregator & fusion |

---

## 3. Real-Time Command-Line Usage (`s8ctl`)

The native hardware suite `/usr/local/bin/s8ctl` includes built-in sensor telemetry commands:

### 3.1 Live Formatted ASCII Dashboard
```bash
s8ctl sensors
```
**Output Example:**
```text
=================================================================
  Samsung Galaxy S8 (Exynos 8895) Live Hardware Sensors
=================================================================
 [1] Silicon Thermal Zones (Exynos 8895 TMU):
     M2 High-Performance Big Cores : 36.0 °C
     A53 High-Efficiency Little Cores: 37.0 °C
     Mali-G71 MP20 GPU Cores       : 35.0 °C
     Image Signal Processor (ISP)  : 36.0 °C
     Motherboard Ambient (ac)      : 34.3 °C

 [2] Calibrated NTC Thermistors (Sub-Degree Precision):
     AP Board Surface Thermistor   : 34.8 °C (Raw ADC: 1595)
     RF Power Amplifier Thermistor : 33.5 °C (Raw ADC: 2446)

 [3] Hardware ADC Channels (12-Bit / 15b70000.adc):
     CH0  [AP SoC Board Thermistor       ]: 1596 counts |  701.5 mV
     CH1  [Battery Pack NTC Thermistor   ]: 1692 counts |  743.7 mV
     CH3  [Charger IC NTC Thermistor     ]: 1619 counts |  711.6 mV
     CH4  [Wireless Charger / VBUS Sense ]: 3992 counts | 1754.7 mV
     CH8  [Audio Jack / Accessory Sense  ]:  585 counts |  257.1 mV
     CH10 [Power Amplifier Thermistor    ]: 2447 counts | 1075.6 mV
     CH11 [Battery Pack Sense Line       ]: 2719 counts | 1195.2 mV

 [4] Power & MAX77865 PMIC Battery Fuel Gauge:
     State of Charge : 89% (Not charging) | Health: Cold
     Terminal Voltage: 4300 mV (4.300 V)
     Real-Time Flow  : 0 mA

 [5] Optical Heart Rate & SpO2 PPG (Maxim MAX86907E):
     Hardware Chip   : Maxim MAX86907E (ID: 8480811393315, Rev: 22.120)
     Optical PPG Raw : "HRIC":"0","HRRC":"0","HRIA":"0","HRRA":"0"

 [6] Broadcom Sensorhub MCU (BCM4774):
     MCU Chip Model  : BCM4774IUB2G (Firmware: BR0119011400,BR010)
     VDD_MCU_1P8 Reg : ENABLED (1.8V Active) | Mask: 1
=================================================================
```

### 3.2 Continuous Live Watch Mode (1-Second Refresh)
```bash
s8ctl sensors watch
```

### 3.3 Pure JSON Telemetry (For IoT, Home Assistant, Prometheus, Node-RED)
```bash
s8ctl sensors json
```

### 3.4 Hardware ADC Table
```bash
s8ctl sensors adc
```

### 3.5 Optical Heart Rate & Pulse Oximeter PPG Stream
```bash
s8ctl sensors hrm
```

---

## 4. Standard Linux Emulation Tier (`s8_sensor_daemon`)

To allow standard third-party Linux utilities (such as `conky`, `node-exporter`, GNOME desktop widgets, and custom bash scripts) to read sensor data without parsing raw sysfs, the **`s8_sensor_daemon`** background service exposes live atomic files:

### 4.1 Plain-Text Emulation Nodes (`/run/sensors/`)
```bash
# Read CPU Temperatures directly in Celsius
cat /run/sensors/temp_cpu_big       # Returns: 36.0
cat /run/sensors/temp_cpu_little    # Returns: 37.0
cat /run/sensors/temp_gpu           # Returns: 35.0
cat /run/sensors/temp_ambient       # Returns: 34.3

# Read Calibrated Board Thermistors
cat /run/sensors/temp_ap_board      # Returns: 34.8
cat /run/sensors/temp_rf_pa         # Returns: 33.5

# Read Battery & Power
cat /run/sensors/battery_voltage_mv # Returns: 4300
cat /run/sensors/battery_current_ma # Returns: 0
cat /run/sensors/battery_capacity_pct # Returns: 89
```

### 4.2 Global Atomic JSON Snapshot (`/run/s8_sensors.json`)
Updated every 1,000 milliseconds via atomic swap (`os.replace`):
```json
{
  "timestamp": 1483281692.42,
  "device": "Samsung Galaxy S8 (SM-G950N)",
  "platform": "Exynos 8895",
  "thermals": {
    "mngs-thermal": { "zone": 0, "celsius": 35.0, "milli_celsius": 35000 },
    "APOLLO": { "zone": 1, "celsius": 35.0, "milli_celsius": 35000 },
    "GPU": { "zone": 2, "celsius": 36.0, "milli_celsius": 36000 },
    "ISP": { "zone": 3, "celsius": 36.0, "milli_celsius": 36000 }
  },
  "calibrated_thermistors": {
    "ap_board_celsius": 34.8,
    "ap_board_raw_adc": 1596,
    "rf_pa_celsius": 33.5,
    "rf_pa_raw_adc": 2444
  },
  "battery": {
    "voltage_mv": 4301,
    "current_ma": 0,
    "capacity_pct": 89,
    "status": "Not charging",
    "health": "Cold"
  }
}
```

---

## 5. Developer Guide: Reading Sensors Programmatically

### 5.1 Python 3 Quick-Start
```python
import json

def get_live_sensors():
    with open("/run/s8_sensors.json", "r") as f:
        return json.load(f)

data = get_live_sensors()
print(f"M2 Big Core Temp : {data['thermals']['mngs-thermal']['celsius']} °C")
print(f"Battery Voltage  : {data['battery']['voltage_mv']} mV")
print(f"Battery SoC      : {data['battery']['capacity_pct']} %")
```

### 5.2 Direct C / C++ Sysfs Read
```c
#include <stdio.h>
#include <stdlib.h>

float get_cpu_temp(void) {
    FILE *fp = fopen("/sys/class/thermal/thermal_zone0/temp", "r");
    if (!fp) return -1.0f;
    long mdeg = 0;
    fscanf(fp, "%ld", &mdeg);
    fclose(fp);
    return (float)mdeg / 1000.0f;
}

int main(void) {
    printf("CPU Temp: %.1f C\n", get_cpu_temp());
    return 0;
}
```

### 5.3 Shell Script One-Liner
```bash
echo "CPU: $(cat /run/sensors/temp_cpu_big)°C | Battery: $(cat /run/sensors/battery_capacity_pct)%"
```

---

## 6. Sensorhub MCU & Broadcom Bridge Architecture

The Galaxy S8's accelerometer, gyroscope, magnetometer, barometer, and light sensors reside on the **Broadcom BCM4774** co-processor connected via SPI bus `108c0000.spi`.

### Key System Knobs:
1. **Power Regulator:** `/sys/class/sec/sensorhub/mcu_power`  
   Write `1` to power `regulator_vdd_mcu_1p8` (1.8V bus power).
2. **Master Enable Bitmask:** `/sys/class/sensors/ssp_sensor/enable`  
   64-bit integer bitmask controlling individual MCU sensors:
   - Bit 0 (`1`): ST LSM6DSL Accelerometer
   - Bit 1 (`2`): ST LSM6DSL Gyroscope
   - Bit 4 (`16`): AKM AK09916C Compass / Magnetometer
   - Bit 5 (`32`): ST LPS22H Barometric Pressure
   - Bit 7 (`128`): AMS TMD4906 Proximity
   - Bit 9 (`512`): AMS TMD4906 Ambient Light (Lux)
3. **Bridge Communication:** The kernel driver exposes `/dev/bbd_sensor`, `/dev/bbd_control`, and `/dev/bbd_patch` (1,021,091 bytes embedded Broadcom firmware patch). Writing `"ESW:READY"` to `/dev/bbd_control` signals MCU readiness.

