from dataclasses import dataclass
from typing import Optional


@dataclass
class Configuration:
    default_voice: Optional[str] = None
    output_format: str = "pdf"
    default_quality_level: str = "full_notation"
