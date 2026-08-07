# Cliente Web — UX (Work Resolution) e Identidad Visual

> **Status: frozen** — congelado antes de la implementación de V3.4 (ADR-0030).
>
> Define la experiencia de usuario del cliente web alrededor de la **Work Resolution**.
> **No cambia la arquitectura** (ApiClient, Routing, Layout, Components, State, Design
> System) ni la API.

## Frase que resume la filosofía

> **El objetivo de OpenMusicRepository no es devolver una lista de archivos, sino
> identificar una obra musical con el mayor grado de confianza posible y ofrecer al
> usuario todas sus representaciones disponibles junto con la evidencia que justifica esa
> resolución.**

## Principio rector

> **OpenMusicRepository es la marca visible; OSAP es el motor.**

Igual que *Windows / powered by NT* o *Chrome / powered by Chromium*:
**OpenMusicRepository / powered by OSAP**.

## Work Resolution (entidad central)

> **No estamos mostrando resultados: estamos mostrando la resolución de una obra.**

```
Search → Work Resolution → Representations → Evidence → Actions
```

### Resolution (recurso)

Una **Work Resolution es un recurso de la aplicación**, no una vista pasajera:

```
Resolution
  id
  confidence
  work
  candidate_works
  representations
  evidence
  actions
```

Como recurso, permite (sin tocar nada): **compartir una resolución, volver a abrirla,
compararla, guardarla y exportarla**.

### Work Resolution Workspace

> Después de encontrar la obra, el usuario **no ha terminado: empieza el trabajo.**

Por eso la pantalla central es un **Work Resolution Workspace**, no un *search result*.
Dentro del Workspace se puede: **descargar, comparar, abrir MusicXML, abrir PDF, abrir
proveedor, explicar, guardar, compartir y revisar aliases**. Ya no es un resultado: es un
**espacio de trabajo**.

### Progressive Disclosure

> Hay mucho poder en OSAP; no puedes enseñarlo todo de golpe. La pantalla se **descubre
> poco a poco**.

```
Resultado
  ↓
Representaciones
  ↓
Más información
  ↓
Why this result?
  ↓
Evidence
  ↓
Pipeline
```

Nada abierto desde el principio; la profundidad se revela a demanda.

## Entity Resolution (nivel superior a la Work Resolution)

> **La primera resolución no siempre es una obra.** Antes de resolver una obra, OSAP
> resuelve la **entidad** que el usuario busca.

```
Query
  ↓
Intent Detection
  ↓
Entity Resolution
  ↓
Composer · Work · Collection · Catalogue · Representation · Source
  ↓
(si es Work)
  ↓
Work Resolution
  ↓
Representations · Evidence · Actions
```

### Cuatro niveles con responsabilidades distintas

Cada nivel tiene **una responsabilidad**; un desarrollador no debe mezclarlos (no confundir
Composer con Work Resolution):

```
Search              → encontrar
Entity Page         → explorar (Composer / Collection / Catalogue / Source / Representation)
Work Page           → listar obras / decidir
Work Resolution     → trabajar la obra (representaciones, evidence, actions)
Representation      → el recurso final
```

### Search Result ≠ Work Resolution

**Son dos pantallas distintas.** Una consulta abierta devuelve un **Search Result** (una
entidad o un conjunto de obras); la **Work Resolution solo aparece cuando el usuario ha
elegido una obra** (o cuando la consulta identifica una única obra sin ambigüedad). Si se
mezclan, la interfaz acaba **"inventando" una resolución** que el usuario nunca pidió.

```
Search
  ↓
Search Result  (composer / title / catalogue / collection)
  ↓
Work selected
  ↓
Work Resolution
  ↓
Representations · Evidence · Actions
```

### Tres tipos de búsqueda

```
ENTITY SEARCH       Composer · Person · Collection · Publisher · Repository
WORK SEARCH         Obra
REPRESENTATION      PDF · MusicXML · MIDI
```

No todas terminan igual.

### Entity Pages

La entidad resuelta lleva a una **Entity Page** específica. No todas son iguales:

```
Composer Page        → página de exploración (obras del compositor)
Work Page            → Work Resolution (la entidad YA es una obra)
Collection Page      → explora la colección (no resuelve una obra)
Catalogue Page       → colección por catálogo
Representation Page  → representaciones
Source Page          → explora la fuente (no resuelve una obra)
```

