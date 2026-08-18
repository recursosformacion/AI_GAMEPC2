# Túnel SSH para administración de BD vía phpMyAdmin en el entorno PRE.
#
# NOTA: este script pertenece al entorno "facturas-pre" (otro proyecto) y quedó
# en osap-api/script de forma residual. No forma parte de la operación de OSAP.
# Abre un túnel SSH (localhost:LocalHttpPort -> 127.0.0.1:RemoteHttpPort del servidor)
# para acceder a phpMyAdmin por HTTP. Opcionalmente ejecuta el setup remoto (-RunSetup).
# Uso:  powershell -File script/pre_dbadmin_tunnel.ps1 [-RunSetup] [-ServerHost ...] ...
param(
    [string]$ServerHost = "91.134.255.134",
    [string]$ServerUser = "ocw",
    [int]$LocalHttpPort = 18080,
    [int]$RemoteHttpPort = 8080,
    [string]$DbAdminPath = "/_dbadmin_pre",
    [switch]$RunSetup,
    [string]$RemotePrePath = "/home/ocw/apps/facturas-pre",
    [string]$DbAdminHttpUser = "dbadmin",
    [string]$DbAdminHttpPassword = ""
)
Write-Host "Acceso tunel user: dbadmin   pass: MiguelGarcia$2026" -ForegroundColor Cyan


$ErrorActionPreference = "Stop"
$remote = "${ServerUser}@${ServerHost}"
$localSetupScript = Join-Path $PSScriptRoot 'setup_phpmyadmin_pre.sh'

function ConvertTo-BashSingleQuoted {
    param([string]$Value)

    $singleQuote = [string][char]39
    $escapedSingleQuote = $singleQuote + '"' + $singleQuote + '"' + $singleQuote
    $escaped = $Value.Replace($singleQuote, $escapedSingleQuote)
    return $singleQuote + $escaped + $singleQuote
}

if ($RunSetup) {
    Write-Host "Ejecutando setup remoto de phpMyAdmin PRE (solo necesario la primera vez o tras cambios de credenciales/ruta)..." -ForegroundColor Cyan

    if (-not (Test-Path $localSetupScript)) {
        throw "No se encuentra setup local: $localSetupScript"
    }

    Write-Host "Sincronizando setup local al servidor PRE..." -ForegroundColor Cyan
    & scp $localSetupScript "${remote}:${RemotePrePath}/utRemoto/tunelDB/setup_phpmyadmin_pre.sh"
    if ($LASTEXITCODE -ne 0) {
        throw 'No se pudo sincronizar setup_phpmyadmin_pre.sh al servidor PRE.'
    }

    $passwordB64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($DbAdminHttpPassword))
    $escapedRemotePrePath = ConvertTo-BashSingleQuoted -Value $RemotePrePath
    $escapedDbAdminPath = ConvertTo-BashSingleQuoted -Value $DbAdminPath
    $escapedDbAdminHttpUser = ConvertTo-BashSingleQuoted -Value $DbAdminHttpUser
    $escapedPasswordB64 = ConvertTo-BashSingleQuoted -Value $passwordB64

        $remoteSetupTemplate = @'
set -e
cd __REMOTE_PRE_PATH__

max_checks=36
check=1
while sudo fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1 || sudo fuser /var/lib/apt/lists/lock >/dev/null 2>&1; do
    if [ "$check" -ge "$max_checks" ]; then
        echo "[setup] Timeout esperando lock de apt/dpkg." >&2
        exit 1
    fi
    echo "[setup] apt/dpkg lock ocupado. Esperando ($check/$max_checks)..."
    sleep 10
    check=$((check + 1))
done

DBADMIN_HTTP_USER=__DBADMIN_HTTP_USER__ DBADMIN_HTTP_PASSWORD="$(printf '%s' __PASSWORD_B64__ | base64 -d)" bash ./utRemoto/tunelDB/setup_phpmyadmin_pre.sh --dbadmin-path __DBADMIN_PATH__ --http-user __DBADMIN_HTTP_USER__
'@

        $remoteSetupCmd = $remoteSetupTemplate
        $remoteSetupCmd = $remoteSetupCmd.Replace('__REMOTE_PRE_PATH__', $escapedRemotePrePath)
        $remoteSetupCmd = $remoteSetupCmd.Replace('__DBADMIN_HTTP_USER__', $escapedDbAdminHttpUser)
        $remoteSetupCmd = $remoteSetupCmd.Replace('__DBADMIN_PATH__', $escapedDbAdminPath)
        $remoteSetupCmd = $remoteSetupCmd.Replace('__PASSWORD_B64__', $escapedPasswordB64)

        $remoteSetupCmdLf = ($remoteSetupCmd -replace "`r`n", "`n" -replace "`r", "`n")
        $remoteSetupCmdB64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($remoteSetupCmdLf))
        $escapedRemoteSetupCmdB64 = ConvertTo-BashSingleQuoted -Value $remoteSetupCmdB64

        & ssh "${remote}" "printf '%s' $escapedRemoteSetupCmdB64 | base64 -d | bash -s"
    if ($LASTEXITCODE -ne 0) {
        throw 'No se pudo completar setup remoto de phpMyAdmin PRE.'
    }
}

$sshArgs = @("-N", "-L", "${LocalHttpPort}:127.0.0.1:${RemoteHttpPort}", "-T", "-o", "ConnectTimeout=20", "-o", "ServerAliveInterval=15", "-o", "ServerAliveCountMax=2", $remote)

Write-Host "Abriendo tunel SSH para phpMyAdmin PRE..." -ForegroundColor Cyan
Write-Host "URL local: http://127.0.0.1:${LocalHttpPort}${DbAdminPath}" -ForegroundColor Yellow
Write-Host "(Tunel directo a Apache backend remoto en 127.0.0.1:${RemoteHttpPort})" -ForegroundColor DarkGray
Write-Host "Pulsa Ctrl+C para cerrar el tunel." -ForegroundColor Yellow

ssh @sshArgs
