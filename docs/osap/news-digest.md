# Boletín de noticias: librería y cron

## Piezas

`src/osap/news_digest/` es la librería común del boletín:

| Módulo | Responsabilidad |
| --- | --- |
| `models.py` | idiomas, temas, `Subscriber`, `DigestItem`, `Digest` |
| `render.py` | asunto, texto y HTML; solo enlaces `http/https` |
| `clients.py` | suscriptores internos de osap-auth y entrega a osap-support |
| `runner.py` | recorrido, consulta a ai_noticias, idempotencia y reporte |
| `__main__.py` | CLI del cron |

## Flujo

```
cron
  → GET osap-auth /auth/internal/news-subscribers   (solo opt-in, email verificado)
  → por usuario: GET ai_noticias /api/v1/news?languages=…&topics=…
  → render del boletín
  → POST osap-support /internal/communications/news  (CommunicationEvent pendiente)
  → worker de osap-support → EmailSender
```

La identidad, el consentimiento y el envío siguen siendo de OSAP. `ai_noticias` solo
devuelve corpus.

## Ejecución manual (dev)

```powershell
$env:OSAP_INTERNAL_SERVICE_TOKEN = "osap-dev-internal-token"
$env:OSAP_AUTH_INTERNAL_URL = "http://127.0.0.1:8200"
$env:OSAP_NEWS_API_BASE = "http://127.0.0.1:8400"
$env:OSAP_NEWS_API_TOKEN = "osap-dev-news-token"
$env:OSAP_SUPPORT_INTERNAL_URL = "http://127.0.0.1:8300"

# Simulación: escribe .eml + report.json, no toca la cola
python -m src.osap.news_digest --user-id <uuid> --limit 5 --days 3650

# Encolar de verdad (sin SMTP); luego el worker de support lo entrega
python -m src.osap.news_digest --send
& D:\Proyectos\AI_OSAP\osap-support\.venv\Scripts\python.exe -m infrastructure.worker --once
```

En dev el worker usa `OSAP_SUPPORT_EMAIL_SENDER=fake`; en producción exige `smtp`.

## Idempotencia

`dedupe_key = news:YYYY-MM-DD:<user_id>`. `osap-support` devuelve `duplicate` si ya
existe; el runner lo cuenta como omitido. Un cron diario puede ejecutarse varias veces
sin duplicar el correo.

## Requisitos antes de programarlo

- `OSAP_INTERNAL_SERVICE_TOKEN` compartido por osap-auth, osap-api y osap-support.
- Usuarios con `news_opt_in`, email verificado, al menos un tema y un idioma.
- `osap-auth` migración `0018_news_languages` y `osap-support` migración `0003`.
- Cron (Linux) o Programador de tareas (Windows) apuntando a `python -m src.osap.news_digest --send`.
