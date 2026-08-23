from dataclasses import dataclass, field, replace

from .output_format import OutputFormat
from .quality_level import QualityLevel
from .resolve_request import ResolveRequest
from .value_objects import ProviderId


@dataclass(frozen=True)
class SearchRequest:
    """A rich, immutable search query.

    A search is NOT a resolve: it may request terms (composer, instrument,
    date range...) without intending to resolve a specific work.
    """

    query: str | None = None
    title: str | None = None
    composer: str | None = None
    catalogue: str | None = None
    instrumentation: tuple[str, ...] = field(default_factory=tuple)
    voices: tuple[str, ...] = field(default_factory=tuple)
    genre: str | None = None
    key: str | None = None
    year_range: tuple[int, int] | None = None
    language: str | None = None
    desired_format: OutputFormat | None = None
    min_quality: QualityLevel | None = None
    public_domain_only: bool | None = None
    online: bool = True
    offline: bool = True
    allowed_providers: tuple[ProviderId, ...] = field(default_factory=tuple)
    excluded_providers: tuple[ProviderId, ...] = field(default_factory=tuple)
    metadata: dict[str, object] = field(default_factory=dict)

    @classmethod
    def from_resolve(cls, request: ResolveRequest) -> "SearchRequest":
        """Derive a search query from a resolve request (transitional bridge).

        Lets the core reason with `SearchRequest` while providers still accept a
        `ResolveRequest` (until V2.0.2/0.3 align the provider port).
        """
        return cls(
            query=request.query,
            title=request.title,
            composer=request.composer,
            catalogue=request.catalogue,
            genre=request.genre,
            language=request.language,
            instrumentation=request.instrumentation,
            voices=request.voices,
            desired_format=request.desired_format,
            min_quality=request.min_quality,
            public_domain_only=request.public_domain,
            online=request.online,
            offline=request.offline,
            allowed_providers=request.allowed_providers,
            excluded_providers=request.excluded_providers,
            metadata=request.metadata,
        )

    @property
    def searches_by_catalogue(self) -> bool:
        return bool(self.catalogue)

    @property
    def searches_by_instrumentation(self) -> bool:
        return bool(self.instrumentation)

    @property
    def searches_by_genre(self) -> bool:
        return bool(self.genre)

    @property
    def searches_by_key(self) -> bool:
        return bool(self.key)

    @property
    def searches_by_year(self) -> bool:
        return self.year_range is not None


class SearchRequestBuilder:
    """Fluent, immutable builder for a `SearchRequest`."""

    def __init__(self, _request: SearchRequest | None = None) -> None:
        self._request = _request or SearchRequest()

    def text(self, value: str) -> "SearchRequestBuilder":
        return SearchRequestBuilder(replace(self._request, query=value))

    def title(self, value: str) -> "SearchRequestBuilder":
        return SearchRequestBuilder(replace(self._request, title=value))

    def composer(self, value: str) -> "SearchRequestBuilder":
        return SearchRequestBuilder(replace(self._request, composer=value))

    def catalogue(self, value: str) -> "SearchRequestBuilder":
        return SearchRequestBuilder(replace(self._request, catalogue=value))

    def instrumentation(self, *values: str) -> "SearchRequestBuilder":
        return SearchRequestBuilder(replace(self._request, instrumentation=self._request.instrumentation + values))

    def voices(self, *values: str) -> "SearchRequestBuilder":
        return SearchRequestBuilder(replace(self._request, voices=self._request.voices + values))

    def genre(self, value: str) -> "SearchRequestBuilder":
        return SearchRequestBuilder(replace(self._request, genre=value))

    def key(self, value: str) -> "SearchRequestBuilder":
        return SearchRequestBuilder(replace(self._request, key=value))

    def year_range(self, start: int, end: int) -> "SearchRequestBuilder":
        return SearchRequestBuilder(replace(self._request, year_range=(start, end)))

    def format(self, value: OutputFormat) -> "SearchRequestBuilder":
        return SearchRequestBuilder(replace(self._request, desired_format=value))

    def min_quality(self, value: QualityLevel) -> "SearchRequestBuilder":
        return SearchRequestBuilder(replace(self._request, min_quality=value))

    def public_domain_only(self, value: bool) -> "SearchRequestBuilder":
        return SearchRequestBuilder(replace(self._request, public_domain_only=value))

    def allow_provider(self, value: ProviderId) -> "SearchRequestBuilder":
        return SearchRequestBuilder(
            replace(self._request, allowed_providers=self._request.allowed_providers + (value,))
        )

    def exclude_provider(self, value: ProviderId) -> "SearchRequestBuilder":
        return SearchRequestBuilder(
            replace(self._request, excluded_providers=self._request.excluded_providers + (value,))
        )

    def build(self) -> SearchRequest:
        return self._request
