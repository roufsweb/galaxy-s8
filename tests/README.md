# Galaxy S8 Automated Test & Verification Suites

This directory contains benchmark suites, hardware interface verifiers, and end-to-end browser automation scripts used to test every subsystem on the Samsung Galaxy S8 Linux server.

---

## Directory Organization

```
tests/
├── benchmarks/        # Multi-threaded CPU, memory, GPU, and I/O benchmark harnesses
├── hardware/          # Direct kernel ioctl, ION buffer, VSYNC, and ALSA hardware tests
└── ui_verification/   # Playwright-driven end-to-end browser automation suites
```

---

## Benchmark Harnesses (`tests/benchmarks/`)

* `benchmark_suite.py`: Multi-metric hardware evaluation measuring:
  * Single-core and multi-core integer / floating point CPU performance.
  * Memory bandwidth (read, write, copy) via sequential and non-contiguous memory access.
  * MicroSD and internal UFS storage sequential write and cached read throughput.
  * Network socket latency and loopback throughput.
* `test_perf.c`: Direct C benchmark testing compiler vectorization and cache latency on Exynos M2 and Cortex-A53 cores.

---

## Hardware Interface Tests (`tests/hardware/`)

* `test_dp_colors.c` & `test_dp_ion_pattern.c`: Direct Exynos DECON2 framebuffer test patterns verifying 32-bit ARGB8888 color accuracy, stride alignment, and double buffering.
* `test_vsync.c`: Verifies kernel `FBIO_WAITFORVSYNC` blocking ioctl on `/dev/graphics/fb2` to prevent frame tearing during DisplayPort video output.
* `test_audio_devs.py`: Verifies ALSA soundcard enumerations for `hw:0,0` (Speaker) and `hw:0,9` (Digital Mic 1).

---

## UI Automation & Verification Suites (`tests/ui_verification/`)

Automated with Playwright to verify full functionality from the browser perspective:
* `test_casaos_ui.py` & `test_casaos_human_flow.py`: Verifies CasaOS dashboard (:8080) loading, system telemetry widgets, and app store catalogs.
* `test_portainer_ui.py` & `test_portainer_containers.py`: Automates Portainer CE (:9000) login, container inspection, CPU/RAM graph verification, and image pulling.
* `test_uptimekuma_ui.py`: Verifies Uptime Kuma (:3001) setup, creates live HTTP monitors (CasaOS, Portainer, Ollama, FileBrowser), and asserts 100% green status.
* `test_filebrowser_ui.py` & `test_sdcard_filebrowser.py`: Verifies FileBrowser (:8088) login, navigates into `/media/sdcard`, and asserts full read/write file access to the external MicroSD card.
* `verify_ollama_ui.py`: Sends JSON prompt payloads to Ollama LLM REST API (:11434), streaming token responses and verifying inference accuracy.
* `test_codeserver_ui.py` & `test_codeserver_editor.py`: Automates Code-Server (:8082) login, creates and edits source files in the Monaco editor, and validates workspace saving.

