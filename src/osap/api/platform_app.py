"""V3.1 — OSAP Platform API (FastAPI HTTP adapter): composición (F5.5).

Inicialización, container e `include_router`. La infraestructura compartida (DTOs,
ejemplos, tags y helpers) vive en `api/http/shared.py`.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from fastapi import FastAPI

from src.osap.api.http.admin import build_admin_router
from src.osap.api.http.admin_ops import build_admin_ops_router
from src.osap.api.http.analytics import build_analytics_router
from src.osap.api.http.auth import build_auth_router
from src.osap.api.http.composers import build_composers_router
from src.osap.api.http.context import HttpContext
from src.osap.api.http.jobs import build_jobs_router
from src.osap.api.http.knowledge import build_knowledge_router
from src.osap.api.http.omr import build_omr_router
from src.osap.api.http.providers import build_providers_router
from src.osap.api.http.search import build_search_router
from src.osap.api.http.sessions import build_sessions_router
from src.osap.api.http.shared import (
    _TAGS,
)
from src.osap.api.http.sources import build_sources_router
from src.osap.api.http.support import build_support_router
from src.osap.api.http.system import build_system_router
from src.osap.api.http.votes import build_votes_router
from src.osap.api.http.works import build_works_router
from src.osap.api.platform import PlatformApi
from src.osap.bootstrap.configuration import load_configuration
from src.osap.bootstrap.container import Container
from src.osap.bootstrap.wiring import wire

if TYPE_CHECKING:
    from src.osap.api.platform._support import KnowledgeStore

VERSION = "3.1"


def _configure_osap_logging() -> None:
    logger = logging.getLogger("osap.api")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
        logger.addHandler(handler)
    logger.propagate = False


def create_platform_app(
    container: Container | None = None,
    knowledge: KnowledgeStore | None = None,
) -> FastAPI:
    """Build the OSAP Platform API (V3.1) over application services."""
    config = load_configuration(service_name="osap-api")
    container = container or wire(Container(), configuration=config)
    api = PlatformApi(container, knowledge)
    _configure_osap_logging()
    app = FastAPI(
        title="OSAP REST API",
        description="Public REST API of OSAP (V3.1). Exposes the domain as use cases; never internal components.",
        version="3.1",
        license_info={"name": "MIT", "url": "https://opensource.org/licenses/MIT"},
        contact={"name": "OSAP", "url": "https://example.com", "email": "osap@example.com"},
        openapi_tags=_TAGS,
    )

    ctx = HttpContext(api, container)


    # --- search model (Search Studio is driven by it) ------------------------



    # --- searches -----------------------------------------------------------



    # --- jobs ---------------------------------------------------------------

    app.include_router(build_jobs_router(ctx))

    app.include_router(build_providers_router(ctx))

    app.include_router(build_sources_router(ctx))
    app.include_router(build_admin_router(ctx))

    # --- proveedores dinámicos + config (BD operativa de osap-api) -----------









    # --- discovery ----------------------------------------------------------

    app.include_router(build_knowledge_router(ctx))
    app.include_router(build_system_router(ctx))

    app.include_router(build_votes_router(ctx))
    app.include_router(build_analytics_router(ctx))

    # --- mantenimiento de usuarios (façade → osap-auth; la BD es de Auth) -----





    # --- compositores (consulta pública + fusión admin) ----------------------





















    app.include_router(build_support_router(ctx))
    app.include_router(build_auth_router(ctx))



    app.include_router(build_search_router(ctx))
    app.include_router(build_composers_router(ctx))
    app.include_router(build_works_router(ctx))
    app.include_router(build_sessions_router(ctx))
    app.include_router(build_admin_ops_router(ctx))
    app.include_router(build_omr_router(ctx))

    return app

