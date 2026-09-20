@echo off
REM Lanzador de doble clic: reinicia el entorno de desarrollo OSAP.
REM `start` desacopla la ventana: este lanzador no se queda colgado.
start "OSAP dev restart" pwsh -NoProfile -ExecutionPolicy Bypass -NoExit -File "%~dp0restart-dev.ps1" -NoWait
