# OSAP — obras-de-usuario-v1 (consolidado)


## Parte: obras-de-usuario-requisitos-v1.md

---

# OSAP — Obras de usuario / aportación / publicación / privacidad — REQUISITOS (acumulación)

**Estado:** ACUMULACIÓN DE REQUISITOS (contexto). **NO congelado, NO contrato, NO código.**
Este documento recoge el diseño conceptual de la futura **obra de usuario** para alimentar una
fase posterior de decisión → contrato → implementación. **No se implementa nada.**

---

# 1. Propósito

Anticipar que la **subida de obras** NO es un simple `POST /works` con un fichero: es un
**submodelo de OSAP más grande** (privacidad, visibilidad, publicación, referencias externas).
Aquí acumulamos los requisitos y estados sin convertirlos todavía en código ni en contrato.

---

# 2. Niveles de relación de una obra con OSAP (conceptual)

Una obra podría tener varios niveles:

| Nivel | Descripción |
|---|---|
| **Obra privada del usuario** | Guardada en OSAP; el usuario conserva su trabajo aunque no se publique. No necesariamente públicos ni el título ni el contenido. Puede existir en storage como recurso privado. |
| **Obra registrada pero no publicada** | OSAP conoce que existe; el usuario puede aportar metadatos. No necesariamente visible en el catálogo público. |
| **Obra parcialmente visible** | Título, descripción, autor/compositor, metadatos seleccionados. Sin publicar la partitura. |
| **Obra con contenido externo** | OSAP puede mostrar información; la partitura/audio/edición permanece fuera. Se conserva una **referencia externa** (comprar, escuchar, descargar, página del autor, editorial…). |
| **Obra publicada en OSAP** | Entran las reglas actuales de catálogo, búsqueda, valoración y, eventualmente, voto. |

---

# 3. Distinción fundamental (conservar)

> **"Existe en OSAP" ≠ "es visible públicamente en OSAP".**

Una obra guardada por un usuario **no** se convierte automáticamente en contenido público.

---

# 4. Dimensiones a separar (probablemente)

- propiedad / autoría;
- visibilidad;
- contenido almacenado;
- metadatos publicados;
- referencias externas;
- permisos del propietario;
- estado de publicación;
- relación con proveedores/directorios externos.

---

# 5. Vínculo con las obras externas (ya decidido)

Para obras externas:
- `relative_path` puede conservar la **referencia que entrega el proveedor**;
- `tags` puede conservar información como el **proveedor**;
- la **ausencia de file/URL local** permite distinguir que **OSAP no posee el contenido**.

Esto es coherente con el nivel "obra con contenido externo" anterior.

---

# 6. Siguiente paso (cuando toque)

Antes de decidir dónde vive cada dato:

1. Lista **completa de casos de uso** de una obra (todos los estados y transiciones).
2. Lista **completa de estados** de una obra.
3. Decidir **dónde vive cada dato** (storage, osap-api, osap-auth; público/privado).
4. Entonces: decisión → contrato → implementación.

---

*Acumulación de requisitos de obras de usuario v1 (2026-08) — contexto; NO congelado.*



## Parte: ideas para obras usuario.md

---

Sí. Y aquí creo que conviene no intentar convertir todavía estas ideas en un contrato. Estamos entrando en un área bastante más compleja que voto, valoración o compositores, porque aparece una nueva dimensión: la obra como propiedad/contenido de un usuario, frente a la obra catalogada públicamente por OSAP.

Mantengo, por tanto, esto como línea de arquitectura en exploración, sin congelar decisiones.

Ideas que añado al mapa
1. Obra privada del usuario

Un usuario podría:

crear/subir una obra;
conservarla en OSAP;
trabajar con ella sin hacerla pública;
guardar partitura, metadatos, descripción, versiones, etc.

Pero guardar una obra no implica publicarla.

Esto introduce una distinción importante:

Existencia de una obra ≠ visibilidad de una obra.

Podríamos tener una obra perfectamente registrada en OSAP que no aparezca en búsquedas públicas.

2. Niveles independientes de visibilidad

Creo que debemos evitar un simple public/private.

Una obra podría tener, conceptualmente, distintos elementos con visibilidad independiente:

título;
compositor/autor;
descripción;
información de la obra;
partitura;
audio;
otros documentos;
enlaces externos.

Por ejemplo:

Visible: título + descripción + autor
No visible: partitura
Enlace externo: Spotify / YouTube / tienda / página personal.

O:

Visible: ficha completa
Partitura: solo propietario
Audio: enlace externo.

Esto nos lleva a pensar en visibilidad por recurso, no solamente visibilidad de la obra.

3. Referencias externas

La obra podría tener relaciones con recursos que no están almacenados en OSAP:

