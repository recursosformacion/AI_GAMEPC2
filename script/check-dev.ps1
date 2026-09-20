# check-dev.ps1 — Estado rápido del entorno de desarrollo OSAP (NO bloquea, no reinicia nada).
#
# Resumen: comprueba en segundos si cada servicio escucha y responde en su healthcheck, si la
# SPA de Apache responde, y muestra las últimas líneas de log y del último restart. Sirve para
# saber si algo está caído o colgado sin lanzar el restart.
#
# Uso: pwsh script/check-dev.ps1

$services = @(
    [pscustomobject]@{ Name = "osap-storage"; Port = 8000; Health = "http://127.0.0.1:8000/api/v1/health" },
    [pscustomobject]@{ Name = "osap-api"; Port = 8001; Health = "http://127.0.0.1:8001/api/v1/system/health" },
    [pscustomobject]@{ Name = "osap-auth"; Port = 8200; Health = "http://127.0.0.1:8200/health" },
    [pscustomobject]@{ Name = "osap-support"; Port = 8300; Health = "http://127.0.0.1:8300/health" }
)
$logDir = Join-Path $env:LOCALAPPDATA "osap-dev\logs"

function Get-ListeningPid([int]$Port) {
    $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($conn) { return [int]$conn.OwningProcess }
    return $null
}

Write-Host ("== OSAP dev check {0:yyyy-MM-dd HH:mm:ss} ==" -f (Get-Date)) -ForegroundColor Cyan
foreach ($service in $services) {
    $pidValue = Get-ListeningPid $service.Port
    $health = "-"
    if ($pidValue) {
        try {
            $response = Invoke-WebRequest -Uri $service.Health -TimeoutSec 4 -SkipHttpErrorCheck -UseBasicParsing
            $health = [int]$response.StatusCode
        } catch {
            $health = "sin respuesta"
        }
    }
    $state = if ($pidValue -and $health -eq 200) { "OK" } elseif ($pidValue) { "ESCUCHA pero health=$health" } else { "CAIDO" }
    Write-Host ("  {0,-13} puerto={1} pid={2,-7} health={3,-13} {4}" -f $service.Name, $service.Port, $pidValue, $health, $state)
}

$app = try { [int](Invoke-WebRequest -Uri "http://osap-app/" -TimeoutSec 4 -SkipHttpErrorCheck -UseBasicParsing).StatusCode } catch { "sin respuesta" }
Write-Host ("  {0,-13} health={1}" -f "osap-app", $app)

$restartLog = Join-Path $logDir "restart.last.log"
if (Test-Path $restartLog) {
    Write-Host "`n-- últimas líneas del restart --" -ForegroundColor DarkGray
    Get-Content $restartLog | Select-Object -Last 6 | ForEach-Object { "   $_" }
}
foreach ($service in $services) {
    $err = Join-Path $logDir "$($service.Name).err.log"
    if (Test-Path $err) {
        $tail = Get-Content $err | Select-Object -Last 2
        if ($tail) {
            Write-Host "-- $($service.Name) (err.log) --" -ForegroundColor DarkGray
            $tail | ForEach-Object { "   " + $_.Substring(0, [Math]::Min(150, $_.Length)) }
        }
    }
}
