# run-news-digest.ps1 — Lanza una pasada del boletín de noticias en dev.
#
# Resumen: ejecuta `src.osap.news_digest` con los endpoints y tokens locales. Por
# defecto es dry-run (genera .eml en var/news-digest); con -Send encola en osap-support.
#
# Uso:
#   pwsh script/run-news-digest.ps1                 # dry-run de todos los suscriptores
#   pwsh script/run-news-digest.ps1 -UserId <uuid>  # solo un usuario de prueba
#   pwsh script/run-news-digest.ps1 -Send           # encola (el worker hace el envío)
#
[CmdletBinding()]
param(
    [string]$UserId,
    [int]$Limit = 8,
    [int]$Days = 30,
    [switch]$Send
)

$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$tokenDir = Join-Path $env:LOCALAPPDATA "osap-dev"
$env:OSAP_INTERNAL_SERVICE_TOKEN = if (Test-Path (Join-Path $tokenDir "internal-token.txt")) { (Get-Content (Join-Path $tokenDir "internal-token.txt") -Raw).Trim() } else { "osap-dev-internal-token" }
$env:OSAP_AUTH_INTERNAL_URL = "http://127.0.0.1:8200"
$env:OSAP_NEWS_API_BASE = "http://127.0.0.1:8401"
$env:OSAP_NEWS_API_TOKEN = if (Test-Path (Join-Path $tokenDir "news-token.txt")) { (Get-Content (Join-Path $tokenDir "news-token.txt") -Raw).Trim() } else { "osap-dev-news-token" }
$env:OSAP_SUPPORT_INTERNAL_URL = "http://127.0.0.1:8300"

$arguments = @("-m", "src.osap.news_digest", "--limit", "$Limit", "--days", "$Days")
if ($UserId) { $arguments += @("--user-id", $UserId) }
if ($Send) { $arguments += "--send" }

Push-Location $Root
try {
    & python @arguments
    exit $LASTEXITCODE
} finally {
    Pop-Location
}


