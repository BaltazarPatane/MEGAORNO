@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto dependencias
where py >nul 2>nul
if errorlevel 1 goto python_directo
py -3 -m venv .venv
if errorlevel 1 goto fallo
goto dependencias
:python_directo
python -m venv .venv
if errorlevel 1 goto fallo
:dependencias
".venv\Scripts\python.exe" -c "import openpyxl, matplotlib, reportlab, PySide6" >nul 2>nul
if not errorlevel 1 goto abrir
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check --require-hashes -r requirements.lock
if errorlevel 1 goto fallo
:abrir
".venv\Scripts\python.exe" app.py
if errorlevel 1 goto fallo
exit /b 0
:fallo
echo.
echo No se pudo iniciar. Instale Python 3.11 a 3.14 de 64 bits.
echo La primera instalacion de dependencias requiere Internet.
echo Puede copiar el error de esta ventana para revisarlo.
pause
exit /b 1
