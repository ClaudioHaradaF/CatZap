@echo off
title CatZap v1.3 - Servidor de Transcricao
cd /d "%~dp0"

echo ============================================
echo   CatZap v1.3 - Servidor de Transcricao
echo ============================================
echo.

REM Configura caminho do modelo
if exist "models\whisper\model.bin" (
    echo  Modelo embutido detectado (425MB)
    set WHISPER_CACHE_DIR=%cd%\models\whisper
) else (
    echo  AVISO: Modelo nao encontrado - sera baixado (precisa internet)
)

echo  Iniciando servidor...
echo.

REM Inicia WhatsApp Web
start "" "https://web.whatsapp.com" 2>nul

REM Executa o servidor Python
python -u cat_zap.py

echo.
echo [INFO] Pressione qualquer tecla para fechar...
pause >nul