from dataclasses import dataclass, field

from .output_format import OutputFormat


@dataclass(frozen=True)
class RankingConfig:
    """Configurable criteria and weights for the RankingEngine."""

    format_order: tuple[OutputFormat, ...] = field(
        default_factory=lambda: (
            OutputFormat.MUSICXML,
            OutputFormat.MEI,
            OutputFormat.MIDI,
            OutputFormat.PDF,
            OutputFormat.JSON,
            OutputFormat.SCORE,
        )
    )
    public_domain_weight: float = 2.0
    quality_weight: float = 2.0
    composer_exact_weight: float = 2.0
    title_exact_weight: float = 1.5
    confidence_weight: float = 1.0
    local_availability_weight: float = 1.0
    provider_order: tuple[str, ...] = field(default_factory=tuple)
    language_boost: str | None = None
