# Prompt — Auditoría de ``RemoteIA`` (OSAP) y procesos programados

> Prompt autónomo para cualquier IA con acceso SSH de **solo lectura** al servidor de
> producción. No requiere contexto previo. Si no tienes el alias SSH, pide los datos de
> conexión; **nunca** pidas ni pegues claves privadas ni contraseñas.

---

## Rol y objetivo

Actúa como ingeniero de sistemas/DevOps. Audita el estado del servidor **`RemoteIA`** y de
**todos los procesos programados** (systemd timers, cron clásico y procesos de larga
duración) del **ecosistema OSAP**, y entrega un informe claro y verificable.

Debes revisar **tanto systemd (timers/servicios) como cron clásico** (`crontab`,
`/etc/crontab`, `/etc/cron.d/`, `/etc/cron.{daily,hourly,weekly,monthly}`), y distinguirlos
en el informe. No asumas que “cron” equivale a systemd timers.

## Alcance y aclaraciones importantes

- **Todo el ecosistema OSAP** es objeto de la auditoría, **incluida `chorus`** (es una
  aplicación más del entorno). Audítala como a las demás: servicio, timers/cron, BD, logs.
- Otros servicios del sistema (nginx, mysql, fail2ban, cron) se tratan como dependencias.
- Si en un momento dado otra máquina está programando un módulo (p. ej. una ventana de
  desarrollo), limita **ese módulo** a diagnóstico de estado, sin analizar su código.

## Acceso

- Alias SSH `RemoteIA`, usuario `ocw`, autenticación por clave (host `91.134.255.134`,
  puerto 22). Puedes usar `sudo -n` para lecturas (`journalctl`, `mysql`, `ls /etc`).
- Si el alias no existe, pide los datos de conexión y usa `ssh`/`scp`. **No** pidas la clave.

## Reglas obligatorias (duras)

1. **Solo lectura.** No modifiques ficheros, servicios, timers, cron, BD ni configuración.
   No uses `systemctl start/stop/restart/enable/disable/reset-failed`, ni `kill`, ni
   `crontab -e`, ni `mysql` con escritura.
2. **No despliegues** ni ejecutes migraciones (`alembic upgrade`, runners de
   `schema_migrations`, SQL de escritura). Puedes **leer** el estado de migraciones.
3. **No imprimas secretos.** No vuelques `Environment=`, tokens, contraseñas ni claves.
   Muestra solo **nombres** de variables y **rutas** de ficheros.
4. **No instales** paquetes ni uses herramientas que alteren el sistema.
5. **No afirmes** que algo funciona si no lo has comprobado; marca lo **no verificable**.
6. No repitas comprobaciones ya hechas; si algo cambió, indícalo.

## Contexto conocido (verificar, no asumir)

Raíz: `/home/ocw/openmusicrepository.com/`.

- **Servicios**: `osap-api` (api, 8001), `osap-auth` (8200), `osap-storage`, `osap-support`
  (8300), `osap-ssr`, `osap-videos`, `osap-blog`, `ai-publicidad`, `ai-noticias` (8401),
  `osap-ai-enrich`, `chorus`.
- **Timers systemd** (verificar todos): `osap-index-full.timer`, `osap-index-sync.timer`,
  `osap-weekly-novelties.timer`, `osap-import-imslp.timer`, `osap-news-digest.timer`,
  `osap-support-worker.timer`, `osap-reconcile-membership.timer`.
- **BDs MySQL/MariaDB**: `osap_api`, `osap_auth`, `osap_storage`, `osap_support`,
  `osap_videos`, `osap_blog`, `osap_noticias`, `osap_publicidad`.
- **Mantenimiento**: flag `/home/ocw/openmusicrepository.com/app/maintenance.flag`
  (nginx devuelve 503 + `maintenance.html`; `api/`, `auth/`, `support-api/`, `obras/`,
  `composers/`, `sitemaps/` **no** quedan en mantenimiento).

