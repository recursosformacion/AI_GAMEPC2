"""Modelos y utilidades comunes del boletín de noticias."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

SUPPORTED_LANGUAGES = ("es", "ca", "fr", "en", "de", "it", "pt")

LANGUAGE_NAMES = {
    "es": "Español",
    "ca": "Català",
    "fr": "Français",
    "en": "English",
    "de": "Deutsch",
    "it": "Italiano",
    "pt": "Português",
}


def normalize_languages(values: list[str] | None, fallback: str = "es") -> list[str]:
    result = [
        str(value).strip().lower()
        for value in (values or [])
        if str(value).strip().lower() in SUPPORTED_LANGUAGES
    ]
    return list(dict.fromkeys(result)) or ([fallback] if fallback in SUPPORTED_LANGUAGES else ["es"])


def normalize_topics(values: list[str] | None) -> list[str]:
    return list(dict.fromkeys(str(value).strip() for value in (values or []) if str(value).strip()))


@dataclass(frozen=True)
class Subscriber:
    user_id: str
    email: str
    name: str | None
    languages: list[str]
    topics: list[str]


@dataclass(frozen=True)
class DigestItem:
    title: str
    summary: str
    url: str | None
    publisher: str | None
    published_at: str | None


@dataclass(frozen=True)
class Digest:
    subscriber: Subscriber
    items: list[DigestItem]
    subject: str
    text: str
    html: str
    day: date = field(default_factory=date.today)
