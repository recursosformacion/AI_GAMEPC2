# Separación OSAP ↔ Chorus

Fecha: 2026-11-18. Estado: **en preparación en dev**. No desplegado.

## Decisión

- OSAP conserva artículos generales y sus servicios de identidad, repertorio,
  recursos y ficheros.
- Chorus es la autoridad única sobre grupos, miembros, secciones y artículos
  de grupo.
- No se sincronizan grupos. OSAP no consulta grupos de Chorus y Chorus no
  consulta grupos de OSAP.
- `osap-auth` sigue siendo el proveedor de identidad.
- Chorus puede seguir usando OSAP para obras, recursos y ficheros.

## Inventario (dev)

| Funcionalidad | Antes | Ahora |
| --- | --- | --- |
| Grupos y pertenencias | OSAP `amigos_groups` + sync en Chorus | Chorus `groups` / `group_members` |
| Secciones y catálogo | OSAP `amigos_group_catalog` | Chorus `group_sections` |
| Artículos de grupo | OSAP `amigos_articles` (`scope=group`) | Chorus `group_articles` |
| Medios de artículos | OSAP `amigos_media` | Chorus `group_article_media` |
| Artículos generales | OSAP | OSAP (sin cambios) |
| Agenda interna de grupos | Chorus | Chorus |
| Eventos públicos | OSAP | OSAP (se mantiene) |
| Identidad | osap-auth | osap-auth |

Datos migrados en dev: **3 grupos, 2 miembros, 12 secciones, 17 artículos y
16 medios**. El artículo general de OSAP no se migra.

## Migración

`Chorus/scripts/migrate_osap_groups_articles.py`:

- conserva los identificadores de origen como `id`/`legacy_id`;
- es idempotente (`ON DUPLICATE KEY UPDATE`);
- no borra ni modifica datos de OSAP;
- omite artículos cuyo grupo no exista en Chorus;
- no migra artículos con `scope=general`.

Ejecución en dev:

```powershell
$env:OSAP_DATABASE_URL='mysql://.../osap_api'
$env:CHORUS_DATABASE_URL='mysql://.../osap_chorus'
Chorus\.venv\Scripts\python.exe Chorus\scripts\migrate_osap_groups_articles.py
```

## API Chorus nueva

- `GET/POST /api/v1/groups`
- `POST /api/v1/groups/join`
- `GET/PATCH /api/v1/groups/{id}`
- `GET /api/v1/groups/{id}/catalog` (local)
- `GET/PATCH/DELETE /api/v1/groups/{id}/members/{user}`
- `GET/POST /api/v1/groups/{id}/articles`
- `GET/PATCH/DELETE /api/v1/articles/{id}`
- `POST /api/v1/articles/{id}/publish|withdraw`

Permisos comprobados en backend: miembro activo para lectura; `manager` o
`collaborator` para edición; `manager` para publicar. El autor puede editar su
artículo, pero no publicarlo si no tiene responsabilidad de publicación.

## Retirado de la interfaz OSAP

- Menú público «Los amigos».
- Menú de administración «Los amigos».
- Enlaces a Grupos y Mis artículos.
- Mantenimiento de grupos, miembros, cargos, roles musicales y secciones: se realiza en Chorus; la ficha global de usuario OSAP no mantiene ni duplica esos datos.
- **Eventos se mantiene** en el menú público y en administración (`/amigos/eventos` y `/admin/amigos/eventos`): no forma parte de la retirada.
- El enlace a Chorus queda en «Tu espacio».

Las rutas y tablas antiguas de OSAP se conservan temporalmente en dev para
verificar la migración. No se eliminarán hasta completar las pruebas y contar
con autorización.

## Pendiente antes de liberar

1. Probar la UI de artículos con datos migrados.
2. Comprobar permisos de manager, collaborator, autor y miembro.
3. Decidir redirecciones 301 de las URLs públicas de grupos y artículos de OSAP.
4. Retirar endpoints y tablas de grupos de OSAP y actualizar pruebas.
5. Completar en Chorus el mantenimiento administrativo de grupos y miembros, incluida la incorporación de un usuario existente de `osap-auth` como miembro ordinario. La concesión de `manager` queda reservada a un manager autorizado del grupo. OSAP no debe mantener catálogos ni asignar permisos de manager.
6. Revisar documentación y versiones de los cuatro programas.


