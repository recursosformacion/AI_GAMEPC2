from dataclasses import dataclass


@dataclass
class Configuration:
    default_voice: str | None = None
    output_format: str = "pdf"
    default_quality_level: str = "full_notation"
