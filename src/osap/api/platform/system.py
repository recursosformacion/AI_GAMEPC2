"""PlatformApi: mixin de system/admin/auth (F5.4)."""

import json
import secrets
import urllib.parse
import urllib.request
from datetime import UTC, datetime

from src.osap.api.contracts import (
    SystemStatisticsResponse,
    SystemVersionResponse,
)
from src.osap.api.platform import _support as _support
from src.osap.api.platform.core import PlatformApiCore
from src.osap.domain.votes import (
    ForbiddenError,
)

VERSION = "3.1"


















class SystemMixin(PlatformApiCore):
    def storage_web(self, token: str | None, section: str | None = None) -> str:
        self._require_admin(token)
        base = (self._container.storage_web_base() or self.composers().storage_base_url()).rstrip("/")
        if self._container.dev_auth_bypass():
            service_token = secrets.token_urlsafe(16)
        else:
            service_token = self.composers().storage_admin_token()
        url = f"{base}/admin?token={urllib.parse.quote(service_token)}"
        # Mantenimientos standalone (osap-storage): Maestros = CRUD compositores;
        # Obras = CRUD works (listado + Ver/Editar); el resto multimantenimiento.
        if section == "composers":
            url = f"{base}/admin/maestros?token={urllib.parse.quote(service_token)}"
        elif section == "works":
            url = f"{base}/admin/obras?token={urllib.parse.quote(service_token)}"
        elif section == "tables":
            url = f"{url}&tab=tables"
        return url

    def admin_overview(self, token: str | None) -> dict[str, object]:
        stats = self.composer_review_stats(token)
        suggestions = self._store.suggestion_counts()
        storage = self.composers().storage_statistics()
        return {
            "composers": stats,
            "source_suggestions_pending": suggestions.get("pending", 0),
            "source_suggestions": suggestions,
            "storage": storage,
        }

    # --- mantenimiento de usuarios (façade → osap-auth; la BD es de Auth) ----

    def admin_users_list(self, token: str | None) -> object:
        self._require_admin(token)
        bearer = token or ""
        return self._auth_result(*self._container.auth_proxy().admin_users(bearer))

    def admin_user_get(self, token: str | None, user_id: str) -> object:
        self._require_admin(token)
        bearer = token or ""
        return self._auth_result(*self._container.auth_proxy().admin_user(bearer, user_id))

    def admin_user_update(
        self,
        token: str | None,
        user_id: str,
        *,
        name: str | None = None,
        roles: list[str] | None = None,
        status: str | None = None,
    ) -> object:
        self._require_admin(token)
        bearer = token or ""
        payload: dict[str, object] = {}
        if name is not None:
            payload["name"] = name
        if roles is not None:
            payload["roles"] = roles
        if status is not None:
            payload["status"] = status
        return self._auth_result(
            *self._container.auth_proxy().admin_update_user(bearer, user_id, payload)
        )

    def admin_user_disable(self, token: str | None, user_id: str) -> object:
        """Soft delete: deshabilitar (conserva identidad e historial en Auth)."""
        return self.admin_user_update(token, user_id, status="disabled")

    def health(self) -> str:
        return "ok"

    def storage_info(self) -> tuple[str, bool]:
        return self._container.storage_info()

    # --- bypass de desarrollo (SOLO dev; activado por OSAP_DEV_AUTH_BYPASS=1) ---

    def dev_auth_bypass(self) -> bool:
        return self._container.dev_auth_bypass()

    def dev_session(self) -> dict[str, object]:
        """Sesión admin de desarrollo. `JwtAuthenticator` en dev decodifica sin firma;
        este endpoint NUNCA debe activarse en producción (OSAP_DEV_AUTH_BYPASS)."""

        if not self._container.dev_auth_bypass():
            raise ForbiddenError("Dev auth bypass not enabled")
        import base64

        def _b64(data: bytes) -> str:
            return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

        header = _b64(json.dumps({"alg": "none", "typ": "JWT"}).encode("utf-8"))
        payload = _b64(
            json.dumps(
                {
                    "sub": "dev-admin",
                    "token_use": "user",
                    "roles": ["user", "admin"],
                    "email_verified": True,
                    "aud": "osap-api",
                }
            ).encode("utf-8")
        )
        return {
            "access_token": f"{header}.{payload}.",
            "refresh_token": "dev-refresh-token",
            "token_type": "Bearer",
            "expires_in": 86400,
        }

    # --- OIDC (login vía osap-auth como IdP) --------------------------------

    def _load_oidc_pending(self) -> dict[str, dict[str, object]]:
        """Recupera los estados OIDC pendientes desde disco (sobreviven a reinicios)."""
        try:
            with open(self._oidc_pending_path, encoding="utf-8") as fh:
                data = json.load(fh)
            return {k: v for k, v in data.items() if isinstance(v, dict)} if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _persist_oidc_pending(self) -> None:
        """Persiste los estados pendientes en disco (best-effort, nunca bloquea el login)."""
        if not self._oidc_pending_path:
            return
        try:
            with open(self._oidc_pending_path, "w", encoding="utf-8") as fh:
                json.dump(self._oidc_pending, fh)
        except OSError:
            pass

    def oidc_start(self) -> dict[str, object]:
        from src.osap.infrastructure.auth.oidc_rp_client import OidcError

        oidc = self._container.oidc_client()
        if not oidc.configured():
            raise OidcError("OIDC no configurado")
        verifier, challenge = oidc.generate_pkce()
        state = oidc.generate_state()
        nonce = oidc.generate_state()
        with self._oidc_pending_lock:
            self._oidc_pending[state] = {
                "verifier": verifier,
                "nonce": nonce,
                "created_at": datetime.now(UTC).timestamp(),
            }
            self._persist_oidc_pending()
        authorize_url = oidc.build_authorize_url(state, nonce, challenge)
        return {"authorize_url": authorize_url, "configured": True}

    def oidc_error_url(self, message: str) -> str:
        return self._container.oidc_client().error_callback_url(message)

    def oidc_callback(self, code: str | None, state: str | None) -> str:
        from src.osap.infrastructure.auth.oidc_rp_client import OidcError

        oidc = self._container.oidc_client()
        with self._oidc_pending_lock:
            if not state or state not in self._oidc_pending:
                raise OidcError("OIDC state inválido o ausente")
            pending = self._oidc_pending.pop(state)
            self._persist_oidc_pending()
        created = float(str(pending.get("created_at") or 0))
        if datetime.now(UTC).timestamp() - created > 1800:
            raise OidcError("OIDC state caducado")
        if not code:
            raise OidcError("OIDC code ausente")
        tokens = oidc.exchange_code(code, str(pending["verifier"]))
        access = str(tokens.get("access_token") or "")
        refresh = str(tokens.get("refresh_token") or "")
        if not access:
            raise OidcError("OIDC no devolvió access_token")
        return oidc.spa_callback_url(access, refresh)

    def version(self) -> SystemVersionResponse:
        return SystemVersionResponse(version=VERSION)

    # --- repository sources (Source Catalog) --------------------------------

    def statistics(self) -> SystemStatisticsResponse:
        base = self._knowledge.base()
        return SystemStatisticsResponse(
            providers=len(self._container.catalog_manager().providers()),
            searches=len(self._searches),
            jobs=len(self._jobs),
            knowledge_observations=len(base.observations),
            knowledge_facts=len(base.facts),
            knowledge_suggestions=len(base.suggestions),
        )
