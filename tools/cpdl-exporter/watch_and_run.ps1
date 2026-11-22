$ErrorActionPreference = "Stop"
$target = Join-Path $env:USERPROFILE "Downloads\cpdl-parts.json"
$bat = Join-Path $PSScriptRoot "cpdl_pipeline.bat"
Write-Host "Vigilando $target ..."
while ($true) {
  if (Test-Path -LiteralPath $target) {
    Start-Sleep -Seconds 3
    Write-Host "Detectado $target -> lanzando pipeline"
    & $bat $target
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    Rename-Item -LiteralPath $target -NewName ("cpdl-parts.json.uploaded-" + $stamp)
  }
  Start-Sleep -Seconds 20
}
