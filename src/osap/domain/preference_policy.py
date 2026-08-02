from dataclasses import dataclass, field

from .output_format import OutputFormat


@dataclass(frozen=True)
class SourcePreferencePolicy:
    prefer_public_domain: bool = False
    preferred_formats: tuple[OutputFormat, ...] = field(default_factory=tuple)
    prefer_latest_edition: bool = False
    prefer_satb: bool = False
    prefer_offline: bool = False
    allowed_repositories: tuple[str, ...] = field(default_factory=tuple)
    max_results: int | None = None
