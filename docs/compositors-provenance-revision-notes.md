# OSAP — Compositores: proveniencia, revisión e inspección (notas de diseño)

**Estado:** NOTAS / PENDIENTE. **No congelado, no contrato, no código.**
Línea de trabajo para administración de compositores (fusión dirigida e inspección).

---

# 1. Proveniencia de un compositor

Conservar la relación:

```
Compositor
    id
    nombre
    ...
    ├── origen/evidencia
    │     work_id
    │     proveedor
    │     autor_extraido
    │     fecha/dato de extracción
    │     obra (título completo)
    │     representaciones / partitura
    │     enlace a fuente
    └── estado de revisión
```

Permite responder: **"¿Por qué existe este compositor?"** y **"¿El algoritmo extrajo bien el
autor?"** (p. ej. un "autor" que en realidad es "!! Go to settings ... !!" revela extracción
incorrecta).

---

# 2. Fusión dirigida desde el compositor actual

- El sujeto de la fusión es el **compositor actual** (origen implícito).
- Se selecciona solo el **destino** entre todos los compositores existentes (búsqueda global).
- **Confirmación explícita** mostrando Origen + Destino antes de ejecutar.
- El texto deja claro: las obras, alias y relaciones del origen pasan al destino.

## Búsqueda global de destino

- Debe buscar entre **todos** los compositores (correctos, incorrectos, revisados, no
  revisados, generados, corregidos…). No filtrar a "válidos": la administración inspecciona la
  realidad del catálogo.

---

# 3. El detalle como herramienta de inspección

El detalle debe permitir (sin preocuparse por N+1 en esta pantalla administrativa):

- identidad y estado del compositor;
- aliases;
- obra que originó su creación;
- título completo de esa obra;
- autor extraído;
- proveedor;
- identificadores de la obra;
- información completa de la obra;
- representaciones disponibles;
- enlaces al proveedor;
- partitura/previsualización si es accesible.

---

# 4. Distinción: "compositor" vs "compositor revisado"

Conceptualmente distinguir (sin necesariamente añadir aún un estado al contrato):

```
"El algoritmo creó esto"
vs
"Un administrador ha comprobado que esto es correcto"
```

Relevante para futuros datos de usuario/publicación.

---

# 5. Estado

- Pendiente de implementar; notas de diseño para la futura fase de administración de
  compositores (inspección + fusión dirigida + revisión).

---

*Notas de diseño de compositores (2026-08) — pendiente.*
