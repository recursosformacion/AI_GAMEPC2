from dataclasses import dataclass, field

from .output_format import OutputFormat
from .value_objects import ProviderId


@dataclass(frozen=True)
class CatalogCapabilities:
    """What a catalog provider can do. Used by the resolver to decide which
    providers to consult; no hard-coded provider lists."""

    provider_id: ProviderId
    supports_search: bool = True
    supports_download: bool = True
    supports_streaming: bool = False
    offline: bool = False
    formats: tuple[OutputFormat, ...] = field(default_factory=tuple)
    public_domain_only: bool = False
    requires_auth: bool = False
    metadata: dict[str, object] = field(default_factory=dict)
