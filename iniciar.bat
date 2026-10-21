@echo off
rem Arranca Gastos Bimonetarios y abre el navegador. Doble clic.
setlocal
cd /d "%~dp0"

set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

echo.
echo  Gastos Bimonetarios
echo  -------------------
echo  Servidor: http://127.0.0.1:8080
echo  Para detenerlo: Ctrl+C o cerrar esta ventana.
echo.

start "" /min cmd /c "timeout /t 3 >nul & rundll32 url.dll,FileProtocolHandler http://127.0.0.1:8080/"
"%PY%" main.py --port 8080

echo.
echo El servidor se ha detenido.
pause
