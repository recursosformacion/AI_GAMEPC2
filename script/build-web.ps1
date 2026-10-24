# Resumen: compila el bundle SSR y la SPA de `web/` en el orden correcto.
# Uso: pwsh script/build-web.ps1 [-RestartSSR]
param(
    [switch]$RestartSSR
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$web = Join-Path $root "web"
$node = "node"

Push-Location $web
try {
    Remove-Item -LiteralPath "dist-ssr" -Recurse -Force -ErrorAction SilentlyContinue
    & $node "node_modules/vite/bin/vite.js" build --config "vite.ssr.config.ts"
    if ($LASTEXITCODE -ne 0) { throw "vite build SSR falló" }
    & $node "node_modules/vite/bin/vite.js" build
    if ($LASTEXITCODE -ne 0) { throw "vite build SPA falló" }
} finally {
    Pop-Location
}

if (-not $RestartSSR) {
    Write-Host "Build SSR + SPA completado."
    exit 0
}

$listener = Get-NetTCPConnection -LocalPort 3000 -State Listen -ErrorAction SilentlyContinue |
    Select-Object -First 1
if ($listener) {
    try {
        Stop-Process -Id $listener.OwningProcess -Force -ErrorAction Stop
    } catch {
        throw "No se pudo detener el SSR en :3000. Reinícialo manualmente o ejecuta este script con permisos suficientes."
    }
}

$env:OSAP_SSR_DEV = "1"
$env:OSAP_API_ORIGIN = "http://127.0.0.1:8001"
$env:OSAP_PUBLIC_ORIGIN = "http://osap-app"
Start-Process -FilePath "node" -ArgumentList "ssr/server.mjs" -WorkingDirectory $web -WindowStyle Hidden
$ready = $false
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Milliseconds 500
    try {
        $health = Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:3000/health" -TimeoutSec 2
        if ($health.StatusCode -eq 200) { $ready = $true; break }
    } catch {
        # El proceso aún está arrancando.
    }
}
if (-not $ready) { throw "El SSR no respondió en :3000 tras el reinicio" }
Write-Host "SSR reiniciado en http://127.0.0.1:3000"
