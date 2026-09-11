"""Contexto HTTP compartido por los routers de platform_app (F5.5).

`HttpContext` agrupa la fachada de use cases (`PlatformApi`) y los helpers de respuesta
(`ok`/`fail`). Los routers se construyen con `build_*_router(ctx)` y se incluyen en la app;
la lógica y los contratos no cambian.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from src.osap.api.contracts import ErrorBody, ErrorEnvelope, SuccessEnvelope

if TYPE_CHECKING:
    from fastapi import Response

    from src.osap.api.platform import PlatformApi
    from src.osap.bootstrap.container import Container


@dataclass(frozen=True)
class HttpContext:
    api: PlatformApi
    container: Container

    def ok(self, data: object) -> SuccessEnvelope[object]:
        from src.osap.api.http.shared import _request_id

        return SuccessEnvelope(success=True, request_id=_request_id(), data=data)

    def fail(self, status: int, response: Response, code: str, message: str) -> ErrorEnvelope:
        from src.osap.api.http.shared import _request_id

        response.status_code = status
        return ErrorEnvelope(
            success=False,
            request_id=_request_id(),
            error=ErrorBody(code=code, message=message),
        )


def standard_errors(*codes: int) -> dict[int | str, dict[str, Any]]:
    from src.osap.api.http.shared import _standard_errors

    return _standard_errors(*codes)
