# Sincronizar la BD operativa de osap-api desde PRODUCCIÓN a DESARROLLO (solo lectura).
#
# Exporta del VPS todas las tablas de `osap_api` EXCEPTO `app_config` (que en dev
# conserva sus propios valores de configuración: dev_mode, client_ids/secretos) y las
# restaura en la BD local `osap-api`. Con esto las pruebas locales trabajan con el
# índice real (index_works/index_representations) + storage y auth reales (dev_mode=1).
#
# Requiere: ssh/scp/mysqldump/mysql y acceso SSH sin contraseña (host `RemoteIA`).
# Uso:   powershell -ExecutionPolicy Bypass -File script/sync_db_down.ps1
#        powershell -ExecutionPolicy Bypass -File script/sync_db_down.ps1 -HostAlias RemoteIA

param(
    [string]$HostAlias = "RemoteIA",
    [string]$RemoteDb = "osap_api",
    [string]$LocalDb = "osap-api",
    [string]$LocalUser = "osap2027",
    [string]$LocalPassword = "2027osapdb"
)

$ErrorActionPreference = "Stop"
$tmp = Join-Path $env:TEMP "osap-sync-db"
New-Item -ItemType Directory -Force -Path $tmp | Out-Null
$dump = Join-Path $tmp "osap_api.sql"

Write-Host "== [1/3] Exportando $RemoteDb (VPS, excepto app_config) ==" -ForegroundColor Cyan
# Tablas a excluir: app_config (config de cada entorno). El resto se copia íntegro.
ssh -o BatchMode=yes $HostAlias "sudo mysqldump --no-tablespaces --skip-comments --add-drop-table $RemoteDb --ignore-table=${RemoteDb}.app_config > /tmp/osap_api.sql && sudo chmod 644 /tmp/osap_api.sql"
if ($LASTEXITCODE -ne 0) { Write-Error "mysqldump remoto falló"; exit 1 }

Write-Host "== [2/3] Descargando dump ==" -ForegroundColor Cyan
scp -o BatchMode=yes "$($HostAlias):/tmp/osap_api.sql" $dump
if ($LASTEXITCODE -ne 0) { Write-Error "scp falló"; exit 1 }
ssh -o BatchMode=yes $HostAlias "rm -f /tmp/osap_api.sql"

Write-Host "== [3/3] Restaurando en $LocalDb (local) ==" -ForegroundColor Cyan
# Borra y recrea las tablas del dump (add-drop-table), sin tocar app_config ni las tablas
# que no vienen del VPS (authority_entity, authority_identifier, sync_state).
mysql -h 127.0.0.1 -u $LocalUser "-p$LocalPassword" $LocalDb < $dump
if ($LASTEXITCODE -ne 0) { Write-Error "mysql local falló"; exit 1 }

Remove-Item -Force $dump -ErrorAction SilentlyContinue
Write-Host "Sincronización completada: $LocalDb <- $RemoteDb (VPS)." -ForegroundColor Green
