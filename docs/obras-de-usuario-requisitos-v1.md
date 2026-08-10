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
