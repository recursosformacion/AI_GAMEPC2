# Documentación de OSAP API

Esta carpeta reúne la documentación de referencia del repositorio OSAP API (AI_GAMEPC2): arquitectura implementada, contratos HTTP, integración con servicios, desarrollo, operación, auditorías y planificación de cambios.

La web pública de OpenMusicRepository es https://app.openmusicrepository.com/.

## Cómo interpretar los documentos

Cada documento debe indicar su estado y fecha de revisión:

- **VIGENTE**: describe el comportamiento implementado y contrastado con código o pruebas.
- **PLAN**: diseño futuro todavía no implementado.
- **AUDITORÍA**: análisis de una versión o recorrido concreto; sus hallazgos no se presumen vigentes sin revalidarlos.
- **HISTÓRICO**: conserva decisiones o diseños anteriores; no debe utilizarse como guía operativa actual.

El código, las migraciones y las pruebas de la versión desplegada son la evidencia primaria. Una descripción de arquitectura o una plantilla de configuración no demuestra por sí sola que producción esté configurada de ese modo.

## Índices

- [Documentación de OSAP](osap/README.md) — índice detallado por estado y área.
- [Arquitectura actual 6.x](osap/current-architecture.md) — arquitectura implementada y límites de los servicios.
- [Auditoría del índice](osap/auditoria-index-2026-11-24.md) — incidencia confirmada de asociación entre obras numeradas.
- [Manual de usuario](../web/public/manual/es/index.html) — versión maestra en castellano; las traducciones se revisan después de cerrar el texto español.
- [Versionado](osap/versioning.md) — clasificación A/B/C y reglas de entrega.
- [Entorno de desarrollo](osap/dev-environment.md) — Apache local, frontend, backend y servicios.
- [Scripts](osap/scripts.md) — herramientas operativas y de mantenimiento.
- [Matriz M2M](osap/m2m-service-matrix.md) — autenticación entre API, Auth, Storage y Support.
- [Configuración actual](osap/configuration-current.md) — precedencia, OIDC, M2M e integraciones.
- [Modelo V6 Work–Resource–File](osap/v6-work-resource-model.md) — PLAN, no describe el esquema desplegado.
- [Auditoría de identidad y materiales](osap/v6-api-material-identity-audit.md) — AUDITORÍA que debe contrastarse con la implementación actual antes de tomar decisiones.

## Límites entre repositorios

- Este repositorio documenta la aplicación web, la API y su coordinación con los servicios.
- Auth, Storage y Support mantienen sus contratos internos, migraciones, configuración y runbooks en sus propios repositorios. Aquí se documentan las integraciones y los contratos que consume OSAP API; no se duplican manuales internos completos.
- Chorus es un producto y repositorio independiente. Su documentación y su despliegue no forman parte de la documentación operativa de OSAP API.
- OMR es el repositorio musical visible para el usuario. Los datos integrados procedentes de PDMX se consultan como parte de OMR; PDMX no es una fuente independiente que el usuario deba configurar o consultar.

## Reglas de mantenimiento

1. No presentar propuestas, auditorías antiguas ni ejemplos como comportamiento vigente.
2. No documentar secretos, contraseñas, tokens reales ni datos personales.
3. Cada cambio de endpoint debe actualizar el contrato, los ejemplos y las pruebas afectadas.
4. Cada cambio de interfaz debe actualizar primero el manual español y después las traducciones.
5. Los procedimientos de producción deben distinguir explícitamente lectura, escritura, backup, migración, despliegue y rollback.
