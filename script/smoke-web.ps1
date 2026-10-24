# Resumen: smoke test de ficha legado, acciones OMR y SEO de idioma (canónica + hreflang).
# Falla con código distinto de 0 si falta algo.
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

$composer = Invoke-WebRequest -UseBasicParsing "$BaseUrl/composers/d9dd217c-2491-451e-93e8-e9cba76f0182?lang=en"
if ($composer.StatusCode -ne 200) { throw "Compositor: HTTP $($composer.StatusCode)" }
if ($composer.Content -notmatch 'rel="canonical" href="[^"]+\?lang=en"') {
    throw "Compositor: la canónica de la variante ?lang=en no es autorreferente"
}
if ([regex]::Matches($composer.Content, 'rel="alternate" hreflang=').Count -lt 6) {
    throw "Compositor: faltan alternates hreflang"
}

Write-Host "Smoke web OK: ficha legado, representación OMR y SEO de idioma."
