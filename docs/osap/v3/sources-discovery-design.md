# Incorporación y Descubrimiento de Fuentes Musicales — Diseño (V3.6.x)

> **Status: frozen** — congelado antes de la implementación de V3.6.x (ADR-0031).
>
> Extensión de **V3.6 (Administración)**. Define el modelo de **incorporación y
> descubrimiento de fuentes musicales**, tanto de **uso inmediato** como de **incorporación
> permanente**, sin modificar la arquitectura V3.3 ni el dominio V2.

## Principio rector

> **Toda fuente musical puede utilizarse inmediatamente por cualquier usuario; su
> incorporación permanente dependerá únicamente de que dicho usuario decida proponerla y
> de la aprobación posterior del administrador.**
>
> **El administrador no interviene en el uso normal de una fuente.**

OpenMusicRepository favorece el **descubrimiento libre**; la **gobernanza solo afecta a la
incorporación permanente** de nuevas fuentes al repositorio global. El usuario **nunca
debe esperar la aprobación de un administrador** para aprovechar una nueva fuente musical.

## 1. Objetivo

Permitir que **cualquier usuario** pueda **utilizar inmediatamente** una nueva fuente
musical durante una búsqueda, ejecución o sesión, mientras que solo la **propuesta
voluntaria** y la **aprobación del administrador** convierten esa fuente en un **origen
permanente** de OpenMusicRepository.

## 2. Connector vs Source

Dos conceptos **distintos**:

```
Connector                     → cómo acceder
    Git · HTTP · WebDAV · FTP
    IMSLP · OpenScore · MuseScore · ...

Source Definition             → qué colección concreta
    "Repositorio Coral Bach"
    "Biblioteca Coral de Valencia"
```

- **Connector** define **cómo acceder**.
- **Source Definition** define **qué colección** se utiliza.

```
Connector
    ↓
Source Definition
    ↓
Representations
```

En el futuro, un **plugin puede añadir un connector sin tocar el modelo**.

## 3. Source, Instancia y Profile

**Una Session/Repository es una instancia de uso, no un tipo distinto de Source.** La
fuente sigue siendo la misma; lo que cambia es **dónde vive**.

```
Connector
    │
    ▼
Source Definition
    │
    ├────────────► Session Instance     (uso inmediato, en la sesión)
    │
    └────────────► Repository Instance  (permanente, tras aprobación)
```

### Source Profile

Dos usuarios pueden usar la **misma** Source con **credenciales/ramas distintas**:

```
Source Profile
  source          # Source Definition (Git → Repositorio Coral)
  credentials     # credenciales del usuario
  branch          # rama / contexto
```

La **Source es la misma; el Profile cambia.** Permite **reutilizar la definición**.

## 4. Tipos de uso

### Session Instance (uso inmediato)

- Utilizada únicamente durante una **búsqueda**, una **ejecución** o una **sesión**.
- **No modifica** ninguna configuración.
- No requiere aprobación.

### Repository Instance (permanente)

- Origen permanente de OpenMusicRepository.
- **Solo existe tras la aprobación** de una propuesta por el administrador.
- Disponible para todos los usuarios.

## 5. Flujo normal (uso inmediato)

```
Usuario
     │
     ▼
Añade una nueva fuente
     │
     ▼
OSAP analiza automáticamente
     │
     ▼
¿Desea utilizarla?
     │
     ▼
Sí
     │
     ▼
La búsqueda la utiliza inmediatamente
```

**Aquí termina el flujo normal. El administrador no participa.**

## 6. Propuesta voluntaria (flujo independiente)

```
Usuario → Proponer esta fuente → Propuesta → Administrador → Aceptar / Rechazar
```

**El administrador nunca aprueba el uso** de una fuente; **únicamente decide si la fuente
pasa a formar parte de OpenMusicRepository.**

## 7. Análisis automático + Quality Score

Antes de utilizar una fuente, OSAP realiza un **análisis automático** (formatos, nº de
archivos, metadatos, compositores, catálogos, representaciones, duplicados, calidad).

**Quality Score (desglosado):**

```
Quality Score: 91/100

Metadata completeness    98
Duplicate probability    89
MusicXML validity        96
Coverage                 85
```

