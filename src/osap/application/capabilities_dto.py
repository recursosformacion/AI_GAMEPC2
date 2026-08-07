from src.osap.domain.catalog_capabilities import CatalogCapabilities
from src.osap.domain.output_format import OutputFormat


class CapabilitiesDto:
    """A stable, serializable description of a provider's capabilities for the
    frontend. The frontend builds its UI from this; it never knows provider
    rules."""

    @staticmethod
    def build(provider_id: str, caps: CatalogCapabilities, available: bool, authenticated: bool) -> dict[str, object]:
        formats = {f for f in caps.formats}
        return {
            "provider": provider_id,
            "available": available,
            "authenticated": authenticated,
            "status": str(caps.metadata.get("availability") or "ok"),
            "supports_search": caps.supports_search,
            "supports_download": caps.supports_download,
            "supports_musicxml": OutputFormat.MUSICXML in formats,
            "supports_mei": OutputFormat.MEI in formats,
            "supports_pdf": OutputFormat.PDF in formats,
            "supports_midi": OutputFormat.MIDI in formats,
            "supports_streaming": caps.supports_streaming,
            "offline": caps.offline,
            "quality": _quality_label(provider_id),
            "priority": _priority(provider_id),
        }


def _quality_label(provider_id: str) -> str:
    # Heuristic label; providers with structured formats are 'excellent'.
    if provider_id in ("openscore",):
        return "excellent"
    if provider_id == "imslp":
        return "good"
    if provider_id == "cpdl":
        return "good"
    if provider_id == "local":
        return "excellent"
    return "unknown"


def _priority(provider_id: str) -> int:
    order = {
        "local": 90,
        "openscore": 85,
        "cpdl": 70,
        "imslp": 50,
    }
    return order.get(provider_id, 40)
