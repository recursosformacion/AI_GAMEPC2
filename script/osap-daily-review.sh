#!/bin/bash
# Revisión diaria del VPS OSAP. Envía email solo si hay problemas o avisos.
set -u

HOST=$(hostname)
ALERT_TO="migarcia@recursosformacion.com"
MAILER=/usr/local/sbin/osap-send-alert.py
LOG=/var/log/osap-daily-review.log
problems=()
warnings=()
info=()
work=()

add_problem() { problems+=("$1"); }
add_warning() { warnings+=("$1"); }
add_info() { info+=("$1"); }
add_work() { work+=("$1"); }

echo "[$(date -Is)] revisión diaria OSAP en $HOST"

# Unidades fallidas
failed=$(systemctl --failed --no-legend 2>/dev/null | awk '{print $1}')
if [ -n "$failed" ]; then
  while IFS= read -r unit; do
    [ -n "$unit" ] && add_problem "unidad fallida: $unit"
  done <<< "$failed"
fi

# Servicios requeridos
for svc in osap-api osap-auth osap-storage osap-ssr osap-support osap-blog osap-videos ai-publicidad nginx apache2 mariadb nginx-ui fail2ban; do
  systemctl is-active --quiet "$svc" || add_problem "servicio no activo: $svc"
done

# Disco y memoria
use=$(df -P / | awk 'NR==2 {gsub("%", "", $5); print $5}')
if [ "${use:-0}" -gt 85 ]; then add_problem "disco / al ${use}%"; else add_info "disco / ${use}%"; fi
inode=$(df -Pi / | awk 'NR==2 {gsub("%", "", $5); print $5}')
if [ "${inode:-0}" -gt 90 ]; then add_problem "inodos / al ${inode}%"; fi
avail=$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)
if [ "${avail:-0}" -lt 524288 ]; then add_problem "memoria disponible baja: $((avail/1024)) MB"; else add_info "memoria disponible $((avail/1024)) MB"; fi

# Reinicio y actualizaciones
if [ -e /var/run/reboot-required ]; then add_warning "reinicio pendiente (reboot-required)"; fi
upgradable=$(apt list --upgradable 2>/dev/null | grep -c upgradable || true)
security=$(apt list --upgradable 2>/dev/null | grep -ci security || true)
if [ "${security:-0}" -gt 0 ]; then add_warning "$security actualizaciones de seguridad pendientes"; fi
add_info "paquetes actualizables: ${upgradable:-0}"

# HTTP local
check_http() {
  local name="$1" url="$2" expect="${3:-200}" code
  code=$(curl -sS -o /dev/null -w '%{http_code}' --max-time 5 "$url" 2>/dev/null || true)
  if [ "$code" != "$expect" ]; then
    add_problem "$name HTTP $code (esperado $expect)"
  fi
}
check_http api http://127.0.0.1:8001/api/v1/system/health
check_http auth http://127.0.0.1:8200/auth/.well-known/jwks.json
check_http storage http://127.0.0.1:8000/api/v1/health
check_http blog http://127.0.0.1:8500/health
check_http support http://127.0.0.1:8300/
check_http videos http://127.0.0.1:8400/
check_http nginx-ui http://127.0.0.1:9000/

# Configuración web
nginx -t >/dev/null 2>&1 || add_problem "nginx: configuración inválida"
apache2ctl configtest >/dev/null 2>&1 || add_warning "Apache: configtest con aviso/error"

# SSH / firewall
if ! sshd -T 2>/dev/null | grep -q '^passwordauthentication no'; then
  add_problem "SSH: autenticación por contraseña activa"
fi
if ! ufw status 2>/dev/null | grep -q '^Status: active'; then
  add_problem "UFW no está activo"
fi

# Fail2ban
if systemctl is-active --quiet fail2ban; then
  add_info "fail2ban activo"
else
  add_problem "fail2ban no está activo"
fi
banned=$(fail2ban-client status sshd 2>/dev/null | awk '/Currently banned/ {print $NF}')
[ -n "${banned:-}" ] && add_info "fail2ban sshd baneados: $banned"

