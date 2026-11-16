"""Clientes internos para el boletín (identidad y entrega)."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from src.osap.news_digest.models import Subscriber, normalize_languages, normalize_topics


class SubscribersUnavailableError(RuntimeError):
    pass


def fetch_subscribers(
    *, base_url: str, token: str, timeout: float = 10.0, user_id: str | None = None
) -> list[Subscriber]:
    if not token:
        raise SubscribersUnavailableError("OSAP_INTERNAL_SERVICE_TOKEN no configurado")
    url = base_url.rstrip("/") + "/auth/internal/news-subscribers"
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "X-OSAP-Internal-Token": token},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            payload = json.loads(response.read() or b"[]")
    except urllib.error.HTTPError as exc:
        raise SubscribersUnavailableError(f"osap-auth HTTP {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise SubscribersUnavailableError(f"osap-auth no disponible: {exc}") from exc
    if not isinstance(payload, list):
        raise SubscribersUnavailableError("respuesta de suscriptores inválida")

    result: list[Subscriber] = []
    for raw in payload:
        if not isinstance(raw, dict) or not raw.get("email"):
            continue
        if user_id and str(raw.get("user_id")) != user_id:
            continue
        result.append(
            Subscriber(
                user_id=str(raw.get("user_id") or ""),
                email=str(raw["email"]),
                name=str(raw["name"]) if raw.get("name") else None,
                languages=normalize_languages(
                    raw.get("news_languages") if isinstance(raw.get("news_languages"), list) else None,
                    str(raw.get("news_language") or "es"),
                ),
                topics=normalize_topics(
                    raw.get("news_topics") if isinstance(raw.get("news_topics"), list) else None
                ),
            )
        )
    return result


def post_support_digest(
    *, base_url: str, token: str, payload: dict[str, Any], timeout: float = 10.0
) -> dict[str, Any]:
    """Entrega al endpoint interno de osap-support (si está configurado)."""
    if not base_url or not token:
        raise SubscribersUnavailableError("entrega por support no configurada")
    request = urllib.request.Request(
        base_url.rstrip("/") + "/internal/communications/news",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-OSAP-Internal-Token": token,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            data = json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as exc:
        raise SubscribersUnavailableError(f"osap-support HTTP {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise SubscribersUnavailableError(f"osap-support no disponible: {exc}") from exc
    return data if isinstance(data, dict) else {}

