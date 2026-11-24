# test_repair_index_split_pieltain.ps1 — Prueba en DEV la reparación del split No.1/No.3.
# Crea una BD de test con la obra No.3 viva copiada de osap_api, ejecuta
# script/repair_index_split_pieltain.py y valida que:
#   - La No.3 conserva id/public_id/catálogo/título/title_key y solo su rep 533295.
#   - Se crea la No.1 (catálogo IDP 2) con rep 533293 y title_key desambiguada.
#   - Aliases/legacy map y osap_storage no cambian.
# Uso: pwsh script/test_repair_index_split_pieltain.ps1

$ErrorActionPreference = "Stop"
$mysql = "C:\xampp\mysql\bin\mysql.exe"
$python = Join-Path $PSScriptRoot "..\.venv\Scripts\python.exe"
$live = "osap_api"
$storage = "osap_storage"
$test = "osap_api_repair_test"
$backup = Join-Path $env:TEMP "kilo\repair-test-backup"
$env:MYSQL_PWD = "2027osapdb"
$mysqlArgs = @("-h", "127.0.0.1", "-P", "3306", "-u", "osap2027", "-N", "-B")
$fail = 0
function Q([string]$sql) { & $mysql @mysqlArgs -e $sql }
function Check([bool]$ok, [string]$msg) {
    if ($ok) { "PASS  $msg" } else { "FAIL  $msg"; $script:fail = 1 }
}
try {
    Q "DROP DATABASE IF EXISTS $test; CREATE DATABASE $test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
    $tables = @("index_works", "index_representations", "index_work_voicings", "index_id_aliases")
    if ((Q "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='$live' AND table_name='legacy_index_map';").Trim() -eq "1") {
        $tables += "legacy_index_map"
    }
    foreach ($table in $tables) {
        Q "CREATE TABLE $test.$table LIKE $live.$table;"
    }
    $no3 = (Q "SELECT id FROM $live.index_works WHERE title LIKE 'Violin Concerto No.3 in B-flat major%' AND catalogue='IDP 3' LIMIT 1;" | Select-Object -First 1).Trim()
    if (-not $no3) { throw "No encuentro la obra No.3 (IDP 3) en $live" }
    Q "INSERT INTO $test.index_works SELECT * FROM $live.index_works WHERE id=$no3;"
    Q "INSERT INTO $test.index_representations SELECT * FROM $live.index_representations WHERE work_id=$no3;"
    Q "INSERT INTO $test.index_work_voicings SELECT * FROM $live.index_work_voicings WHERE work_id=$no3;"
    Q "INSERT INTO $test.index_id_aliases SELECT * FROM $live.index_id_aliases WHERE old_id=$no3 OR new_id=$no3;"
    if ($tables -contains "legacy_index_map") {
        Q "INSERT INTO $test.legacy_index_map SELECT * FROM $live.legacy_index_map WHERE old_id=$no3 OR new_id=$no3;"
    }

    $before = Q "SELECT public_id,catalogue,title,title_key,source_count FROM $test.index_works WHERE id=$no3;"
    $aliasesBefore = (Q "SELECT COUNT(*) FROM $test.index_id_aliases;").Trim()
    $legacyBefore = if ($tables -contains "legacy_index_map") { (Q "SELECT COUNT(*) FROM $test.legacy_index_map;").Trim() } else { "0" }
    $storageBefore = Q "SELECT COUNT(*) FROM $storage.works WHERE works_origin_id IN ('533293','533295');"

    $output = & $python (Join-Path $PSScriptRoot "repair_index_split_pieltain.py") `
        --api-db $test --storage-db $storage --db-user osap2027 --db-password 2027osapdb `
        --confirm-database $test --apply --backup-dir $backup 2>&1
    $output
    if ($LASTEXITCODE -ne 0) { throw "El script de reparación falló" }

    $after = Q "SELECT public_id,catalogue,title,title_key,source_count FROM $test.index_works WHERE id=$no3;"
    $no3no1 = (Q "SELECT COUNT(*) FROM $test.index_representations WHERE work_id=$no3 AND source_rep_id='533293';").Trim()
    $no3no3 = (Q "SELECT COUNT(*) FROM $test.index_representations WHERE work_id=$no3 AND source_rep_id='533295';").Trim()
    $new = Q "SELECT id,public_id,title,title_key,catalogue,source_count FROM $test.index_works WHERE catalogue='IDP 2' AND title LIKE 'Violin Concerto No.1 in F major%';"
    $newParts = @($new | Select-Object -First 1) -split "`t"
    $newId = $newParts[0]
    $newRep = if ($newId) { (Q "SELECT COUNT(*) FROM $test.index_representations WHERE work_id=$newId AND source_rep_id='533293';").Trim() } else { "" }
    $aliasesAfter = (Q "SELECT COUNT(*) FROM $test.index_id_aliases;").Trim()
    $legacyAfter = if ($tables -contains "legacy_index_map") { (Q "SELECT COUNT(*) FROM $test.legacy_index_map;").Trim() } else { "0" }
    $storageAfter = Q "SELECT COUNT(*) FROM $storage.works WHERE works_origin_id IN ('533293','533295');"

    $b = @($before | Select-Object -First 1) -split "`t"
    $a = @($after | Select-Object -First 1) -split "`t"
    Check ($b[0] -eq $a[0]) "No.3 public_id intacto ($($a[0]))"
    Check ($b[1] -eq $a[1]) "No.3 catálogo intacto ($($a[1]))"
    Check ($b[2] -eq $a[2]) "No.3 título intacto"
    Check ($b[3] -eq $a[3]) "No.3 title_key intacto ($($a[3]))"
    Check ($a[4] -eq "1") "No.3 source_count=1"
    Check ($no3no1 -eq "0") "No.1 rep ya no cuelga de No.3"
    Check ($no3no3 -eq "1") "No.3 conserva su rep 533295"
    Check ($newParts.Count -ge 6) "Existe obra No.1 (IDP 2)"
    Check ($newParts[1] -eq "index-562742") "No.1 public_id nuevo/estable ($($newParts[1]))"
    Check ($newParts[3] -eq "violin concerto 1") "No.1 title_key desambiguada ($($newParts[3]))"
    Check ($newParts[4] -eq "IDP 2") "No.1 catálogo IDP 2"
    Check ($newParts[5] -eq "1") "No.1 source_count=1"
    Check ($newRep -eq "1") "No.1 rep 533293 en su obra"
    Check ($aliasesBefore -eq $aliasesAfter) "index_id_aliases intactos"
    Check ($legacyBefore -eq $legacyAfter) "legacy_index_map intacto"
    Check (($storageBefore -join "|") -eq ($storageAfter -join "|")) "osap_storage intacto"
}
finally {
    & $mysql @mysqlArgs -e "DROP DATABASE IF EXISTS $test;" 2>$null
    Remove-Item -LiteralPath $backup -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item Env:MYSQL_PWD -ErrorAction SilentlyContinue
}
"RESULT: " + $(if ($fail -eq 0) { "OK" } else { "FAIL" })
exit $fail
