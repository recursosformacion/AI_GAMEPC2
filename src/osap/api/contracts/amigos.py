"""Contratos de «Los amigos»: grupos, membresías, artículos y recursos.

Modelo mínimo y normalizado. Los artículos pertenecen a un grupo; los recursos
(vídeos/fotografías) son filas propias para poder añadir tipos en el futuro sin tocar
el artículo. La fecha del evento (`event_date`) es independiente de `published_at`.
"""

from __future__ import annotations

from .base import _Frozen


class AmigosMediaRequest(_Frozen):
    kind: str  # video | photo
    url: str
    caption: str | None = None
    credit: str | None = None
    position: int = 0


class AmigosArticleCreateRequest(_Frozen):
    title: str
    event_date: str  # AAAA-MM-DD
    body: str
    summary: str | None = None
    cover_url: str | None = None
    media: list[AmigosMediaRequest] = []
    action: str = "draft"  # draft | publish


class AmigosArticleUpdateRequest(_Frozen):
    title: str | None = None
    event_date: str | None = None
    body: str | None = None
    summary: str | None = None
    cover_url: str | None = None
    media: list[AmigosMediaRequest] | None = None


class AmigosArticleReturnRequest(_Frozen):
    note: str = ""


class AmigosGroupLink(_Frozen):
    """Enlace común del grupo (web/redes). `label` solo se usa para `kind='other'`."""

    kind: str  # facebook | instagram | other
    url: str
    label: str | None = None


class AmigosGroupCreateRequest(_Frozen):
    name: str
    kind: str = "coral"
    slug: str | None = None
    description: str | None = None
    image_url: str | None = None
    editorial_mode: str = "moderated"
    website: str | None = None
    email: str | None = None
    logo_url: str | None = None
    links: list[AmigosGroupLink] = []


class AmigosGroupUpdateRequest(_Frozen):
    name: str | None = None
    description: str | None = None
    image_url: str | None = None
    editorial_mode: str | None = None
    status: str | None = None
    website: str | None = None
    email: str | None = None
    logo_url: str | None = None
    links: list[AmigosGroupLink] | None = None


class AmigosMemberGrantRequest(_Frozen):
    user_id: str
    role: str = "collaborator"  # collaborator | admin


class AmigosMediaRead(_Frozen):
    kind: str
    url: str
    provider: str | None = None
    video_id: str | None = None
    caption: str | None = None
    credit: str | None = None
    position: int = 0


class AmigosGroupRead(_Frozen):
    id: str
    slug: str
    name: str
    kind: str
    description: str | None = None
    image_url: str | None = None
    website: str | None = None
    email: str | None = None
    logo_url: str | None = None
    links: list[AmigosGroupLink] = []
    status: str
    editorial_mode: str
    created_at: str = ""
    updated_at: str = ""


class AmigosArticleRead(_Frozen):
    id: str
    group_id: str
    group_slug: str | None = None
    group_name: str | None = None
    title: str
    slug: str
    event_date: str
    summary: str | None = None
    body: str = ""
    cover_url: str | None = None
    author_user_id: str
    status: str
    published_at: str | None = None
    created_at: str = ""
    updated_at: str = ""
    media: list[AmigosMediaRead] = []


class AmigosArticleListRead(_Frozen):
    items: list[AmigosArticleRead]
    total: int


class AmigosMemberRead(_Frozen):
    group_id: str
    user_id: str
    role: str
    status: str
    created_at: str = ""
    updated_at: str = ""


class AmigosMemberListRead(_Frozen):
    items: list[AmigosMemberRead]
    total: int


# --- Especialización por tipo: ficha de coral --------------------------------


class AmigosCoralDetailsUpdate(_Frozen):
    """Ficha estructurada de un coral (PUT: reemplaza la ficha; los vacíos se limpian)."""

    foundation_date: str | None = None
    dissolution_date: str | None = None
    locality: str | None = None
    region: str | None = None
    country_code: str | None = None
    venue: str | None = None
    formation_type: str | None = None
    member_count: int | None = None
    website: str | None = None
    public_email: str | None = None
    director_person_id: str | None = None
    director_label: str | None = None
    linked_entity: str | None = None
    repertoire: list[str] | None = None
    languages: list[str] | None = None
    places: list[str] | None = None


class AmigosCoralDetailsRead(_Frozen):
    group_id: str
    kind: str = "coral"
    foundation_date: str | None = None
    dissolution_date: str | None = None
    locality: str | None = None
    region: str | None = None
    country_code: str | None = None
    venue: str | None = None
    formation_type: str | None = None
    member_count: int | None = None
    website: str | None = None
    public_email: str | None = None
    director_person_id: str | None = None
    director_label: str | None = None
    linked_entity: str | None = None
    repertoire: list[str] = []
    languages: list[str] = []
    places: list[str] = []


# --- Agenda: actuaciones y eventos -------------------------------------------


class AmigosEventGroup(_Frozen):
    group_id: str
    role: str = "participant"  # participant | organizer


class AmigosActuacionRequest(_Frozen):
    title: str | None = None
    summary: str | None = None
    description: str | None = None
    image_url: str | None = None
    kind: str | None = None
    modality: str | None = None
    event_status: str | None = None
    starts_on: str | None = None
    starts_at: str | None = None
    ends_on: str | None = None
    ends_at: str | None = None
    timezone: str | None = None
    registration_deadline: str | None = None
    venue_name: str | None = None
    venue_address: str | None = None
    locality: str | None = None
    region: str | None = None
    country_code: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    map_url: str | None = None
    organizer_name: str | None = None
    organizer_website: str | None = None
    event_url: str | None = None
    tickets_url: str | None = None
    price: str | None = None
    access_info: str | None = None
    public_contact: str | None = None
    organizer_group_id: str | None = None
    last_verified_on: str | None = None
    internal_notes: str | None = None
    groups: list[AmigosEventGroup] = []
    action: str = "draft"


class AmigosActuacionStatusRequest(_Frozen):
    editorial_status: str


class AmigosActuacionRead(_Frozen):
    id: str
    slug: str
    title: str
    summary: str | None = None
    description: str | None = None
    image_url: str | None = None
    kind: str
    modality: str
    event_status: str
    editorial_status: str
    starts_on: str
    starts_at: str | None = None
    ends_on: str | None = None
    ends_at: str | None = None
    timezone: str | None = None
    registration_deadline: str | None = None
    venue_name: str | None = None
    venue_address: str | None = None
    locality: str | None = None
    region: str | None = None
    country_code: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    map_url: str | None = None
    organizer_name: str | None = None
    organizer_website: str | None = None
    event_url: str | None = None
    tickets_url: str | None = None
    price: str | None = None
    access_info: str | None = None
    public_contact: str | None = None
    organizer_group_id: str | None = None
    last_verified_on: str | None = None
    author_user_id: str = ""
    published_at: str | None = None
    created_at: str = ""
    updated_at: str = ""
    groups: list[AmigosEventGroup] = []


class AmigosActuacionListRead(_Frozen):
    items: list[AmigosActuacionRead]
    total: int
