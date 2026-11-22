@echo off
setlocal
set "SRC=%~1"
if "%SRC%"=="" set "SRC=%USERPROFILE%\Downloads\cpdl-parts.json"
if not exist "%SRC%" (
  echo No existe el fichero: %SRC%
  exit /b 1
)
echo [1/2] Subiendo %SRC% al servidor...
scp -o BatchMode=yes "%SRC%" RemoteIA:/home/ocw/cpdl_dump/cpdl-parts.json
if errorlevel 1 ( echo Error en scp & exit /b 1 )
echo [2/2] Lanzando proceso en el servidor...
ssh -o BatchMode=yes RemoteIA "bash /home/ocw/run_cpdl_import.sh"
if errorlevel 1 ( echo Error en ssh & exit /b 1 )
echo Hecho.
endlocal
