Objetivos del proyecto
Qué pretende resolver OSAP.
Qué problemas quedan fuera de su alcance.
Principios irrenunciables
Los metadatos originales nunca se modifican.
La normalización solo existe para el matching.
El usuario nunca ve datos normalizados.
Una obra no es una representación.
Ningún proveedor tiene privilegios arquitectónicos.
Modelo de dominio
Representation
RawMetadata
RepresentationFeatures
WorkIdentity
ResolvedWork
Alias
DownloadInfo
Provider
CatalogIdentifier
MergeDecision
Conflict
Relaciones entre entidades
Un ResolvedWork posee N representaciones.
Cada representación pertenece exactamente a una obra.
Una representación conserva siempre sus metadatos originales.
Una obra puede tener múltiples alias.
Una obra puede tener movimientos y arreglos relacionados.
Pipeline de resolución
Ingesta.
Extracción.
Normalización interna.
Construcción de la identidad.
Matching.
Resolución.
Selección del título canónico.
IdentityResolver
Qué entradas recibe.
Qué decisiones puede tomar.
Qué nunca debe hacer.
Algoritmo de matching
Reglas veto.
Scoring.
Umbrales.
Revisión manual.
Sistema de conflictos
Cómo registrar una decisión.
Cómo revertir una fusión.
Cómo auditar el proceso.
Modelo de descarga
Descarga directa.
Descarga manual.
URL oficial.
Motivo.
Restricciones.
Estado.
API pública
Qué devuelve /search.
Qué devuelve /works/{id}.
Qué devuelve /resolve.
Qué devuelve una representación.
Qué devuelve DownloadInfo.
CLI
Qué debe mostrar.
Qué nunca debe mostrar.
Cómo presentar conflictos.
Extensibilidad
Cómo añadir nuevos proveedores.
Cómo añadir nuevos sistemas de catálogo.
Cómo añadir nuevos algoritmos de matching.
No objetivos
Lo que el proyecto deliberadamente no hace.
Casos de prueba canónicos
Ave Verum Corpus.
Requiem K626.
Symphony No. 40.
Obras sin catálogo.
Arreglos.
Movimientos.
Traducciones.
Alias.
Decisiones arquitectónicas (ADR)
Por qué se eligió este diseño.
Qué alternativas se descartaron.

Creo que incluso cambiaría algunos nombres.

Por ejemplo:

Actual	Propuesto
WorkMergeService	IdentityResolver
MetadataNormalizer	FeatureExtractor + InternalNormalizer
WorkGroup	ResolvedWork
CandidateRepresentation	Representation
canonical_score	MatchConfidence
primary	PreferredRepresentation

Esos nombres expresan mejor el dominio musical y reducen la sensación de que el sistema "fusiona títulos".

Y añadiría un principio que considero fundamental

OSAP no identifica títulos; identifica obras musicales.

Los títulos, catálogos, formatos, idiomas, movimientos y representaciones son únicamente evidencias utilizadas para inferir la identidad de una obra. La identidad resultante es una entidad propia, independiente de cualquier proveedor, y todas las representaciones permanecen vinculadas a ella sin alterar nunca sus metadatos originales.

Creo sinceramente que este documento puede convertirse en la "constitución" del proyecto. Una vez aprobado, cualquier implementación (CLI, REST, React o futuros proveedores) deberá respetarlo, evitando que la arquitectura cambie cada vez que intervenga un modelo de IA.