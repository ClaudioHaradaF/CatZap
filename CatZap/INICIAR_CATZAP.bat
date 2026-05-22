@echo off
title CatZap Server
cd /d "%~dp0"

set CUDA_VISIBLE_DEVICES=-1
set PLAYWRIGHT_BROWSERS_PATH=%USERPROFILE%\AppData\Local\ms-playwright

echo ============================================
echo   CatZap v1.0 - Servidor de Transcricao
echo ============================================
echo.
echo  Na primeira execucao, o CatZap vai:
echo  1. Extrair a extensao para %APPDATA%\CatZap\extension
echo  2. Abrir instrucoes para instalar no Chrome
echo  3. Baixar o modelo Whisper
echo  4. Criar atalho na Area de Trabalho
echo.
echo  Nas proximas, inicia o servidor direto.
echo.
echo ============================================
echo.

if exist "CatZap.exe" (
    CatZap.exe
) else (
    python cat_zap.py
)
echo [INFO] Servidor encerrado (codigo: %ERRORLEVEL%).
pause
