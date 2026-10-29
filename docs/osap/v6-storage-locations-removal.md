# Decisión V6: retirada de `storage_locations`

**Fecha:** 2026-10-29  
**Estado:** decisión de arquitectura para V6; documentación únicamente. No se modifica el esquema ni el código actual.

## Decisión

`storage_locations` debe desaparecer del modelo y de la implementación objetivo de OSAP V6. No se conservará como entidad del catálogo ni como mecanismo operativo permanente.

La razón de dominio es que OSAP no dispone actualmente de una herramienta que demuestre que dos proveedores han entregado exactamente el mismo fichero. Por tanto, un fichero obtenido de otro proveedor no se tratará como una segunda ubicación del mismo `File`: se incorporará como otro `Resource` con su propio `File`, salvo que un proceso futuro de verificación de identidad de bytes demuestre de forma explícita que se trata del mismo objeto y se decida cambiar esta regla. La coincidencia de título, URL, nombre, formato o contenido musical no demuestra identidad binaria.

## Evidencia de la auditoría actual

- El esquema actual impone `UNIQUE (file_id, provider_id)`, lo que permite como máximo una ubicación por proveedor para cada File.
- `FilePublisher.publish()` crea o reutiliza la ubicación del proveedor indicado; el esquema permite otra fila si el mismo File se publica en otro proveedor.
- Los datos auditados en local y producción muestran cero Files con más de una ubicación y un máximo de una ubicación por File.
- Por tanto, la cardinalidad observada es `File 1:1 StorageLocation`, aunque el esquema permita `File 1:N StorageLocation`.

La tabla interviene hoy en la resolución de disponibilidad y en las descargas. Esta observación describe el contrato heredado, no justifica conservarlo en V6.

## Modelo objetivo

- `Work` identifica la obra musical canónica.
- `Resource` identifica una realización musical concreta y pertenece a una Work.
- `File` identifica un artefacto digital de un único Resource y apunta directamente a la ubicación de su objeto físico.
- Un Resource puede tener varios Files cuando sean artefactos distintos de la misma realización, por ejemplo PDF, MXL y MIDI. No se exige disponer de todos.
- Un objeto físico no se comparte entre Files ni entre Resources. No se introduce `Blob`.
- La adquisición de un fichero desde otro proveedor crea su propio Resource y File cuando no existe verificación fiable de identidad binaria.

## Trabajo necesario para retirarla

1. Cambiar el contrato de almacenamiento para que `File` mantenga una referencia directa y estable al objeto físico.
2. Sustituir las consultas que calculan disponibilidad a partir de `storage_locations`.
3. Adaptar publicación, subida, descarga, URL de acceso, administración y recuperación de errores para operar sin esa tabla.
4. Definir la política de almacenamiento y copias de seguridad dentro del servicio Storage, sin exponer réplicas como entidades del catálogo.
5. Migrar las referencias físicas existentes a la referencia directa de `File`, validando que cada objeto se puede resolver y leer.
6. Añadir pruebas que demuestren subida, publicación, descarga, disponibilidad, fallo y recuperación sin `storage_locations`.
7. Eliminar tabla, entidad, repositorio, migraciones y consumidores heredados solo después de superar las pruebas en un entorno de ensayo.

## Condición de aceptación

La retirada se considera completa cuando ninguna ruta de código, migración activa, consulta, endpoint, tarea ni interfaz depende de `storage_locations`; cada File almacenado resuelve directamente su objeto; y las pruebas de disponibilidad, descarga y recuperación pasan sin esa tabla.

**Alcance de este cambio documental:** no se ha modificado código, base de datos ni configuración de almacenamiento.
