# Integración de ai_publicidad en OSAP

**Estado del código:** INTEGRADA en OSAP API y React.  
**Estado de producción:** la configuración y la entrega publicitaria real no se han verificado en esta auditoría.  
**Revisión:** 2026-11-24.  
**Repositorios:** [AI_GAMEPC2 (OSAP)](https://github.com/recursosformacion/AI_GAMEPC2) y [ai_publicidad](https://github.com/recursosformacion/ai_publicidad).

## 1. Arquitectura vigente

El navegador nunca llama directamente a ai_publicidad ni recibe el secreto del servicio.

```text
React / AdSlot
  └─ POST /api/v1/ads/compose (mismo origen OSAP; recibe HTML)
       └─ OSAP API / http/ads.py
            └─ POST {OSAP_ADS_BASE_URL}/api/v1/ads/compose
                 Header: X-OSAP-Service-Token
                 └─ ai_publicidad compone HTML y registra la impresión por anuncio

Clic en una creatividad
  └─ https://app.openmusicrepository.com/r/{token}
       └─ Nginx → ai_publicidad /r/{token}
            └─ registra clic y redirige al destino guardado
```

La entrega de anuncios se realiza mediante composición dinámica de HTML. El endpoint legado JSON de una creatividad y la confirmación separada de impresión siguen siendo contratos distintos; no deben confundirse con el flujo actual /compose.

## 2. Estado de la implementación

### Backend OSAP

- Router: `src/osap/api/http/ads.py`.
- `POST /api/v1/ads/compose`: reenvía el JSON a ai_publicidad, añade `X-OSAP-Service-Token` desde el servidor y devuelve el HTML como `HTMLResponse`.
- `POST /api/v1/ads/impression`: fachada para el evento de impresión explícito del contrato legado.
- La fachada devuelve `503` si falta configuración o ai_publicidad no responde, y `502` si la respuesta no es HTML.
- Las respuestas HTML llevan `Cache-Control: no-store`.

### Configuración de OSAP API

| Variable | Uso |
|---|---|
| `OSAP_ADS_BASE_URL` | URL interna de ai_publicidad |
| `OSAP_ADS_SERVICE_TOKEN` | Secreto compartido servidor-a-servidor |
| `OSAP_ADS_WEB_BASE` | Base pública del servicio publicitario |
| `OSAP_ADS_TIMEOUT_SECONDS` | Timeout de la llamada |

El token debe coincidir con el valor que valida ai_publicidad. No es un JWT de usuario ni un token M2M emitido por osap-auth. Nunca incluirlo en `VITE_*`, HTML, JavaScript, respuestas API o repositorios.

### Frontend React

El componente `web/src/components/AdSlot.tsx`:

- mide el área real con `ResizeObserver`;
- envía aplicación, tipo de página, entidad, idioma, ubicación, dispositivo, dimensiones y máximo de anuncios;
- llama a `apiClient.composeAd()`, que consume la fachada OSAP;
- inserta el fragmento HTML recibido;
- utiliza `SponsorSlot` como fallback si no hay inventario, la respuesta indica `no-fill` o el servicio falla.

Ubicaciones actuales:

| Página | pageType | placement | fallback |
|---|---|---|---|
| Ficha de obra | `work_detail` | `content_inline` | `work` |
| Ficha de compositor | `person_detail` | `content_inline` | `composer` |
| Listado de compositores | `search_results` | `content_inline` | `composers` |

Los valores `work`, `composer` y `composers` son claves del fallback local; no deben confundirse con ubicaciones físicas que el motor publicitario pueda admitir.

## 3. Nginx y despliegue

El vhost versionado en `deploy/app.openmusicrepository.com.conf` contiene:

- `/r/{token}` → ai_publicidad en `127.0.0.1:8305`, para registrar clic y redirigir.
- `/publicidad/p` → panel administrativo de ai_publicidad, sin exponer el puerto interno.

La API OSAP se despliega por el procedimiento de su propio repositorio. ai_publicidad es otro servicio y debe tener su propio despliegue, configuración, base de datos y servicio systemd. No asumir que `script/deploy_all.ps1` de OSAP actualiza ai_publicidad.

El repositorio contiene la configuración de Nginx y los clientes, pero eso no demuestra que el servicio publicitario esté activo o que sus secretos efectivos coincidan en producción. Esa comprobación requiere probar el endpoint público y revisar la salud de ai_publicidad sin revelar el token.

## 4. Impresiones y clics

- Una respuesta de `/api/v1/ads/compose` registra en ai_publicidad una impresión por cada anuncio emitido.
- El flujo actual de `AdSlot` no necesita llamar después a `/api/v1/ads/impression`.
- Cada nueva composición es una nueva emisión; no reintentar automáticamente una petición fallida si eso pudiera generar entregas duplicadas.
- El clic utiliza `/r/{token}`; ai_publicidad registra el evento y redirige al destino guardado.
- La ruta de clic no debe revelar IDs internos ni aceptar destinos arbitrarios suministrados por el navegador.

## 5. Pruebas de aceptación pendientes

1. Con ai_publicidad activo y con inventario, `/api/v1/ads/compose` devuelve HTML válido y registra una impresión por anuncio.
2. El navegador no recibe ni puede leer el service token.
3. Con `no-fill`, timeout, 503 o HTML inválido, el componente muestra SponsorSlot y el resto de la página sigue funcionando.
4. Un clic en una creatividad pasa por `/r/{token}`, registra el clic y redirige al destino esperado.
5. Verificar las ubicaciones de obra, compositor y listado de compositores, tanto en escritorio como en móvil.
6. Comprobar que la composición respeta las dimensiones del área y el máximo de anuncios.
7. Desconectar ai_publicidad en staging y comprobar que no bloquea búsqueda, fichas ni navegación.
8. Comprobar que la entrega no queda cacheada por navegador, proxy o CDN.

## 6. Rollback

Si la entrega falla:

1. Desactivar la llamada dinámica desde el frontend o retirar la configuración de Ads del backend.
2. Mantener `SponsorSlot` y `sponsors.json` como fallback local.
3. Si falla el click-through, retirar temporalmente la ruta Nginx `/r/` tras confirmar que no quedan creatividades activas apuntando a ella.
4. No borrar `ad_deliveries` ni `ad_events` como método de rollback.

El rollback visual no requiere cambios en el catálogo OSAP ni en su base de datos.

## 7. Fuente de verdad

- OSAP: `src/osap/api/http/ads.py`, `src/osap/bootstrap/configuration.py`, `web/src/components/AdSlot.tsx`, `web/src/components/SponsorSlot.tsx`, `web/src/api/ApiClient.ts`.
- Enrutamiento: `deploy/app.openmusicrepository.com.conf`.
- Servicio publicitario: repositorio ai_publicidad y su propia documentación.

Antes de afirmar que la integración funciona en producción hay que ejecutar las pruebas de aceptación contra el servicio desplegado. La presencia de los componentes y rutas en el código solo acredita que la integración está implementada.