### Modelo de navegación

```
Quick Search
        │
        ▼
Entity Resolution
        │
        ├── Composer Page
        │        │
        │        ▼
        │    Work Page (obras desplegables)
        │        │
        │        ▼
        │    Work Resolution
        │
        ├── Work Page
        │        ▼
        │    Work Resolution
        │
        ├── Collection Page
        ├── Catalogue Page
        ├── Representation Page
        └── Source Page
```

### Composer Page (exploración, no resolución)

Una página **musical**, no una lista plana:

```
Wolfgang Amadeus Mozart
179 works

Collections
Symphonies · Concertos · Sacred Music · Operas · Piano
-------------------
Sacred Music
▼ Ave Verum Corpus    6 representaciones (IMSLP · OpenScore …)
▼ Requiem
▼ Missa Brevis
```

Solo una obra expandida a la vez; al expandir se ven las **variantes** y la **mejor**. El
panel de "resolución" **no aparece** hasta elegir obra.

### Matching Works (Candidate Works) — definición

La pantalla puente entre la búsqueda y la resolución. Cada obra es una **tarjeta**:

```
★★★★★  Ave Verum Corpus · Mozart · KV618
        18 representations · 6 providers
        ▼
        Overview
          Confidence · Representations · Providers · Best representation
        [ Open Work Resolution ]
```

- No va directamente a Resolution: primero muestra el **Overview** de la obra.
- **Open Work Resolution** solo cuando el usuario decide.

### Works desplegables

```
▶ Ave Verum Corpus
   ▼ Ave Verum Corpus
      ★★★★★ Resolution
      IMSLP · OpenScore · Local
      PDF · MusicXML · MIDI
```

La lista pasiva de "varias obras compatibles" se sustituye por obras **seleccionables,
desplegables y comparables**. *("Candidate Works" es terminología del algoritmo; en la UI se
usa **Matching Works / Possible Works / Works found**.)*

### Breadcrumb natural

No técnico; sigue la navegación real del usuario:

```
Home > Mozart > Ave Verum > Resolution
Home > Discover > Mozart > Ave Verum > Resolution
```

> **OpenMusicRepository nunca fuerza una Work Resolution cuando la consulta aún no
> identifica una obra. Primero resuelve la entidad consultada y solo cuando el usuario
> selecciona una obra se muestra la Work Resolution.**

### El valor

Permite que **Work Resolution siga siendo el núcleo**, pero **solo cuando la entidad
resuelta es realmente una obra musical**. OSAP deja de comportarse como un buscador de
documentos y actúa como una **plataforma de inteligencia musical**.

### Jerarquía visual de las páginas

Cada nivel tiene su propia pantalla y su propia responsabilidad; un desarrollador (o una
IA) no debe "saltar" de Search a Work Resolution. Este es el resumen de la filosofía de
V3.4 de un vistazo:

```
Quick Search
      │
      ▼
──────────────────────────────
 Entity Page
──────────────────────────────
Mozart

Collections
Biography
Statistics

Works
 ▼ Ave Verum
 ▼ Requiem
 ▼ ...

      │
      ▼
──────────────────────────────
 Work Page
──────────────────────────────
Overview

Best representation

Open Work Resolution

      │
      ▼
──────────────────────────────
 Work Resolution
──────────────────────────────
Overview

Representations

Evidence

Relationships

History

Actions

      │
      ▼
Representation
```

La implementación debe hacer que **cada pantalla tenga exactamente la responsabilidad que
el documento le asigna**, sin mezclar niveles: búsqueda, exploración, selección,
resolución y representación.

## Product First

> **La interfaz muestra primero el valor del producto y después las herramientas de
> administración.**

```
Producto → Búsqueda → Resolución → Conocimiento

Administración   (al final, nunca al revés)
```

## Diseño basado en tareas

El usuario piensa **"quiero encontrar una obra"**, no "quiero abrir Providers". La
navegación se organiza por **tareas**:

```
Discover · Compare · Knowledge
```

## 1. Navegación principal

**Search deja de ser una página**: es una **acción global** disponible desde cualquier
página (siempre en el Header).

```
Home · Discover · Knowledge
───────────────────────────
Administration   (área secundaria/colapsable)
```

```
Header
OpenMusicRepository   [ Search________________ ]  [es|dark|👤]
```

