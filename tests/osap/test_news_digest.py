"""Librería común del boletín de noticias."""

from __future__ import annotations

from src.osap.news_digest.models import Subscriber, normalize_languages, normalize_topics
from src.osap.news_digest.render import render_digest


def test_normalize_preferences():
    assert normalize_languages(["EN", "es", "xx", "en"]) == ["en", "es"]
    assert normalize_languages([], "ca") == ["ca"]
    assert normalize_topics(["coral", " coral ", "opera"]) == ["coral", "opera"]


def test_render_digest_contains_items_and_safe_links():
    subscriber = Subscriber(
        user_id="u1", email="user@example.com", name="Ana", languages=["es"], topics=["coral"]
    )
    from src.osap.news_digest.models import DigestItem

    digest = render_digest(
        subscriber,
        [
            DigestItem(
                title="Concierto de coro",
                summary="Programa de otoño",
                url="https://example.org/noticia",
                publisher="Ejemplo",
                published_at="2026-11-15",
            )
        ],
        language="es",
    )
    assert "Noticias musicales para ti" in digest.subject
    assert "Concierto de coro" in digest.text
    assert "https://example.org/noticia" in digest.html
    assert "Hola Ana" in digest.text