escuchar;
comprar;
descargar;
página personal del compositor;
editorial;
Bandcamp;
YouTube;
Spotify;
otra biblioteca;
página del proveedor.

Y aquí encaja muy bien la decisión que tomamos para obras procedentes de proveedores:

relative_path puede representar una referencia externa, mientras tags puede conservar información del proveedor/origen.

Pero habría que distinguir conceptualmente:

obra OSAP
 ├── recurso interno
 │    └── file
 │
 └── recurso externo
      └── URL / referencia

No deberíamos hacer que el sistema interprete automáticamente que todo relative_path es un fichero local si también puede representar una referencia externa.

4. Relaciones entre obras

Esto me parece especialmente interesante.

Un usuario podría tener:

una obra original;
una versión revisada;
una reducción para piano;
una versión orquestal;
una transcripción;
una interpretación;
una grabación;
una edición;
una publicación externa.

Podríamos necesitar en el futuro relaciones del tipo:

Obra A
 ├── versión de → Obra B
 ├── arreglo de → Obra C
 ├── interpretación de → Obra A
 └── publicado en → recurso externo

No lo cerraría todavía como modelo concreto, pero sí lo anotaría como requisito arquitectónico futuro.

5. Propietario ≠ compositor

Muy importante.

El usuario que sube una obra no tiene por qué ser necesariamente el compositor.

Puede ser:

el propio compositor;
un intérprete;
un profesor;
un alumno;
un editor;
un administrador;
alguien que tiene permiso para conservarla.

Por tanto, debemos evitar diseñar algo como:

work.user_id = composer

Podrían existir al menos dos conceptos distintos:

owner / contributor
composer / creator

Y posiblemente varios usuarios relacionados con una obra.

6. "Publicar" debería ser una acción explícita

Subir/guardar una obra no debería convertirla automáticamente en contenido público.

Podríamos terminar teniendo:

BORRADOR / PRIVADA
        ↓
VISIBLE PARCIALMENTE
        ↓
PÚBLICA

Y posiblemente permitir volver atrás.

Esto también resuelve tu ejemplo:

"Quiero que dejéis visible los datos de mi obra, descripción, pero no la partitura."

No necesitamos crear otra obra para ello. Es la misma obra con otra política de exposición.

7. Solicitudes del usuario a OSAP

Tu frase de:

"un usuario puede pedirnos que dejemos visible..."

abre otra posibilidad.

No todo cambio de visibilidad tiene por qué ser inmediato.

Podría existir:

Usuario
   │
   └── solicita publicación/modificación
             ↓
       revisión OSAP
             ↓
       aceptada / rechazada

Especialmente si queremos que OSAP tenga algún criterio editorial o de derechos.

Esto conecta directamente con Administración, aunque probablemente no queramos meterlo ahora en Administración v1.

8. Derechos y permisos

Aquí aparecerá probablemente una dimensión que todavía no hemos necesitado:

¿Quién puede hacer qué con una obra?

No es lo mismo:

verla;
descargarla;
escucharla;
votarla;
modificarla;
compartirla;
publicarla;
eliminarla;
cambiar su visibilidad;
añadir un enlace externo.

Y además:

que alguien pueda ver una obra no significa que pueda descargar su partitura.

Por eso no recomendaría diseñar ahora un único visibility.

9. La obra externa y la obra de usuario podrían converger

Hay una cuestión arquitectónica que me parece especialmente importante.

Hoy tenemos:

osap-storage
   └── catálogo de obras

Y hemos añadido el caso:

proveedor externo
   └── obra registrada en nuestra BD
       ├── sin file
       ├── relative_path = referencia proveedor
       └── tags = proveedor

Ahora aparece:

usuario
   └── obra propia
       ├── puede tener file
       ├── puede no tener file
       ├── puede tener recursos externos
       └── puede ser privada

No deberíamos crear dos modelos incompatibles de Work.

Idealmente, la arquitectura futura debería poder representar ambos:

                    WORK
                     │
          ┌──────────┴──────────┐
          │                     │
      catálogo externo       usuario
          │                     │
       sin file             con/sin file
       proveedor            privado/público

La naturaleza/origen sería un atributo o relación, no dos tablas conceptualmente desconectadas.

Y hay otra idea que anotaría desde ya

Una obra puede tener recursos, pero la obra no es el recurso.

Por ejemplo:

WORK
 ├── metadata
 ├── ownership
 ├── visibility
 ├── relationships
 │
 └── resources
      ├── score.pdf
      ├── audio.mp3
      ├── preview.pdf
      ├── external-listen
      ├── external-purchase
      └── external-page

Esto nos puede evitar muchos problemas posteriormente.


