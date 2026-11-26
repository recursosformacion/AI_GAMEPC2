# Sonda temporal (solo lectura): último commit de cada repo local y estado de "deploy sucio".
$root = "D:\Proyectos\AI_OSAP"
foreach ($d in @("ai_publicidad", "osap-storage", "osap-support", "osap-auth", "osap-blog", "Chorus", "osap-api")) {
  $p = Join-Path $root $d
  if (-not (Test-Path (Join-Path $p ".git"))) { Write-Output "== $d (sin .git)"; continue }
  $log = git -C $p log -1 --format="%h %ad %s" --date=short
  $dirty = (git -C $p status --short | Measure-Object -Line).Lines
  $ver = (Select-String -Path (Join-Path $p "pyproject.toml") -Pattern '^version' | Select-Object -First 1).Line
  Write-Output ("== {0}`n   {1}`n   {2}`n   cambios sin commit: {3}" -f $d, $log, $ver, $dirty)
}