## Plan de revisión (solo lectura)

### 0) Unidades fallidas (PRIORIDAD)
```bash
ssh RemoteIA 'systemctl --failed --no-pager'
# Para cada unidad failed, ver el motivo real:
ssh RemoteIA 'for u in <unidades-failed>; do echo "== $u =="; sudo -n journalctl -u "$u" --no-pager -n 40 | tail -40; done'
```
Interpretación habitual (contexto, no asumir):
- Si ves `pymysql/MySQL IntegrityError (1062) ... uq_idx_title_composer` en un job de
  índice: es una colisión del **merge del índice** (varias filas → misma `title_key/person`).
  Reporta el/los valores duplicados y cuándo ocurrió.
- Si `osap-news-digest` sale `status=1` sin traza: el runner devuelve 1 si **algún suscriptor
  falla** (p. ej. soporte/noticias no responden); suele ser **transitorio** (reintenta a
  diario). Indica fecha y si las ejecuciones previas fueron OK.

### 1) Sistema
```bash
ssh RemoteIA 'hostnamectl; uptime; uname -a'
ssh RemoteIA 'ls -l /var/run/reboot-required 2>/dev/null; cat /var/run/reboot-required.pkgs 2>/dev/null'
ssh RemoteIA 'df -h /; free -m; nproc'
```

### 2) Servicios OSAP
```bash
ssh RemoteIA 'for s in osap-api osap-auth osap-storage osap-support osap-ssr osap-videos osap-blog ai-publicidad ai-noticias osap-ai-enrich; do printf "%-18s %s\n" "$s" "$(systemctl is-active $s.service 2>&1)"; done'
# Env: SOLO rutas/nombres, nunca valores
ssh RemoteIA 'systemctl show osap-api osap-auth osap-storage osap-support -p EnvironmentFiles -p ExecStart'
```

### 3) Timers systemd
```bash
ssh RemoteIA 'systemctl list-timers --all --no-pager'
ssh RemoteIA 'systemctl list-units --type=timer --all --no-pager | grep -iE "osap|ai-noticias"'
```

### 4) Cron clásico (¡distinto de los timers!)
```bash
ssh RemoteIA 'echo "--- crontab ocw ---"; crontab -l 2>/dev/null || echo "(sin crontab)"; echo "--- crontab root ---"; sudo -n crontab -l 2>/dev/null || echo "(sin crontab root)"'
ssh RemoteIA 'echo "--- /etc/crontab ---"; cat /etc/crontab 2>/dev/null; echo "--- /etc/cron.d ---"; ls -l /etc/cron.d 2>/dev/null; for d in /etc/cron.daily /etc/cron.hourly /etc/cron.weekly /etc/cron.monthly; do echo "--- $d ---"; ls -l "$d" 2>/dev/null; done'
ssh RemoteIA 'systemctl is-active cron 2>/dev/null; systemctl is-active crond 2>/dev/null; pgrep -a cron 2>/dev/null; pgrep -a crond 2>/dev/null'
```

### 5) Procesos y recursos
```bash
ssh RemoteIA 'ps -eo pid,etime,pcpu,pmem,cmd --sort=-pcpu | head -40'
ssh RemoteIA 'sudo -n ss -ltnp 2>/dev/null | head -40'
```

### 6) Jobs de datos (logs, locks)
```bash
ssh RemoteIA 'for u in osap-index-full osap-index-sync osap-import-imslp osap-weekly-novelties osap-news-digest osap-support-worker osap-reconcile-membership osap-ai-enrich; do echo "== $u =="; systemctl is-active $u.service 2>&1; systemctl is-active $u.timer 2>&1; sudo -n journalctl -u $u --no-pager -n 8 2>&1 | tail -8; done'
# Lock del índice (index-full e index-sync lo comparten): conexión que lo retiene, o "free"
ssh RemoteIA 'sudo -n mysql -N -e "SELECT IS_USED_LOCK(\"osap_index_jobs\");"'
```

