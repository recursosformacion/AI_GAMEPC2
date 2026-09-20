# restart-dev.ps1 — Reinicio limpio del entorno de desarrollo OSAP.
#
# Resumen: mata TODOS los procesos de los servicios OSAP locales (por puerto y por
# command line) y los vuelve a levantar en segundo plano, esperando a que cada uno
# responda en su healthcheck. Pensado para lanzarse desde el escritorio antes de probar.
#
# Servicios (host 127.0.0.1): osap-storage 8000, osap-api 8001, osap-auth 8200,
# osap-support 8300. Apache (osap-app) NO se toca: sirve la SPA y hace de proxy.
#
# Uso:
#   pwsh script/restart-dev.ps1              # se autoeleva (necesario para matar procesos
#                                            # de otra sesión/administrador)
#   pwsh script/restart-dev.ps1 -NoElevate   # sin pedir UAC (puede no poder matar todo)
#   pwsh script/restart-dev.ps1 -SkipKill    # solo arrancar (no mata)

[CmdletBinding()]
param(
    [switch]$NoElevate,
    [switch]$SkipKill,
    [switch]$NoWait,
    [int]$TimeoutSeconds = 120
)

$ErrorActionPreference = "Stop"
$Root = "D:\Proyectos\AI_OSAP"

$services = @(
    [pscustomobject]@{ Name = "osap-storage"; Repo = "osap-storage"; Port = 8000; App = "api.main:app"; Factory = $false; Health = "http://127.0.0.1:8000/api/v1/health"; Env = @{ OSAP_CONFIG = "config.yaml" } },
    [pscustomobject]@{ Name = "osap-api"; Repo = "osap-api"; Port = 8001; App = "src.osap.api.platform_app:create_platform_app"; Factory = $true; Health = "http://127.0.0.1:8001/api/v1/system/health"; Env = @{} },
    [pscustomobject]@{ Name = "osap-auth"; Repo = "osap-auth"; Port = 8200; App = "api.main:create_app_from_settings"; Factory = $true; Health = "http://127.0.0.1:8200/health"; Env = @{} },
    [pscustomobject]@{ Name = "osap-support"; Repo = "osap-support"; Port = 8300; App = "api.main:create_app_from_settings"; Factory = $true; Health = "http://127.0.0.1:8300/health"; Env = @{} }
)

function Test-Admin {
    $principal = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

# Matar procesos de otra sesión (o elevados) exige ser admin. Si no lo somos, se relanza
# elevado y el proceso actual termina.
if (-not (Test-Admin) -and -not $NoElevate) {
    Write-Host "Pidiendo permisos de administrador (necesario para matar todos los procesos)..." -ForegroundColor Yellow
    $relaunch = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-NoExit", "-File", "`"$PSCommandPath`"", "-NoElevate")
    if ($SkipKill) { $relaunch += "-SkipKill" }
    if ($NoWait) { $relaunch += "-NoWait" }
    Start-Process -FilePath "pwsh" -Verb RunAs -ArgumentList $relaunch
    exit 0
}

function Resolve-Python([string]$RepoPath) {
    $venv = Join-Path $RepoPath ".venv\Scripts\python.exe"
    if (Test-Path -LiteralPath $venv) {
        & $venv -c "import sys" 2>$null
        if ($LASTEXITCODE -eq 0) { return $venv }
        Write-Host "  venv inválido en $RepoPath (se usa Python del sistema)" -ForegroundColor DarkYellow
    }
    foreach ($candidate in @((Get-Command python -ErrorAction SilentlyContinue).Source, (py -3.12 -c "import sys; print(sys.executable)" 2>$null))) {
        if ($candidate -and (Test-Path -LiteralPath $candidate)) { return $candidate }
    }
    throw "No hay intérprete Python válido para $RepoPath"
}

function Get-PortPids([int]$Port) {
    $pids = @()
    $ErrorActionPreference = "SilentlyContinue"
    $pids += (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess)
    $net = netstat -ano | Select-String -Pattern ":$Port\s+\S+\s+LISTENING"
    foreach ($line in $net) { $pids += [int](($line -split '\s+')[-1]) }
    $ErrorActionPreference = "Stop"
    return @($pids | Where-Object { $_ -gt 0 } | Sort-Object -Unique)
}

function Stop-OsapProcesses {
    $targets = New-Object System.Collections.Generic.HashSet[int]
    foreach ($service in $services) {
        foreach ($procId in (Get-PortPids $service.Port)) { [void]$targets.Add([int]$procId) }
    }
    $stray = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        $_.CommandLine -and $_.CommandLine -match "(?i)uvicorn" -and $_.CommandLine -match "(?i)osap-(api|storage|support|auth)"
    }
    foreach ($proc in $stray) { [void]$targets.Add([int]$proc.ProcessId) }

    if ($targets.Count -eq 0) { Write-Host "  (no había procesos OSAP)" -ForegroundColor DarkGray; return }
    foreach ($procId in $targets) {
        if ($procId -eq $PID) { continue }
        $output = taskkill /PID $procId /T /F 2>&1
        if ($LASTEXITCODE -eq 0) { Write-Host "  matado PID $procId" -ForegroundColor DarkGray }
        else { Write-Host "  PID $procId no se pudo matar: $output" -ForegroundColor DarkYellow }
    }
}

