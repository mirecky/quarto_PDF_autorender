@echo off
rem Spustenie Quarto Studio: qgui.bat [PRIECINOK]
set PYTHONPATH=%~dp0;%PYTHONPATH%
python -m qgui %*
