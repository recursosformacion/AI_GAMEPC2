# Integración de ai_publicidad en OSAP

**Estado:** guía de implementación; no implica que la integración ya esté desplegada.  
**Repositorios:** [AI_GAMEPC2 (OSAP)](https://github.com/recursosformacion/AI_GAMEPC2) y [ai_publicidad](https://github.com/recursosformacion/ai_publicidad).

**Composición dinámica disponible en ai_publicidad:** `POST /api/v1/ads/compose` devuelve un fragmento HTML listo para insertar, a partir de un formato fijo o un área disponible, y puede incluir hasta tres anuncios. La emisión registra inmediatamente una impresión por anuncio y no requiere una petición de impresión posterior. La API y el laboratorio están implementados en el servicio publicitario, pero todavía falta incorporarlos a la fachada de `osap-api` y al frontend. Ver [el diseño y comportamiento actual](https://github.com/recursosformacion/ai_publicidad/blob/main/docs/ad-layout-optimization.md).

## 1. Objetivo y estado actual

Integrar `ai_publicidad` como servicio independiente de entrega de anuncios, manteniendo la aplicación React de OSAP. OSAP reserva el espacio real y le pasa sus dimensiones y ubicación; `ai_publicidad` selecciona y compone hasta tres creatividades, devuelve HTML, registra una entrega/impresión por cada anuncio emitido y recibe los clics. El endpoint antiguo `/ads/serve` seguirá disponible para consumidores que prefieran JSON y confirmación de impresión separada.

La inspección de `main` confirma estos puntos de integración existentes:

- El cliente React concentra las llamadas HTTP en `web/src/api/ApiClient.ts`. Usa el prefijo `/api/v1` y espera respuestas OSAP con envoltura `success/request_id/data/error`.
- Ya existe `web/src/components/SponsorSlot.tsx`, que descarga `/sponsors.json` y muestra patrocinadores configurados estáticamente o un mensaje propio de reserva.
- El componente está utilizado en `web/src/pages/WorkPage.tsx` (`placement="work"`), `web/src/pages/ComposerDetailPage.tsx` (`placement="composer"`) y `web/src/pages/ComposersPage.tsx` (`placement="composers"`).
- `web/public/sponsors.json` define esos espacios estáticos. Sus claves `work`, `composer` y `composers` describen pantallas, **no** son los códigos de ubicación física que espera `ai_publicidad`.
- El API se compone en `src/osap/api/platform_app.py` con routers construidos mediante `build_*_router(ctx)`. `HttpContext.ok(...)` crea la envoltura estándar de OSAP.
- En desarrollo, Vite reenvía `/api` a `http://127.0.0.1:8001`. En producción, Nginx reenvía `/api/` a `osap_api` en `deploy/app.openmusicrepository.com.conf`.

Por tanto, **no basta con cambiar `sponsors.json`**: hoy el componente no llama al servicio publicitario, su diseño no representa directamente banners de 728×90 o 300×250 y el navegador no puede guardar la clave de servicio. La integración debe pasar por una fachada servidor-a-servidor en `osap-api`.

## 2. Arquitectura obligatoria

```text
Navegador React
  └─ POST /api/v1/ads/compose (mismo origen OSAP; respuesta text/html)
       └─ osap-api valida y reenvía la petición
            └─ HTTP interno → ai_publicidad /api/v1/ads/compose
                 Header: X-OSAP-Service-Token (solo servidor)
                 └─ HTML calculado + entrega/impresión de cada tarjeta

Enlace de cada anuncio
  └─ https://app.openmusicrepository.com/r/{token}
       └─ Nginx → ai_publicidad /r/{token} → registra clic y redirige

Contrato legado opcional:
  POST /ads/serve → JSON de una creatividad
  POST /events/impression → confirmación separada de ese anuncio
```

La llamada de entrega **no debe hacerse directamente desde React a `ai_publicidad`**. La cabecera `X-OSAP-Service-Token` es una credencial de servidor; nunca se incluye en JavaScript, variables `VITE_*`, HTML ni en una respuesta al navegador. Para `/compose`, la fachada de OSAP debe devolver una respuesta HTTP `text/html` sin la envoltura JSON habitual, de modo que el frontend inserte el fragmento que ya generó el servicio y no tenga que construir tarjetas ni recalcular posiciones.

El contrato actual de `ai_publicidad` usa esa cabecera estática compartida. No es automáticamente equivalente a los JWT de servicio de `osap-auth`; el valor enviado por OSAP debe coincidir con `AI_PUBLICIDAD_SERVICE_TOKEN` que valida el servicio publicitario.

## 3. Incorporar una fachada en osap-api

### 3.1 Configuración del backend

En `src/osap/bootstrap/configuration.py` añadir configuración de backend (servidor, no frontend), por ejemplo:

- `OSAP_ADS_BASE_URL`: dirección interna de `ai_publicidad`; si ambos procesos están en el mismo VPS, preferir `http://127.0.0.1:8305`.
- `OSAP_ADS_SERVICE_TOKEN`: mismo secreto que `AI_PUBLICIDAD_SERVICE_TOKEN` en `ai_publicidad`.

Añadir los campos al dataclass `Configuration` y al mapa `_CONFIG_FIELDS`, siguiendo el patrón actual. Añadir nombres vacíos o instrucciones a los ejemplos de configuración, nunca el secreto real. El secreto debe quedar en un archivo de entorno protegido del servicio systemd o en el mecanismo privado de secretos que ya utilice el despliegue de OSAP.

No se debe utilizar la URL pública del servicio como destino interno si se puede acceder por la red privada o localhost.

### 3.2 Router HTTP

Crear `src/osap/api/http/ads.py` con el patrón del proyecto:

- `build_ads_router(ctx: HttpContext) -> APIRouter`.
- `POST /api/v1/ads/compose`: valida el contexto de área/forma y ubicación, envía la petición al endpoint de `ai_publicidad` y devuelve exactamente el cuerpo HTML con `HTMLResponse` y `Content-Type: text/html`. No envolverlo en `ctx.ok`, ya que el cliente necesita insertar el fragmento de HTML producido por el servicio.
- Mantener opcionalmente `POST /api/v1/ads/serve` para una sola creatividad JSON y `POST /api/v1/ads/impression` para el flujo legado.
- Incluir `build_ads_router(ctx)` en `src/osap/api/platform_app.py`.
- Documentar errores de servicio no disponible mediante el formato de error OSAP.

La fachada debe usar un cliente HTTP de servidor con timeout corto y cerrado, controlar errores HTTP/JSON y no filtrar cabeceras ni secretos. No registrar el token ni la URL privada con credenciales en los logs.

**No reintentar automáticamente `POST /ads/serve`** si se pierde la respuesta: cada llamada válida crea una entrega histórica y el reintento puede producir otra. Ante timeout o error de `ai_publicidad`, la fachada debe devolver un error de disponibilidad bien definido; el frontend lo trata como fallo publicitario, no como fallo de la navegación. La confirmación de impresión es idempotente en el servicio de anuncios, por lo que se puede reportar como operación de mejor esfuerzo y no debe bloquear la página.

### 3.3 Contrato de petición

La fachada recibe el mismo JSON que `ai_publicidad` y conserva los códigos estables de página y ubicación. Ejemplo para un banner de escritorio en la ficha de una obra:

```json
{
  "application": "osap",
  "page": {
    "type": "work_detail",
    "entity_type": "work",
    "entity_id": "12345",
    "language": "es"
  },
  "placement": "header",
  "format": {
    "type": "responsive",
    "width": 728,
    "height": 90
  },
  "device": "desktop"
}
```

Para el banner móvil se solicitaría `width=320`, `height=50`, `device="mobile"`. Para los otros formatos: `300×250`, `160×600` y `200×200`. `width` y `height` deben enviarse juntos. El campo `format.type` describe el tipo de creatividad que se admite; las dimensiones corresponden al formato estándar del espacio.

La respuesta interna de `ai_publicidad` es JSON directo. OSAP la debe envolver con `ctx.ok(payload)` para respetar el contrato de `ApiClient`. Campos relevantes:

- `ad_id`, `impression_id`, `kind` (`commercial` o `house`).
- `title`, `body`, `image_url`, `alt_text`, `format`, `language`.
- `click_url`, que debe usarse en el enlace del anuncio, no sustituirse por el destino final.
- `ad_format_code`, `ad_format_name`, `ad_width`, `ad_height`, si se seleccionó un formato del catálogo.

### 3.4 Impresiones según el endpoint

Para `/ads/compose`, la petición es el acto de emitir el bloque: el servicio crea en la misma transacción una entrega y una impresión para cada tarjeta incluida en el HTML. No hace falta implementar una llamada adicional ni un endpoint de impresión para los anuncios de esa respuesta. Si el servicio devuelve `no-fill`, no crea impresiones.

El contrato legado `/ads/serve` sigue devolviendo un `impression_id` para una única creatividad y se puede confirmar por `POST /api/v1/ads/impression`, que la fachada reenvía a `ai_publicidad /api/v1/events/impression`. No mezclar ambos flujos.

## 4. Integración React

### 4.1 Cliente API

En `web/src/api/ApiClient.ts` añadir tipos TypeScript para el anuncio y métodos, usando las funciones `post<T>()` existentes. La página o componente no debe llamar a `fetch` directamente al backend publicitario.

Añadir un método dedicado para `POST /ads/compose` que devuelva el cuerpo como texto HTML, no como DTO JSON. El método genérico `ApiClient.post<T>()` interpreta la envoltura OSAP y no debe reutilizarse para una respuesta `text/html` sin adaptar su lectura. El frontend llama siempre al mismo origen OSAP; la fachada oculta las credenciales y la dirección interna del servicio publicitario.

El cliente de OSAP ya añade `/api/v1` a sus llamadas estándar. Para la ruta de composición, implementar explícitamente una lectura de texto y comprobar `response.ok` y `Content-Type`; no duplicar el prefijo y no enviar el token de servicio al navegador.

### 4.2 Componente de representación

Crear un componente pequeño `web/src/components/AdSlot.tsx` o refactorizar `SponsorSlot.tsx`, manteniendo el fallback estático hasta validar la integración. El componente no calcula las distribuciones ni genera el contenido interno de las tarjetas; eso ya lo hace `ai_publicidad`.

1. Recibir **dos conceptos separados**: el tipo de página/contexto y la ubicación física real de la ranura. No enviar `work`, `composer` o `composers` como `placement` publicitario.
2. Medir el espacio que la página haya reservado y solicitarlo con `mode="auto_area"`; usar `fixed_format` solo donde el diseño exija expresamente un tamaño concreto.
3. Llamar a la fachada del mismo origen OSAP, comprobar el estado HTTP y que la respuesta sea `text/html`, y colocar el fragmento devuelto dentro del contenedor publicitario. No construir una tarjeta por anuncio en React ni llamar directamente a `ai_publicidad`; el fragmento sale de la plantilla controlada del backend y sus textos/URLs ya se escapan allí.
4. El contenedor externo debe estar limitado al área solicitada y no puede cambiar el ancho de la columna a espaldas del diseño de página. El servicio solo devuelve tarjetas que caben en las dimensiones recibidas.
5. Si el servicio falla, responde con un error o el fragmento contiene `data-layout-status="no-fill"`, conservar el fallback de `SponsorSlot`/`sponsors.json`. La publicidad no debe bloquear la navegación de OSAP.
6. Para `/compose`, no enviar una petición extra de impresión: la emisión del bloque registra una impresión por cada tarjeta. El flujo legado `/serve` conserva la confirmación independiente.
7. Mantener la ranura identificable y accesible, y etiquetarla como «Publicidad» o «Patrocinado». Los enlaces ya incluidos por la plantilla usan `click_url`, que registra el clic y redirige al destino guardado.

Los anuncios propios se distinguen en el HTML por `data-kind="house"` (y en el contrato JSON legado por `is_house_ad=true`); se contabilizan igual, pero deben separarse de las métricas comerciales.

### 4.3 Contexto y ubicaciones

El componente actual tiene tres instancias, ubicadas al final del contenido de la página correspondiente:

| Código actual del componente | Contexto API recomendado | Estado de la ubicación |
|---|---|---|
| `SponsorSlot placement="work"` | `page.type="work_detail"`, `entity_type="work"` | Actualmente al final de la ficha; definir `content_bottom` si no se cambia de lugar. |
| `SponsorSlot placement="composer"` | `page.type="person_detail"`, `entity_type="person"` | Actualmente al final de la ficha de compositor; ubicación física por definir como `content_bottom`. |
| `SponsorSlot placement="composers"` | `page.type="search_results"` (o código estable acordado), sin entidad concreta | Actualmente al final del listado; definir `content_bottom`. |

**Importante antes de activar la campaña preparada:** el seed de `ai_publicidad` asigna reglas de ubicación `header`, `content_top`, `sidebar` y `content_inline` a las cuatro creatividades. Esos códigos no coinciden con los tres usos actuales de `SponsorSlot`, que son claves de pantalla. En el frontend revisado no hay todavía un componente que materialice las cuatro ranuras físicas para esos tamaños. Para mostrar los cuatro anuncios como se diseñaron, se deben añadir las ranuras reales en esas ubicaciones, o cambiar de manera deliberada las reglas de la campaña y los tamaños para que coincidan con las ranuras que OSAP implemente. No hay que poner el mismo código en ambos campos para eludir esta diferencia.

Orden de integración recomendado:

1. Añadir una ranura de cabecera con variantes 728×90 / 320×50.
2. Añadir una ranura 300×250 en la zona de contenido superior.
3. Añadir la ranura vertical 160×600 solo en una columna que disponga realmente de al menos 160 px.
4. Añadir la ranura cuadrada 200×200 dentro del contenido.
5. Conservar los tres `SponsorSlot` actuales como respaldo hasta confirmar todas las nuevas ubicaciones. Se pueden migrar después a `AdSlot` cuando sus códigos de ubicación física estén acordados.

No colocar un formato de 160×600 en una columna estrecha móvil. El catálogo lo clasifica como ubicación vertical/audiovisual, pero el anuncio de campaña inicial es textual: un formato de espacio no proporciona vídeo ni reproductor por sí mismo.

## 5. Clicks: exponer únicamente la ruta de redirección

Las creatividades devuelven `click_url` construida con `AI_PUBLICIDAD_PUBLIC_BASE_URL` más `/r/{token}`. Para el despliegue en el mismo dominio OSAP se propone:

- `AI_PUBLICIDAD_PUBLIC_BASE_URL=https://app.openmusicrepository.com`.
- Mantener `ai_publicidad` escuchando en `127.0.0.1:8305` (no en una interfaz pública).
- Añadir en Nginx una ubicación específica `location ^~ /r/` que reenvíe a `http://127.0.0.1:8305`, con cabeceras de proxy normales. Debe ir antes del fallback general de la SPA.
- No modificar `location /api/`: esa ruta continúa encaminada a `osap-api`, que actúa como fachada autenticada para solicitar anuncios e impresiones.

Ejemplo orientativo para la configuración del servidor HTTPS existente de `app.openmusicrepository.com`:

```nginx
location ^~ /r/ {
    proxy_pass http://127.0.0.1:8305;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

Este bloque solo expone la ruta pública de clics. No añadir un proxy público para `/admin`, `/api/v1/admin`, `/docs` ni `/openapi.json` de `ai_publicidad`: la autorización de mantenimiento todavía está pendiente. Antes de aplicar cambios, validar la sintaxis de Nginx y revisar el fichero completo de producción.

## 6. Despliegue por etapas

### Etapa A — servicio publicitario listo

1. Configurar `ai_publicidad` con su base independiente `OSAP_PUBLICIDAD` y migrar con `python -m alembic upgrade head`.
2. Configurar `AI_PUBLICIDAD_ENV=production`, `AI_PUBLICIDAD_DATABASE_URL` o el `osap.toml` privado, `AI_PUBLICIDAD_SERVICE_TOKEN` y `AI_PUBLICIDAD_PUBLIC_BASE_URL=https://app.openmusicrepository.com`.
3. Ejecutar las cargas idempotentes después de verificar el destino: `python scripts/seed_house_ads.py --apply` y `python scripts/seed_omr_campaign.py --apply`.
4. Ejecutar el servicio detrás de systemd/Uvicorn enlazado a localhost, por ejemplo en el puerto 8305. No publicar el panel `/admin`.

### Etapa B — fachada OSAP

1. Añadir las variables privadas `OSAP_ADS_BASE_URL=http://127.0.0.1:8305` y `OSAP_ADS_SERVICE_TOKEN` al entorno del servicio `osap-api`; el token debe coincidir con el configurado en `ai_publicidad`.
2. Implementar `src/osap/api/http/ads.py`, registrar el router en `platform_app.py` y exponer únicamente las rutas de entrega e impresión requeridas por el frontend.
3. Añadir pruebas de contrato, errores de servicio y respuesta OSAP envuelta.

### Etapa C — React y proxy

1. Añadir los contratos y métodos a `ApiClient.ts`.
2. Crear el componente de anuncio con renderizado por tamaño, confirmación de impresión y fallback.
3. Implementar las ranuras físicas y hacer coincidir sus códigos con las reglas de campaña.
4. Añadir la ruta Nginx `/r/`, validar `nginx -t`, recargar Nginx y desplegar los bundles del frontend.
5. Probar primero en staging; no exponer la administración.

## 7. Pruebas de aceptación

### Pruebas del backend OSAP

- La petición pública de la fachada responde con la envoltura `success=true` y los datos esperados.
- OSAP envía `X-OSAP-Service-Token` desde servidor y nunca lo devuelve al cliente.
- Si el servicio remoto falla o tarda más que el timeout, la búsqueda, ficha de obra y ficha de compositor siguen funcionando.
- Un fallo de `POST /ads/serve` no provoca varios reintentos que generen entregas adicionales.
- `/ads/compose` crea una impresión por anuncio incluido al emitir HTML y no necesita llamadas posteriores; si se repite la misma petición, cada respuesta emitida genera sus propios registros.

### Pruebas del frontend

- Una respuesta HTML válida queda insertada en el área reservada, respeta las dimensiones, usa `click_url` y el servicio registra inmediatamente una impresión por tarjeta emitida.
- Un error, una respuesta inválida o una petición sin inventario muestra el fallback ya existente.
- El banner 728×90 no desborda escritorio; el 320×50 se emplea en móvil.
- 300×250, 160×600 y 200×200 solo se insertan en áreas cuyo tamaño real los admite.
- Las páginas funcionan con JavaScript publicitario deshabilitado o con `ai_publicidad` desconectado.

### Prueba de extremo a extremo

| Contexto solicitado | Resultado esperado |
|---|---|
| `header`, escritorio, 728×90 | `ad_format_code=leaderboard_728x90` |
| `header`, móvil, 320×50 | `ad_format_code=mobile_banner_320x50` |
| `content_top`, 300×250 | `ad_format_code=medium_rectangle_300x250` |
| `sidebar`, escritorio, 160×600 | `ad_format_code=wide_skyscraper_160x600` |
| `content_inline`, 200×200 | `ad_format_code=square_200x200` |
| Servicio detenido | OSAP sigue siendo navegable y muestra el fallback estático |

Para cada entrega válida, confirmar que el navegador recibe un `impression_id`, que el evento se cuenta una sola vez y que el clic abre `/r/{token}` con una redirección al destino guardado.

## 8. Rollback

Si aparecen errores visuales o de red:

1. Revertir la inserción de `AdSlot` o desactivar la llamada de anuncios desde el frontend.
2. Mantener `SponsorSlot` y `sponsors.json` como reserva.
3. Retirar la ubicación Nginx `/r/` si la redirección está fallando.
4. Dejar el servicio y su histórico independientes; no borrar `ad_deliveries` ni `ad_events` como método de rollback.

El rollback de la integración visual no requiere cambios en la base de datos del catálogo OSAP ni en la base publicitaria.

## 9. Criterio para dar por integrada la aplicación

La integración se considera completa cuando el router de fachada y el cliente React están implementados, las cuatro ubicaciones tienen correspondencia física y de segmentación, la confirmación de impresión es idempotente, la redirección pública funciona y las pruebas de aceptación pasan en staging. Hasta entonces, `ai_publicidad` debe considerarse un servicio separado preparado para integración, no una fuente que el frontend ya esté consumiendo.
