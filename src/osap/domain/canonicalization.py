from dataclasses import dataclass, field


@dataclass(frozen=True)
class CanonicalRule:
    """A declarative alias → canonical rule (loaded from a rules file)."""

    canonical: str
    aliases: tuple[str, ...] = field(default_factory=tuple)
    confidence: float = 1.0


@dataclass(frozen=True)
class AppliedRule:
    """A rule that was applied to a piece of text, for traceability."""

    rule_id: str = ""  # stable identifier, e.g. "catalogue.kv"
    rule: str = ""  # the rules file it came from, e.g. "catalogue_aliases.yaml"
    canonical: str = ""  # the canonical form it produced
    confidence: float = 1.0  # strength of the normalization (0..1)


@dataclass(frozen=True)
class CanonicalResult:
    """Output of canonicalization, with full traceability."""

    input: str
    output: str
    applied: tuple[AppliedRule, ...] = field(default_factory=tuple)
    confidence: float = 0.0  # strength of the normalization (0..1); 0 if no rule

    @property
    def normalized(self) -> str:
        return self.output

    @property
    def rules(self) -> tuple[AppliedRule, ...]:
        return self.applied
