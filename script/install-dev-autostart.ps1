# install-dev-autostart.ps1 — Registra el arranque de los servicios OSAP de desarrollo.
#
# Resumen: crea/actualiza una tarea programada que ejecuta restart-dev.ps1 al iniciar
# sesión, para que tras un reinicio no haya que arrancar los servicios a mano.
#
# Uso: pwsh script/install-dev-autostart.ps1 [-Remove]
[CmdletBinding()]
param([switch]$Remove)

$ErrorActionPreference = "Stop"
$taskName = "OSAP dev services"
$root = Split-Path $PSScriptRoot -Parent
$restart = Join-Path $PSScriptRoot "restart-dev.ps1"

if ($Remove) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Tarea '$taskName' eliminada."
    exit 0
}

$pwsh = (Get-Command pwsh).Source
$action = New-ScheduledTaskAction -Execute $pwsh `
    -Argument "-NoProfile -File `"$restart`" -NoElevate" `
    -WorkingDirectory $root
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 10)

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
    -Settings $settings -Description "Arranca los servicios OSAP de desarrollo al iniciar sesión" `
    -Force | Out-Null
Write-Host "Tarea '$taskName' registrada para $env:USERNAME."

