"""Normalized metadata for comparing musical works.

``NormalizedMetadata`` is a COMPARISON-ONLY value object: it is produced from a
raw title + extracted metadata and consumed exclusively by the ``WorkMatcher``.
It is NEVER shown to the user. The display title always comes from the original
(canonical) title, never from this object.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NormalizedMetadata:
    """Stable, comparison-only representation of a work's identity.

    Each field is a normalized feature used by the matcher. Keeping these as
    explicit fields (instead of a concatenated key) means the matcher can be
    a rule-based scorer today and an ML model later without changing the
    pipeline.
    """

    normalized_title: str
    normalized_composer: str | None = None
    normalized_catalog: str | None = None
    normalized_number: str | None = None
    normalized_key: str | None = None

    def signature(self) -> str:
        """A stable, compact fingerprint of this identity.

        Used only to assign a stable id to a merged work. It is NOT used for
        merging decisions (those use the matcher's score).
        """
        parts = [
            self.normalized_composer or "",
            self.normalized_title,
            self.normalized_catalog or "",
            self.normalized_number or "",
            self.normalized_key or "",
        ]
        return "|".join(part for part in parts if part)
