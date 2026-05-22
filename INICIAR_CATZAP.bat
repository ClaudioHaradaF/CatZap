@echo off
title CatZap Server
cd /d "%~dp0"

set CUDA_VISIBLE_DEVICES=-1
set PLAYWRIGHT_BROWSERS_PATH=%USERPROFILE%\AppData\Local\ms-playwright

echo ============================================
echo   CatZap v1.0 - Servidor de Transcricao
echo ============================================
echo.
echo  Instale a extensao no Chrome/Edge:
echo  1. Abra chrome://extensions (ou edge://extensions)
echo  2. Ative "Modo do desenvolvedor"
echo  3. Clique "Carregar sem compactacao"
echo  4. Selecione a pasta "cat_zap_extension"
echo  5. Abra web.whatsapp.com e clique em um audio
echo.
echo ============================================
echo.
echo.

if exist "CatZap.exe" (
    CatZap.exe
) else (
    python cat_zap.py
)
echo [INFO] Servidor encerrado (codigo: %ERRORLEVEL%).
pause
