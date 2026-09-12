"""PlatformApi: mixin de correcciones/contacto (F5.4)."""

import logging

from src.osap.api.contracts import (
    CorrectionRead,
)
from src.osap.api.platform import _support as _support
from src.osap.api.platform.core import PlatformApiCore
from src.osap.domain.votes import (
    UnauthenticatedError,
)

VERSION = "3.1"
















class CorrectionsMixin(PlatformApiCore):
    def submit_correction(
        self,
        token: str | None,
        kind: str,
        message: str,
        entity_id: str | None = None,
        entity_provider: str | None = None,
        field: str | None = None,
        current_value: str | None = None,
        proposed_value: str | None = None,
        contact_email: str | None = None,
    ) -> CorrectionRead:
        """Registra una solicitud de contacto o corrección de catálogo (queda `pending`).

        Contacto es público; el resto requiere login. El catálogo NO se modifica aquí.
        """
        from src.osap.application.corrections import CorrectionService

        requested_by: str | None = None
        requested_by_name: str | None = None
        requested_by_email: str | None = None
        if kind != "contact":
            principal = self._container.authenticator().resolve(token)
            if principal is None or not getattr(principal, "user_id", None):
                from src.osap.domain.votes import UnauthenticatedError

                raise UnauthenticatedError("Login required to submit a correction")
            requested_by = str(getattr(principal, "user_id", None)) if getattr(principal, "user_id", None) else None
            raw_name = getattr(principal, "name", None)
            requested_by_name = str(raw_name) if raw_name else None
            raw_email = getattr(principal, "email", None)
            requested_by_email = str(raw_email) if raw_email else None
        service = CorrectionService(self._store, exists=self._correction_entity_exists)
        row = service.submit(
            kind=kind,
            message=message,
            entity_id=entity_id,
            entity_provider=entity_provider,
            field=field,
            current_value=current_value,
            proposed_value=proposed_value,
            contact_email=contact_email,
            requested_by=requested_by,
            requested_by_name=requested_by_name,
            requested_by_email=requested_by_email,
        )
        return self._correction_read(row)

    def _correction_entity_exists(self, kind: str, entity_id: str) -> bool:
        if kind == "representation":
            # La representación es un registro de proveedor: se acepta siempre (no hay
            # store consultable aquí) y el admin la revisa en la pantalla de correcciones.
            return bool(entity_id)
        if kind == "source":
            ids = {str(p.provider_id.value) for p in self._container.catalog_manager().providers()}
            ids.update(str(pid) for pid, _n, _b, _w in self._container.defined_providers())
            try:
                for row in self._store.list_providers():
                    ids.add(str(row.get("provider_id") or ""))
            except Exception:  # noqa: BLE001
                pass
            return entity_id in ids
        try:
            if kind == "composer":
                return self.composers().get_composer(entity_id) is not None
            if kind == "work":
                return self.composers().get_work(entity_id) is not None
        except Exception:  # noqa: BLE001 — storage inaccesible: no bloquear la petición
            return True
        return True

    def list_corrections(self, token: str | None) -> list[CorrectionRead]:
        self._require_admin(token)
        return [self._correction_read(row) for row in self._store.list_corrections()]

    def resolve_correction(
        self, token: str | None, correction_id: str, action: str, message: str
    ) -> CorrectionRead | None:
        self._require_admin(token)

        principal = self._container.authenticator().resolve(token)
        if principal is None:
            raise UnauthenticatedError("Login required")
        decided_by = str(getattr(principal, "user_id", "admin"))
        status = "reviewed" if action == "review" else "closed"
        row = self._store.resolve_correction(correction_id, status, message, decided_by)
        if row is None:
            return None
        logging.getLogger("osap.corrections").info(
            "correction %s -> %s: %s", correction_id, status, message
        )
        return self._correction_read(row)

    def _correction_read(self, row: dict[str, object]) -> CorrectionRead:
        return CorrectionRead(
            id=str(row["id"]),
            kind=str(row["kind"]),
            entity_id=str(row["entity_id"]) if row.get("entity_id") else None,
            entity_provider=str(row["entity_provider"]) if row.get("entity_provider") else None,
            field=str(row["field"]) if row.get("field") else None,
            current_value=str(row["current_value"]) if row.get("current_value") else None,
            proposed_value=str(row["proposed_value"]) if row.get("proposed_value") else None,
            message=str(row.get("message") or ""),
            contact_email=str(row["contact_email"]) if row.get("contact_email") else None,
            requested_by=str(row["requested_by"]) if row.get("requested_by") else None,
            requested_by_name=str(row["requested_by_name"]) if row.get("requested_by_name") else None,
            requested_by_email=str(row["requested_by_email"]) if row.get("requested_by_email") else None,
            status=str(row["status"]),
            admin_message=str(row["admin_message"]) if row.get("admin_message") else None,
            created_at=str(row["created_at"]),
        )