El **buscador es el centro del producto**.

## 2. Home (no Dashboard)

```
Search music
[________________________________________]
                Search

Recent searches
Most accessed works
Recently added representations
Repository status
```

Los proveedores son infraestructura: no empiezan el home. La música es el producto.

## 3. Landing Hero

Antes del buscador:

```
OpenMusicRepository

Search, compare and discover musical works
across multiple music repositories.

[____________________________]
            Search
```

## 4. Search y Result (dos vistas)

- **Search** (vista 1): el formulario, acción global.
- **Result / Work Resolution** (vista 2): **el verdadero protagonista**.

```
Search
   ↓
Result (Work Resolution)
```

## 5. Work Resolution (la pantalla protagonista)

> **La búsqueda devuelve obras, no representaciones independientes.**

La pantalla refleja la jerarquía del dominio:

```
Composer
   ↓
Work
   ↓
Representation
```

Y el flujo interno de la resolución:

```
Search → Matching Works → Selected Work → Representations → Actions
```

### 5.1 Matching Works

Buscar "Mozart" devuelve una **lista de obras** (no una lista de PDFs):

```
▶ Ave Verum Corpus KV 618      18 representaciones · 99.8 %
▶ Requiem KV 626               52 representaciones · 98.7 %
▶ Missa Brevis KV 220          12 representaciones
```

### 5.2 Works expandibles

Cada obra es **expandible**. Al desplegar:

```
▼ Ave Verum Corpus KV 618

Representaciones
★★★★★ IMSLP
★★★★☆ OpenScore
★★★★☆ Local

Ver MusicXML · Ver PDF · Descargar
```

Únicamente al **seleccionar una obra** se muestran sus representaciones y la **mejor**.

### 5.3 Selected Work

Al seleccionar la obra se muestra su **resolución**: la obra (Nivel 1) y sus
representaciones agrupadas por proveedor (Nivel 2).

### 5.4 Obras candidatas

Si hay varias obras compatibles, se muestran ordenadas por confianza:

```
Hemos encontrado varias obras compatibles
★★★★★ Mozart — Ave Verum KV 618
★★★★☆ Byrd — Ave Verum Corpus
★★☆☆☆ Poulenc — Ave Verum
```

## 6. Explainability (contextual)

> **Todo resultado puede ser explicado.**

El razonamiento **no ocupa espacio permanente**: es una **ayuda contextual**. Se abre a
petición (botón ⓘ **Why this work?** / **Explain**) en un **panel lateral o diálogo**.

```
matched title
matched composer
aliases utilizados
catálogo reconocido
coincidencias entre proveedores
score final
confidence
```

Aprovecha el pipeline de **matcher · ranking · merge · evidence**. Una vez el usuario ya
eligió la obra, la explicación contextual deja de ser necesaria en primer plano.

## 7. Discover (definido) — exploración musical

> **"No sé exactamente qué busco; ayúdame a explorar."** (como Spotify, Google Books o IMDb)

Discover responde preguntas de **música**, no de infraestructura:

```
Trending works
Trending composers
Recently incorporated works
New collections
Featured editions
Recently discovered repositories   (solo un bloque, normalmente el último)
```

**Explore by**:

```
Composer · Period · Genre · Instrumentation · Collection · Catalogue · Source
```

**Discover NO muestra las fuentes como elemento principal**: las fuentes son
**infraestructura**; la **música es el producto**. Las fuentes viven en su propia página
(`Sources` / `Repository`), y Discover solo las **utiliza**, no las exhibe.

## 8. Compare (una acción más, no un bloque)

El usuario no piensa "Compare"; piensa **"¿qué puedo hacer ahora?"**. **Compare** no es un
bloque propio: es **otra acción** del bloque de acciones.

- Compare editions · Compare metadata · Compare providers

## 9. Knowledge → Intelligence (propuesta de branding)

```
Knowledge → Insights
         → Music Intelligence
         → Repository Intelligence
```

Depende del branding final.

## 10. Flujos de navegación (según la entidad resuelta)

```
Quick Search → Intent Detection → Composer → Composer Page → Works → Work Resolution
Quick Search → Intent Detection → Work → Matching Works → Work Resolution
Quick Search → Intent Detection → Catalogue → Work Resolution
Home → Discover → Work → Work Resolution
Home → Search Studio → Matching Works → Work Resolution
```

