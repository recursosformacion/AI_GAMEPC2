# Arquitectura actual de OSAP API

**Estado:** VIGENTE, revisión documental 2026-11-24.  
**Versión visible en la web pública:** 6.4.1.  
**Ámbito:** arquitectura del código de OSAP API y sus contratos con los servicios del ecosistema.  
**No equivale a:** una certificación de que todos los servicios o todas las variables de producción estén correctamente configurados.

## 1. Producto y responsabilidades

OpenMusicRepository es la aplicación pública que permite localizar obras musicales, consultar compositores y fichas de obra, comparar representaciones y acceder a recursos disponibles o a sus proveedores originales.

OSAP API coordina la experiencia pública y la búsqueda federada. No es la base autoritativa de todos los datos ni el almacenamiento físico de todos los ficheros.

| Componente | Responsabilidad |
|---|---|
| OSAP API (este repositorio) | API pública, aplicación web, búsqueda federada, índice de búsqueda, páginas públicas SEO y coordinación de servicios |
| osap-auth | Identidad de usuario, login, tokens de usuario y emisión de tokens M2M |
| osap-storage | Datos maestros del catálogo, recursos musicales y acceso a ficheros |
| osap-support | Donaciones, membresías, reconocimientos y operaciones de apoyo |
| Proveedores externos | Catálogos y fuentes de metadatos/recursos consultados por adaptadores |

La SPA pública debe consumir OSAP API. No debe acceder directamente a bases de datos ni a endpoints internos protegidos de Auth, Storage o Support.

## 2. Aplicación web y API

### Cliente web

- Código React y TypeScript en `web/src/`.
- Build estático generado en `web/dist/`.
- Manual de usuario en `web/public/manual/`.
- La aplicación publicada se sirve en https://app.openmusicrepository.com/.

En desarrollo, la guía operativa describe Apache/XAMPP sirviendo `web/dist` y enviando las peticiones API al backend FastAPI. Por tanto, modificar componentes React no actualiza el cliente servido hasta reconstruir `web/dist`.

### Backend

- Aplicación FastAPI y composición de servicios en `src/osap/api/`.
- Routers HTTP en `src/osap/api/http/`.
- Contratos Pydantic en `src/osap/api/contracts/`.
- Lógica de plataforma en `src/osap/api/platform/`.
- Integraciones e infraestructura en `src/osap/infrastructure/`.
- Wiring y configuración en `src/osap/bootstrap/`.

La aplicación de plataforma se crea mediante la factory `src.osap.api.platform_app:create_platform_app`. Antes de documentar una ruta como contrato estable, comprobar su router, modelo de entrada/salida, dependencias de autenticación y pruebas.

## 3. Recorridos públicos principales

### Búsqueda

1. El cliente envía una petición a `POST /api/v1/searches`.
2. API crea una búsqueda y devuelve un identificador y estado.
3. El cliente consulta `GET /api/v1/searches/{search_id}` hasta obtener el resultado.
4. Los resultados incluyen Work, representación principal, representaciones alternativas, puntuación, evidencias y relaciones cuando están disponibles.

El contrato actual se define en `src/osap/api/contracts/search.py`. Entre los criterios admitidos figuran título, compositor, catálogo, instrumentación, idioma, formatos, proveedores, voces y géneros.

### Ficha y acceso a una representación

Las rutas de representación incluyen:

- `GET /api/v1/representations/{representation_id}`: ficha del material.
- `GET /api/v1/representations/{representation_id}/probe`: comprueba si el servidor puede leer un fichero externo.
- `GET /api/v1/representations/{representation_id}/download`: descarga o sirve el fichero; `?view=1` solicita visualización inline.

El acceso depende del origen. Un fichero OMR se resuelve a través de Storage; un recurso externo puede abrirse en el proveedor o ser leído por el servidor si el proveedor lo permite. Los retos anti-bot pueden obligar al navegador a abrir la fuente original. Que una representación aparezca en el catálogo no garantiza que el fichero esté disponible en ese momento.

Las cuotas de descarga se aplican a las descargas OMR que correspondan; la visualización inline y los proveedores externos no deben confundirse con una descarga facturable OMR.

### Páginas públicas indexables

OSAP API genera páginas HTML públicas para obras, compositores y representaciones. Las rutas canónicas y heredadas se gestionan en `src/osap/api/http/seo.py`; las plantillas y vistas asociadas viven en `src/osap/api/seo/`.

