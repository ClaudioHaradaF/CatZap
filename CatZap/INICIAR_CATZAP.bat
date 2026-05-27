@echo off
title CatZap Server
cd /d "%~dp0"

REM Define variáveis de ambiente para modelo embutido
set WHISPER_CACHE_DIR=%~dp0models\whisper
set PLAYWRIGHT_BROWSERS_PATH=%USERPROFILE%\AppData\Local\ms-playwright

echo ============================================
echo   CatZap v1.3 - Servidor de Transcricao
echo ============================================
echo.
echo  Iniciando servidor...
echo.

REM Verifica se o modelo existe
if exist "models\whisper\model.bin" (
    echo  Modelo embutido detectado
) else (
    echo  AVISO: Modelo nao encontrado - sera baixado (precisa internet)
)

REM Inicia o servidor
python cat_zap.py
if errorlevel 1 (
    echo.
    echo  Erro ao iniciar. Pressione qualquer tecla para sair...
    pause >nul
)

echo [INFO] Servidor encerrado (codigo: %ERRORLEVEL%).
pause