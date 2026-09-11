"""REST API: an HTTP adapter over the OSAP application services.

FastAPI only transforms HTTP <-> DTO <-> application services. No business
logic lives here. The domain/application/providers own all behavior.

Producción (V3.1): ``src.osap.api.platform_app:create_platform_app``. La entrada
legacy ``app.py`` (create_app, V1/V2) se retiró en 2026-09-09 (ADR-0035/D2).
"""

__all__: list[str] = []
