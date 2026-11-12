#!/bin/bash
# init_audio.sh - Native ALSA Audio Bring-Up for Samsung Galaxy S8
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

# 1. Speaker Playback Routing (hw:0,0 -> MAX98506 Amp)
amixer -c 0 cset name='ABOX SPUS IN0' 'RDMA' >/dev/null 2>&1 || true
amixer -c 0 cset name='ABOX SPUS OUT0' 'SIFS1' >/dev/null 2>&1 || true
amixer -c 0 cset name='ABOX SIFS1' 'SPUS OUT0' >/dev/null 2>&1 || true
amixer -c 0 cset name='ABOX UAIF SPK4' 'SIFS1' >/dev/null 2>&1 || true
amixer -c 0 cset name='SPK out' 'Enable' >/dev/null 2>&1 || true
amixer -c 0 cset name='SPK Enable Switch' 'Enable' >/dev/null 2>&1 || true
amixer -c 0 cset name='Speaker Gain' 25 >/dev/null 2>&1 || true

# 2. Microphone Capture Routing (DMIC1 -> hw:0,9)
amixer -c 0 cset name='ABOX NSRC0' 'UAIF0' >/dev/null 2>&1 || true
amixer -c 0 cset name='ABOX SPUM ASRC1' 'Off' >/dev/null 2>&1 || true
amixer -c 0 cset name='ABOX SIFM0' 'WDMA' >/dev/null 2>&1 || true
amixer -c 0 cset name='DMIC1 Switch' 1 >/dev/null 2>&1 || true
amixer -c 0 cset name='LHPF1 Input 1' 'IN3L' >/dev/null 2>&1 || true
amixer -c 0 cset name='ASRC1IN1L Input 1' 'LHPF1' >/dev/null 2>&1 || true
amixer -c 0 cset name='AIF1TX1 Input 1' 'ASRC1IN1L' >/dev/null 2>&1 || true
amixer -c 0 cset name='AIF1TX2 Input 1' 'ASRC1IN1L' >/dev/null 2>&1 || true
amixer -c 0 cset name='IN3L Digital Volume' 140 >/dev/null 2>&1 || true

echo "Galaxy S8 Native Audio Initialized (Speaker + DMIC1 Mic)"

