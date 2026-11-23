# Smoke test de autenticacion M2M tras un despliegue (Auth D).
# Obtiene un service token por scope/audiencia desde el host y llama a cada dependencia
# (auth M2M por URL publica, support M2M interna y la fachada de colaboradores end-to-end).
# Sale con codigo != 0 si algo no responde lo esperado, para abortar/avisar el deploy.
#
# Uso (desde osap-api):
#   pwsh -File script/verify-auth-m2m.ps1

param(
    [string]$HostAlias = "RemoteIA"
)

$ErrorActionPreference = "Stop"

$remote = @'
set -u
pid=$(systemctl show -p MainPID --value osap-api 2>/dev/null)
if [ -z "$pid" ] || [ "$pid" = "0" ]; then echo "FAIL  osap-api no esta activo"; exit 1; fi
env=$(sudo tr '\0' '\n' < /proc/$pid/environ 2>/dev/null)
cid=$(printf '%s\n' "$env" | grep '^OSAP_SERVICE_CLIENT_ID=' | cut -d= -f2-)
sec=$(printf '%s\n' "$env" | grep '^OSAP_SERVICE_CLIENT_SECRET=' | cut -d= -f2-)
support_admin_cid=$(printf '%s\n' "$env" | grep '^OSAP_SUPPORT_ADMIN_CLIENT_ID=' | cut -d= -f2-)
support_admin_sec=$(printf '%s\n' "$env" | grep '^OSAP_SUPPORT_ADMIN_CLIENT_SECRET=' | cut -d= -f2-)
admin_cid=$(printf '%s\n' "$env" | grep '^OSAP_ADMIN_CLIENT_ID=' | cut -d= -f2-)
admin_sec=$(printf '%s\n' "$env" | grep '^OSAP_ADMIN_CLIENT_SECRET=' | cut -d= -f2-)
if [ -z "$cid" ] || [ -z "$sec" ]; then echo "FAIL  faltan OSAP_SERVICE_CLIENT_ID/SECRET"; exit 1; fi
if [ -z "$support_admin_cid" ] || [ -z "$support_admin_sec" ]; then echo "FAIL  faltan OSAP_SUPPORT_ADMIN_CLIENT_ID/SECRET"; exit 1; fi
if [ -z "$admin_cid" ] || [ -z "$admin_sec" ]; then echo "FAIL  faltan OSAP_ADMIN_CLIENT_ID/SECRET"; exit 1; fi

UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'
TOKEN_URL='https://auth.openmusicrepository.com/auth-api/oauth/token'
fail=0

token() {
  scope="$1"; aud="$2"; client_id="${3:-$cid}"; client_secret="${4:-$sec}"
  if [ -n "$aud" ]; then
    body="{\"grant_type\":\"client_credentials\",\"client_id\":\"$client_id\",\"client_secret\":\"$client_secret\",\"scope\":\"$scope\",\"audience\":\"$aud\"}"
  else
    body="{\"grant_type\":\"client_credentials\",\"client_id\":\"$client_id\",\"client_secret\":\"$client_secret\",\"scope\":\"$scope\"}"
  fi
  curl -s -A "$UA" -H 'Content-Type: application/json' -X POST "$TOKEN_URL" -d "$body" \
    | python3 -c 'import sys,json
try:
    print(json.load(sys.stdin).get("access_token",""))
except Exception:
    print("")'
}

check() {
  name="$1"; expected="$2"; url="$3"; tok="$4"
  if [ -n "$tok" ]; then
    code=$(curl -s -o /dev/null -w '%{http_code}' -A "$UA" -H "Authorization: Bearer $tok" "$url")
  else
    code=$(curl -s -o /dev/null -w '%{http_code}' -A "$UA" "$url")
  fi
  if [ "$code" = "$expected" ]; then echo "PASS  $name ($code)"; else echo "FAIL  $name ($code != $expected)"; fail=1; fi
}

t_storage=$(token 'storage:read' '')
t_storage_admin=$(token 'storage:admin' '' "$admin_cid" "$admin_sec")
t_support=$(token 'api:read' 'osap-support')
t_support_admin=$(token 'support:admin' 'osap-support' "$support_admin_cid" "$support_admin_sec")
t_auth=$(token 'auth:read_public_names' 'osap-auth')
report_token() {
  name="$1"; value="$2"
  if [ -n "$value" ]; then echo "PASS  token $name"; else echo "FAIL  token $name"; fail=1; fi
}
report_token 'storage:read' "$t_storage"
report_token 'storage:admin' "$t_storage_admin"
report_token 'api:read/osap-support' "$t_support"
report_token 'support:admin/osap-support' "$t_support_admin"
report_token 'auth:read_public_names/osap-auth' "$t_auth"

STORAGE_BASE=$(printf '%s\n' "$env" | grep '^OSAP_STORAGE_BASE_URL=' | cut -d= -f2-)
[ -n "$STORAGE_BASE" ] || STORAGE_BASE='https://storage.openmusicrepository.com'
STORAGE_READ_URL="${STORAGE_BASE%/}/api/v1/works?limit=1"
SUPPORT_ADMIN_URL='http://127.0.0.1:8300/api/v1/admin/recognitions?user_id=__m2m_smoke_test__'

check 'storage sin token' 401 "$STORAGE_READ_URL" ''
check 'storage storage:read' 200 "$STORAGE_READ_URL" "$t_storage"
check 'storage scope insuficiente (storage:admin)' 403 "$STORAGE_READ_URL" "$t_storage_admin"
check 'support admin sin token' 401 "$SUPPORT_ADMIN_URL" ''
check 'support admin scope insuficiente (api:read)' 403 "$SUPPORT_ADMIN_URL" "$t_support"
check 'support admin cliente dedicado' 200 "$SUPPORT_ADMIN_URL" "$t_support_admin"
check 'auth m2m public-users' 200 'https://auth.openmusicrepository.com/auth-api/auth/m2m/public-users' "$t_auth"
check 'support m2m recognitions' 200 'http://127.0.0.1:8300/api/v1/m2m/recognitions?project=omr' "$t_support"
check 'app colaboradores (e2e)' 200 'https://api.openmusicrepository.com/api/v1/public/collaborators?project=omr' ''

if [ "$fail" -ne 0 ]; then exit 1; fi
exit 0
'@

# PowerShell traduce a CRLF al tuberías a procesos nativos; se envía en base64 para
# preservar los saltos de línea LF del script remoto.
$payload = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes(($remote -replace "`r", "")))
Write-Host "== Smoke test auth/M2M (osap-api -> auth/storage/support) ==" -ForegroundColor Cyan
ssh -o BatchMode=yes $HostAlias "echo $payload | base64 -d | bash"
if ($LASTEXITCODE -ne 0) { Write-Error "Smoke test auth/M2M FALLO"; exit 1 }
Write-Host "Smoke test auth/M2M OK." -ForegroundColor Green
