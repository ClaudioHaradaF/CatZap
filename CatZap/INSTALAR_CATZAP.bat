@echo off
title CatZap - Instalacao
cd /d "%~dp0"

set PLAYWRIGHT_BROWSERS_PATH=%USERPROFILE%\AppData\Local\ms-playwright

echo ============================================
echo   CatZap v1.0 - Instalacao Completa
echo ============================================
echo.
echo [1/3] Verificando componentes do sistema...
echo.
if exist "vc_redist.x64.exe" (
    echo [+] Instalando Visual C++ Redistributavel...
    vc_redist.x64.exe /quiet /norestart >nul 2>&1
)

echo [2/3] Iniciando servidor CatZap...
echo.
echo.

echo ============================================
echo   PASSO 3 - Instale a extensao no navegador
echo ============================================
echo.
echo  No Chrome ou Edge:
echo  1. Abra chrome://extensions (edge://extensions)
echo  2. Ative "Modo do desenvolvedor" (canto sup.dir.)
echo  3. Clique "Carregar sem compactacao"
echo  4. Selecione a pasta "cat_zap_extension"
echo  5. Pronto! Va para web.whatsapp.com
echo.
echo ============================================
echo.
echo  O servidor vai iniciar agora (rodando em segundo plano).
echo  Para fechar, clique em "Sair" no icone do gatinho
echo  na bandeja do sistema (ao lado do relogio).
echo.
echo ============================================
echo.
pause

if exist "CatZap.exe" (
    CatZap.exe
) else (
    echo [INFO] CatZap.exe nao encontrado, usando python...
    python cat_zap.py
)

echo [INFO] Servidor encerrado (codigo: %ERRORLEVEL%).
pause
