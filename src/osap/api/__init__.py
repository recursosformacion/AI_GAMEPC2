"""REST API: an HTTP adapter over the OSAP application services.

FastAPI only transforms HTTP <-> DTO <-> application services. No business
logic lives here. The domain/application/providers own all behavior.
"""

from .app import create_app

__all__ = ["create_app"]
