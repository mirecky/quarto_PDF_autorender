@echo off
rem Spustenie Quarto Studio: qgui.bat [PRIECINOK]
setlocal
set "PYTHONPATH=%~dp0;%PYTHONPATH%"
where py >nul 2>nul
if %ERRORLEVEL%==0 (
  py -3 -m qgui %*
) else (
  python -m qgui %*
)
