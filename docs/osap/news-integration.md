# Noticias en OSAP

> **Estado 2026-11-24:** la integración de lectura está implementada en OSAP API. El servicio independiente [ai_noticias](https://github.com/recursosformacion/ai_noticias) tiene su primera implementación RSS/Atom y la BD `osap_noticias` creada/verificada en el entorno local. Esto no acredita un despliegue productivo de ai_noticias; la disponibilidad real del servicio y sus secretos deben verificarse por separado.

## Acceso

Las noticias se leen en **`/noticias`** con la sesión de OSAP. No hay acceso por correo
ni un perfil de noticias separado: OSAP lee `news_language`, `news_topics` y
`news_opt_in` de `osap-auth`.

```
/noticias
  → OSAP /api/v1/news
  → ai_noticias /api/v1/news (language, topics)
  → tarjetas con enlace a la fuente original
```

## Consentimiento y comunicaciones

- Leer noticias en la web **no envía correos**.
- `news_opt_in` solo autoriza un futuro resumen por correo; es opcional y se puede
  desactivar en cualquier momento.
- Cualquier envío futuro pertenece a OSAP: `CommunicationEvent → worker → EmailSender`
  (`osap-support`). `ai_noticias` no conoce identidades, correos ni listas de usuarios.
- No se crean notificaciones in-app automáticas por cada noticia. La campana se reserva
  para avisos operativos y de relación con el usuario.

## Backend

| Pieza | Ubicación |
| --- | --- |
| Cliente interno | `src/osap/infrastructure/news/client.py` |
| Fachada / casos de uso | `src/osap/api/platform/news.py` |
| Rutas | `src/osap/api/http/news.py` |
| Configuración | `[news] base_url`, `service_token`, `timeout_seconds` |

Variables: `OSAP_NEWS_API_BASE`, `OSAP_NEWS_API_TOKEN`,
`OSAP_NEWS_API_TIMEOUT_SECONDS`.

El token es de servicio (cabecera `X-OSAP-News-Token`). Si no está configurado, la
página muestra “servicio no disponible”; nunca se consulta la base de noticias
directamente.

## Servicio ai_noticias

El contrato y la configuración de desarrollo están en
`ai_noticias/docs/16-integracion-osap.md`. Los comandos `mailbox`, `digest` y
`outbound_messages` quedan como herramientas históricas y no forman parte de OSAP.

