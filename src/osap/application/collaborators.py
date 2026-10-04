"""Composición de la lista pública de colaboradores (fachada osap-api).

La lista la dirige **osap-auth** (identidad): todos los usuarios con consentimiento de cuenta
(`nickname_public_consent`) y nickname. `osap-support` solo aporta los **reconocimientos**
(badges) del proyecto, que se adjuntan por `user_id` (pueden no tener ninguno). osap-api no
replica reglas: compone y **nunca** expone `user_id`, email, `name`, economía ni metadatos.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class CollaboratorsUnavailableError(Exception):
    """Un servicio aguas arriba (support/auth) no respondió o devolvió un error."""


class PublicProjectNotFoundError(Exception):
    """El proyecto no existe en la whitelist de osap-support."""


@dataclass(frozen=True)
class PublicProfile:
    """Identidad pública de cuenta (auth), lookup por id: nickname y su consentimiento."""

    nickname: str | None
    nickname_public_consent: bool


@dataclass(frozen=True)
class PublicUser:
    """Entrada de la lista pública (auth): usuario consentido con nickname."""

    user_id: str
    nickname: str


class RecognitionsSource(Protocol):
    def active_project_recognitions(self, project: str) -> list[dict[str, Any]]: ...


class ProfilesSource(Protocol):
    def public_users(self) -> list[PublicUser]: ...


class ComposePublicCollaboratorsUseCase:
    def __init__(self, *, recognitions: RecognitionsSource, profiles: ProfilesSource) -> None:
        self._recognitions = recognitions
        self._profiles = profiles

    def execute(self, project: str) -> list[dict[str, object]]:
        users = self._profiles.public_users()
        badges: dict[str, list[dict[str, Any]]] = {
            str(row["user_id"]): list(row.get("recognitions", []))
            for row in self._recognitions.active_project_recognitions(project)
        }
        return [
            {
                "nickname": user.nickname,
                "recognitions": [
                    {"type": rec["type"], "granted_at": rec["granted_at"]}
                    for rec in badges.get(user.user_id, [])
                ],
            }
            for user in users
        ]