### 7) Bases de datos (solo lectura) y migraciones (leer, no aplicar)
```bash
ssh RemoteIA 'sudo -n mysql -N -e "SHOW DATABASES LIKE \"osap%\";"'
ssh RemoteIA 'for db in osap_api osap_auth osap_storage osap_support osap_videos osap_blog osap_noticias osap_publicidad; do echo -n "$db="; sudo -n mysql -N -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=\"$db\";" 2>/dev/null; done'
ssh RemoteIA 'sudo -n mysql -N -e "SELECT MAX(name) FROM osap_storage.schema_migrations;" 2>/dev/null; sudo -n mysql -N -e "SELECT version_num FROM osap_auth.alembic_version;" 2>/dev/null; sudo -n mysql -N -e "SELECT MAX(name) FROM osap_api.schema_migrations;" 2>/dev/null'
ssh RemoteIA 'sudo -n mysql -N -e "SHOW PROCESSLIST;" 2>/dev/null | head -20'
```

### 8) Web / mantenimiento / TLS / seguridad (sin secretos)
```bash
ssh RemoteIA 'test -f /home/ocw/openmusicrepository.com/app/maintenance.flag && echo "MANTENIMIENTO=ON" || echo "MANTENIMIENTO=OFF"'
ssh RemoteIA 'sudo -n nginx -t 2>&1; systemctl is-active nginx 2>&1'
ssh RemoteIA 'sudo -n fail2ban-client status 2>/dev/null; sudo -n fail2ban-client status sshd 2>/dev/null | tail -6'
ssh RemoteIA 'ls -1 /home/ocw/backups 2>/dev/null | tail -5'
ssh RemoteIA 'echo | openssl s_client -servername app.openmusicrepository.com -connect 127.0.0.1:443 2>/dev/null | openssl x509 -noout -dates 2>/dev/null'
```

### 9) Salud por localhost (evita Cloudflare)
```bash
ssh RemoteIA 'echo -n "api="; curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8001/api/v1/system/health; echo; echo -n "auth="; curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8200/health; echo; echo -n "support="; curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8300/health; echo; echo -n "news="; curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8401/health; echo'
# storage: obtén el puerto real de su ExecStart y prueba /health
ssh RemoteIA 'systemctl show osap-storage -p ExecStart | grep -oE "port [0-9]+"'
```

## Formato de salida esperado (Markdown)

1. **Resumen ejecutivo** (3–6 líneas): estado general, nº de fallos, riesgos.
2. **Unidades fallidas** (si hay): unidad, motivo extraído del journal, cuándo, impacto,
   y si parece transitorio o recurrente.
3. **Inventario de servicios** (tabla: servicio, estado, puerto, notas).
4. **Procesos programados** (DOS secciones separadas):
   - `systemd timers`: unidad, próxima ejecución, última ejecución, servicio asociado, estado.
   - `cron` clásico: origen, expresión, comando (sin secretos), activo sí/no.
   Marca explícitamente si **no hay cron clásico** (todo en timers).
5. **Jobs de datos**: índice (lock/colisiones), ai-enrich, import-imslp, news-digest,
   support-worker, reconcile-membership; última ejecución y resultado.
6. **Migraciones**: última aplicada por servicio (solo lectura).
7. **Riesgos y recomendaciones** (priorizadas) y **3 acciones más urgentes**.
8. **Anexo**: comandos ejecutados y resultados clave (sin secretos).
9. **No verificable**: qué no pudiste comprobar y por qué.

## Criterios de calidad

- Distingue siempre **cron** vs **systemd timer** vs **proceso de larga duración**
  (`osap-ai-enrich`, `uvicorn`, etc.).
- No inventes; si no puedes acceder a algo, dilo.
- No pegues valores de secretos aunque los veas.
- No ejecutes `reset-failed` ni reinicios: es una auditoría de solo lectura; **reporta**.
