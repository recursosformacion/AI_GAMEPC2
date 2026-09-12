# maintenance.ps1 — Activa/desactiva el modo mantenimiento de la web (Apache sirve web/dist).
#
# Resumen: crea o elimina `dist/maintenance.flag`. Con el flag activo, Apache responde 503
# con `maintenance.html` para el público, salvo assets y el bypass de revisión:
#     http://osap-app/?preview=<TOKEN>
# El token se guarda en `dist/maintenance.token` y la visita deja cookie `osap_preview=1`
# (1 día), de modo que el equipo puede revisar la web antes de liberar.
#
# Uso:
#   pwsh web/scripts/maintenance.ps1 -On      # activa mantenimiento (imprime URL de revisión)
#   pwsh web/scripts/maintenance.ps1 -Off     # desactiva
#   pwsh web/scripts/maintenance.ps1 -Status  # estado

param(
    [switch]$On,
    [switch]$Off,
    [switch]$Status
)

$ErrorActionPreference = "Stop"
$dist = Join-Path $PSScriptRoot "..\dist"
$flag = Join-Path $dist "maintenance.flag"
$tokenFile = Join-Path $dist "maintenance.token"

function Get-Token {
    if (Test-Path -LiteralPath $tokenFile) { return (Get-Content -LiteralPath $tokenFile -Raw).Trim() }
    $token = -join ((1..16) | ForEach-Object { "{0:x}" -f (Get-Random -Minimum 0 -Maximum 16) })
    Set-Content -LiteralPath $tokenFile -Value $token -NoNewline
    return $token
}

if ($On) {
    if (-not (Test-Path -LiteralPath $dist)) { throw "No existe web/dist. Ejecuta antes el build (vite build)." }
    New-Item -ItemType File -Force -Path $flag | Out-Null
    $token = Get-Token
    Write-Output "MANTENIMIENTO ACTIVO"
    Write-Output "Revisión del equipo: http://osap-app/?preview=$token"
    exit 0
}
if ($Off) {
    if (Test-Path -LiteralPath $flag) { Remove-Item -LiteralPath $flag -Force }
    Write-Output "Mantenimiento desactivado"
    exit 0
}
if (Test-Path -LiteralPath $flag) {
    $token = Get-Token
    Write-Output "Estado: MANTENIMIENTO ACTIVO"
    Write-Output "Revisión del equipo: http://osap-app/?preview=$token"
} else {
    Write-Output "Estado: web pública (sin mantenimiento)"
}