function Wait-Health([string]$Url, [int]$Timeout) {
    $deadline = (Get-Date).AddSeconds($Timeout)
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest -Uri $Url -TimeoutSec 5 -SkipHttpErrorCheck -UseBasicParsing
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) { return [int]$response.StatusCode }
        } catch { }
        Start-Sleep -Seconds 2
    }
    return $null
}

Write-Host "=== OSAP dev restart ===" -ForegroundColor Cyan

$busyNames = @()
if (-not $SkipKill) {
    Write-Host "[1/3] Matando servicios OSAP..." -ForegroundColor Cyan
    Stop-OsapProcesses
    foreach ($service in $services) {
        for ($i = 0; $i -lt 30; $i++) {
            if ((Get-PortPids $service.Port).Count -eq 0) { break }
            Start-Sleep -Milliseconds 500
        }
    }
    $busy = @($services | Where-Object { (Get-PortPids $_.Port).Count -gt 0 })
    if ($busy.Count -gt 0) {
        $busyNames = @($busy | ForEach-Object { $_.Name })
        Write-Host "  Puertos aún ocupados (se omiten): $($busyNames -join ', ')" -ForegroundColor Yellow
        Write-Host "  Ejecuta como administrador para poder matarlos." -ForegroundColor Yellow
    }
} else {
    Write-Host "[1/3] Kill omitido (-SkipKill)" -ForegroundColor DarkGray
}

$logDir = Join-Path $env:LOCALAPPDATA "osap-dev\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

Write-Host "[2/3] Arrancando servicios..." -ForegroundColor Cyan
$started = @()
foreach ($service in $services) {
    if ($busyNames -contains $service.Name) {
        Write-Host "  $($service.Name) omitido (puerto $($service.Port) ocupado)" -ForegroundColor DarkYellow
        continue
    }
    $repoPath = Join-Path $Root $service.Repo
    $python = Resolve-Python $repoPath
    $arguments = @("-m", "uvicorn")
    if ($service.Factory) { $arguments += @("--factory", $service.App) } else { $arguments += @($service.App) }
    $arguments += @("--host", "127.0.0.1", "--port", "$($service.Port)")

    foreach ($key in $service.Env.Keys) { Set-Item -Path "Env:$key" -Value $service.Env[$key] }
    try {
        Start-Process -FilePath $python -ArgumentList $arguments -WorkingDirectory $repoPath -WindowStyle Hidden `
            -RedirectStandardOutput (Join-Path $logDir "$($service.Name).out.log") `
            -RedirectStandardError (Join-Path $logDir "$($service.Name).err.log")
        $started += $service
        Write-Host "  $($service.Name) -> puerto $($service.Port) ($([IO.Path]::GetFileName($python)))" -ForegroundColor DarkGray
    } finally {
        foreach ($key in $service.Env.Keys) { Remove-Item -Path "Env:$key" -ErrorAction SilentlyContinue }
    }
}

Write-Host "[3/3] Esperando healthchecks..." -ForegroundColor Cyan
$failed = @($busyNames)
if ($NoWait) {
    Write-Host "  (-NoWait: no se espera; comprueba los logs)" -ForegroundColor DarkGray
    $startedNames = @($started | ForEach-Object { $_.Name })
    Write-Host ""
    Write-Host "Arrancados en segundo plano: $($startedNames -join ', ')" -ForegroundColor Cyan
    Write-Host "Web dev:  http://osap-app" -ForegroundColor Cyan
    Write-Host "Logs:     $logDir" -ForegroundColor Cyan
    exit 0
}
foreach ($service in $started) {
    $code = Wait-Health $service.Health $TimeoutSeconds
    if ($code) { Write-Host "  OK  $($service.Name) ($code)  $($service.Health)" -ForegroundColor Green }
    else { Write-Host "  FALLO $($service.Name)  $($service.Health)  (ver $logDir\$($service.Name).err.log)" -ForegroundColor Red; $failed += $service.Name }
}

$appCode = Wait-Health "http://osap-app/api/v1/system/health" 20
if ($appCode) { Write-Host "  OK  osap-app (proxy Apache -> osap-api)" -ForegroundColor Green }
else { Write-Host "  AVISO osap-app no responde (¿Apache/XAMPP arrancado?)" -ForegroundColor Yellow }

Write-Host ""
Write-Host "Web dev:  http://osap-app" -ForegroundColor Cyan
Write-Host "Logs:     $logDir" -ForegroundColor Cyan
if ($failed.Count -gt 0) {
    Write-Host "Servicios con fallo: $($failed -join ', ')" -ForegroundColor Red
    Write-Host "Pulsa una tecla para cerrar..." -ForegroundColor Yellow
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    exit 1
}
Write-Host "Entorno listo." -ForegroundColor Green