# Certificados
if ! systemctl is-active --quiet certbot.timer; then
  add_problem "certbot.timer no está activo"
fi
min_days=$(certbot certificates 2>/dev/null | grep -oE 'VALID: [0-9]+ days' | awk '{print $2}' | sort -n | head -1)
if [ -z "${min_days:-}" ]; then
  add_problem "no se pudieron leer los certificados TLS"
elif [ "$min_days" -lt 21 ]; then
  add_problem "certificado TLS a $min_days días"
else
  add_info "TLS mínimo $min_days días"
fi

# IA: osap-ai-enrich es un oneshot, no un daemon; solo importa si su última
# ejecución falló o si el pipeline quedó en pausa.
ai_result=$(systemctl show -p Result --value osap-ai-enrich 2>/dev/null || true)
if [ "${ai_result:-}" = "failed" ]; then
  add_problem "osap-ai-enrich falló en su última ejecución"
fi
if tail -200 /home/ocw/openmusicrepository.com/osap-storage/data/ai_enrich_prod.log 2>/dev/null | grep -q 'pausa 24.0 h'; then
  add_warning "enriquecimiento IA en pausa por cuota/API"
fi

# Tokens de servicio: nada externo y sin picos
bad_tokens=$(mysql -N osap_auth -e "SELECT COUNT(*) FROM audit_events WHERE event_type='service.token.issued' AND timestamp >= NOW() - INTERVAL 1 HOUR AND ip NOT IN ('127.0.0.1','::1');" 2>/dev/null || echo 0)
if [ "${bad_tokens:-0}" -gt 0 ]; then
  add_problem "tokens de servicio desde IP externa: $bad_tokens en 1h"
fi
rate=$(mysql -N osap_auth -e "SELECT COUNT(*) FROM audit_events WHERE event_type='service.token.issued' AND timestamp >= NOW() - INTERVAL 1 HOUR;" 2>/dev/null || echo 0)
if [ "${rate:-0}" -gt 5000 ]; then add_warning "pico de tokens de servicio: $rate en 1h"; else add_info "tokens de servicio 1h: ${rate:-0}"; fi
ext_token=$(tail -n 5000 /var/log/nginx/access.log 2>/dev/null | grep -c '/auth-api/oauth/token' || true)
[ "${ext_token:-0}" -gt 0 ] && add_warning "peticiones a /auth-api/oauth/token: $ext_token en el último tramo de log"

# Persistencia conocida del incidente
for p in /bin/perfcc /root/.config/cron/perfcc /usr/lib/libfsnldev.so /usr/lib/libpprocps.so /lib/libgcwrap.so /etc/ld.so.preload /etc/ld.so.preload_ /etc/cron.d/perfclean /etc/cron.daily/perfclean /usr/bin/wbin; do
  [ -e "$p" ] && add_problem "IOC presente: $p"
done

# Stub_status no debe escuchar en 0.0.0.0
if ss -ltn 2>/dev/null | grep -q '0.0.0.0:51820'; then
  add_warning "stub_status nginx-ui escuchando en 0.0.0.0:51820"
fi

# Cron, timers y enriquecimiento
for timer in osap-news-digest.timer osap-support-worker.timer; do
  systemctl is-active --quiet "$timer" || add_problem "timer no activo: $timer"
done
for unit in osap-news-digest.service osap-support-worker.service; do
  result=$(systemctl show -p Result --value "$unit" 2>/dev/null || true)
  [ "$result" = "failed" ] && add_problem "cron fallido: $unit"
done
systemctl is-active --quiet cron || add_problem "cron no está activo"
if tail -300 /home/ocw/openmusicrepository.com/osap-storage/data/ai_enrich_prod.log 2>/dev/null | grep -qE 'aplicación de obras falló|ERROR:'; then
  add_warning "enriquecimiento IA con errores recientes"
fi

