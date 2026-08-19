# Evolución de la búsqueda: índice local de obras

> Documento de diseño que explica cómo evoluciona la búsqueda actual (proveedores en
> vivo, incierta y lenta) hacia un **índice local completo** (rápida, determinista e
> idéntica siempre), respondiendo a las preguntas de arquitectura: quién lo construye,
> dónde, cómo se sincroniza, cómo se invalida con los cambios del Maestro y qué pasa
> con los proveedores que no entregan lista completa.

## 1. Problemas actuales (motivación)

- **Inconsistencia**: buscar "mozart" y "ave verum" da representaciones distintas para
  la misma obra; depende de la query y de lo que cada proveedor devuelve en vivo.
- **Tiempos**: 5-60 s la primera búsqueda (proveedores en paralelo + enriquecimiento
  por obra en background).
- **Descargas rotas**: OMR (nuestro corpus, MusicXML) sin URL de descarga; Mutopia
  deja el navegador en "Reanudar"; MusicBrainz no tiene fichero (solo metadata).
- **Resultados inciertos**: el cache del orquestador expira y el enriquecimiento
  depende del estado; cada run puede diferir.

## 2. El índice local (qué es, físicamente)

Dos tablas en la BD de osap-api:

```
index_works          -- una fila por Obra ÚNICA (deduplicada)
  id · title · title_key (normalizado) · composer_name · composer_id (FK → Maestro)
  catalogue · catalogue_key · year · instrumentation · created_at · updated_at
  Índices: title_key, composer_id, catalogue_key

index_representations -- una fila por representación de cada obra
  id · work_id · provider · format · download_url · title_provider · available · quality
  Índice: work_id
```

**Clave del diseño:** el índice **guarda el resultado normalizado** (`title_key`,
`composer_id`), no lo recalcula por búsqueda. La búsqueda es un `SELECT` por
`title_key LIKE` / `composer_id` / `catalogue_key` → obra + representaciones.
**~ms, determinista, idéntico siempre.**

## 3. ¿Quién lo construye? osap-api (no storage)

**osap-api es el constructor natural del índice**, porque ya es dueño de TODAS las
piezas necesarias:

| Pieza | Dónde vive | Rol en el índice |
|---|---|---|
| Capa de proveedores | `osap-api` (fetchers, orquestador) | enumera los catálogos |
| Normalización de títulos | `MetadataNormalizer` (osap-api) | `title_key` |
| Canonicalización de compositor | `Canonicalizer` (osap-api) | compositor canónico |
| Unificación de compositores | Maestro + autoridad + `composer_identity_resolution` (osap-api/storage) | `composer_id` |
| Agrupación/fusión de obras | `work_merge_service` / `work_grouper` / `work_grouping_matcher` (osap-api) | dedupe del índice |
| Búsqueda | osap-api | lee el índice |

La confusión legítima: **la carga de obras** (import PDMX) fue de osap-storage, pero la
**normalización y fusión para la búsqueda** son de osap-api (normalizer, canonicalizer,
grouper, matcher y resolución). Desde la perspectiva de la búsqueda, **storage es un
proveedor más** (OMR); no es dueño del índice. El índice es un **derivado** de los
proveedores + la normalización/fusión de osap-api + el Maestro.

**El indexador** es un servicio interno de osap-api (job de sincronización) que REUSA
los componentes de normalización/fusión existentes — no los reinventa. El trabajo duro
ya hecho (Maestro, autoridad, resolución, normalización) **se capitaliza, no se repite**.

## 4. ¿Dónde se construye? En producción, sin copiar tablas

- El índice es **derivado de datos de prod**: el Maestro (compositores, aliases,
  identifiers), la autoridad, la resolución y los dumps de los proveedores. Por eso se
  construye **en prod directamente**.
- El build es un **job en background** (como `provider-sync`) que escribe con `upsert`
  (`INSERT ... ON DUPLICATE KEY UPDATE`) y **no bloquea** las búsquedas (la búsqueda lee
  las filas ya escritas).
- **No hay copia de tablas** prod↔staging. La alternativa staging (construir en un
  staging conectado a la BD de prod y luego `mysqldump` las tablas del índice) es posible
  pero innecesaria: construir en prod es directo y evita la copia.

