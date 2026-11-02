# Smoke SEO de producción: comprueba que las fichas públicas no son solo SPA.
#
# Uso:
#   pwsh -File script/smoke-seo.ps1
#   pwsh -File script/smoke-seo.ps1 -BaseUrl https://app.openmusicrepository.com
#
# Es de solo lectura y usa el User-Agent de Googlebot. Falla si una ruta pública
# devuelve un shell sin título/canonical o el estado vacío de la SPA.

param(
    [string]$BaseUrl = "https://app.openmusicrepository.com"
)

$ErrorActionPreference = "Stop"
$base = $BaseUrl.TrimEnd("/")
$ua = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
$checks = @(
    @{ Name = "obra"; Path = "/obras/index-1/i-shall-be-no-stranger-there-william-j-kirkpatrick" },
    @{ Name = "compositor"; Path = "/composers/2aaa06a5-6888-453d-861d-5da81d5722d4/a-a-westbrook" },
    @{ Name = "representacion"; Path = "/representacion/idx-1-omr-1-musicxml" },
    @{ Name = "generos"; Path = "/genres" },
    @{ Name = "catalogos"; Path = "/catalogues" },
    @{ Name = "instrumentos"; Path = "/instruments" }
)
$failures = [System.Collections.Generic.List[string]]::new()

foreach ($check in $checks) {
    $url = "$base$($check.Path)"
    try {
        $response = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 30 `
            -Headers @{ "User-Agent" = $ua }
        $html = [string]$response.Content
        $problems = [System.Collections.Generic.List[string]]::new()
        if ($response.StatusCode -ne 200) { $problems.Add("HTTP $($response.StatusCode)") }
        if ($html.Length -lt 8000) { $problems.Add("HTML demasiado corto ($($html.Length))") }
        if ($html -notmatch "<title>[^<]+</title>") { $problems.Add("sin <title>") }
        if ($html -notmatch 'rel="canonical"') { $problems.Add("sin canonical") }
        if ($html -match "Cargando|Nada por aquí") { $problems.Add("estado vacío de SPA") }
        if ($problems.Count -gt 0) {
            $failures.Add("$($check.Name): $($problems -join ', ')")
            Write-Host "FAIL $($check.Name) $url"
        } else {
            Write-Host "OK   $($check.Name) $($html.Length) bytes"
        }
    } catch {
        $failures.Add("$($check.Name): $($_.Exception.Message)")
        Write-Host "FAIL $($check.Name) $url"
    }
}

try {
    $sitemap = Invoke-WebRequest -Uri "$base/sitemap.xml" -UseBasicParsing -TimeoutSec 30
    if ($sitemap.StatusCode -ne 200 -or $sitemap.Content -notmatch "<sitemapindex") {
        $failures.Add("sitemap: respuesta no válida")
    } else {
        Write-Host "OK   sitemap"
    }
} catch {
    $failures.Add("sitemap: $($_.Exception.Message)")
}

try {
    $catalog = Invoke-WebRequest -Uri "$base/catalog" -UseBasicParsing -TimeoutSec 30
    if ($catalog.StatusCode -ne 200) { $failures.Add("catalog: HTTP $($catalog.StatusCode)") }
    else { Write-Host "OK   catalog" }
} catch {
    $failures.Add("catalog: $($_.Exception.Message)")
}

try {
    $sources = Invoke-WebRequest -Uri "$base/api/v1/repository-sources" -UseBasicParsing -TimeoutSec 30
    $sourceCount = @(($sources.Content | ConvertFrom-Json).data).Count
    if ($sources.StatusCode -ne 200 -or $sourceCount -eq 0) {
        $failures.Add("repository-sources: HTTP $($sources.StatusCode), $sourceCount fuentes")
    } else {
        Write-Host "OK   repository-sources ($sourceCount)"
    }
} catch {
    $failures.Add("repository-sources: $($_.Exception.Message)")
}

try {
    Invoke-WebRequest -Uri "$base/obras/1" -UseBasicParsing -MaximumRedirection 0 -TimeoutSec 30 | Out-Null
    $failures.Add("redirect numerico: no devolvio 301")
} catch {
    $response = $_.Exception.Response
    if ([int]$response.StatusCode -ne 301 -or "$($response.Headers.Location)" -notmatch "/obras/index-1$") {
        $failures.Add("redirect numerico: no apunta a /obras/index-1")
    } else {
        Write-Host "OK   redirect numerico"
    }
}

if ($failures.Count -gt 0) {
    Write-Error ("Smoke SEO fallido:`n  " + ($failures -join "`n  "))
    exit 1
}

Write-Host "Smoke SEO correcto: las fichas públicas entregan HTML SSR."
