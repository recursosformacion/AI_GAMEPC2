# predeploy_backup.ps1 — Copia de seguridad ANTES de subir una versión a producción.
#
# Resumen: en el servidor (`RemoteIA`) crea ~/backups/<fecha>/ con:
#   - dump comprimido de cada BD OSAP (osap_api, osap_auth, osap_storage, osap_support);
#   - tar comprimido de cada programa (app=SPA, osap-api, osap-auth, osap-storage,
#     osap-support) excluyendo .venv/__pycache__.
# Sirve de punto de rollback: restaurar el .sql.gz y/o reextraer el .tar.gz.
#
# Uso:
#   pwsh script/predeploy_backup.ps1
#   pwsh script/predeploy_backup.ps1 -HostAlias RemoteIA -Stamp 20260926-1200

param(
    [string]$HostAlias = "RemoteIA",
    [string]$Stamp = (Get-Date -Format "yyyyMMdd-HHmmss"),
    [string]$RemoteRoot = "/home/ocw/openmusicrepository.com",
    [string]$BackupRoot = "/home/ocw/backups"
)

$ErrorActionPreference = "Stop"
$dbs = @("osap_api", "osap_auth", "osap_storage", "osap_support")
$dirs = @("app", "osap-api", "osap-auth", "osap-storage", "osap-support")

$dbDumps = ($dbs | ForEach-Object {
    "sudo mysqldump --no-tablespaces --single-transaction --routines --events $_ | gzip > `"$BackupRoot/$Stamp/$_.sql.gz`""
}) -join "; "
$tarDumps = ($dirs | ForEach-Object {
    "tar -czf `"$BackupRoot/$Stamp/$_.tar.gz`" -C $RemoteRoot --exclude=.venv --exclude=__pycache__ --exclude='*.pyc' $_"
}) -join "; "

$remote = "set -e; mkdir -p $BackupRoot/$Stamp; $dbDumps; $tarDumps; " +
          "echo '--- contenido ---'; ls -lh $BackupRoot/$Stamp"

Write-Host "== Backup previo a la subida ($Stamp) en $HostAlias ==" -ForegroundColor Cyan
ssh -o BatchMode=yes $HostAlias $remote
if ($LASTEXITCODE -ne 0) { Write-Error "Backup falló"; exit 1 }
Write-Host "Backup completado en $BackupRoot/$Stamp" -ForegroundColor Green
