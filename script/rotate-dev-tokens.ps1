# rotate-dev-tokens.ps1 — Rota los tokens internos de los servicios de desarrollo.
#
# Resumen: genera tokens aleatorios para osap-internal y ai-noticias, los guarda en
# %LOCALAPPDATA%\osap-dev\*.txt, reinicia los servicios y, opcionalmente, programa una
# tarea semanal para repetirlo.
#
# Uso:
#   pwsh script/rotate-dev-tokens.ps1
#   pwsh script/rotate-dev-tokens.ps1 -ScheduleWeekly
[CmdletBinding()]
param([switch]$ScheduleWeekly)

$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
$tokenDir = Join-Path $env:LOCALAPPDATA "osap-dev"
New-Item -ItemType Directory -Force -Path $tokenDir | Out-Null

function New-Token {
    $bytes = [Security.Cryptography.RandomNumberGenerator]::GetBytes(32)
    return [Convert]::ToHexString($bytes).ToLowerInvariant()
}

$internal = New-Token
$news = New-Token
[IO.File]::WriteAllText((Join-Path $tokenDir "internal-token.txt"), $internal, [Text.UTF8Encoding]::new($false))
[IO.File]::WriteAllText((Join-Path $tokenDir "news-token.txt"), $news, [Text.UTF8Encoding]::new($false))
Write-Host "Tokens rotados en $tokenDir"

& pwsh -NoProfile -File (Join-Path $PSScriptRoot "restart-dev.ps1") -NoElevate
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if ($ScheduleWeekly) {
    $taskName = "OSAP dev token rotation"
    $pwshPath = (Get-Command pwsh).Source
    $script = Join-Path $PSScriptRoot "rotate-dev-tokens.ps1"
    $action = New-ScheduledTaskAction -Execute $pwshPath `
        -Argument "-NoProfile -File `"$script`"" -WorkingDirectory $root
    $trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At 4am
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 20)
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
        -Settings $settings -Description "Rota tokens internos de OSAP dev" -Force | Out-Null
    Write-Host "Tarea semanal '$taskName' registrada."
}
