# ADR-0032 – Metadata Ownership

## Estado

Aceptado. Fija el principio arquitectónico de **propiedad de la metadata** (contrato
osap-storage ↔ osap-api v1.3).

## Principio

> **La metadata pertenece a `osap-storage`. El CDN solo almacena binarios. `osap-api`
> nunca lee el CDN para obtener información de una obra.**

## Contexto

`osap-api` reconstruía metadata leyendo JSON del CDN (p. ej.
`https://cdn.openmusicrepository.com/storage2017/metadata/100654.json`) y dependía del
formato de la fuente (MuseScore). Esto acoplaba `osap-api` a la estructura interna del
almacenamiento y al formato de origen.

## Decisión

**Prohibido en `osap-api`** (a partir de esta versión):

- abrir JSON del CDN;
- descargar metadata del CDN;
- interpretar metadata MuseScore;
- conocer el layout del storage.

### Responsabilidades

- **`osap-storage`** es el **propietario de la metadata**: almacena archivos, almacena
  metadata, la indexa, la enriquece (desde el proceso ETL) y la **expone mediante API**.
- **`osap-api`** es responsable únicamente de: búsqueda, matching, ranking, merge,
  evidence y work resolution. **Nunca** lee JSON.
- **CDN** queda reducido a **servir binarios** (MusicXML, PDF, MIDI, MEI, PNG, ZIP...).
  **Nunca metadata.**
- El **JSON de la fuente** deja de ser una fuente consultable; pasa a `ETL → Base de
  datos → API`. Solo existe para auditoría, reprocesado y reconstrucción del índice.
  **Nunca para responder peticiones.**

### Contrato (v1.3)

- El proveedor devuelve **Work enriquecida**: `Work` + `Metadata` + `Statistics` +
  `Representations`.
- La búsqueda (`/api/search`) es **ligera** (solo localizar); el recurso
  (`/api/resource/{id}?include=metadata,representations,statistics`) es **rico**.
- Las **representaciones exponen `links` públicos** generados por `osap-storage`, nunca
  rutas físicas, `relative_path` ni hashes.
- `osap-api` copia esos campos a su `RepresentationInfo`; **no construye URLs** a partir
  de `relative_path` (no conoce CDN, directorios, R2 ni hashes).
- El endpoint de descarga es anidado:
  `/api/resource/{id}/representations/{rid}/download`.

## Consecuencias

- Desaparecen los **accesos al CDN desde `osap-api`**.
- Desaparecen las **dependencias del formato MuseScore**.
- La metadata queda **centralizada** en `osap-storage`.
- `osap-storage` se convierte realmente en el **repositorio de conocimiento**.
- El CDN vuelve a ser simplemente un **almacén de binarios**.
- `osap-api` construye la Work Resolution a partir de entidades `Work` enriquecidas; no
  transfiere lógica de resolución a Storage (el proveedor nunca devuelve una Work
  Resolution).
