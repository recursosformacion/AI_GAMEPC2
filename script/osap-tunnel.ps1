# Resumen: abre manualmente el túnel SSH 3307 -> MySQL de producción cuando se quiere
# conectar dev a remoto. Por defecto NO hace nada, para que dev trabaje con la BD local.
# Uso: powershell -File script/osap-tunnel.ps1 -Start
# La tarea programada «OSAP tunel produccion» lo ejecuta sin -Start: queda cerrado.

param([switch]$Start)

if (-not $Start) {
    Write-Output "Túnel 3307 cerrado. Dev usa la BD local. Para conectar a remoto: -Start"
    exit 0
}

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
