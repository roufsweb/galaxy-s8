@echo off
title Galaxy S8 AI Voice Assistant - Animoji Face Demo
echo =======================================================
echo   GALAXY S8 LOCAL AI VOICE ASSISTANT - ANIMOJI DEMO
echo =======================================================
echo.
echo Launching Interactive 60 FPS Animoji Talking Face in your browser...
echo.
echo Interactive Keyboard Controls:
echo   [1] Idle State      - Smiling, natural blinking eyes
echo   [2] Listening State - Reactive concentric soundwave ripples
echo   [3] Thinking State  - Rotating amber synapse halo (Qwen 1.5B)
echo   [4] Speaking State  - Dynamic real-time lip-sync mouth
echo.
start "" "%~dp0ui\avatar.html"
python "%~dp0scripts\s8_voice_assistant.py" --test-cycle --prompt "Hello Rouf! I am running 100%% locally on your Galaxy S8 Exynos 8895 processor with 4GB RAM."
pause

