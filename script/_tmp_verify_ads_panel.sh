
#!/bin/bash
# Verificación: panel de publicidad servido por el proxy /publicidad/ y su sesión.
R='--resolve app.openmusicrepository.com:443:127.0.0.1 -k'
echo "--- GET /publicidad/p"
curl -s $R -o /tmp/_p -w '  -> %{http_code} size=%{size_download}\n' https://app.openmusicrepository.com/publicidad/p; head -c 200 /tmp/_p; echo
echo "--- GET /publicidad/ (raíz del servicio)"
curl -s $R -o /tmp/_p -w '  -> %{http_code}\n' https://app.openmusicrepository.com/publicidad/; head -c 160 /tmp/_p; echo
echo "--- health del servicio"
curl -s $R -o /tmp/_p -w 'GET /publicidad/health -> %{http_code}\n' https://app.openmusicrepository.com/publicidad/health
echo "--- sesión válida simulada (cookie tras 303): cabeceras"
curl -s $R -o /dev/null -D /tmp/_h -X POST https://app.openmusicrepository.com/publicidad/auth/session -H 'Origin: https://app.openmusicrepository.com' -H 'Content-Type: application/x-www-form-urlencoded' --data 'token=fake&next=/p'; grep -iE '^(HTTP|location|set-cookie)' /tmp/_h | sed -E 's/(ai_publicidad_session=)[^;]+/\1<redacted>/'
echo "--- GET /publicidad/admin (ruta interna del panel)"
curl -s $R -o /dev/null -w '  -> %{http_code}\n' https://app.openmusicrepository.com/publicidad/admin