**Valoración por estrellas:**

```
★★★★★  Excelente   · ★★★★  Buena
★★★   Aceptable   · ★★   Baja   · ★   Muy baja
```

**El análisis se guarda** (no solo se muestra): `analysis`, `quality`, `trust`,
`last_analysis`, `last_sync`. El administrador **no vuelve a analizar**.

## 8. Capabilities del conector

```
Search · Read · Download · Upload · Metadata · Incremental Sync · Authentication Required
```

Ejemplo:

```
IMSLP   Search · Read · Download · Metadata      (sin Upload)
Git     Read · Write · Sync · Delete
```

## 9. Preview antes de importar

```
12 obras
31 representaciones
7 compositores
2 duplicados

[ Importar ]
```

## 10. El administrador aprueba la INSTANCIA

El administrador aprueba la **Source (instancia)**, no el **Connector**:

```
GitHub → Repositorio Bach → Repositorio Mozart → Repositorio Coral
```

Son **instancias distintas** del mismo conector.

## 11. Discover Sources

Una fuente descubierta puede: **utilizarse inmediatamente · descartarse · proponerse**.
**Nunca obliga a pasar por un administrador antes de utilizarla.** Categorías:

```
Suggested · Trending · Recently added · Most used
Official · Verified · Nearby · Community
```

Empieza a parecer un **gestor de repositorios**.

## 12. Origin y Trust

Dos ejes **independientes**:

```
Origin             Trust
Official           Official
Community          Verified
Private            Community
Generated          Experimental
Mirrored
```

Puedes tener `Origin: Official` + `Trust: Low` (los datos son malos). Filtros por ambos.

## 13. Pipeline

El análisis usa **exactamente el pipeline normal**:

```
Analyze → Collect → Normalize → Match → Merge → Evidence → Quality
```

## 14. Seguridad

Las Session Instances: **no modifican** la configuración; **nunca almacenan credenciales**
salvo autorización; pueden ejecutarse en **modo solo lectura**.

## 15. Ampliación de la API (nuevos recursos)

La API existente **no se modifica**: se **amplía**. El flujo se **separa**:
`create → analyze → use`. El administrador **nunca opera sobre Session Instances**.

**Uso (cualquier usuario):**

```
POST   /api/v1/sources                     # crea una Source (definición/temporal)
POST   /api/v1/sources/{id}/analyze        # análisis automático (persistido)
POST   /api/v1/sources/{id}/use            # la utiliza en la búsqueda/sesión actual
GET    /api/v1/sources/{id}                # detalle + analysis + quality + trust
DELETE /api/v1/sources/{id}                # olvida una Session Instance
POST   /api/v1/sources/{id}/sync           # re-analiza una fuente (evita obsolescencia)
POST   /api/v1/sources/{id}/propose        # convertir en propuesta
```

**Administración (solo propuestas):**

```
GET    /api/v1/sources/proposals
POST   /api/v1/sources/proposals/{id}/approve
POST   /api/v1/sources/proposals/{id}/reject
POST   /api/v1/sources/proposals/{id}/review
```

**Descubrimiento:**

```
GET    /api/v1/discover/sources            # catálogo de descubrimiento (sugerencias externas)
```

### Nomenclatura (tres responsabilidades)

```
/sources               → Session Instances (recursos temporales del usuario)
/repository-sources    → catálogo permanente del sistema (Repository Sources)
/discover/sources      → sugerencias externas
```

## 16. Source Catalog

> **Toda Repository Source dispone de una ficha con información automática y
> documentación editable.** Filosofía de un **catálogo de bibliotecas**.

La ficha separa los datos en **tres categorías** (nunca se mezcla lo objetivo con la
opinión):

```
AUTOMÁTICOS
───────────
Los calcula OSAP
• formatos · estadísticas · calidad · trust · sincronización · capacidades

DOCUMENTACIÓN
─────────────
La escribe un humano
• descripción · notas · licencia · contacto · recomendaciones

COMUNIDAD
─────────
La generan los usuarios
• comentarios · valoraciones · incidencias · propuestas
```

### 16.1 Información automática (OSAP)

