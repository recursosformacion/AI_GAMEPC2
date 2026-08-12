# Deploy de OSAP a producción (app.openmusicrepository.com)
#
#   - Construye el frontend (web/dist) localmente.
#   - Empaqueta el backend (src/, providers/, resources/, run.py, pyproject.toml).
#   - Sube los tarballs al servidor y los extrae sobre ~/osap-api (backend) y
#     ~/openmusicrepository.com/app (SPA).
#   - Reinicia el servicio systemd osap-api.
#
# Requiere: ssh/scp/tar y acceso SSH sin contraseña (host `RemoteIA`).
# Uso:   powershell -ExecutionPolicy Bypass -File script/deploy.ps1

param(
    [string]$HostAlias = "RemoteIA",
    [string]$BackendDir = "~/osap-api",
    [string]$SpaDir = "~/openmusicrepository.com/app"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$tmp = Join-Path $env:TEMP "osap-deploy"
New-Item -ItemType Directory -Force -Path $tmp | Out-Null

function Fail($msg) { Write-Error $msg; exit 1 }

Write-Host "== [1/5] Construyendo frontend ==" -ForegroundColor Cyan
Push-Location (Join-Path $root "web")
& ".\node_modules\.bin\tsc.cmd" --noEmit
if ($LASTEXITCODE -ne 0) { Fail "tsc --noEmit falló" }
& node "node_modules/vite/bin/vite.js" build
if ($LASTEXITCODE -ne 0) { Fail "vite build falló" }
Pop-Location

Write-Host "== [2/5] Empaquetando backend y SPA ==" -ForegroundColor Cyan
Push-Location $root
tar -czf (Join-Path $tmp "backend.tar.gz") `
    --exclude="__pycache__" --exclude="*.pyc" `
    src providers resources pyproject.toml
if ($LASTEXITCODE -ne 0) { Fail "tar backend falló" }
tar -czf (Join-Path $tmp "dist.tar.gz") -C (Join-Path $root "web\dist") .
if ($LASTEXITCODE -ne 0) { Fail "tar dist falló" }
Pop-Location

Write-Host "== [3/5] Subiendo al servidor ==" -ForegroundColor Cyan
ssh -o BatchMode=yes $HostAlias "mkdir -p ~/deploy_tmp"
scp -o BatchMode=yes (Join-Path $tmp "backend.tar.gz") (Join-Path $tmp "dist.tar.gz") "$($HostAlias):~/deploy_tmp/"
if ($LASTEXITCODE -ne 0) { Fail "scp falló" }

Write-Host "== [4/5] Extrayendo en el servidor y reiniciando ==" -ForegroundColor Cyan
$remoteCmd = "set -e; cd $BackendDir && tar -xzf ~/deploy_tmp/backend.tar.gz && " +
    ".venv/bin/pip install --quiet PyMySQL && " +
    "cd $SpaDir && rm -rf assets index.html && tar -xzf ~/deploy_tmp/dist.tar.gz && " +
    "rm -rf ~/deploy_tmp && sudo systemctl restart osap-api.service && echo RESTART_DONE"
$out = ssh -o BatchMode=yes $HostAlias $remoteCmd
$out

Write-Host "== [5/5] Verificando salud ==" -ForegroundColor Cyan
Start-Sleep -Seconds 3
$r = Invoke-RestMethod -Uri "https://app.openmusicrepository.com/api/v1/system/health" -Method Get -TimeoutSec 30
Write-Host "health: $($r.data.status)"
Write-Host "Deploy completado."
