# deploy_all.ps1 — Sube TODOS los programas a producción (SPA + 4 backends).
#
# Resumen: construye la SPA, empaqueta el CÓDIGO de osap-api, osap-auth, osap-storage y
# osap-support (sin configs ni .venv), lo sube a `RemoteIA` y lo extrae sobre
# /home/ocw/openmusicrepository.com/<repo>; luego reinicia los 4 servicios systemd y
# comprueba salud. NO toca las BBDD (eso va aparte).
#
# Uso: powershell -ExecutionPolicy Bypass -File script/deploy_all.ps1

param(
    [string]$HostAlias = "RemoteIA",
    [string]$IosapRoot = "D:\Proyectos\AI_OSAP",
    [string]$RemoteRoot = "/home/ocw/openmusicrepository.com",
    [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"
$apiRoot = Split-Path -Parent $PSScriptRoot
$tmp = Join-Path $env:TEMP "osap-deploy-all"
New-Item -ItemType Directory -Force -Path $tmp | Out-Null
function Fail($m) { Write-Error $m; exit 1 }

$repos = @(
    @{ Name = "osap-api";     Include = @("src", "providers", "resources", "lexicon", "pyproject.toml"); Service = "osap-api.service" },
    @{ Name = "osap-auth";    Include = @("api", "application", "domain", "infrastructure", "scripts", "pyproject.toml", "alembic.ini"); Service = "osap-auth.service" },
    @{ Name = "osap-storage"; Include = @("api", "application", "domain", "infrastructure", "scripts", "pyproject.toml"); Service = "osap-storage.service" },
    @{ Name = "osap-support"; Include = @("api", "application", "domain", "infrastructure", "scripts", "pyproject.toml", "alembic.ini"); Service = "osap-support.service" }
)

if (-not $SkipBuild) {
    Write-Host "== [1/4] Construyendo SPA ==" -ForegroundColor Cyan
    Push-Location (Join-Path $apiRoot "web")
    & ".\node_modules\.bin\tsc.cmd" --noEmit; if ($LASTEXITCODE -ne 0) { Fail "tsc falló" }
    & node "node_modules/vite/bin/vite.js" build; if ($LASTEXITCODE -ne 0) { Fail "vite build falló" }
    Pop-Location
}

Write-Host "== [2/4] Empaquetando ==" -ForegroundColor Cyan
foreach ($r in $repos) {
    $repoDir = Join-Path $IosapRoot $r.Name
    $paths = $r.Include | ForEach-Object { Join-Path $r.Name $_ }
    tar -czf (Join-Path $tmp "$($r.Name).tar.gz") -C $IosapRoot --exclude=__pycache__ --exclude=*.pyc @paths
    if ($LASTEXITCODE -ne 0) { Fail "tar $($r.Name) falló" }
}
tar -czf (Join-Path $tmp "dist.tar.gz") -C (Join-Path $apiRoot "web\dist") .
if ($LASTEXITCODE -ne 0) { Fail "tar dist falló" }

Write-Host "== [3/4] Subiendo ==" -ForegroundColor Cyan
ssh -o BatchMode=yes $HostAlias "mkdir -p /home/ocw/deploy_tmp"
foreach ($r in $repos) { scp -o BatchMode=yes (Join-Path $tmp "$($r.Name).tar.gz") "$($HostAlias):/home/ocw/deploy_tmp/" }
scp -o BatchMode=yes (Join-Path $tmp "dist.tar.gz") "$($HostAlias):/home/ocw/deploy_tmp/"
scp -o BatchMode=yes (Join-Path $apiRoot "osap.production.toml") "$($HostAlias):/home/ocw/deploy_tmp/osap.production.toml"
if ($LASTEXITCODE -ne 0) { Fail "scp falló" }

Write-Host "== [4/4] Extrayendo y reiniciando ==" -ForegroundColor Cyan
$extract = (($repos | ForEach-Object { "tar -xzf /home/ocw/deploy_tmp/$($_.Name).tar.gz -C $RemoteRoot;" }) -join " ")
$restart = (($repos | ForEach-Object { "sudo systemctl restart $($_.Service);" }) -join " ")
$cmd = "set -e; $extract " +
    "cp -f /home/ocw/deploy_tmp/osap.production.toml $RemoteRoot/osap-api/osap.toml; " +
    "rm -rf $RemoteRoot/app/assets $RemoteRoot/app/index.html; " +
    "tar -xzf /home/ocw/deploy_tmp/dist.tar.gz -C $RemoteRoot/app; " +
    "$restart rm -rf /home/ocw/deploy_tmp; echo DEPLOY_DONE"
ssh -o BatchMode=yes $HostAlias $cmd

Write-Host "== Verificando salud ==" -ForegroundColor Cyan
Start-Sleep -Seconds 8
foreach ($u in "https://app.openmusicrepository.com/api/v1/system/health",
               "https://openmusicrepository.com/api/v1/health",
               "https://auth.openmusicrepository.com/health",
               "https://app.openmusicrepository.com/support-api/health") {
    try { $r = Invoke-WebRequest -Uri $u -TimeoutSec 20 -SkipHttpErrorCheck -UseBasicParsing; Write-Host "  $u -> $($r.StatusCode)" }
    catch { Write-Host "  $u -> DOWN" -ForegroundColor Red }
}
Write-Host "Deploy de programas completado." -ForegroundColor Green
