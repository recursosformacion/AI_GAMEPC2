# Índice de documentación de OSAP API

**Revisión:** 2026-11-24.  
**Repositorio:** recursosformacion/AI_GAMEPC2 (OSAP API y cliente web).  
**Estado:** índice de trabajo; los documentos marcados como PLAN, AUDITORÍA o HISTÓRICO no describen necesariamente producción.

## 1. Documentación vigente y operativa

| Documento | Uso | Estado |
|---|---|---|
| [Entorno de desarrollo](dev-environment.md) | Apache/XAMPP, build SPA, uvicorn, servicios locales y modo de solo lectura | VIGENTE, revisar tras cambios de infraestructura |
| [Versionado](versioning.md) | Clasificación A/B/C, coherencia de versiones y reglas de publicación | VIGENTE |
| [Scripts](scripts.md) | Inventario y precauciones de scripts de API | VIGENTE, inventario en script/README.md |
| [Matriz M2M](m2m-service-matrix.md) | Clientes, audiencias y scopes entre servicios | VIGENTE CON CONFIGURACIÓN DE PRODUCCIÓN PENDIENTE DE VERIFICAR |
| [Base de datos de API](../osap-api-database.md) | Esquema y persistencia de API | AUDITORÍA PENDIENTE |
| [Configuración actual](configuration-current.md) | Loader, precedencia, OIDC, M2M e integraciones | VIGENTE |
| [Configuración v1](../configuration-v1.md) | Etapa anterior; contiene valores y reglas obsoletos | HISTÓRICO — NO USAR |

## 2. Arquitectura y contratos actuales

- [Arquitectura actual 6.x](current-architecture.md) — VIGENTE, contrastada con el código y los contratos de la línea 6.x.
- [Mapa de rutas API](api-route-map.md) — VIGENTE, familias de routers, endpoints de referencia y aliases SEO.
- [Auditoría del índice 2026-11-24](auditoria-index-2026-11-24.md) — incidencia confirmada de una representación IDP 2 asociada a IDP 3; reparación de datos pendiente de traza de solo lectura.

La arquitectura vigente describe el código de la línea 6.x: aplicación React servida como build estático, backend FastAPI, API pública consumida por la SPA e integración autenticada con Auth, Storage y Support.

El documento [Architecture Book V2.2](v2/osap-architecture-book.md) y los documentos de v1/, v2/ y v3/ conservan la evolución del diseño anterior. **Son HISTÓRICOS**, no la fuente de verdad de la arquitectura 6.x. Se mantienen para trazabilidad hasta completar su clasificación y archivo.

No usar el antiguo libro V2.2 como descripción de la arquitectura desplegada.

## 3. Integración entre servicios

- [Matriz M2M](m2m-service-matrix.md): contrato de llamadas y separación de credenciales.
- Auth, Storage y Support mantienen sus runbooks, migraciones y configuración interna en sus repositorios respectivos.
- La configuración real de producción solo se considera verificada después de comprobar el servicio desplegado y su comportamiento HTTP; el código y las plantillas no bastan.

## 4. V6 — PLAN, todavía no implementado como modelo de producción

Los documentos siguientes describen la remodelación Work → Resource → File y sus impactos. No deben utilizarse para interpretar el esquema actual como si la migración ya estuviera ejecutada:

- [Modelo Work–Resource–File](v6-work-resource-model.md).
- [Matriz de consumidores de Work](v6-work-field-consumer-matrix.md).
- [Contrato DTO e identidad](v6-work-dto-identity-contract.md).
- [Espacio personal y aportaciones](v6-user-workspace-contributions.md).
- [Integración Storage e índice](v6-storage-integration-index.md).
- [Feed del índice](v6-index-feed.md).
- [Retirada de StorageLocations](v6-storage-locations-removal.md).
- [Auditoría de identidad y materiales](v6-api-material-identity-audit.md).

La decisión de iniciar la implementación V6 requiere cerrar el inventario de columnas, consumidores, contratos, migración y validaciones. No se debe inferir que un documento de planificación autoriza escrituras o migraciones en producción.

## 5. Auditorías, incidencias y documentación histórica

- incidents/: informes de incidentes con fecha; válidos para el episodio descrito, no como diagnóstico actual.
- old/: investigación histórica y documentación obsoleta.
- adr/: decisiones de arquitectura. Una ADR registra una decisión en su contexto temporal; comprobar si ha sido sustituida por otra posterior.
- v1/, v2/, v3/: documentación de versiones anteriores, en proceso de clasificación como histórica.

## 6. Manual público

El manual de usuario vive en web/public/manual/. El castellano es el texto maestro. La revisión debe contrastar cada instrucción con la interfaz actual y las operaciones reales; las traducciones no se consideran correctas solo por existir.

## 7. Regla de actualización

Cuando cambie una funcionalidad:

1. actualizar pruebas y contrato de API;
2. actualizar este índice si cambia el estado o la ubicación de la documentación;
3. actualizar la guía española si afecta al usuario;
4. revisar las traducciones después de cerrar el castellano;
5. registrar fecha, versión, evidencia y estado de verificación.
