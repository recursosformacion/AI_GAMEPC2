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
if [ -z "$cid" ] || [ -z "$sec" ]; then echo "FAIL  faltan OSAP_SERVICE_CLIENT_ID/SECRET"; exit 1; fi

UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'
TOKEN_URL='https://auth.openmusicrepository.com/auth-api/oauth/token'
fail=0

token() {
  scope="$1"; aud="$2"
  if [ -n "$aud" ]; then
    body="{\"grant_type\":\"client_credentials\",\"client_id\":\"$cid\",\"client_secret\":\"$sec\",\"scope\":\"$scope\",\"audience\":\"$aud\"}"
  else
    body="{\"grant_type\":\"client_credentials\",\"client_id\":\"$cid\",\"client_secret\":\"$sec\",\"scope\":\"$scope\"}"
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
if [ -n "$t_storage" ]; then echo "PASS  token storage:read"; else echo "FAIL  token storage:read"; fail=1; fi
t_support=$(token 'api:read' 'osap-support')
if [ -n "$t_support" ]; then echo "PASS  token api:read/osap-support"; else echo "FAIL  token api:read/osap-support"; fail=1; fi
t_auth=$(token 'auth:read_public_names' 'osap-auth')
if [ -n "$t_auth" ]; then echo "PASS  token auth:read_public_names/osap-auth"; else echo "FAIL  token auth:read_public_names/osap-auth"; fail=1; fi

check 'auth m2m public-users' 200 'https://auth.openmusicrepository.com/auth-api/auth/m2m/public-users' "$t_auth"
check 'support m2m recognitions' 200 'http://127.0.0.1:8300/api/v1/m2m/recognitions?project=omr' "$t_support"
check 'app colaboradores (e2e)' 200 'https://api.openmusicrepository.com/api/v1/public/collaborators?project=omr' ''

if [ "$fail" -ne 0 ]; then exit 1; fi
exit 0
'@

# PowerShell traduce a CRLF al tuberías a procesos nativos; se envía en base64 para
# preservar los saltos de línea LF del script remoto.
$payload = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes(($remote -replace "`r", "")))
Write-Host "== Smoke test auth/M2M (osap-api -> auth/support) ==" -ForegroundColor Cyan
ssh -o BatchMode=yes $HostAlias "echo $payload | base64 -d | bash"
if ($LASTEXITCODE -ne 0) { Write-Error "Smoke test auth/M2M FALLO"; exit 1 }
Write-Host "Smoke test auth/M2M OK." -ForegroundColor Green
