# Deploy de osap-blog (dev -> producción RemoteIA).
# Resumen: empaqueta el repo local (sin .venv/datos/config privada), lo sube, instala deps en el
# venv del servidor, reinicia osap-blog y verifica /health + que /auth/session sea POST-only
# con validación de Origin. Requiere OSAP_BLOG_SESSION_SECRET en /etc/openmusicrepository/osap-blog.env.
# Uso: powershell -NoProfile -ExecutionPolicy Bypass -File script\deploy_blog.ps1 [-WhatIf]
param([string]$HostAlias = "RemoteIA", [string]$RemoteDir = "/home/ocw/openmusicrepository.com/osap-blog", [switch]$Apply)
$ErrorActionPreference = "Stop"
$src = "D:\Proyectos\AI_OSAP\osap-blog"
if (-not $Apply) { Write-Host "Dry-run: añade -Apply para desplegar."; exit 0 }
Write-Host "== Empaquetando osap-blog" -ForegroundColor Cyan
Push-Location $src
tar -czf "$env:TEMP\osap-blog.tar.gz" --exclude=.venv --exclude=__pycache__ --exclude=.git --exclude=.pytest_cache --exclude=.ruff_cache --exclude=.aider --exclude=data --exclude=config.yaml --exclude=*.db app.py share_icons.py schema.sql requirements.txt pyproject.toml templates static deploy
Pop-Location
if ($LASTEXITCODE -ne 0) { throw "tar falló" }
Write-Host "== Subiendo y desplegando" -ForegroundColor Cyan
ssh -o BatchMode=yes $HostAlias "mkdir -p ~/deploy_tmp"
scp -o BatchMode=yes "$env:TEMP\osap-blog.tar.gz" "$($HostAlias):~/deploy_tmp/"
if ($LASTEXITCODE -ne 0) { throw "scp falló" }
$remote = @'
set -e
cd __REMOTE__
mkdir -p /tmp/osap_blog_bak_20261125 && cp -a app.py templates static /tmp/osap_blog_bak_20261125/
tar -xzf ~/deploy_tmp/osap-blog.tar.gz
.venv/bin/pip install -q -r requirements.txt
sudo systemctl restart osap-blog
sleep 5
curl -s -o /dev/null -w 'health -> %{http_code}\n' http://127.0.0.1:8500/health
echo 'GET /auth/session?token=x (debe ser 405):'
curl -s -o /dev/null -w '  -> %{http_code}\n' 'http://127.0.0.1:8500/auth/session?token=x'
echo 'POST /auth/session con Origin de OSAP y token falso (debe ser 303 a /?session=error):'
curl -s -o /dev/null -D - -X POST http://127.0.0.1:8500/auth/session -H 'Origin: https://app.openmusicrepository.com' -H 'Content-Type: application/x-www-form-urlencoded' --data 'access_token=fake&next=/admin' | grep -E '^HTTP|^location'
echo 'POST /auth/session con Origin ajeno (debe ser 403):'
curl -s -o /tmp/_b -w '  -> %{http_code} ' -X POST http://127.0.0.1:8500/auth/session -H 'Origin: https://attacker.example' -H 'Content-Type: application/x-www-form-urlencoded' --data 'access_token=fake'; head -c 120 /tmp/_b; echo
rm -rf ~/deploy_tmp
'@
$remote = $remote.Replace("__REMOTE__", $RemoteDir)
$tmpFile = Join-Path $env:TEMP "blog_deploy.sh"
[IO.File]::WriteAllText($tmpFile, $remote.Replace("`r`n","`n"))
Get-Content $tmpFile -Raw | ssh -o BatchMode=yes $HostAlias "bash -s"
