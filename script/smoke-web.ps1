# Resumen: smoke test de la ficha de obra por id legado y de las acciones de una
# representación OMR. Falla con código distinto de 0 si no aparecen Ver/Descargar.
# Uso: pwsh script/smoke-web.ps1 [-BaseUrl http://osap-app]
param(
    [string]$BaseUrl = "http://osap-app"
)

$ErrorActionPreference = "Stop"
$BaseUrl = $BaseUrl.TrimEnd("/")

$work = Invoke-WebRequest -UseBasicParsing "$BaseUrl/obras/121355"
if ($work.StatusCode -ne 200) { throw "Ficha /obras/121355: HTTP $($work.StatusCode)" }
if ($work.Content -notmatch "Humoresque") { throw "Ficha /obras/121355: no se renderizó la obra" }
if ($work.Content -notmatch 'aria-label="Ver"') { throw "Ficha /obras/121355: falta Ver" }
if ($work.Content -notmatch 'aria-label="Descargar"') { throw "Ficha /obras/121355: falta Descargar" }

$rep = Invoke-WebRequest -UseBasicParsing "$BaseUrl/representacion/idx-456780-omr-121355-musicxml"
if ($rep.StatusCode -ne 200) { throw "Representación OMR: HTTP $($rep.StatusCode)" }
if ($rep.Content -notmatch "Descargar") { throw "Representación OMR: falta Descargar" }
if ($rep.Content -notmatch "Abrir en el visor") { throw "Representación OMR: falta el visor" }
if ($rep.Content -match "Abrir en omr") { throw "Representación OMR: sigue ofreciendo solo abrir OMR" }

Write-Host "Smoke web OK: ficha legado y representación OMR."
