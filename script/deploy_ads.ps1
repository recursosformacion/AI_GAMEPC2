# Deploy de ai_publicidad (dev -> producción RemoteIA).
# Resumen: empaqueta el repo local (sin .venv/datos/config privada), lo sube, instala deps en el
# venv del servidor, reinicia ai-publicidad y verifica /health + que /auth/session sea POST-only.
# Uso: powershell -NoProfile -ExecutionPolicy Bypass -File script\deploy_ads.ps1
param([string]$HostAlias = "RemoteIA", [string]$RemoteDir = "/home/ocw/openmusicrepository.com/ai_publicidad")
$ErrorActionPreference = "Stop"
$src = "D:\Proyectos\AI_OSAP\ai_publicidad"
$remote = @"
set -e
cd $RemoteDir
cp -a api application domain infrastructure osap.toml /tmp/ai_pub_bak_20261125_ 2>/dev/null || true
tar -xzf ~/deploy_tmp/ai_publicidad.tar.gz
.venv/bin/pip install -q -e .
sudo systemctl restart ai-publicidad
sleep 5
curl -s -o /dev/null -w 'health -> %{http_code}\n' http://127.0.0.1:8305/health
echo 'POST /auth/session (Origin correcto, token falso):'
curl -s -o /tmp/_b -w '  -> %{http_code} ' -X POST http://127.0.0.1:8305/auth/session -H 'Origin: https://app.openmusicrepository.com' -H 'Content-Type: application/x-www-form-urlencoded' --data 'token=fake&next=/admin'; head -c 150 /tmp/_b; echo
echo 'GET /auth/session (debe ser 405):'
curl -s -o /dev/null -w '  -> %{http_code}\n' http://127.0.0.1:8305/auth/session
rm -rf ~/deploy_tmp
"@
Write-Host "== Empaquetando ai_publicidad" -ForegroundColor Cyan
Push-Location $src
tar -czf "$env:TEMP\ai_publicidad.tar.gz" --exclude=.venv --exclude=__pycache__ --exclude=.git --exclude=.pytest_cache --exclude=.ruff_cache --exclude=.mypy_cache --exclude=data --exclude=*.sqlite3 --exclude=.env api application domain infrastructure scripts pyproject.toml docs README.md LICENSE alembic.ini
Pop-Location
if ($LASTEXITCODE -ne 0) { throw "tar falló" }
Write-Host "== Subiendo y desplegando" -ForegroundColor Cyan
ssh -o BatchMode=yes $HostAlias "mkdir -p ~/deploy_tmp"
scp -o BatchMode=yes "$env:TEMP\ai_publicidad.tar.gz" "$($HostAlias):~/deploy_tmp/"
if ($LASTEXITCODE -ne 0) { throw "scp falló" }
$remote | Out-File -Encoding ascii -NoNewline (Join-Path $env:TEMP "ads_deploy.sh")
Get-Content (Join-Path $env:TEMP "ads_deploy.sh") -Raw | ssh -o BatchMode=yes $HostAlias "bash -s"
