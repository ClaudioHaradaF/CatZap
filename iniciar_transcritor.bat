@echo off
title WaTranscriber
cd /d "%~dp0"
set PLAYWRIGHT_BROWSERS_PATH=%USERPROFILE%\AppData\Local\ms-playwright
if exist "dist\WaTranscriber\WaTranscriber.exe" (
    "dist\WaTranscriber\WaTranscriber.exe"
) else (
    python whatsapp_transcriber.py
)
pause
