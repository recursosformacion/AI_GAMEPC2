# Descargar el dump completo de MusicBrainz (mbdump.tar.bz2) al directorio Carga.
#
# Fuente oficial: https://data.metabrainz.org/pub/musicbrainz/data/fullexport/<LATEST>/mbdump.tar.bz2
# (~7.5 GB). La descarga es reanudable (curl -C -) por si se corta.
#
# Uso:  powershell -ExecutionPolicy Bypass -File script/download_mbdump.ps1
#       powershell -ExecutionPolicy Bypass -File script/download_mbdump.ps1 -Dest K:\DiscoD\Proyectos\AI_OSAP\osap-compositores\Carga

param(
    [string]$Dest = "K:\DiscoD\Proyectos\AI_OSAP\osap-compositores\Carga",
    [string]$DateStamp = ""  # p. ej. 20260822-002831; vacio = ultimo LATEST
)

$ErrorActionPreference = "Stop"
$out = Join-Path $Dest "mbdump.tar.bz2"

if ($DateStamp -eq "") {
    $DateStamp = (Invoke-RestMethod -Uri "https://data.metabrainz.org/pub/musicbrainz/data/fullexport/LATEST" -Method Get -TimeoutSec 30).Trim()
    Write-Host "Ultimo dump disponible: $DateStamp"
}
$url = "https://data.metabrainz.org/pub/musicbrainz/data/fullexport/$DateStamp/mbdump.tar.bz2"

Write-Host "== Descargando mbdump.tar.bz2 ($DateStamp) ==" -ForegroundColor Cyan
Write-Host "   $url"
Write-Host "   -> $out"

if (Test-Path -LiteralPath $out) {
    Write-Host "   Existe parcialmente; reanudando..." -ForegroundColor Yellow
    & curl.exe -L -C - -o $out $url
} else {
    & curl.exe -L -o $out $url
}
if ($LASTEXITCODE -ne 0) { Write-Error "Descarga falló (curl exit $LASTEXITCODE)"; exit 1 }

$size = (Get-Item -LiteralPath $out).Length
Write-Host "Descarga completada: $([math]::Round($size/1GB,2)) GB" -ForegroundColor Green