## 5. Sincronización: periódica e incremental (no continua)

- **1ª carga completa**: horas (IMSLP ~2 h, MusicBrainz más) — en background, una vez.
- **Incrementales**: minutos. IMSLP/MusicBrainz exponen "cambios recientes"; OMR se
  difiere por `updated_at`; Mutopia es pequeño.
- **La normalización es determinista**: misma entrada → misma `title_key`/`composer_id`.
  Las reglas NO cambian; se aplican a filas nuevas con las mismas funciones. No es
  "re-hacer el trabajo" — es aplicar reglas fijadas a datos nuevos.
- **Nuevos compositores** se resuelven automáticamente con el pipeline existente (o
  quedan en revisión, como hoy). El Maestro/autoridad **crece, no se recalcula**.
- Único re-build: si se cambia una regla de normalización → re-indexar las filas
  afectadas (script acotado).

## 6. Invalidación por cambios del Maestro (fusión, alias, atribución)

**Problema:** el índice guarda `composer_id` (FK al Maestro). Si el admin fusiona
compositores (A→B), marca uno como atribución (lo retira) o altera aliases, el índice
**queda desactualizado** para las obras afectadas.

**Solución (tres capas):**
1. **En la operación (recomendado):** la fusión y la conversión a atribución
   **actualizan el índice en la misma transacción**:
   `UPDATE index_works SET composer_id = B WHERE composer_id = A`. Las correcciones del
   admin son **puntuales y raras** → el coste es despreciable.
2. **En la sync:** la sincronización incremental re-resuelve el compositor de las obras
   afectadas usando el Maestro actual (seguridad extra).
3. **Aliases:** cambiar un alias no cambia `composer_id`, pero sí cómo se resuelven
   nombres nuevos → los incrementales lo aplican.

El índice es un **derivado**: refleja el estado del Maestro. Cualquier cambio de
identidad se propaga por la transacción de la operación + la sync. No hay
incoherencia persistente.

## 7. Proveedores sin lista completa: marcar NO es la solución

- **Marcar cobertura (flag `indexados vs conocidos`)** es **transparencia**, no solución.
  Mostrar "cobertura parcial" avisa, pero no mejora el resultado.
- La mejora real es el **modo híbrido**:
  - Proveedores **indexados** (IMSLP, OMR, Mutopia) → respuesta del índice (ms, idéntica).
  - Proveedores **sin lista completa** (RISM, MusicBrainz si el dump es inviable) →
    **consulta en vivo** en esa búsqueda y se fusiona con el índice.
  - **Enriquecimiento orgánico**: cada búsqueda en vivo cachea lo encontrado al índice →
    la cobertura crece sola para ese proveedor.
- El flag solo hace visible la limitación; el **híbrido + orgánico** es lo que aporta
  valor y evita que quede "sin efecto".

## 8. Descargas (problemas actuales a resolver en paralelo)

| Proveedor | Problema | Fix |
|---|---|---|
| OMR (nuestro corpus, MusicXML) | el search de storage no devuelve `url` → `download_url=null` → sin botones | el fetcher OMR debe **construir la URL** (`{storage}/api/v1/...`) con el token de servicio |
| Mutopia (PDF) | el proxy de descarga deja el navegador en "Reanudar" | revisar el endpoint de descarga (Content-Length/streaming o anti-bot) |
| MusicBrainz | no tiene fichero (solo metadata) | `available=False` + "abrir en MusicBrainz" (página web) — ya corregido |

## 9. Evolución / roadmap

1. **Índice local completo** (consistencia + velocidad + determinismo) — el problema
   central.
2. **Fix descarga OMR** (nuestro corpus descargable).
3. **Fix proxy Mutopia** (descargas reales).
4. **Híbrido + cobertura** (proveedores parciales).
5. **Invalidación por Maestro** (fusión/atribución → actualiza el índice).

## 10. Resumen de decisiones

- El índice lo construye **osap-api** (reusando su normalización/fusión/resolución).
- Se construye **en prod**, job background, sin copiar tablas.
- Sync **incremental y determinista** (no continua).
- Los cambios del Maestro **invalidan y se propagan** (transacción + sync).
- Marcando proveedores **no basta**: el híbrido + enriquecimiento orgánico es lo que
  da valor.
