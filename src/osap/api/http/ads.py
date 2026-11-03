"""Fachada server-side para ai_publicidad.

El navegador nunca recibe el service token ni conoce la URL interna del servicio.
`/ads/compose` devuelve el HTML ya compuesto y registra las impresiones en el servicio
publicitario; si no está disponible, el frontend conserva su fallback local.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import requests
from fastapi import APIRouter, Response
from fastapi.responses import HTMLResponse

if TYPE_CHECKING:
    from src.osap.api.http.context import HttpContext


def build_ads_router(ctx: HttpContext) -> APIRouter:
    router = APIRouter()

    @router.post("/api/v1/ads/compose", response_class=HTMLResponse)
    def compose(payload: dict[str, Any], response: Response) -> Any:
        base = (ctx.container.ads_base_url() or "").rstrip("/")
        token = ctx.container.ads_service_token() or ""
        if not base or not token:
            return ctx.fail(503, response, "ADS_UNAVAILABLE", "Publicidad no configurada")
        try:
            upstream = requests.post(
                f"{base}/api/v1/ads/compose",
                json=payload,
                headers={"X-OSAP-Service-Token": token},
                timeout=ctx.container.ads_timeout_seconds(),
            )
        except requests.RequestException:
            return ctx.fail(503, response, "ADS_UNAVAILABLE", "Publicidad no disponible")

        if upstream.status_code != 200:
            return ctx.fail(503, response, "ADS_UNAVAILABLE", "Publicidad no disponible")
        if "text/html" not in upstream.headers.get("content-type", "").lower():
            return ctx.fail(502, response, "ADS_INVALID_RESPONSE", "Respuesta publicitaria inválida")
        return HTMLResponse(
            content=upstream.text,
            status_code=200,
            headers={"Cache-Control": "no-store"},
        )

    @router.post("/api/v1/ads/impression")
    def impression(payload: dict[str, Any], response: Response) -> Any:
        base = (ctx.container.ads_base_url() or "").rstrip("/")
        token = ctx.container.ads_service_token() or ""
        if not base or not token:
            return ctx.fail(503, response, "ADS_UNAVAILABLE", "Publicidad no configurada")
        try:
            upstream = requests.post(
                f"{base}/api/v1/events/impression",
                json=payload,
                headers={"X-OSAP-Service-Token": token},
                timeout=ctx.container.ads_timeout_seconds(),
            )
        except requests.RequestException:
            return ctx.fail(503, response, "ADS_UNAVAILABLE", "Publicidad no disponible")
        if upstream.status_code != 200:
            return ctx.fail(503, response, "ADS_UNAVAILABLE", "Publicidad no disponible")
        return ctx.ok(upstream.json().get("data", upstream.json()))

    return router
