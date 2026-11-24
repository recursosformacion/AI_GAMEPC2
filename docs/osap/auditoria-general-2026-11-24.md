# Auditoría general OSAP — 2026-11-24

**Ámbito:** web pública, código OSAP API, seguridad de configuración, manual español y documentación técnica.  
**Rama de trabajo:** cambios aplicados directamente en main; no se han creado ramas ni PR.  
**Producción:** solo lectura desde la web pública. No se han ejecutado escrituras, migraciones, reconstrucciones del índice ni despliegues.

## 1. Web pública

- Sitio correcto: https://app.openmusicrepository.com/.
- La web responde y permite consultar páginas públicas de compositores y obras.
- El pie de página mostraba la versión de producto 6.4.1 durante la inspección.
- La diferencia de 198 compositores indicada en una revisión anterior no se ha podido reproducir; se retira como incidencia confirmada.
- Se ha encontrado una ficha de obra con una representación de otro número de concierto. Detalle y recorrido técnico: [auditoría de asociaciones del índice](auditoria-index-2026-11-24.md).

## 2. Correcciones de código

### 2.1 Enriquecimiento de búsqueda

El enriquecimiento enfocado eliminaba números y tonalidades para comparar títulos y después aceptaba una coincidencia basada solo en solapamiento de palabras. Esto podía considerar equivalentes dos obras numeradas distintas del mismo compositor.

Corrección:
- _title_core_match compara también el número explícito de obra cuando está presente en ambos títulos.
- _focused_representations pasa el título original como referencia.
- Se añaden pruebas para No.1/No.3, ediciones del mismo número y títulos sin numeración.

Commits: 44a852b, 14f736d, 8928d2d.

Esta corrección afecta al enriquecimiento dinámico. No repara las filas ya persistidas en index_representations; esa reparación requiere el diagnóstico de solo lectura descrito en la auditoría del índice.

### 2.2 Configuración de base de datos

Se eliminaron los valores de fallback de conexión embebidos en el wiring y en los valores por defecto de IndexCatalogProvider. OSAP API exige ahora que host, usuario, contraseña y nombre de BD estén definidos explícitamente también en desarrollo.

Se añadió una prueba para impedir que el arranque de desarrollo vuelva a recurrir a credenciales implícitas.

Commits: 0d87dd4, 64dd5d8, 78bd5ef, 391fab9.

### 2.3 Metadatos OpenAPI

Se retiró el contacto de ejemplo que apuntaba a example.com y se sustituyó por la web pública real, sin inventar una dirección de correo.

Commit: 31351c9.

## 3. Manual español

Revisión y correcciones aplicadas en web/public/manual/es/:

- Corregida la navegación activa duplicada en Clasificación.
- Corregido el cierre duplicado de main en Otras herramientas.
- Actualizado el nombre público Los Amigos.
- Eliminadas las referencias a repositorios internos separados que no forman parte de la experiencia del usuario.
- Corregida la descripción de CPDL: las referencias y formatos se muestran en OSAP, pero el archivo permanece en ChoralWiki y la apertura puede depender de su protección anti-bot.
- Simplificada la explicación de acceso externo frente a repositorio propio OMR.
- Corregido el enlace de incidencias de Clasificación a Contacto y correcciones.
- Retirada una promesa de redirección automática que no estaba garantizada.
- Ajustada la explicación de caducidad de sesión.

La revisión de traducciones queda para después de cerrar el texto maestro español y de las pruebas de cuenta. Se han detectado metadatos canónicos/hreflang de traducciones que apuntan a la versión española.

## 4. Documentación técnica

Se creó y reorganizó el índice central en docs/:

- docs/README.md: índice raíz y reglas de vigencia.
- docs/osap/README.md: índice por estado.
- docs/osap/current-architecture.md: arquitectura actual 6.x, límites y propiedad de datos.
- docs/osap/api-route-map.md: familias de routers, endpoints de referencia y aliases SEO.
- docs/osap/configuration-current.md: precedencia de configuración, OIDC, M2M e integraciones.
- docs/osap/m2m-service-matrix.md: estado real de API → Support y separación de clientes.
- docs/osap/scripts.md: inventario y seguridad de scripts.
- docs/osap/auditoria-index-2026-11-24.md: incidencia de identidad del índice.
- docs/configuration-v1.md: retirado y sustituido por un aviso que enlaza a la configuración vigente.

El Architecture Book V2.2 se marca como histórico. Los documentos V6 siguen marcados como PLAN, no como esquema ya desplegado.

## 5. Pendiente de verificación

1. Ejecutar las pruebas añadidas de búsqueda y configuración en el entorno local; el estado de CI consultado no devolvió checks.
2. Ejecutar un diagnóstico SQL de solo lectura sobre la Work IDP 3 y sus representaciones; rastrear el origen de la fila IDP 2.
3. Preparar y validar en desarrollo el rebuild o la reparación de índice, conservando IDs públicos y aliases.
4. Probar con una cuenta de usuario: login/registro, nombre visible, Mi Actividad, cuotas, aportaciones, biblioteca y operaciones de subida/descarga disponibles.
5. Cerrar el manual español con esas pruebas; después corregir traducciones y metadatos canónicos/hreflang en los cuatro idiomas.
6. Completar la verificación funcional de las áreas públicas y privadas que requieren interacción real.

## 6. Restricciones respetadas

- No se ha conectado a producción para escribir datos.
- No se ha ejecutado ninguna migración ni rebuild de índice.
- No se ha realizado ningún despliegue.
- No se ha tocado el repositorio Chorus.
- No se han creado ramas ni PR.
