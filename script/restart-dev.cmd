@echo off
REM Lanzador de doble clic: reinicia el entorno de desarrollo OSAP.
REM El script de PowerShell se autoeleva (UAC) para poder matar todos los procesos.
pwsh -NoProfile -ExecutionPolicy Bypass -NoExit -File "%~dp0restart-dev.ps1"
