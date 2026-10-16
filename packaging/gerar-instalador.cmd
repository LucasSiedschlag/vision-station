@echo off
rem Builds the program and the installer (docs/guias/gerar-instalador.md).
rem Double-click it, or from a terminal:  packaging\gerar-instalador.cmd [-NoInstaller]
setlocal
cd /d "%~dp0.."
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_windows.ps1" %*
set "code=%errorlevel%"
echo.
if "%code%"=="0" (echo Pronto: veja a pasta dist.) else (echo O build falhou ^(codigo %code%^). Veja as mensagens acima.)
rem keep the window open only when it was opened with a double click
echo %cmdcmdline% | find /i "%~0" >nul && pause
exit /b %code%
