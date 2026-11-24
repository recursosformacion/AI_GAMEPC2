# Base de datos actual de OSAP API

**Estado:** procedimiento vigente; inventario físico pendiente de generar y contrastar.  
**Revisión:** 2026-11-24.

## 1. Propiedad y límites

La BD de OSAP API almacena estado propio de la aplicación: configuración operativa, índice federado, trabajos/sesiones, analítica, sugerencias, colaboraciones y datos de las funciones que pertenecen a este servicio.

No es la fuente autoritativa de:
- identidad, credenciales o clientes OAuth (osap-auth);
- catálogo maestro de obras, personas, atribuciones y recursos musicales (osap-storage);
- membresías, pagos y operaciones de apoyo (osap-support).

Las bases son independientes. No hacer JOIN entre esquemas de servicios; usar contratos HTTP autenticados.

## 2. Fuente de verdad del esquema

El esquema se construye y evoluciona desde el código de persistencia y las migraciones versionadas. Entre los puntos principales:

- `src/osap/infrastructure/state/op_store.py`: estado operativo e índice.
- `src/osap/infrastructure/state/resolution_store.py`: sesiones y resultados de resolución.
- Stores de Amigos, contribuciones, actividad y otros dominios en `src/osap/infrastructure/`.
- Migraciones versionadas de API, cuando existan, y sus pruebas.

No asumir que el antiguo documento `docs/osap-api-database.md` contiene todas las tablas: es un snapshot parcial del 2026-09-06.

## 3. Generar inventario físico de solo lectura

Se ha añadido `script/export_api_schema_inventory.py`. Consulta únicamente `information_schema` y genera tablas, columnas, índices y claves foráneas. No lee filas de negocio ni modifica el esquema.

En desarrollo, seleccionar explícitamente el entorno y confirmar el nombre exacto de la BD:

```powershell
$env:OSAP_DEPLOYMENT = "development"
python script/export_api_schema_inventory.py --confirm-database <nombre-exacto> --output docs/osap/database-inventory-dev.md
```

Para producción, la consulta está bloqueada salvo que se autorice expresamente:

```powershell
python script/export_api_schema_inventory.py --confirm-database <nombre-exacto> --allow-production-read --output docs/osap/database-inventory-prod.md
```

El argumento debe coincidir exactamente con `osap_api_db_name` de la configuración activa. El script abre una transacción `READ ONLY`, ejecuta SELECT sobre `information_schema`, hace rollback y cierra la conexión. No imprime usuario, contraseña ni host.

## 4. Qué falta para cerrar el inventario

1. Generar el inventario de desarrollo.
2. Compararlo con los DDL del código, migraciones y pruebas.
3. Generar el inventario de producción con autorización de lectura.
4. Comparar tablas, columnas, índices, claves y estado de migraciones.
5. Documentar divergencias concretas y su migración de corrección.
6. Incorporar al repositorio un inventario generado y fechado, sin credenciales ni datos de negocio.

Hasta completar esa comparación, no afirmar que el número de tablas o la versión del esquema de producción coincide con desarrollo.

## 5. Seguridad

- No documentar credenciales ni valores reales de configuración.
- No ejecutar DDL, migraciones, backfills ni rebuilds como parte de una auditoría de esquema.
- No inferir el estado de producción a partir del esquema local.
- Cualquier cambio de producción requiere backup, revisión de migración y rollback explícito.
