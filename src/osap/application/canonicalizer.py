import re
import unicodedata
from pathlib import Path

import yaml  # type: ignore[import-untyped]

from src.osap.domain.canonicalization import AppliedRule, CanonicalResult

_WORD_RE = re.compile(r"[A-Za-zÀ-ÿ]+|[0-9]+")


def _words(text: str) -> list[str]:
    """Tokenize text into runs of letters or digits (keeps accents)."""
    return _WORD_RE.findall(text)


def _strip(word: str) -> str:
    """Accent-stripped, lowercased matching key (consistent with normalize_name)."""
    decomposed = unicodedata.normalize("NFKD", word)
    ascii_text = decomposed.encode("ascii", "ignore").decode("ascii")
    return ascii_text.lower()


def _slug(value: str) -> str:
    """Lowercase alphanumeric slug used to build a stable rule_id."""
    return re.sub(r"[^A-Za-z0-9]+", "-", value.lower()).strip("-")


class Canonicalizer:
    """Applies declarative alias→canonical rules (ADR-0021).

    It is deterministic, does not learn, does not use AI and does not generate
    rules. It only rewrites aliases to their canonical form and reports exactly
    which rule (and from which file) was applied, for traceability. Matching is
    accent-insensitive and case-insensitive (like the matcher's normalize_name).
    """

    def __init__(self, directory: Path) -> None:
        self._single: dict[str, AppliedRule] = {}
        self._multi: dict[tuple[str, ...], AppliedRule] = {}
        self._reverse: dict[str, set[str]] = {}
        self._load(directory)

    def aliases_for(self, canonical: str) -> tuple[str, ...]:
        """Reverse lookup: the aliases (and the canonical) that map to `canonical`."""
        values = self._reverse.get(canonical)
        if not values:
            return ()
        return tuple(sorted(values))

    def canonicalize(self, text: str) -> CanonicalResult:
        words = _words(text)
        stripped = [_strip(word) for word in words]
        count = len(words)
        replacement: dict[int, tuple[AppliedRule, int]] = {}
        used = [False] * count

        # Multi-word aliases first (longest, most specific).
        for key, rule in self._multi.items():
            span = len(key)
            for start in range(count - span + 1):
                if any(used[start + offset] for offset in range(span)):
                    continue
                if all(stripped[start + offset] == key[offset] for offset in range(span)):
                    for offset in range(span):
                        used[start + offset] = True
                    replacement[start] = (rule, span)
                    break

        out: list[str] = []
        applied: list[AppliedRule] = []
        index = 0
        while index < count:
            if index in replacement:
                rule, span = replacement[index]
                out.append(rule.canonical)
                applied.append(rule)
                index += span
            else:
                single = self._single.get(stripped[index])
                if single is not None:
                    out.append(single.canonical)
                    applied.append(single)
                else:
                    out.append(words[index])
                index += 1
        confidence = min((applied_rule.confidence for applied_rule in applied), default=0.0)
        return CanonicalResult(input=text, output=" ".join(out), applied=tuple(applied), confidence=confidence)

    def _load(self, directory: Path) -> None:
        for yaml_file in sorted(directory.glob("*.yaml")):
            try:
                document = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
            except yaml.YAMLError:
                continue  # tolerate malformed rule files
            if not isinstance(document, list):
                continue
            for item in document:
                if not isinstance(item, dict):
                    continue
                canonical = item.get("canonical")
                aliases = item.get("aliases")
                if not isinstance(canonical, str) or not isinstance(aliases, list):
                    continue
                confidence = item.get("confidence", 1.0)
                if not isinstance(confidence, (int, float)):
                    confidence = 1.0
                rule = AppliedRule(
                    rule_id=_rule_id(yaml_file, canonical),
                    rule=yaml_file.name,
                    canonical=canonical,
                    confidence=float(confidence),
                )
                for alias in aliases:
                    if not isinstance(alias, str):
                        continue
                    self._register(alias, rule)
                self._register(canonical, rule)

    def _register(self, value: str, rule: AppliedRule) -> None:
        self._reverse.setdefault(rule.canonical, set()).add(value)
        words = [_strip(word) for word in _words(value)]
        if not words:
            return
        if len(words) == 1:
            self._single.setdefault(words[0], rule)
        else:
            self._multi.setdefault(tuple(words), rule)


def _rule_id(yaml_file: Path, canonical: str) -> str:
    """Stable rule identifier, e.g. ``catalogue.kv`` (family + canonical slug)."""
    family = yaml_file.stem
    if family.endswith("_aliases"):
        family = family[: -len("_aliases")]
    return f"{family}.{_slug(canonical)}"
