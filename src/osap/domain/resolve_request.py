from dataclasses import dataclass, field, replace

from .output_format import OutputFormat
from .quality_level import QualityLevel
from .value_objects import ProviderId


@dataclass(frozen=True)
class ResolveRequest:
    """A rich, immutable request to resolve a musical work.

    Works over musical concepts only; catalog providers translate it internally.
    """

    query: str | None = None
    title: str | None = None
    composer: str | None = None
    genre: str | None = None
    language: str | None = None
    instrumentation: tuple[str, ...] = field(default_factory=tuple)
    voices: tuple[str, ...] = field(default_factory=tuple)
    desired_format: OutputFormat | None = None
    min_quality: QualityLevel | None = None
    license: str | None = None
    public_domain: bool | None = None
    online: bool = True
    offline: bool = True
    use_cache: bool = True
    update_cache: bool = False
    allowed_providers: tuple[ProviderId, ...] = field(default_factory=tuple)
    excluded_providers: tuple[ProviderId, ...] = field(default_factory=tuple)
    metadata: dict[str, object] = field(default_factory=dict)


class ResolveRequestBuilder:
    """Fluent, immutable builder for a `ResolveRequest`."""

    def __init__(self, _request: ResolveRequest | None = None) -> None:
        self._request = _request or ResolveRequest()

    def text(self, value: str) -> "ResolveRequestBuilder":
        return ResolveRequestBuilder(replace(self._request, query=value))

    def title(self, value: str) -> "ResolveRequestBuilder":
        return ResolveRequestBuilder(replace(self._request, title=value))

    def composer(self, value: str) -> "ResolveRequestBuilder":
        return ResolveRequestBuilder(replace(self._request, composer=value))

    def genre(self, value: str) -> "ResolveRequestBuilder":
        return ResolveRequestBuilder(replace(self._request, genre=value))

    def language(self, value: str) -> "ResolveRequestBuilder":
        return ResolveRequestBuilder(replace(self._request, language=value))

    def instrumentation(self, *values: str) -> "ResolveRequestBuilder":
        return ResolveRequestBuilder(replace(self._request, instrumentation=self._request.instrumentation + values))

    def voices(self, *values: str) -> "ResolveRequestBuilder":
        return ResolveRequestBuilder(replace(self._request, voices=self._request.voices + values))

    def format(self, value: OutputFormat) -> "ResolveRequestBuilder":
        return ResolveRequestBuilder(replace(self._request, desired_format=value))

    def min_quality(self, value: QualityLevel) -> "ResolveRequestBuilder":
        return ResolveRequestBuilder(replace(self._request, min_quality=value))

    def license(self, value: str) -> "ResolveRequestBuilder":
        return ResolveRequestBuilder(replace(self._request, license=value))

    def public_domain(self, value: bool) -> "ResolveRequestBuilder":
        return ResolveRequestBuilder(replace(self._request, public_domain=value))

    def online(self, value: bool) -> "ResolveRequestBuilder":
        return ResolveRequestBuilder(replace(self._request, online=value))

    def offline(self, value: bool) -> "ResolveRequestBuilder":
        return ResolveRequestBuilder(replace(self._request, offline=value))

    def use_cache(self, value: bool) -> "ResolveRequestBuilder":
        return ResolveRequestBuilder(replace(self._request, use_cache=value))

    def allow_provider(self, value: ProviderId) -> "ResolveRequestBuilder":
        return ResolveRequestBuilder(
            replace(self._request, allowed_providers=self._request.allowed_providers + (value,))
        )

    def exclude_provider(self, value: ProviderId) -> "ResolveRequestBuilder":
        return ResolveRequestBuilder(
            replace(self._request, excluded_providers=self._request.excluded_providers + (value,))
        )

    def build(self) -> ResolveRequest:
        return self._request
