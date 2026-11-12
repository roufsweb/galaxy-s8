# Galaxy S8 Native Linux Test & Verification Suite

Unified testing framework covering hardware peripherals, system benchmarks, homelab cloud services, and unit logic.

---

## Directory Organization

```
tests/
├── hardware/             # Physical device, DisplayPort, ABOX audio, and VSYNC tests
│   ├── test_dp_colors.c          # DisplayPort RGB color test
│   ├── test_dp_ion_pattern.c     # /dev/ion DMA buffer pattern generator
│   ├── test_vsync.c              # FBIO_WAITFORVSYNC timing verification
│   └── test_audio_devs.py        # ALSA Calliope DSP & Maxim amplifier checks
├── benchmarks/           # CPU, GPU, memory bandwidth, and thermal torture tests
│   ├── benchmark_suite.py        # Comprehensive Sysbench, memory, and disk suite
│   └── test_perf.c               # Native C CPU torture loop
├── services/             # Docker homelab services & Web UI automated validation
│   ├── test_casaos_ui.py         # CasaOS cloud dashboard verification (:8080)
│   ├── test_portainer_ui.py      # Portainer CE container manager (:9000)
│   ├── test_codeserver_ui.py     # Code-Server / VS Code browser editor (:8082)
│   ├── test_uptimekuma_ui.py     # Uptime Kuma monitoring dashboard (:3001)
│   ├── test_filebrowser_ui.py    # FileBrowser MicroSD NAS interface (:8088)
│   └── verify_ollama_ui.py       # Ollama LLM local inference API (:11434)
└── unit/                 # Application architecture and telemetry unit tests
    ├── test_app_structure.py     # Path resolution, config, and binary audits
    └── test_poller.py            # Hardware telemetry parser validation
```

---

## How to Run Tests

### Running Unit Tests
```bash
python -m unittest discover tests/unit
```

### Running Service Verification Tests (Against Live Galaxy S8)
```bash
python -m unittest tests/services/test_casaos_ui.py
python -m unittest tests/services/test_portainer_ui.py
```

### Compiling and Running Hardware Tests on Device
```bash
adb -s ce10171ab3e9620804 push tests/hardware/test_vsync.c /data/local/tmp/
adb -s ce10171ab3e9620804 shell "gcc -O2 /data/local/tmp/test_vsync.c -o /data/local/tmp/test_vsync && /data/local/tmp/test_vsync"
```
