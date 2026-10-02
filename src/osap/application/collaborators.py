"""Composición de la lista pública de colaboradores (fachada osap-api).

`osap-support` sigue siendo la fuente de verdad de los reconocimientos y `osap-auth` la de la
identidad: este caso de uso **no replica reglas**, solo compone:
  1) reconocimientos públicos del proyecto (support): ya vienen agrupados por `user_id`,
  2) nombres visibles por lote de `user_id` (auth, ≤500 por llamada),
y **omite** a quien no tenga nombre visible (usuario eliminado o `name=null`).

Nunca expone `user_id` ni email, economía, origin, reason, granted_by o membership.
"""

from __future__ import annotations

from typing import Any, Protocol


class CollaboratorsUnavailableError(Exception):
    """Un servicio aguas arriba (support/auth) no respondió o devolvió un error."""


class PublicProjectNotFoundError(Exception):
    """El proyecto no existe en la whitelist de osap-support."""


class RecognitionsSource(Protocol):
    def public_project_recognitions(self, project: str) -> list[dict[str, Any]]: ...


class NamesSource(Protocol):
    def names(self, user_ids: list[str]) -> dict[str, str | None]: ...


class ComposePublicCollaboratorsUseCase:
    def __init__(self, *, recognitions: RecognitionsSource, names: NamesSource) -> None:
        self._recognitions = recognitions
        self._names = names

    def execute(self, project: str) -> list[dict[str, object]]:
        rows = self._recognitions.public_project_recognitions(project)
        names = self._names.names([str(row["user_id"]) for row in rows])
        colaboradores: list[dict[str, object]] = []
        for row in rows:
            nombre = names.get(str(row["user_id"]))
            if not nombre:
                continue  # eliminado o sin nombre público: no se publica
            colaboradores.append(
                {
                    "name": nombre,
                    "recognitions": [
                        {"type": rec["type"], "granted_at": rec["granted_at"]}
                        for rec in row.get("recognitions", [])
                    ],
                }
            )
        return colaboradores
