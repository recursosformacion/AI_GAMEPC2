# check-versions.ps1 — Verifica la versión A.B.C coordinada del conjunto OSAP.
#
# Resumen: lee `version` de los cuatro `pyproject.toml` (osap-api/auth/storage/support) y de
# `osap-api/web/package.json`, y falla si no coinciden (regla "un número para todo el
# conjunto", docs/osap/versioning.md). Read-only: no escribe nada.
#
# Uso:
#   pwsh script/check-versions.ps1                  # comprueba que todos coinciden
#   pwsh script/check-versions.ps1 -Expected 4.3.0  # además exige ese número

param(
    [string]$IosapRoot = "D:\Proyectos\AI_OSAP",
    [string]$Expected = ""
)

$ErrorActionPreference = "Stop"

function Get-PyprojectVersion([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return $null }
    $match = Select-String -Path $Path -Pattern '^\s*version\s*=\s*"([^"]+)"' | Select-Object -First 1
    if (-not $match) { return $null }
    return $match.Matches[0].Groups[1].Value
}

function Get-PackageJsonVersion([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return $null }
    $json = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
    return $json.version
}

$targets = [ordered]@{
    "osap-api/pyproject.toml"     = Get-PyprojectVersion   (Join-Path $IosapRoot "osap-api\pyproject.toml")
    "osap-api/web/package.json"   = Get-PackageJsonVersion (Join-Path $IosapRoot "osap-api\web\package.json")
    "osap-storage/pyproject.toml" = Get-PyprojectVersion   (Join-Path $IosapRoot "osap-storage\pyproject.toml")
    "osap-auth/pyproject.toml"    = Get-PyprojectVersion   (Join-Path $IosapRoot "osap-auth\pyproject.toml")
    "osap-support/pyproject.toml" = Get-PyprojectVersion   (Join-Path $IosapRoot "osap-support\pyproject.toml")
}

$versions = @()
foreach ($key in $targets.Keys) {
    $value = $targets[$key]
    "{0,-30} {1}" -f $key, ($(if ($value) { $value } else { "(no encontrado)" }))
    if ($value) { $versions += $value }
}

$unique = @($versions | Sort-Object -Unique)
if ($unique.Count -ne 1) {
    Write-Host "MISMATCH: hay $($unique.Count) versiones distintas ($($unique -join ', '))." -ForegroundColor Red
    exit 1
}

$version = $unique[0]
if ($Expected -and $version -ne $Expected) {
    Write-Host "MISMATCH: esperado $Expected, encontrado $version." -ForegroundColor Red
    exit 1
}

Write-Host "OK: version $version en todos los programas." -ForegroundColor Green
exit 0
