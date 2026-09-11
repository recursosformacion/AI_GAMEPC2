"""PlatformApi: mixin de fuentes (repo/sesión/descubrimiento) (F5.4)."""

import json
import logging
import urllib.parse
import urllib.request

from src.osap.api.contracts import (
    DiscoverSource,
    RepositorySource,
    RepositorySourceSummary,
    SessionSource,
    SourceSuggestionRead,
)
from src.osap.api.platform import _support as _support
from src.osap.api.platform._support import (
    _host_of,
    _repository_source_from_defined,
    _summary,
    _validate_preview_url,
)
from src.osap.api.platform.core import PlatformApiCore

VERSION = "3.1"















class SourcesMixin(PlatformApiCore):
    def list_repository_sources(self) -> list[RepositorySourceSummary]:
        summaries = [_summary(s) for s in self._catalog.list()]
        seen = {s.source_id for s in summaries}
        for pid, name, base_url, wired in self._container.defined_providers():
            if pid in seen or pid == "local":
                continue
            summaries.append(
                RepositorySourceSummary(
                    source_id=pid,
                    name=name,
                    type="Provider",
                    origin=_host_of(base_url),
                    trust="Verified" if wired else "Community",
                    status="Online" if wired else "Defined",
                    quality=90 if wired else 50,
                    quality_label="Excellent" if wired else "Pending",
                    updated_at="",
                )
            )
            seen.add(pid)
        return summaries

    def get_repository_source(self, source_id: str) -> RepositorySource | None:
        seeded = self._catalog.get(source_id)
        if seeded is not None:
            return seeded
        for pid, name, base_url, wired in self._container.defined_providers():
            if pid == source_id and pid != "local":
                return _repository_source_from_defined(pid, name, base_url, wired)
        return None

    # --- session sources (user's temporary sources) -------------------------

    def create_session_source(self, name: str, source_type: str, location: str) -> SessionSource:
        return self._sessions.create(name, source_type, location)

    def list_session_sources(self) -> list[SessionSource]:
        return list(self._sessions.list())

    def get_session_source(self, source_id: str) -> SessionSource | None:
        return self._sessions.get(source_id)

    def forget_session_source(self, source_id: str) -> bool:
        return self._sessions.forget(source_id)

    def analyze_session_source(self, source_id: str) -> SessionSource | None:
        return self._sessions.analyze(source_id)

    def use_session_source(self, source_id: str) -> SessionSource | None:
        return self._sessions.use(source_id)

    # --- fuente propuesta por un usuario (Añadir fuente) --------------------

    def preview_source(self, url: str) -> tuple[bool, list[str], str | None]:
        """Intenta leer el fichero de la URL y adivinar los campos (mapping).

        Es best-effort: si no se puede leer o no es JSON, devuelve error sin romper
        el flujo. Los campos son las claves de primer nivel más las de una muestra
        de elementos (works/items/results/data/files).
        """
        if not url:
            return False, [], "Provide a URL"
        guard_error = _validate_preview_url(url)
        if guard_error:
            return False, [], guard_error
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (OpenMusicRepository)"})
            with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310 (user-provided source URL)
                raw = resp.read(2_000_000)
        except Exception as exc:  # noqa: BLE001
            return False, [], f"Could not read URL: {exc}"
        try:
            import json

            doc = json.loads(raw)
        except Exception:  # noqa: BLE001
            return False, [], "The URL does not contain valid JSON"
        if not isinstance(doc, dict):
            return False, [], "Expected a JSON object"
        fields = [k for k in doc if isinstance(k, str)]
        for arr_key in ("works", "items", "results", "data", "files", "scores"):
            value = doc.get(arr_key)
            if isinstance(value, list) and value and isinstance(value[0], dict):
                for k in value[0]:
                    if isinstance(k, str) and k not in fields:
                        fields.append(k)
        return True, fields, None

    def suggest_source(
        self,
        token: str | None,
        name: str,
        source_type: str,
        location: str,
        mapping: dict[str, object],
    ) -> SourceSuggestionRead:
        principal = self._container.authenticator().resolve(token)
        if principal is None or not getattr(principal, "user_id", None):
            from src.osap.domain.votes import UnauthenticatedError

            raise UnauthenticatedError("Login required to suggest a source")
        user = str(getattr(principal, "user_id", "anonymous"))
        self._suggestion_counter += 1
        suggestion_id = f"sug-{self._suggestion_counter}"
        row = self._store.add_suggestion(
            suggestion_id,
            name,
            source_type,
            location,
            dict(mapping),
            user,
        )
        suggestion = SourceSuggestionRead(
            id=str(row["id"]),
            name=str(row["name"]),
            type=str(row["type"]),
            location=str(row["location"]),
            mapping=json.loads(str(row["mapping"])),
            requested_by=str(row["requested_by"]),
            status=str(row["status"]),
            admin_message=str(row["admin_message"]) if row.get("admin_message") else None,
            created_at=str(row["created_at"]),
        )
        # En esta sesión se incluye en los resultados de búsqueda.
        self._sessions.create(name, source_type, location)
        return suggestion

    def list_source_suggestions(self, token: str | None) -> list[SourceSuggestionRead]:
        self._require_admin(token)
        result: list[SourceSuggestionRead] = []
        for row in self._store.list_suggestions():
            result.append(
                SourceSuggestionRead(
                    id=str(row["id"]),
                    name=str(row["name"]),
                    type=str(row["type"]),
                    location=str(row["location"]),
                    mapping=json.loads(str(row["mapping"])),
                    requested_by=str(row["requested_by"]),
                    status=str(row["status"]),
                    admin_message=str(row["admin_message"]) if row.get("admin_message") else None,
                    created_at=str(row["created_at"]),
                )
            )
        return result

    def resolve_source_suggestion(
        self,
        token: str | None,
        suggestion_id: str,
        action: str,
        message: str,
    ) -> SourceSuggestionRead | None:
        self._require_admin(token)
        principal = self._container.authenticator().resolve(token)
        decided_by = str(getattr(principal, "user_id", "admin"))
        status = "approved" if action == "approve" else "cancelled"
        row = self._store.resolve_suggestion(suggestion_id, status, message, decided_by)
        if row is None:
            return None
        # Notificación por email (pendiente de SMTP: se registra en log).
        logging.getLogger("osap.sources").info(
            "source suggestion %s -> %s for user %s: %s", suggestion_id, status, row.get("requested_by"), message
        )
        return SourceSuggestionRead(
            id=str(row["id"]),
            name=str(row["name"]),
            type=str(row["type"]),
            location=str(row["location"]),
            mapping=json.loads(str(row["mapping"])),
            requested_by=str(row["requested_by"]),
            status=str(row["status"]),
            admin_message=str(row["admin_message"]) if row.get("admin_message") else None,
            created_at=str(row["created_at"]),
        )

    def discover_sources(self) -> list[DiscoverSource]:
        sources = [
            DiscoverSource(
                source_id=s.source_id,
                name=s.name,
                type=s.type,
                origin=s.origin,
                trust=s.trust,
                quality=s.quality,
                url=s.website,
            )
            for s in self._catalog.list()
        ]
        seen = {s.source_id for s in sources}
        for pid, name, base_url, wired in self._container.defined_providers():
            if pid in seen:
                continue
            sources.append(
                DiscoverSource(
                    source_id=pid,
                    name=name,
                    type="Provider",
                    origin=_host_of(base_url),
                    trust="Verified" if wired else "Community",
                    quality=90 if wired else 50,
                    url=base_url,
                )
            )
            seen.add(pid)
        return sources