# Trabajo reciente: contexto breve para el email de incidencias.
STORAGE=/home/ocw/openmusicrepository.com/osap-storage
cursor_raw=$(cat "$STORAGE/var/imslp_works_cursor.txt" 2>/dev/null || true)
cursor=${cursor_raw:-0}
case "$cursor" in ''|*[!0-9]*) cursor=0 ;; esac
remaining=$(mysql -N osap_storage -e \
  "SELECT COUNT(*) FROM works WHERE works_origin='IMSLP' \
   AND works_source_url LIKE 'https://imslp.org/wiki/%' AND id > ${cursor} \
   AND (works_year IS NULL OR TRIM(COALESCE(works_instrumentation,''))='' \
        OR works_epoch_id IS NULL);" 2>/dev/null || true)
if systemctl list-units --state=running --no-legend 2>/dev/null | grep -q 'osap-imslp-enrich'; then
  imslp_state="lote en curso"
else
  imslp_state="sin lote en curso"
fi
imslp_total=$(python3 - "$STORAGE" <<'PY'
import glob, json, sys
totals = {"year": 0, "instrumentation": 0, "epoch": 0}
for path in glob.glob(sys.argv[1] + "/var/imslp_works_*.json"):
    data = json.load(open(path, encoding="utf-8"))
    if not data.get("applied"):
        continue
    stats = data.get("stats", {})
    for key in totals:
        totals[key] += int(stats.get(key, 0) or 0)
print(
    f"{totals['year']} años, "
    f"{totals['instrumentation']} instrumentaciones, "
    f"{totals['epoch']} épocas"
)
PY
) || true
if [ -n "${imslp_total:-}" ]; then
  add_work "IMSLP acumulado: ${imslp_total}; cursor ${cursor_raw:-0}; ${remaining:-?} candidatas; ${imslp_state}"
else
  add_work "IMSLP: cursor ${cursor_raw:-0}; ${remaining:-?} candidatas; ${imslp_state}"
fi

visible_persons=$(mysql -N osap_storage -e \
  "SELECT COUNT(*) FROM persons WHERE persons_visible=1;" 2>/dev/null || true)
promote_report=$(ls -1t "$STORAGE"/var/hidden_persons_promote_*.json 2>/dev/null | head -1)
promoted=""
if [ -n "${promote_report:-}" ]; then
  promoted=$(python3 - "$promote_report" <<'PY'
import json, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
print(data.get("count", len(data.get("persons", []))))
PY
  ) || true
fi
if [ -n "${promoted:-}" ]; then
  add_work "Personas: ${visible_persons:-?} visibles; última promoción ${promoted} ($(basename "$promote_report"))"
else
  add_work "Personas: ${visible_persons:-?} visibles"
fi

# Resultado
if [ ${#problems[@]} -eq 0 ] && [ ${#warnings[@]} -eq 0 ]; then
  [ ${#work[@]} -gt 0 ] && printf '[%s] trabajo reciente: %s | %s\n' \
    "$(date -Is)" "${work[0]}" "${work[1]:-}"

  echo "[$(date -Is)] OK"
  exit 0
fi

BODY=$(mktemp /tmp/osap-review.XXXXXX)
{
  echo "Revisión diaria OSAP — $HOST"
  echo "Fecha: $(date -Is)"
  echo
  if [ ${#problems[@]} -gt 0 ]; then
    echo "PROBLEMAS:"
    printf ' - %s\n' "${problems[@]}"
    echo
  fi
  if [ ${#warnings[@]} -gt 0 ]; then
    echo "AVISOS:"
    printf ' - %s\n' "${warnings[@]}"
    echo
  fi
  if [ ${#info[@]} -gt 0 ]; then
    echo "INFORMACIÓN:"
    printf ' - %s\n' "${info[@]}"
    echo
  fi
  if [ ${#work[@]} -gt 0 ]; then
    echo "TRABAJO RECIENTE:"
    printf ' - %s\n' "${work[@]}"
    echo
  fi
} > "$BODY"

if [ ${#problems[@]} -gt 0 ]; then
  subject="OSAP: ${#problems[@]} problema(s) en $HOST"
else
  subject="OSAP: ${#warnings[@]} aviso(s) en $HOST"
fi

if "$MAILER" "$subject" "$ALERT_TO" < "$BODY"; then
  echo "[$(date -Is)] email enviado a $ALERT_TO"
else
  echo "[$(date -Is)] ERROR enviando email"
fi
rm -f "$BODY"
exit 0
