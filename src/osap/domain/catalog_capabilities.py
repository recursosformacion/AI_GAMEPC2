from dataclasses import dataclass, field

from .cost_level import CostLevel
from .output_format import OutputFormat
from .value_objects import ProviderId


@dataclass(frozen=True)
class CatalogCapabilities:
    """What a catalog provider can do (and can search by).

    Used by the resolver to decide which providers to consult; no hard-coded
    provider lists.
    """

    provider_id: ProviderId
    supports_search: bool = True
    supports_download: bool = True
    supports_streaming: bool = False
    supports_reference: bool = False
    offline: bool = False
    formats: tuple[OutputFormat, ...] = field(default_factory=tuple)
    public_domain_only: bool = False
    requires_auth: bool = False
    cost_level: CostLevel = CostLevel.FREE
    supports_title: bool = True
    supports_composer: bool = True
    supports_catalogue: bool = True
    supports_instrumentation: bool = True
    supports_genre: bool = True
    supports_key: bool = True
    supports_year: bool = True
    metadata: dict[str, object] = field(default_factory=dict)
