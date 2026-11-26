"""V1 — Puerto para la identidad de servicio.

Proporciona un service token (SERVICE JWT) para que osap-api se autentique frente a
osap-storage. El token se obtiene de osap-auth mediante ``client_credentials``; cada llamada
solicita únicamente los scopes necesarios (least privilege).
"""

from abc import ABC, abstractmethod


class IServiceTokenProvider(ABC):
    """Emite/entrega un service token con los scopes solicitados."""

    @abstractmethod
    def token(self, scopes: tuple[str, ...], *, force_refresh: bool = False) -> str:
        """Devuelve un token con los scopes.

        `force_refresh=True` obliga a pedir uno nuevo a osap-auth. Los handoffs al
        panel admin lo usan para no entregar al navegador un token cacheado que puede
        estar a pocos segundos de caducar.
        """
        raise NotImplementedError
