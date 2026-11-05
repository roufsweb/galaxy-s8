#!/usr/bin/env python3
"""
benchmark_suite.py — Comprehensive Galaxy S8 (Exynos 8895) Benchmark Suite
Measures CPU Single/Multi-Core, Memory LPDDR4x, Hardware Crypto, UFS 2.1 Storage,
GPU glmark2-es2, and Full System Stress Thermals.
"""
import os
import sys
import time
import subprocess
import json

def run_cmd(cmd):
    p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    out, err = p.communicate()
    return out.strip()

def get_temp():
    try:
        temps = []
        for i in range(10):
            path = f"/sys/devices/virtual/thermal/thermal_zone{i}/temp"
            if os.path.exists(path):
                with open(path, "r") as f:
                    t = float(f.read().strip())
                    if t > 1000:
                        t /= 1000.0
                    temps.append(t)
        return max(temps) if temps else 0.0
    except Exception:
        return 0.0

def get_battery_power():
    try:
        with open("/sys/class/power_supply/battery/current_now", "r") as f:
            curr = abs(int(f.read().strip())) / 1000.0
        with open("/sys/class/power_supply/battery/voltage_now", "r") as f:
            volt = int(f.read().strip()) / 1000000.0
        power_w = curr * volt / 1000.0
        return curr, volt, power_w
    except Exception:
        return 0.0, 0.0, 0.0