## 11. Actions (la resolución como espacio de trabajo)

Todo lo que se puede hacer con la resolución, en un único bloque **Actions** (no
"Compare"):

```
View score · View MusicXML · Download PDF
Download MusicXML · Download MIDI · Open provider
Explain result · Bookmark · Share · Report issue
```

Si algún día existe comparación, **Compare editions / metadata / providers** es **otra
acción** más de este bloque, no un bloque propio.

**Sin botones muertos en el MVP**: las acciones que la API ya soporta (abrir
representación, descargar, abrir proveedor, mostrar evidencias) deben **funcionar**. Solo
se muestran deshabilitadas las funcionalidades futuras, marcadas claramente ("Coming soon").

## 12. Work Resolution as Knowledge Hub

> **La Work Resolution no es únicamente el resultado de una búsqueda; es la ficha viva de
> una obra musical. Toda la información conocida sobre la obra (metadatos,
> representaciones, evidencias, historial y acciones) se organiza alrededor de ella.**

La resolución deja de ser *"qué encontré"* y pasa a ser *"todo lo que sé de esta obra"* —
una ficha tipo Wikipedia/Discogs/MusicBrainz:

```
Ave Verum Corpus KV618 · Mozart
★★★★☆ 99.8 %

Representaciones 18 · Proveedores 6
MusicXML 12 · PDF 16 · MIDI 4
────────────────────────────
Catálogo      KV618
Compositor    Wolfgang Amadeus Mozart
Fecha         1791
Duración      3'
Instrumentación SATB
Idioma        Latín
```

### 12.1 Representaciones enriquecidas

Cada representación muestra más que proveedor+formato:

```
MusicXML
Version 4.0 · Compressed · Validated
Measures 128 · Voices SATB · Generated 2025
[ Download ]
```

### 12.2 Evidence y Relationships como pestañas

La resolución se organiza en **pestañas** (el razonamiento ya no va asociado a un botón
supletorio):

```
Overview · Representations · Metadata · Evidence · Relationships · History
```

Solo al entrar en **Evidence** aparecen los detalles:

```
Title 98 % · Composer 100 % · Catalogue 100 %
Aliases 94 % · Providers 97 %
```

**Relationships** convierte la resolución en una **ficha musical** completa:

```
Same work · Different editions · Related catalogue
Aliases · Arrangements · Transcriptions
Movements · Parent work
```

### 12.3 Matching Works con vista previa

Cada obra candidata muestra una **preview** (clave al buscar un compositor con cientos de
obras):

```
Ave Verum Corpus KV618
Mozart · SATB · 1791
18 representaciones
★★★★★
```

### 12.4 Resumen automático (idea diferencial)

Un pequeño resumen automático que ningún buscador musical suele ofrecer:

```
This work has
18 representations · 6 providers
3 validated MusicXML · 2 conflicting PDFs
Confidence 99.8 %

Most complete representation   OpenScore
Highest quality PDF            IMSLP
Best MIDI                      Local Repository
```

Aprovecha la inteligencia del motor y ayuda a decidir **sin inspeccionar cada
representación**. La unidad principal del producto es **la obra, no el archivo**.

## 13. Breadcrumb semántico

- Representa **jerarquía de producto**, no rutas.
- **El breadcrumb representa navegación lógica, nunca rutas REST ni URLs.**

```
Home > Searches
Home > Knowledge > Suggested aliases
```

## 14. Administración secundaria

- Agrupada aparte (pie de página o panel colapsable).

## 15. Providers como tarjetas

```
IMSLP        OpenScore       PDMX
✓ Online     ✓ Online        ✗ Offline
PDF          MusicXML        MusicXML
MusicXML
MIDI
```

## 16. Identidad visual musical

- **color** y **tipografía** propios (no gris administrativo);
- **iconografía** musical y de recursos;
- **portada / elemento visual** de producto;
- **sensación de producto**, no de ERP.

## 17. Modo oscuro

- **Parte del Design System** (tokens claro/oscuro, accesibles en ambos).

## 18. Preferencias persistentes

Persisten: **idioma · modo oscuro · nº de resultados · filtros**.

## 19. Sin scroll innecesario

Siempre que sea posible: **resultados, buscador y filtros visibles**; no obligar a
desplazarse.

## 20. Vacíos elegantes