```
IMSLP
Estado                  Online
Tipo                    HTTP
Origen                  Official
Trust                   Verified
Quality                 ★★★★★ (96/100)
Última sincronización   2026-08-12 09:14 UTC
Representaciones        128.431
Obras detectadas        38.912
Compositores            3.281
Formatos                MusicXML · PDF · MIDI
Catálogos detectados    BWV · KV · Hob. · Op.
Duplicados estimados    1.2 %
Cobertura               Barroco · Clásico · Romanticismo
```

### 16.2 Información documental (humano)

```
Descripción    Repositorio oficial de partituras de dominio público.
Licencia       Public Domain
Página web     https://...
Contacto       ...
Notas          Muy buena cobertura de Mozart. Los PDFs anteriores a 2012 tienen baja resolución.
```

### 16.3 Observaciones (estilo GitHub)

```
2026-07-18   Se detectan problemas con las búsquedas de Händel.
2026-08-02   El proveedor vuelve a estar sincronizado.
```

### 16.4 Estadísticas

```
Uso: Búsquedas realizadas 3214 · Representaciones descargadas 9321
Contribuciones: 42 propuestas aceptadas · Disponibilidad: 99.8 %
```

### 16.5 Capacidades (visuales)

```
✓ Search · ✓ Download · ✓ MusicXML · ✓ PDF · ✓ MIDI · ✓ Incremental Sync · ✗ Upload
```

### 16.6 Etiquetas

```
Baroque · Choral · Critical Editions · Public Domain · Academic
```

(El etiquetado facilita el **Discover**.)

### 16.7 Valoraciones

```
Calidad automática    96/100
Valoración comunidad  ★★★★☆
Comentarios           27
```

### 16.8 API del catálogo

```
GET    /api/v1/repository-sources        # listado del catálogo
GET    /api/v1/repository-sources/{id}   # ficha completa de una fuente permanente
```

Con esta ampliación, OpenMusicRepository pasa de *"un sistema donde añado proveedores"* a
*"una plataforma que descubre, analiza, documenta, evalúa y comparte conocimiento sobre
fuentes musicales"*.

## 17. Estados

- **Session Instance**: `ACTIVE` (transitorio).
- **Repository Instance**: `PROPOSED → APPROVED → ACTIVE`, y `DISABLED` / `REJECTED`.
- **DISABLED**: una fuente aprobada que dejó de funcionar; se **conserva su historial**.

## 18. Invariantes

- **Toda fuente puede utilizarse inmediatamente** tras superar el análisis automático.
- **El administrador nunca interviene** en el uso temporal de una fuente.
- **Solo las propuestas** pueden convertirse en Repository Instances.
- **Session y Repository Instances usan exactamente el mismo pipeline** de resolución.
- El **análisis automático siempre precede** al uso de una fuente desconocida.
- El análisis y la valoración **se persisten** (no se repite innecesariamente).
- Toda comunicación pasa por `ApiClient`.
- No se modifica el dominio V2; la API existente solo se **amplía**.

---

## Criterios de aceptación

- uso **inmediato** (Session Instance) sin aprobación;
- flujo API **separado**: `create → analyze → use`;
- **propuesta voluntaria** → revisión del administrador;
- **Repository Instance** solo tras aprobación;
- **Connector** separado de **Source Definition**; **Source** separada de **Instance**;
- **Source Profile** para reutilizar la definición con credenciales/ramas distintas;
- **Quality Score** desglosado y **persistido**;
- **Capabilities** por conector;
- **Preview** antes de importar;
- **Sync** para re-analizar fuentes;
- **Forget** (`DELETE /sources/{id}`) para olvidar una Session Instance;
- **Origin** y **Trust** como ejes independientes;
- **Discover Sources** (usa/descarta/propone; nunca obliga a admin);
- estado **DISABLED** (sin perder historial);
- reutilización del **mismo pipeline** de resolución;
- **sin romper** la arquitectura V3.3.

---

## Plan de entrega

1. **Diseño de fuentes (Descubrimiento)** (este documento, congelado).
2. **ADR-0031**.
3. **Ampliación de la API** (`/sources/*`, `/discover/sources`).
4. **UI de Administración / Discover Sources**.
5. **Tests** (sin cambios de arquitectura; API solo ampliada).
