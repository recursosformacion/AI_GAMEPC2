<#
.SYNOPSIS
  Reinicia en local OSAP para probar cambios de osap-storage / osap-api / osap-app.

.DESCRIPTION
  - Compila la SPA de osap-app (tsc + vite build) si ha cambiado web/src.
  - Detiene y relanza los uvicorn de osap-storage (8000), osap-api (8001) y
    osap-auth (8200), con logs en _pruebas/logs/*.log.
  - La SPA se sirve por Apache (http://osap-app) desde web/dist; /api y /auth
    se proxian a los uvicorn reiniciados.

.PARAMETER SkipBuild
  Omite la compilación de la SPA (solo reinicia backends).

.PARAMETER NoAuth
  No reinicia osap-auth.

.EXAMPLE
  pwsh -File _pruebas\restart-dev.ps1
  pwsh -File _pruebas\restart-dev.ps1 -SkipBuild
#>
param(
  [switch]$SkipBuild,
  [switch]$NoAuth
)
$ErrorActionPreference = 'Stop'
$root = 'D:\Proyectos\AI_OSAP'
$logs = Join-Path $root '_pruebas\logs'
New-Item -ItemType Directory -Force -Path $logs | Out-Null

function Stop-Port([int]$port) {
  # Mata el proceso que escucha en el puerto y, si no aparece, cualquier python cuyo
  # CommandLine contenga ese puerto (evita "fantasmas" tras uvicorn con reload).
  Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
    ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
  Get-CimInstance Win32_Process -Filter "Name LIKE '%python%'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -match "--port $port" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
  Start-Sleep -Milliseconds 700
}

function Wait-Port([int]$port, [string]$path, [string]$name) {
  for ($i = 0; $i -lt 12; $i++) {
    try {
      $r = Invoke-WebRequest -Uri "http://127.0.0.1:$port$path" -TimeoutSec 2 -SkipHttpErrorCheck
      if ($r.StatusCode -lt 500) { return }
    } catch { }
    Start-Sleep -Milliseconds 600
  }
  throw "No responde $name en http://127.0.0.1:$port$path"
}

function Start-Uvi([string]$dir, [string]$py, [string[]]$argsList, [string]$name) {
  $stdout = Join-Path $logs "$name.log"
  $stderr = Join-Path $logs "$name.err.log"
  $p = Start-Process -FilePath $py -ArgumentList $argsList -WorkingDirectory $dir `
    -RedirectStandardOutput $stdout -RedirectStandardError $stderr -WindowStyle Hidden -PassThru
  Write-Host "  $name -> pid $($p.Id) (logs $logs\$name.log)"
}

if (-not $SkipBuild) {
  Write-Host '== Build osap-app (tsc + vite) =='
  Push-Location (Join-Path $root 'osap-api\web')
  try {
    & .\node_modules\.bin\tsc.cmd --noEmit
    if ($LASTEXITCODE -ne 0) { throw 'tsc falló' }
    node node_modules\vite\bin\vite.js build
    if ($LASTEXITCODE -ne 0) { throw 'vite build falló' }
  } finally {
    Pop-Location
  }
}

Write-Host '== Parando servicios =='
Stop-Port 8000
Stop-Port 8001
Stop-Port 8300
if (-not $NoAuth) { Stop-Port 8200 }
Start-Sleep -Seconds 1

Write-Host '== Arrancando servicios =='
Start-Uvi (Join-Path $root 'osap-storage') (Join-Path $root 'osap-storage\.venv\Scripts\python.exe') `
  @('-m', 'uvicorn', 'api.main:app', '--host', '127.0.0.1', '--port', '8000') 'storage'
Start-Uvi (Join-Path $root 'osap-api') 'python' `
  @('-m', 'uvicorn', '--factory', 'src.osap.api.platform_app:create_platform_app', '--host', '127.0.0.1', '--port', '8001') 'api'
Start-Uvi (Join-Path $root 'osap-support') 'python' `
  @('-m', 'uvicorn', '--factory', 'api.main:create_app_from_settings', '--host', '127.0.0.1', '--port', '8300') 'support'
if (-not $NoAuth) {
  Start-Uvi (Join-Path $root 'osap-auth') (Join-Path $root 'osap-auth\.venv\Scripts\python.exe') `
    @('-m', 'uvicorn', 'api.main:create_app_from_settings', '--factory', '--host', '127.0.0.1', '--port', '8200') 'auth'
}

Write-Host '== Verificando arranque =='
Wait-Port 8000 '/health' 'storage'
Wait-Port 8001 '/api/v1/system/health' 'osap-api'
Wait-Port 8300 '/health' 'osap-support'
if (-not $NoAuth) { Wait-Port 8200 '/openapi.json' 'osap-auth' }

Write-Host 'Listo: http://osap-app (Apache) | API 8001 | storage 8000 | auth 8200 | support 8300'
Write-Host 'si da error, taskkill /IM "python3.exe" /F y volver a lanzar este script'