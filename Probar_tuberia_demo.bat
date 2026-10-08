@echo off
setlocal
cd /d "%~dp0"
set "HORNO_CSC=%WINDIR%\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if not exist "%HORNO_CSC%" set "HORNO_CSC=%WINDIR%\Microsoft.NET\Framework\v4.0.30319\csc.exe"
if not exist "%HORNO_CSC%" goto sin_compilador
if not exist "%LOCALAPPDATA%\HornoMadgeTech" mkdir "%LOCALAPPDATA%\HornoMadgeTech"
"%HORNO_CSC%" /nologo /target:exe /out:"%LOCALAPPDATA%\HornoMadgeTech\DemoHost.exe" /r:System.ServiceModel.dll /r:System.Runtime.Serialization.dll wcf\DemoHost.cs
if errorlevel 1 goto fallo
"%LOCALAPPDATA%\HornoMadgeTech\DemoHost.exe"
if errorlevel 1 goto fallo
exit /b 0
:sin_compilador
echo No se encuentra el compilador de .NET Framework 4.x.
:fallo
echo No se pudo ejecutar el servicio de prueba WCF.
pause
exit /b 1
