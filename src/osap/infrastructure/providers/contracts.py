"""Provider Work DTO (Provider API v1.3 contract).

All providers return exactly this object shape. OSAP-API is the only layer that
transforms it into the internal model. Providers never know the internal model.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ProviderLinks:
    download: str | None = None
    view: str | None = None
    thumbnail: str | None = None


@dataclass(frozen=True)
class ProviderResource:
    id: str
    format: str
    mime_type: str | None = None
    available: bool = True
    license: str | None = None
    links: ProviderLinks = field(default_factory=ProviderLinks)


@dataclass(frozen=True)
class ProviderIdentity:
    id: str
    title: str
    composer: str | None = None
    catalogue: str | None = None
    confidence: float = 0.9


@dataclass(frozen=True)
class ProviderMetadata:
    subtitle: str | None = None
    opus: str | None = None
    musical_key: str | None = None
    duration: str | None = None
    measures: int | None = None
    pages: int | None = None
    parts: int | None = None
    license: str | None = None
    public_domain: bool | None = None
    description: str | None = None
    genres: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    instruments: tuple[str, ...] = ()
    parts_names: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProviderStatistics:
    favorites: int = 0
    downloads: int = 0
    views: int = 0
    rating: float = 0.0


@dataclass(frozen=True)
class ProviderWork:
    identity: ProviderIdentity
    metadata: ProviderMetadata = field(default_factory=ProviderMetadata)
    statistics: ProviderStatistics = field(default_factory=ProviderStatistics)
    resources: tuple[ProviderResource, ...] = ()
