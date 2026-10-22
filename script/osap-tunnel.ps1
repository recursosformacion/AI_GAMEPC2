# Resumen: mantiene abierto el túnel SSH 3307 -> MySQL de producción (modo dev_mode=1).
# Uso: powershell -NoProfile -ExecutionPolicy Bypass -File script/osap-tunnel.ps1
# Lo lanza la tarea programada «OSAP tunel produccion» al iniciar sesión. Si ssh cae,
# reintenta cada 10 s y deja traza en %LOCALAPPDATA%\osap-tunnel.log.

$ErrorActionPreference = "Continue"
$log = Join-Path $env:LOCALAPPDATA "osap-tunnel.log"
$ssh = (Get-Command ssh.exe -ErrorAction SilentlyContinue).Source
if (-not $ssh) { $ssh = "C:\Windows\System32\OpenSSH\ssh.exe" }

while ($true) {
    $start = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $log -Value "$start abriendo túnel 3307 -> RemoteIA"
    & $ssh -N -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=3 `
        -o BatchMode=yes -L 3307:127.0.0.1:3306 RemoteIA 2>> $log
    $code = $LASTEXITCODE
    $end = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $log -Value "$end túnel terminado (exit $code); reintento en 10 s"
    Start-Sleep -Seconds 10
}