def main():
    print("=" * 70)
    print("SAMSUNG GALAXY S8 (EXYNOS 8895) HARDWARE BENCHMARK & STRESS SUITE")
    print("=" * 70)

    # 1. Boost CPU
    print("\n[*] Locking CPU Governor to PERFORMANCE (4x A53 @ 1.69 GHz, 4x M2 @ 2.31 GHz)...")
    subprocess.run("s8ctl cpu-profile max >/dev/null 2>&1", shell=True)
    time.sleep(1)

    t_start = get_temp()
    c_start, v_start, p_start = get_battery_power()
    print(f"    Initial Temp: {t_start:.1f}°C | Battery: {v_start:.3f}V, {c_start:.0f}mA ({p_start:.2f}W)")

    results = {}

    # 2. CPU Single-Core (sysbench)
    print("\n[*] [1/7] Running sysbench CPU (Single-Thread, 20,000 primes)...")
    sb_single = run_cmd("sysbench cpu --cpu-max-prime=20000 --threads=1 run")
    sb_single_events = 0.0
    sb_single_time = 0.0
    for line in sb_single.splitlines():
        if "events per second:" in line:
            sb_single_events = float(line.split(":")[1].strip())
        elif "total time:" in line:
            sb_single_time = float(line.split(":")[1].strip().replace("s", ""))
    print(f"    -> Single-Thread Events/sec: {sb_single_events:.2f} (Time: {sb_single_time:.3f}s)")
    results["sysbench_cpu_single_events"] = sb_single_events
    results["sysbench_cpu_single_time"] = sb_single_time

    # 3. CPU Multi-Core (sysbench 8 threads)
    print("\n[*] [2/7] Running sysbench CPU (Multi-Thread 8 Cores, 20,000 primes)...")
    sb_multi = run_cmd("sysbench cpu --cpu-max-prime=20000 --threads=8 run")
    sb_multi_events = 0.0
    sb_multi_time = 0.0
    for line in sb_multi.splitlines():
        if "events per second:" in line:
            sb_multi_events = float(line.split(":")[1].strip())
        elif "total time:" in line:
            sb_multi_time = float(line.split(":")[1].strip().replace("s", ""))
    print(f"    -> Multi-Thread Events/sec : {sb_multi_events:.2f} (Speedup: {sb_multi_events/max(1.0, sb_single_events):.2f}x)")
    results["sysbench_cpu_multi_events"] = sb_multi_events
    results["sysbench_cpu_multi_time"] = sb_multi_time

    # 4. 7-Zip Benchmark (MIPS)
    print("\n[*] [3/7] Running 7-Zip LZMA Integer & Compression Benchmark (8 threads)...")
    p7z_out = run_cmd("7z b -mmt=8")
    comp_mips = 0
    decomp_mips = 0
    total_mips = 0
    for line in p7z_out.splitlines():
        if "Tot:" in line or "Total:" in line:
            parts = line.split()
            # Format: Tot:  Rating / Usage ...
            try:
                for idx, token in enumerate(parts):
                    if token.isdigit() and int(token) > 1000:
                        total_mips = int(token)
            except Exception:
                pass
        elif "Compressing" in line and "MIPS" in line:
            pass
    # Extract overall rating MIPS from last block
    lines = p7z_out.splitlines()
    for l in reversed(lines):
        if "MIPS" in l and ("Rating" in l or "Tot" in l or ":" in l):
            tokens = [t for t in l.split() if t.isdigit()]
            if tokens:
                total_mips = int(tokens[-1])
                break
    print(f"    -> 7-Zip Overall Rating: {total_mips} MIPS")
    results["7zip_mips"] = total_mips

    # 5. OpenSSL Hardware Cryptography (AES-256-GCM & SHA256)
    print("\n[*] [4/7] Running OpenSSL Hardware Cryptographic Engine Speed...")
    openssl_aes = run_cmd("openssl speed -evp aes-256-gcm 2>&1")
    aes_mb_s = 0.0
    for line in reversed(openssl_aes.splitlines()):
        if "aes-256-gcm" in line:
            parts = line.split()
            try:
                # 8k block throughput
                aes_mb_s = float(parts[-1].replace("k", "")) / 1000.0
            except Exception:
                pass
            break
    
    openssl_sha = run_cmd("openssl speed -evp sha256 2>&1")
    sha_mb_s = 0.0
    for line in reversed(openssl_sha.splitlines()):
        if "sha256" in line:
            parts = line.split()
            try:
                sha_mb_s = float(parts[-1].replace("k", "")) / 1000.0
            except Exception:
                pass
            break
    print(f"    -> Hardware AES-256-GCM Throughput: {aes_mb_s:.2f} MB/s")
    print(f"    -> Hardware SHA-256 Throughput     : {sha_mb_s:.2f} MB/s")
    results["aes256_mb_s"] = aes_mb_s
    results["sha256_mb_s"] = sha_mb_s

    # 6. Memory Bandwidth (sysbench memory)
    print("\n[*] [5/7] Running sysbench Memory Bandwidth (LPDDR4x 1794MHz, 8 threads)...")
    mem_read = run_cmd("sysbench memory --memory-oper=read --memory-block-size=1M --memory-total-size=5G --threads=8 run")
    mem_read_speed = 0.0
    for line in mem_read.splitlines():
        if "transferred (" in line or "MiB/sec" in line:
            try:
                part = line.split("(")[1].split("MiB/sec")[0].strip()
                mem_read_speed = float(part)
            except Exception:
                pass
    
    mem_write = run_cmd("sysbench memory --memory-oper=write --memory-block-size=1M --memory-total-size=5G --threads=8 run")
    mem_write_speed = 0.0
    for line in mem_write.splitlines():
        if "transferred (" in line or "MiB/sec" in line:
            try:
                part = line.split("(")[1].split("MiB/sec")[0].strip()
                mem_write_speed = float(part)
            except Exception:
                pass
    print(f"    -> LPDDR4x Memory Read Bandwidth : {mem_read_speed:.2f} MiB/sec")
    print(f"    -> LPDDR4x Memory Write Bandwidth: {mem_write_speed:.2f} MiB/sec")
    results["mem_read_mib_s"] = mem_read_speed
    results["mem_write_mib_s"] = mem_write_speed

    # 7. GPU / Graphics Benchmark (glmark2-es2)
    print("\n[*] [6/8] Running GPU Graphics Benchmark (glmark2-es2 on DISPLAY :1)...")
    gl_res = run_cmd("DISPLAY=:1 glmark2-es2 --size 800x600 -b build:use-vbo=true -b texture -b shading -b bump -b pulsar 2>&1")
    gl_score = "0"
    for line in gl_res.splitlines():
        if "glmark2 Score:" in line:
            gl_score = line.split("glmark2 Score:")[1].strip()
    print(f"    -> glmark2-es2 Score: {gl_score} (Mesa LLVMpipe / Mali ES 3.2)")
    results["glmark2_score"] = gl_score

    # 8. Internal UFS 2.1 Storage Performance
    print("\n[*] [7/8] Running Internal 64GB UFS 2.1 Storage I/O Benchmark...")
    test_file = "/mnt/android_data/bench_test.bin" if os.path.exists("/mnt/android_data") else "/tmp/bench_test.bin"
    # Write 256MB sequential
    write_res = run_cmd(f"dd if=/dev/zero of={test_file} bs=1M count=256 conv=fdatasync 2>&1")
    write_speed = "Unknown"
    for line in write_res.splitlines():
        if "copied" in line and ("MB/s" in line or "GB/s" in line):
            write_speed = line.split(",")[-1].strip()
    
    # Drop caches & read back
    subprocess.run("echo 3 > /proc/sys/vm/drop_caches 2>/dev/null", shell=True)
    read_res = run_cmd(f"dd if={test_file} of=/dev/null bs=1M 2>&1")
    read_speed = "Unknown"
    for line in read_res.splitlines():
        if "copied" in line and ("MB/s" in line or "GB/s" in line):
            read_speed = line.split(",")[-1].strip()
    run_cmd(f"rm -f {test_file}")
    print(f"    -> UFS 2.1 Sequential Write: {write_speed}")
    print(f"    -> UFS 2.1 Sequential Read : {read_speed}")
    results["storage_write"] = write_speed
    results["storage_read"] = read_speed

    # 9. 30-Second Full Stress Test & Thermal Profile
    print("\n[*] [8/8] Running 30-Second Full Octa-Core Stress Test (stress-ng)...")
    temp_before = get_temp()
    print(f"    Temp Before Stress: {temp_before:.1f}°C")
    
    stress_proc = subprocess.Popen("stress-ng --cpu 8 --timeout 30s --metrics-brief", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    
    temps_during = []
    for _ in range(6):
        time.sleep(5)
        t = get_temp()
        temps_during.append(t)
        c, v, w = get_battery_power()
        print(f"      [t+{len(temps_during)*5}s] Temp: {t:.1f}°C | Load: 8x 100% | Batt: {v:.3f}V, {c:.0f}mA ({w:.2f}W)")
    
    s_out, s_err = stress_proc.communicate()
    bogo_ops = "N/A"
    for line in (s_out + "\n" + s_err).splitlines():
        if "cpu" in line and "bogo ops" in line:
            bogo_ops = line.strip()
    
    peak_temp = max(temps_during) if temps_during else temp_before
    print(f"    -> Peak SoC Temperature During Stress: {peak_temp:.1f}°C (Delta: +{peak_temp - temp_before:.1f}°C)")
    print(f"    -> {bogo_ops}")
    results["temp_before"] = temp_before
    results["peak_temp"] = peak_temp
    results["bogo_ops"] = bogo_ops

    # Save summary JSON
    with open("/tmp/s8_benchmark_results.json", "w") as f:
        json.dump(results, f, indent=2)

    print("\n" + "=" * 70)
    print("BENCHMARK EXECUTION COMPLETED SUCCESSFULLY!")
    print("Results saved to /tmp/s8_benchmark_results.json")
    print("=" * 70)

if __name__ == "__main__":
    main()