En vez de "No results":

> **No works found. Try another title, composer or catalogue number.**

## 21. Animaciones

Muy pocas y bien usadas: **transición entre páginas, loading skeleton, tarjetas**. Nunca
decorativas.

## 22. Iconografía consistente

**Un único set** de iconos (p. ej. **Heroicons** o **Lucide**). No mezclar.

## 23. Responsive Design (mobile-first)

> **El cliente web se diseña mobile-first**, de teléfono a escritorio sin perder
> funcionalidad.

## 24. Accesibilidad

> **WCAG AA siempre que sea posible.** Los componentes reutilizables del Design System son
> **accesibles por defecto**.

## 25. Internacionalización (i18n)

> **Multiidiomas**: **Castellano (es) · Català (ca) · Français (fr) · English (en) ·
> Deutsch (de)**.

- Componentes/Design System independientes del idioma; texto extraído a cadenas
  traducibles.
- Posible añadir más idiomas y, en breve, una **pantalla de login** (auth).

## 26. Search Experience

> **OpenMusicRepository ofrece dos niveles de búsqueda claramente diferenciados.**

```
Quick Search   →  Header, consulta libre (80 % de los casos)
Search Studio  →  página dedicada a construir consultas (20 %, investigación)
```

> **Invariante**: **Quick Search nunca sustituye a Search Studio**; ambos representan dos
> formas complementarias de acceder al **mismo motor de resolución de obras**.

### 26.1 Quick Search

Disponible **permanentemente en el Header**. Optimizada para **consultas libres**; punto de
entrada principal. Resuelve la mayoría de búsquedas cotidianas.

```
Header
OpenMusicRepository  [ 🔍 Search a work... ]
```

Al pulsar **Enter** → **Quick Search → Work Resolution**.

(Incluye detección de intención simple: "KV618 → catalogue", "Mozart → composer".)

### 26.2 Search Studio — constructor de consultas

Una **página dedicada** a **construir una consulta semántica** (no un formulario clásico).
Expone todas las capacidades del motor OSAP y combina criterios con **AND**. Orientada a
usuarios que necesitan búsquedas precisas o de investigación.

```
WHAT
────────────
Composer = Mozart

AND

Catalogue starts with KV

AND

Representation = MusicXML

AND

Confidence > 90%

──────────────────────
        [ Resolve Works ]
```

El usuario **construye una consulta**, no rellena campos.

### 26.3 Bloques de Search Studio

La búsqueda se organiza por **bloques** (escalable), combinables con AND:

```
WHAT         Title · Composer · Catalogue · Alias
WHERE        Providers · Collections · Repositories
WHAT KIND    MusicXML · PDF · MIDI
QUALITY      Confidence · Only verified · Only official
OPTIONS      Limit · Sort · Duplicates
```

### 26.4 Flujos

```
Header [ Enter ] → Quick Search → Entity Page / Matching Works → Work Resolution
Header [ Advanced Search… ] → Search Studio → build → Matching Works → Work Resolution
```

### 26.5 Valor

El **Search Studio** hace visible la potencia de OSAP: el usuario **descubre que puede
buscar por** compositor, título, catálogo, alias, representación, proveedor, colección y
confianza. OSAP deja de parecer un buscador de texto y pasa a mostrarse como un **motor de
resolución de obras con múltiples criterios de consulta**.

## 27. Workspace, memoria y resolución reutilizable

### Workspace

Una Resolution no vive aislada: el usuario construye una **sesión de trabajo**.

```
Workspace — Mozart
────────────
Ave Verum · Requiem · Coronation Mass
────────────
[ Compare ] [ Download ] [ Export ]
```

### Resolución reutilizable

Cuando una obra ya está resuelta, **no vuelve a aparecer como un simple resultado**: se
marca como **objeto reutilizable**.

```
Mozart · 179 works
★★★★★ Ave Verum   ✔ already resolved
★★★★  Requiem
★★★   Mass in C
```

### Search History

```
Recent Searches
Mozart · Ave Verum · KV618 · Palestrina · Missa Papae Marcelli
```

### Favoritos

Simplemente **Bookmark** en la Work Resolution.

### Sources (ficha potente)

Cada fuente es una **ficha de referencia**:

```
IMSLP
★★★★★ · Official · HTTP

Coverage      MusicXML · PDF · MIDI
Works · Composers · Collections
Last synchronization · Health · Response time
Trust · Quality · Statistics

Description · License · Maintainer
Tags · Observations
```

## Invariantes (de V3.3)

- La web **nunca habla con el dominio**; toda comunicación pasa por `ApiClient`.
- Las páginas no realizan HTTP directo.
- Estados Loading / Ready / Empty / Error.
- Design System único y centralizado.
- **No se modifica** la API V3.1 ni el dominio V2.

## Lo que NO se toca

`ApiClient` · `Zustand` · `React`/`Routing` · Design System (se amplía, no se rompe).

---

## Criterios de aceptación

- **Work Resolution** como entidad central y **recurso** (`id`, confidence, work,
  Matching Works, representations, evidence, actions).
- **Entity Resolution**: la búsqueda identifica la entidad (Composer/Work/Collection/
  Catalogue/Representation/Source) y navega a la pantalla según el tipo.
- **Search Result ≠ Work Resolution**: pantallas distintas; la resolución solo aparece al
  elegir obra (o si la consulta es inequívoca); no se "inventa" una obra al buscar
  "Mozart".
- **Composer Page**: compositor → obras desplegables (una a la vez) → elegir → Work
  Resolution; sin panel de "resolución" hasta elegir obra.
- **Discover** = exploración musical (trending works/composers, recently incorporated,
  new collections, featured editions); las fuentes NO son el elemento principal (viven en
  Sources).
- **Cuatro niveles** separados: Search → Entity Page → Work Page → Work Resolution →
  Representation (responsabilidades distintas; no mezclar Composer con Work Resolution).
- **Search Studio como constructor de consultas** (AND semántico, "Resolve Works").
- **Matching Works** definidas (tarjetas con Overview → Open Work Resolution).
- **Composer Page** con colecciones primero y obras desplegables.
- **Relationships** en la Work Resolution (same work, editions, arrangements, movements…).
- **Workspace** (sesión de obras: compare/download/export), **resolución reutilizable**
  ("already resolved"), **Search History**, **Favoritos (Bookmark)**.
- **Sources** con ficha potente (coverage, health, trust, quality, statistics, tags…).
- **Workspace** (no *search result*) + **Progressive Disclosure**.
- **La búsqueda devuelve obras, no representaciones** (jerarquía Composer → Work →
  Representation).
- **Matching Works** listados como obras, **expandibles** (al desplegar se muestran las
  representaciones y la mejor).
- **Work Resolution como Knowledge Hub**: ficha viva de la obra (metadatos,
  representaciones enriquecidas, evidence en pestaña, historial, acciones) + **resumen
  automático** (mejor representación por tipo).
- **Explainability contextual** (ⓘ Why this work? / Explain en panel lateral), no
  permanente.
- **Compare es una acción más**, no un bloque propio; el bloque es **Actions**.
- **Sin botones muertos en el MVP** (abrir representación, descargar, abrir proveedor,
  mostrar evidencias funcionan).
- **Search como acción global** (Header), no página.
- **Search Experience**: **Quick Search** (Header, consulta libre) + **Search Studio**
  (página de construcción de consultas por bloques WHAT/WHERE/WHAT KIND/QUALITY/OPTIONS);
  ambos acceden al mismo motor; la búsqueda libre **nunca limita** al motor.
- Navegación: **Home · Discover · Knowledge** (+ Administración secundaria).
- **Explainability** en toda resolución; Discover y Compare definidos.
- Home = Search + Recent/Most accessed/Recently added/Repository status.
- Breadcrumb semántico (navegación lógica, nunca rutas).
- Modo oscuro y preferencias persistentes; sin scroll innecesario; vacíos elegantes;
  animaciones mínimas; iconos consistentes.
- Mobile-first, WCAG AA, i18n (es, ca, fr, en, de).
- Se conservan arquitectura V3.3 e invariantes.

---

## Versionado

```
V3.3  Cliente Web (Arquitectura)
V3.4  UX — Work Resolution e identidad visual
V3.5  Autenticación
V3.6  Administración
```

---

## Plan de entrega

1. **Diseño de UX (Work Resolution) e identidad** (este documento, congelado).
2. **ADR-0030**.
3. **Implementación** (V3.4.b) sobre la infraestructura existente.
4. **Tests** (sin cambios de arquitectura).
