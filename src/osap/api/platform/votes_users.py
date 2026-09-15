"""PlatformApi: mixin de votos y usuarios (F5.4)."""

import logging

from src.osap.api.platform import _support as _support
from src.osap.api.platform.core import PlatformApiCore
from src.osap.application.votes_service import VotesService
from src.osap.domain.principal import Principal
from src.osap.domain.votes import (
    ComposerStats,
    ForbiddenError,
    UnauthenticatedError,
    WorkNotFoundError,
    WorkStats,
    WorkVote,
)
from src.osap.infrastructure.auth.auth_proxy_client import AuthProxyError

VERSION = "3.1"

_LOGGER = logging.getLogger("osap.auth")













class VotesUsersMixin(PlatformApiCore):
    def votes(self) -> VotesService:
        return self._container.votes_service()

    def principal_for(self, token: str | None) -> Principal | None:
        return self.votes().principal_for(token)

    def current_user(self, token: str | None) -> Principal | None:
        return self.principal_for(token)

    def require_can_vote(self, token: str | None) -> Principal:
        return self.votes().require_can_vote(token)

    def require_admin(self, token: str | None) -> Principal:
        return self.votes().require_admin(token)

    def cast_vote(self, token: str | None, work_id: str, vote: int) -> WorkVote:
        return self.votes().cast_vote(token, work_id, vote)

    def work_statistics(self, work_id: str) -> WorkStats:
        return self.votes().work_statistics(work_id)

    def composer_statistics(self, composer_id: str) -> ComposerStats:
        return self.votes().composer_statistics(composer_id)

    def votes_overview(self) -> dict[str, object]:
        return self.votes().overview()

    # --- registro / verificación de usuario (proxy a osap-auth) --------------

    def register_user(self, email: str, password: str, name: str | None = None) -> tuple[int, dict[str, object]]:
        return self._container.auth_proxy().register(email, password, name)

    def verify_email(self, token: str) -> tuple[int, dict[str, object]]:
        return self._container.auth_proxy().verify_email(token)

    # --- compositores (consulta pública + fusión admin) ----------------------

    @staticmethod
    def _auth_result(code: int, doc: object) -> object:
        if 200 <= code < 300:
            return doc
        if code == 401:
            raise UnauthenticatedError("osap-auth: credenciales de administración inválidas")
        if code == 403:
            raise ForbiddenError("osap-auth: rol admin requerido")
        if code == 404:
            raise WorkNotFoundError("User not found")
        raise AuthProxyError(f"osap-auth devolvió HTTP {code}")

    # --- proveedores dinámicos + config (BD operativa) -----------------------

    def _require_admin(self, token: str | None) -> None:

        principal = self._container.authenticator().resolve(token)
        if principal is None:
            raise UnauthenticatedError("Login required")
        if getattr(principal, "has_role", lambda r: False)("admin"):
            return
        # El claim `roles` es una foto del momento de emisión del token: si la cuenta se
        # promovió a admin después, el token sigue siendo válido pero sin el rol, y el
        # usuario veía "Admin role required" aunque /auth/me y la web sí lo tratasen como
        # admin. osap-auth (BD) es la autoridad: se consulta y se acepta si allí es admin.
        bearer = token or ""
        try:
            code, doc = self._container.auth_proxy().me(bearer)
        except Exception as exc:  # noqa: BLE001 — si osap-auth no responde, se deniega
            _LOGGER.warning("admin check: osap-auth inaccesible (%s)", exc)
            raise ForbiddenError("Admin role required") from None
        roles = doc.get("roles") if isinstance(doc, dict) else None
        if code == 200 and isinstance(roles, list) and "admin" in roles:
            _LOGGER.info("admin check: aceptado por roles de osap-auth (token obsoleto)")
            return
        _LOGGER.warning(
            "admin check: denegado (token_roles=%s osap_auth=%s/%s)",
            getattr(principal, "roles", None),
            code,
            roles,
        )
        raise ForbiddenError("Admin role required")

    # --- discovery ----------------------------------------------------------