Las rutas SEO no son equivalentes a los endpoints JSON de `/api`. La SPA y el HTML indexable pueden tener mecanismos de renderizado diferentes; las pruebas deben cubrir ambos.

## 4. Búsqueda federada y proveedores

La búsqueda combina el índice local con adaptadores de proveedores. En el código actual, la búsqueda general declara proveedores por defecto `imslp`, `cpdl`, `rism` y `omr`; el índice local se consulta además como proyección federada.

El indexador `script/index_works.py` mantiene `index_works`, `index_representations` e información auxiliar. Lee datos de OMR/Storage y CPDL ya materializado en Storage, y puede incorporar IMSLP, Mutopia y MusicBrainz según los parámetros y fuentes disponibles. La cobertura exacta depende de la última ejecución del indexador y de los proveedores activos.

OMR es el repositorio propio que se presenta al usuario. Los datos históricos integrados se consultan a través de OMR; no se configura ni consulta PDMX como repositorio independiente.

## 5. Modelo de datos actual y destino V6

### Modelo actual

El código y las bases de datos actuales conservan estructuras heredadas de Work, Representation, relaciones Work–Resource, Files y un índice federado independiente. Los DTO de búsqueda todavía exponen `representation` y `representations`.

La Work del índice no debe confundirse automáticamente con la Work canónica de Storage. Los materiales externos federados tampoco deben tratarse como Files propios de Storage.

### Destino V6 (PLAN)

La remodelación prevista establece:

```
Work (obra canónica)
  └── Resource (edición, arreglo, realización o referencia)
        └── File (artefacto digital concreto)
```

La Work concentra identidad y autoría intelectual; Resource describe una realización y su procedencia/derechos; File identifica un artefacto digital. La migración completa, el nuevo contrato y el corte coordinado todavía requieren su propio cierre y validación. No interpretar este diagrama como esquema de producción ya migrado.

Documentos de planificación: [modelo V6](v6-work-resource-model.md), [matriz de campos](v6-work-field-consumer-matrix.md), [contrato de identidad](v6-work-dto-identity-contract.md) y [auditoría de materiales](v6-api-material-identity-audit.md).

## 6. Autenticación entre servicios

osap-auth es el emisor central de tokens de servicio OAuth2 `client_credentials`. Cada llamante usa un cliente propio, con scopes y audiencias limitados al receptor. Los service tokens no representan a un usuario.

La integración administrativa API → Support utiliza un cliente independiente:

- audiencia: `osap-support`;
- scope: `support:admin`;
- variables API: `OSAP_SUPPORT_ADMIN_CLIENT_ID` y `OSAP_SUPPORT_ADMIN_CLIENT_SECRET`;
- provisionamiento en Auth: `scripts/provision_support_admin_client.py`.

La integración está implementada y cubierta por pruebas de código. La configuración y el smoke test HTTP de producción deben comprobarse por separado. No reutilizar las credenciales de API general, Storage ni Chorus.

En Support deben mantenerse separadas las audiencias de usuario y servicio: los tokens de usuario conservan `auth_audience=osap-api`; los tokens de servicio se validan con `service_audience=osap-support`.

Véase [Matriz M2M](m2m-service-matrix.md).

## 7. Configuración, desarrollo y operación

- Entorno local, Apache, build y arranque: [dev-environment.md](dev-environment.md).
- Versiones y clasificación A/B/C: [versioning.md](versioning.md).
- Scripts: [scripts.md](scripts.md), pendiente de depurar referencias históricas.
- Configuración: [configuration-v1.md](../configuration-v1.md), pendiente de contrastar cada clave con el código actual.
- Persistencia de API: [osap-api-database.md](../osap-api-database.md), pendiente de auditoría integral de tablas y migraciones.

No ejecutar una migración por el mero hecho de que aparezca documentada. Antes de cualquier operación de producción hay que identificar la base de datos efectiva, revisar backup, migraciones aplicadas y rollback.

## 8. Evidencia y límites de esta revisión

Esta revisión se ha contrastado con el código de búsqueda, contratos, SEO, representación, configuración M2M y el manual versionado en GitHub. La web pública mostraba el pie de versión 6.4.1 durante la inspección del 2026-11-24.

No se ha realizado desde este documento una prueba autenticada de usuario, una escritura en producción, una migración ni un despliegue. La verificación funcional completa requiere probar los flujos internos con una cuenta de usuario de prueba y confirmar las dependencias reales desplegadas.
