"""Modelo de dominio de «Los amigos» (miniblog de grupos musicales).

Tipos cerrados y estables compartidos por el servicio de aplicación, el almacén
operativo y el API. No contiene lógica de persistencia ni de HTTP.

Jerarquía funcional: Los amigos → Corales → CTV → Artículos. El modelo es genérico
por tipo de grupo (`GROUP_KINDS`): «coral» es solo el primer tipo soportado.
"""

from __future__ import annotations

# Tipos/categorías de agrupación. La categoría de navegación («Corales») equivale al
# tipo de grupo: los grupos concretos (CTV) son instancias de un tipo. La lista es aditiva
# (futuras orquestas, entidades anunciantes… se añaden sin rehacer el modelo).
GROUP_KINDS = frozenset({"coral"})

# Estados de un grupo. «disuelto» es un estado terminal que NO borra historial ni relaciones.
GROUP_STATUSES = frozenset({"active", "inactive", "dissolved"})

# Modalidades editoriales por grupo (decisión del administrador del grupo).
#   direct    — el colaborador autorizado publica sin aprobación previa.
#   moderated — el artículo queda `pending` hasta que un admin del grupo lo aprueba.
EDITORIAL_MODES = frozenset({"direct", "moderated"})

# Roles dentro de un grupo. NO son roles globales de OSAP.
MEMBER_ROLES = frozenset({"admin", "collaborator"})
MEMBER_STATUSES = frozenset({"active", "revoked"})

# Estados editoriales de un artículo.
#   draft     — borrador privado del autor.
#   pending   — enviado y a la espera de aprobación (solo en modalidad `moderated`).
#   published — visible públicamente.
#   withdrawn — retirado; deja de ser público pero NO se borra (trazabilidad).
ARTICLE_STATUSES = frozenset({"draft", "pending", "published", "withdrawn"})
# Estados que se exponen públicamente.
PUBLIC_ARTICLE_STATUSES = frozenset({"published"})

# Tipos de recurso audiovisual asociados a un artículo (aditivo).
MEDIA_KINDS = frozenset({"video", "photo"})

# Tipos de enlace social de un grupo (datos comunes a cualquier grupo). Extensible.
GROUP_LINK_KINDS = frozenset({"facebook", "instagram", "other"})

# --- Especialización «coral» (datos estructurados propios del tipo) -------------

# Tipo de formación de un coral. Vocabulario controlado (catálogo en código; se
# distingue de la clasificación de obras del catálogo musical).
FORMATION_TYPES = frozenset(
    {"mixed", "equal_voices", "children", "youth", "male", "female", "other"}
)

# Facetas multivalor de un coral (relación normalizada, nunca CSV).
#   repertoire — ámbitos principales de repertorio
#   language   — idiomas habituales del repertorio
#   place      — lugares de actuación habituales
CORAL_ATTRIBUTE_FACETS = frozenset({"repertoire", "language", "place"})

# --- Subida de imágenes (recursos de «Los amigos») ------------------------------

# Solo imágenes; el contenido se guarda en osap-storage y se sirve desde osap-api.
IMAGE_MIME_TYPES = frozenset(
    {"image/jpeg", "image/png", "image/webp", "image/gif", "image/avif"}
)
MAX_IMAGE_BYTES = 5 * 1024 * 1024

# --- Agenda de actuaciones y eventos (categoría «Próximas actuaciones y eventos») ---

# Tipo de evento.
EVENT_KINDS = frozenset(
    {"concert", "meeting", "festival", "workshop", "mass", "competition", "rehearsal", "other"}
)
# Estado del evento (independiente del estado editorial de publicación).
EVENT_STATUSES = frozenset({"scheduled", "postponed", "cancelled", "held"})
# Modalidad de asistencia.
EVENT_MODALITIES = frozenset({"onsite", "online", "hybrid"})
# Relación grupo↔evento.
EVENT_GROUP_ROLES = frozenset({"organizer", "participant"})

