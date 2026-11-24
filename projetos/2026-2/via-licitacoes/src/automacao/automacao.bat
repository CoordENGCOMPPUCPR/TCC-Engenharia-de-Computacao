
@echo off
setlocal

cd /d "%~dp0"

echo ==========================================
echo       VIA LICITACOES - AUTOMACAO RPA
echo ==========================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo ERRO: Ambiente virtual Python nao encontrado.
    echo.
    echo Execute primeiro:
    echo python -m venv .venv
    echo .venv\Scripts\python.exe -m pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" main.py

if errorlevel 1 (
    echo.
    echo A automacao terminou com erro.
)

pause
