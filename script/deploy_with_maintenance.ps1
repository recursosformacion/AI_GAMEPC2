# deploy_with_maintenance.ps1 — Despliegue a producción con la pantalla de mantenimiento.
#
# Resumen: activa el mantenimiento SOLO en el servidor (el público ve 503 +
# maintenance.html; el equipo entra con ?preview=TOKEN), ejecuta `deploy_all.ps1`
# (SPA + los cuatro backends) y deja el mantenimiento ACTIVO para revisar. Cuando se
# valide, se desactiva a mano con `web/scripts/maintenance.ps1 -RemoteOnly -Off`.
#
# No despliega el SSR de React: producción sigue sirviendo /composers y /obras con
# osap-api (Jinja) hasta la ventana del plan `docs/osap/prod-ssr-plan.md`.
#
# Uso:
#   pwsh script/deploy_with_maintenance.ps1
#   pwsh script/deploy_with_maintenance.ps1 -SkipBuild   # reutiliza web/dist actual
#
# Requiere SSH sin contraseña a `RemoteIA`.

param(
    [string]$HostAlias = "RemoteIA",
    [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

Write-Host "== [1/2] Activando mantenimiento en producción ==" -ForegroundColor Cyan
& pwsh -NoProfile -File (Join-Path $root "web\scripts\maintenance.ps1") -RemoteOnly -On
if ($LASTEXITCODE -ne 0) { throw "No se pudo activar el mantenimiento" }

Write-Host "== [2/2] Desplegando (SPA + backends) ==" -ForegroundColor Cyan
$deployArgs = @("-NoProfile", "-File", (Join-Path $root "script\deploy_all.ps1"), "-HostAlias", $HostAlias)
if ($SkipBuild) { $deployArgs += "-SkipBuild" }
& pwsh @deployArgs
$code = $LASTEXITCODE

if ($code -ne 0) {
    Write-Host ""
    Write-Host "El despliegue falló. EL MANTENIMIENTO SIGUE ACTIVO." -ForegroundColor Red
    Write-Host "Revisa los logs y, si hay que revertir, usa el backup previo." -ForegroundColor Red
    Write-Host "Cuando esté resuelto: pwsh web/scripts/maintenance.ps1 -RemoteOnly -Off" -ForegroundColor Yellow
    exit $code
}

Write-Host ""
Write-Host "Despliegue terminado. EL MANTENIMIENTO SIGUE ACTIVO." -ForegroundColor Yellow
$tokenFile = Join-Path $root "web\dist\maintenance.token"
if (Test-Path -LiteralPath $tokenFile) {
    $token = (Get-Content -LiteralPath $tokenFile -Raw).Trim()
    if ($token) {
        Write-Host "Preview de revisión:" -ForegroundColor Yellow
        Write-Host "  https://app.openmusicrepository.com/?preview=$token" -ForegroundColor White
    }
}
Write-Host "Si todo está bien, publica con:" -ForegroundColor Yellow
Write-Host "  pwsh web/scripts/maintenance.ps1 -RemoteOnly -Off" -ForegroundColor White
