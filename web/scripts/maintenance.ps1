# maintenance.ps1 — Activa/desactiva el modo mantenimiento de la web.
#
# Resumen: mantiene el flag `maintenance.flag` en DOS sitios:
#   - Local (Apache sirve web/dist): web/dist/maintenance.flag -> 503 con maintenance.html.
#   - Producción (nginx app.openmusicrepository.com): maintenance.flag en el root de la SPA.
# El público ve la página de mantenimiento; el equipo entra con `?preview=<TOKEN>` (la
# página fija la cookie osap_preview durante 1 día) para revisar antes de liberar.
#
# Uso:
#   pwsh web/scripts/maintenance.ps1 -On      # activa local + producción
#   pwsh web/scripts/maintenance.ps1 -Off     # desactiva ambos
#   pwsh web/scripts/maintenance.ps1 -Status  # estado de ambos
#   ... -LocalOnly | -RemoteOnly              # acotar el ámbito

param(
    [switch]$On,
    [switch]$Off,
    [switch]$Status,
    [switch]$LocalOnly,
    [switch]$RemoteOnly,
    [string]$RemoteHost = "RemoteIA",
    [string]$RemoteAppDir = "/home/ocw/openmusicrepository.com/app",
    [string]$ProdUrl = "https://app.openmusicrepository.com"
)

$ErrorActionPreference = "Stop"
$dist = Join-Path $PSScriptRoot "..\dist"
$flag = Join-Path $dist "maintenance.flag"
$tokenFile = Join-Path $dist "maintenance.token"
$doLocal = -not $RemoteOnly
$doRemote = -not $LocalOnly

function Get-Token {
    if (Test-Path -LiteralPath $tokenFile) { return (Get-Content -LiteralPath $tokenFile -Raw).Trim() }
    $token = -join ((1..16) | ForEach-Object { "{0:x}" -f (Get-Random -Minimum 0 -Maximum 16) })
    if (Test-Path -LiteralPath $dist) { Set-Content -LiteralPath $tokenFile -Value $token -NoNewline }
    return $token
}

function Set-RemoteFlag([bool]$active) {
    if ($active) {
        ssh -o BatchMode=yes $RemoteHost "touch '$RemoteAppDir/maintenance.flag'"
    } else {
        ssh -o BatchMode=yes $RemoteHost "rm -f '$RemoteAppDir/maintenance.flag'"
    }
    if ($LASTEXITCODE -ne 0) { throw "Fallo al $(if ($active) { 'activar' } else { 'desactivar' }) mantenimiento en $RemoteHost" }
}

function Get-RemoteFlag {
    $out = ssh -o BatchMode=yes $RemoteHost "test -f '$RemoteAppDir/maintenance.flag' && echo ON || echo OFF"
    return ($out | Select-Object -Last 1).Trim()
}

if ($On) {
    $token = Get-Token
    if ($doLocal) {
        if (-not (Test-Path -LiteralPath $dist)) { throw "No existe web/dist. Ejecuta antes el build (vite build)." }
        New-Item -ItemType File -Force -Path $flag | Out-Null
        Write-Output "LOCAL: mantenimiento ACTIVO -> http://osap-app/?preview=$token"
    }
    if ($doRemote) {
        Set-RemoteFlag $true
        Write-Output "PROD:  mantenimiento ACTIVO -> $ProdUrl/?preview=$token"
    }
    exit 0
}
if ($Off) {
    if ($doRemote) { Set-RemoteFlag $false; Write-Output "PROD:  mantenimiento desactivado" }
    if ($doLocal) {
        if (Test-Path -LiteralPath $flag) { Remove-Item -LiteralPath $flag -Force }
        Write-Output "LOCAL: mantenimiento desactivado"
    }
    exit 0
}
if ($doLocal) {
    if (Test-Path -LiteralPath $flag) {
        Write-Output "LOCAL: MANTENIMIENTO ACTIVO -> http://osap-app/?preview=$(Get-Token)"
    } else {
        Write-Output "LOCAL: web pública"
    }
}
if ($doRemote) {
    $state = Get-RemoteFlag
    if ($state -eq "ON") {
        Write-Output "PROD:  MANTENIMIENTO ACTIVO -> $ProdUrl/?preview=$(Get-Token)"
    } else {
        Write-Output "PROD:  web pública -> $ProdUrl"
    }
}
