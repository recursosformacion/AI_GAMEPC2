"""Router de admin_ops (F5.5)."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from fastapi import APIRouter, Header, Query, Response

from src.osap.api.contracts import (
    AddAliasRequest,
    AliasResponse,
    ComposerDetailResponse,
    ComposerSummaryResponse,
    CreateComposerRequest,
    ErrorEnvelope,
    MergeComposersRequest,
    MergeComposersResultResponse,
    MoveAliasRequest,
    MoveAliasResultResponse,
    PromoteAliasResultResponse,
    ReviewComposerRequest,
    SetAttributionRequest,
    SetAttributionResultResponse,
    SetOpConfigRequest,
    SetProviderWiredRequest,
    SourceSuggestionRead,
    SourceSuggestionResolveRequest,
    SuccessEnvelope,
    UpsertProviderRequest,
    WorkAiReviewRequest,
)
from src.osap.domain.errors import AiNotConfiguredError, ProposalNotAssignableError
from src.osap.domain.votes import ForbiddenError, UnauthenticatedError, WorkNotFoundError
from src.osap.infrastructure.storage.storage_composer_client import StorageComposerError

if TYPE_CHECKING:
    from src.osap.api.http.context import HttpContext


def build_admin_ops_router(ctx: HttpContext) -> APIRouter:
    from src.osap.api.http import shared as _shared

    router: APIRouter = APIRouter()

    @router.get(
        "/api/v1/admin/op/providers",
        tags=["Providers"],
        summary="List dynamic providers",
        description="Lista los proveedores registrados dinámicamente en la BD operativa. "
        "Exige role=admin.",
        response_model=SuccessEnvelope[list[dict[str, object]]] | ErrorEnvelope,
        responses={
            200: _shared._resp("Providers", _shared._example([])),
            401: _shared._UNAUTHORIZED_401,
            403: _shared._FORBIDDEN_403,
        },
    )
    def list_op_providers(
        response: Response,
        authorization: str | None = Header(default=None),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            return ctx.ok(ctx.api.list_op_providers(authorization))
        except UnauthenticatedError:
            return ctx.fail(401, response, "UNAUTHORIZED", "Login required")
        except ForbiddenError:
            return ctx.fail(403, response, "FORBIDDEN", "Admin role required")

    @router.post(
        "/api/v1/admin/op/providers",
        status_code=201,
        tags=["Providers"],
        summary="Register / update a dynamic provider",
        description="Da de alta o actualiza un proveedor dinámico en la BD operativa. "
        "Exige role=admin.",
        response_model=SuccessEnvelope[dict[str, object]] | ErrorEnvelope,
        responses={
            201: _shared._resp("Provider", _shared._example({})),
            401: _shared._UNAUTHORIZED_401,
            403: _shared._FORBIDDEN_403,
        },
    )
    def upsert_op_provider(
        payload: UpsertProviderRequest,
        response: Response,
        authorization: str | None = Header(default=None),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            return ctx.ok(
                ctx.api.upsert_op_provider(
                    authorization,
                    payload.provider_id,
                    payload.name,
                    payload.base_url,
                    payload.wired,
                    payload.config,
                    payload.description,
                    payload.endpoints,
                    payload.mapping,
                    payload.resources,
                    payload.transforms,
                )
            )
        except UnauthenticatedError:
            return ctx.fail(401, response, "UNAUTHORIZED", "Login required")
        except ForbiddenError:
            return ctx.fail(403, response, "FORBIDDEN", "Admin role required")

    @router.delete(
        "/api/v1/admin/op/providers/{provider_id}",
        tags=["Providers"],
        summary="Delete a dynamic provider",
        description="Elimina un proveedor dinámico de la BD operativa. Exige role=admin.",
        response_model=SuccessEnvelope[dict[str, object]] | ErrorEnvelope,
        responses={200: _shared._resp("Deleted", _shared._example({"deleted": True})), 401: _shared._UNAUTHORIZED_401,
                   403: _shared._FORBIDDEN_403, 404: _shared._NOT_FOUND_404},
    )
    def delete_op_provider(
        provider_id: str,
        response: Response,
        authorization: str | None = Header(default=None),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            deleted = ctx.api.delete_op_provider(authorization, provider_id)
        except UnauthenticatedError:
            return ctx.fail(401, response, "UNAUTHORIZED", "Login required")
        except ForbiddenError:
            return ctx.fail(403, response, "FORBIDDEN", "Admin role required")
        if not deleted:
            return ctx.fail(404, response, "NOT_FOUND", "Provider not found")
        return ctx.ok({"deleted": True, "provider_id": provider_id})

    @router.post(
        "/api/v1/admin/op/providers/{provider_id}/wire",
        tags=["Providers"],
        summary="Set provider wired flag",
        description="Activa/desactiva un proveedor dinámico. Exige role=admin.",
        response_model=SuccessEnvelope[dict[str, object]] | ErrorEnvelope,
        responses={
            200: _shared._resp("Provider", _shared._example({})),
            401: _shared._UNAUTHORIZED_401,
            403: _shared._FORBIDDEN_403,
        },
    )
    def set_op_provider_wired(
        provider_id: str,
        payload: SetProviderWiredRequest,
        response: Response,
        authorization: str | None = Header(default=None),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            provider = ctx.api.set_op_provider_wired(authorization, provider_id, payload.wired)
        except UnauthenticatedError:
            return ctx.fail(401, response, "UNAUTHORIZED", "Login required")
        except ForbiddenError:
            return ctx.fail(403, response, "FORBIDDEN", "Admin role required")
        if provider is None:
            return ctx.fail(404, response, "NOT_FOUND", "Provider not found")
        return ctx.ok(provider)

    @router.get(
        "/api/v1/admin/op/config",
        tags=["System"],
        summary="Get operational config",
        description="Devuelve la configuración operativa persistida en la BD. Exige role=admin.",
        response_model=SuccessEnvelope[dict[str, object]] | ErrorEnvelope,
        responses={
            200: _shared._resp("Config", _shared._example({})),
            401: _shared._UNAUTHORIZED_401,
            403: _shared._FORBIDDEN_403,
        },
    )
    def get_op_config(
        response: Response,
        authorization: str | None = Header(default=None),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            return ctx.ok(ctx.api.get_op_config(authorization))
        except UnauthenticatedError:
            return ctx.fail(401, response, "UNAUTHORIZED", "Login required")
        except ForbiddenError:
            return ctx.fail(403, response, "FORBIDDEN", "Admin role required")

    @router.put(
        "/api/v1/admin/op/config",
        tags=["System"],
        summary="Set a configuration value",
        description="Persiste una clave de configuración operativa en la BD. Exige role=admin.",
        response_model=SuccessEnvelope[dict[str, object]] | ErrorEnvelope,
        responses={
            200: _shared._resp("Config", _shared._example({})),
            401: _shared._UNAUTHORIZED_401,
            403: _shared._FORBIDDEN_403,
        },
    )
    def set_op_config(
        payload: SetOpConfigRequest,
        response: Response,
        authorization: str | None = Header(default=None),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            return ctx.ok(ctx.api.set_op_config(authorization, payload.key, payload.value))
        except UnauthenticatedError:
            return ctx.fail(401, response, "UNAUTHORIZED", "Login required")
        except ForbiddenError:
            return ctx.fail(403, response, "FORBIDDEN", "Admin role required")

    @router.get(
        "/api/v1/admin/source-suggestions",
        tags=["Sources"],
        summary="List pending source suggestions",
        description="Administrator view of user source suggestions. Exige role=admin.",
        response_model=SuccessEnvelope[list[SourceSuggestionRead]] | ErrorEnvelope,
        responses={
            200: _shared._resp("Suggestions", _shared._example([])),
            401: _shared._UNAUTHORIZED_401,
            403: _shared._FORBIDDEN_403,
        },
    )
    def list_source_suggestions(
        response: Response,
        authorization: str | None = Header(default=None),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            return ctx.ok(ctx.api.list_source_suggestions(authorization))
        except UnauthenticatedError:
            return ctx.fail(401, response, "UNAUTHORIZED", "Login required")
        except ForbiddenError:
            return ctx.fail(403, response, "FORBIDDEN", "Admin role required")

    @router.post(
        "/api/v1/admin/source-suggestions/{suggestion_id}/resolve",
        tags=["Sources"],
        summary="Resolve a source suggestion (approve / cancel)",
        description="The administrator approves or cancels a user suggestion, with a message. "
        "La decisión se notifica al usuario solicitante.",
        response_model=SuccessEnvelope[SourceSuggestionRead] | ErrorEnvelope,
        responses={
            200: _shared._resp("Resolved", _shared._example({})),
            401: _shared._UNAUTHORIZED_401,
            403: _shared._FORBIDDEN_403,
            404: _shared._NOT_FOUND_404,
        },
    )
    def resolve_source_suggestion(
        suggestion_id: str,
        payload: SourceSuggestionResolveRequest,
        response: Response,
        authorization: str | None = Header(default=None),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            resolved = ctx.api.resolve_source_suggestion(authorization, suggestion_id, payload.action, payload.message)
        except UnauthenticatedError:
            return ctx.fail(401, response, "UNAUTHORIZED", "Login required")
        except ForbiddenError:
            return ctx.fail(403, response, "FORBIDDEN", "Admin role required")
        if resolved is None:
            return ctx.fail(404, response, "NOT_FOUND", "Suggestion not found")
        return ctx.ok(resolved)

    @router.get(
        "/api/v1/admin/users",
        tags=["Admin"],
        summary="List OSAP users (admin)",
        description="Listado de usuarios desde osap-auth (nombre y email incluidos). "
        "La identidad y su BD viven en osap-auth; osap-api solo reenvía. Exige role=admin.",
        response_model=SuccessEnvelope[object] | ErrorEnvelope,
        responses={
            200: _shared._resp("User list", _shared._example([])),
            401: _shared._UNAUTHORIZED_401,
            403: _shared._FORBIDDEN_403,
        },
    )
    def admin_users_list(
        response: Response,
        authorization: str | None = Header(default=None),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            data = ctx.api.admin_users_list(authorization)
        except UnauthenticatedError:
            return ctx.fail(401, response, "UNAUTHORIZED", "Missing or invalid access token")
        except ForbiddenError:
            return ctx.fail(403, response, "FORBIDDEN", "Admin role required")
        except Exception as exc:  # noqa: BLE001 — osap-auth no disponible
            return ctx.fail(502, response, "AUTH_UNAVAILABLE", str(exc))
        return ctx.ok(data)

    @router.get(
        "/api/v1/admin/users/{user_id}",
        tags=["Admin"],
        summary="Get OSAP user (admin)",
        response_model=SuccessEnvelope[object] | ErrorEnvelope,
        responses={
            200: _shared._resp("User", _shared._example({})),
            401: _shared._UNAUTHORIZED_401,
            403: _shared._FORBIDDEN_403,
            404: _shared._NOT_FOUND_404,
        },
    )
    def admin_user_get(
        user_id: str,
        response: Response,
        authorization: str | None = Header(default=None),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            data = ctx.api.admin_user_get(authorization, user_id)
        except UnauthenticatedError:
            return ctx.fail(401, response, "UNAUTHORIZED", "Missing or invalid access token")
        except ForbiddenError:
            return ctx.fail(403, response, "FORBIDDEN", "Admin role required")
        except WorkNotFoundError:
            return ctx.fail(404, response, "NOT_FOUND", "User not found")
        except Exception as exc:  # noqa: BLE001 — osap-auth no disponible
            return ctx.fail(502, response, "AUTH_UNAVAILABLE", str(exc))
        return ctx.ok(data)

    @router.patch(
        "/api/v1/admin/users/{user_id}",
        tags=["Admin"],
        summary="Update OSAP user (admin)",
        description="Edita nombre, roles y/o estado. Exige role=admin.",
        response_model=SuccessEnvelope[object] | ErrorEnvelope,
        responses={
            200: _shared._resp("User", _shared._example({})),
            401: _shared._UNAUTHORIZED_401,
            403: _shared._FORBIDDEN_403,
            404: _shared._NOT_FOUND_404,
        },
    )
    def admin_user_update(
        user_id: str,
        payload: dict[str, object],
        response: Response,
        authorization: str | None = Header(default=None),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            data = ctx.api.admin_user_update(
                authorization,
                user_id,
                name=cast("str | None", payload.get("name")),
                roles=cast("list[str] | None", payload.get("roles")),
                status=cast("str | None", payload.get("status")),
            )
        except UnauthenticatedError:
            return ctx.fail(401, response, "UNAUTHORIZED", "Missing or invalid access token")
        except ForbiddenError:
            return ctx.fail(403, response, "FORBIDDEN", "Admin role required")
        except WorkNotFoundError:
            return ctx.fail(404, response, "NOT_FOUND", "User not found")
        except Exception as exc:  # noqa: BLE001 — osap-auth no disponible
            return ctx.fail(502, response, "AUTH_UNAVAILABLE", str(exc))
        return ctx.ok(data)

    @router.delete(
        "/api/v1/admin/users/{user_id}",
        tags=["Admin"],
        summary="Dar de baja OSAP user (admin, anonimiza)",
        description="Baja definitiva: osap-auth anonimiza la cuenta (borra email/contraseña, "
        "revoca sesiones y marca el estado como eliminado). Es irreversible. Sirve también "
        "para dar de baja usuarios pendientes de verificar.",
        response_model=SuccessEnvelope[object] | ErrorEnvelope,
        responses={
            200: _shared._resp("User deleted", _shared._example({})),
            401: _shared._UNAUTHORIZED_401,
            403: _shared._FORBIDDEN_403,
            404: _shared._NOT_FOUND_404,
        },
    )
    def admin_user_delete(
        user_id: str,
        response: Response,
        authorization: str | None = Header(default=None),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            data = ctx.api.admin_user_delete(authorization, user_id)
        except UnauthenticatedError:
            return ctx.fail(401, response, "UNAUTHORIZED", "Missing or invalid access token")
        except ForbiddenError:
            return ctx.fail(403, response, "FORBIDDEN", "Admin role required")
        except WorkNotFoundError:
            return ctx.fail(404, response, "NOT_FOUND", "User not found")
        except Exception as exc:  # noqa: BLE001 — osap-auth no disponible
            return ctx.fail(502, response, "AUTH_UNAVAILABLE", str(exc))
        return ctx.ok(data)

    @router.get(
        "/api/v1/admin/storage-web",
        tags=["System"],
        summary="Storage web admin URL (CRUD)",
        description="Devuelve la URL de la capa web de administración de osap-storage, "
        "autenticada con token de servicio (storage:admin). `section` (opcional) abre el "
        "admin de storage en la pestaña correspondiente: composers | works | tables. "
        "Exige role=admin.",
        response_model=SuccessEnvelope[dict[str, str]] | ErrorEnvelope,
        responses={
            200: _shared._resp("URL", _shared._example({})),
            401: _shared._UNAUTHORIZED_401,
            403: _shared._FORBIDDEN_403,
        },
    )
    def storage_web(
        response: Response,
        section: str | None = Query(default=None),
        authorization: str | None = Header(default=None),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            url = ctx.api.storage_web(authorization, section)
        except UnauthenticatedError:
            return ctx.fail(401, response, "UNAUTHORIZED", "Login required")
        except ForbiddenError:
            return ctx.fail(403, response, "FORBIDDEN", "Admin role required")
        return ctx.ok({"url": url})

    @router.post(
        "/api/v1/admin/composers/merge",
        status_code=200,
        tags=["Composers"],
        summary="Merge composers (admin)",
        description="Fusiona `sources` dentro de `target_id` (ambos person_id existentes). "
        "Exige role=admin; backend: osap-storage con storage:admin.",
        response_model=SuccessEnvelope[MergeComposersResultResponse] | ErrorEnvelope,
        responses={
            200: _shared._resp("Merge result", _shared._example({})),
            401: _shared._UNAUTHORIZED_401,
            403: _shared._FORBIDDEN_403,
            404: _shared._NOT_FOUND_404,
            **_shared._standard_errors(422),
        },
    )
    def merge_composers(
        payload: MergeComposersRequest,
        response: Response,
        authorization: str | None = Header(default=None),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            result = ctx.api.merge_composers(authorization, payload.target_id, payload.sources)
        except UnauthenticatedError:
            return ctx.fail(401, response, "UNAUTHORIZED", "Missing or invalid access token")
        except ForbiddenError:
            return ctx.fail(403, response, "FORBIDDEN", "Admin role required")
        except WorkNotFoundError:
            return ctx.fail(404, response, "NOT_FOUND", "Composer not found")
        except StorageComposerError:
            return ctx.fail(
                503, response, "ADMIN_SERVICE_UNAVAILABLE", "Composer admin service is not configured"
            )
        return ctx.ok(_shared._merge_result_dto(result))

    @router.post(
        "/api/v1/admin/composers",
        status_code=201,
        tags=["Composers"],
        summary="Create composer (admin)",
        description="Crea un compositor con el nombre dado (para fusionar hacia un compositor "
        "inexistente). Exige role=admin; backend: osap-storage con storage:admin.",
        response_model=SuccessEnvelope[ComposerSummaryResponse] | ErrorEnvelope,
        responses={
            201: _shared._resp("Created composer", _shared._example({})),
            401: _shared._UNAUTHORIZED_401,
            403: _shared._FORBIDDEN_403,
            **_shared._standard_errors(422),
        },
    )
    def create_composer(
        payload: CreateComposerRequest,
        response: Response,
        authorization: str | None = Header(default=None),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            composer = ctx.api.create_composer(authorization, payload.name)
        except UnauthenticatedError:
            return ctx.fail(401, response, "UNAUTHORIZED", "Missing or invalid access token")
        except ForbiddenError:
            return ctx.fail(403, response, "FORBIDDEN", "Admin role required")
        except StorageComposerError:
            return ctx.fail(
                503, response, "ADMIN_SERVICE_UNAVAILABLE", "Composer admin service is not configured"
            )
        return ctx.ok(_shared._composer_summary_dto(composer))

    @router.post(
        "/api/v1/admin/composers/{person_id}/review",
        status_code=200,
        tags=["Composers"],
        summary="Set composer review status (admin)",
        description="Marca el estado de revisión de un compositor (correct|incorrect|reviewed|"
        "not_reviewed). Exige role=admin; backend: osap-storage con storage:admin.",
        response_model=SuccessEnvelope[ComposerDetailResponse] | ErrorEnvelope,
        responses={
            200: _shared._resp("Reviewed composer", _shared._example({})),
            401: _shared._UNAUTHORIZED_401,
            403: _shared._FORBIDDEN_403,
            404: _shared._NOT_FOUND_404,
            **_shared._standard_errors(422),
        },
    )
    def review_composer(
        person_id: str,
        payload: ReviewComposerRequest,
        response: Response,
        authorization: str | None = Header(default=None),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            composer = ctx.api.review_composer(authorization, person_id, payload.review_status)
        except UnauthenticatedError:
            return ctx.fail(401, response, "UNAUTHORIZED", "Missing or invalid access token")
        except ForbiddenError:
            return ctx.fail(403, response, "FORBIDDEN", "Admin role required")
        except WorkNotFoundError:
            return ctx.fail(404, response, "NOT_FOUND", "Composer not found")
        except StorageComposerError:
            return ctx.fail(
                503, response, "ADMIN_SERVICE_UNAVAILABLE", "Composer admin service is not configured"
            )
        return ctx.ok(_shared._composer_detail_dto(composer))

    @router.post(
        "/api/v1/admin/composers/{person_id}/aliases",
        status_code=200,
        tags=["Composers"],
        summary="Add alias to a composer (admin)",
        description="Añade un alias a un compositor (solo mejora el reconocimiento; no toca obras). "
        "Exige role=admin; backend: osap-storage con storage:admin.",
        response_model=SuccessEnvelope[AliasResponse] | ErrorEnvelope,
        responses={
            200: _shared._resp("Added alias", _shared._example({})),
            401: _shared._UNAUTHORIZED_401,
            403: _shared._FORBIDDEN_403,
            404: _shared._NOT_FOUND_404,
            **_shared._standard_errors(422),
        },
    )
    def add_alias(
        person_id: str,
        payload: AddAliasRequest,
        response: Response,
        authorization: str | None = Header(default=None),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            alias = ctx.api.add_alias(authorization, person_id, payload.alias)
        except UnauthenticatedError:
            return ctx.fail(401, response, "UNAUTHORIZED", "Missing or invalid access token")
        except ForbiddenError:
            return ctx.fail(403, response, "FORBIDDEN", "Admin role required")
        except WorkNotFoundError:
            return ctx.fail(404, response, "NOT_FOUND", "Composer not found")
        except StorageComposerError:
            return ctx.fail(503, response, "ADMIN_SERVICE_UNAVAILABLE", "Composer admin service is not configured")
        return ctx.ok(AliasResponse.model_validate(alias))

    @router.get(
        "/api/v1/admin/composers/{person_id}/aliases",
        status_code=200,
        tags=["Composers"],
        summary="List composer aliases (admin)",
        description="Devuelve los alias de un compositor (con id). Exige role=admin; "
        "backend: osap-storage con storage:admin.",
        response_model=SuccessEnvelope[list[AliasResponse]] | ErrorEnvelope,
        responses={
            200: _shared._resp("Aliases", _shared._example({})),
            401: _shared._UNAUTHORIZED_401,
            403: _shared._FORBIDDEN_403,
            404: _shared._NOT_FOUND_404,
            **_shared._standard_errors(422),
        },
    )
    def list_aliases(
        person_id: str,
        response: Response,
        authorization: str | None = Header(default=None),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            aliases = ctx.api.list_aliases(authorization, person_id)
        except UnauthenticatedError:
            return ctx.fail(401, response, "UNAUTHORIZED", "Missing or invalid access token")
        except ForbiddenError:
            return ctx.fail(403, response, "FORBIDDEN", "Admin role required")
        except WorkNotFoundError:
            return ctx.fail(404, response, "NOT_FOUND", "Composer not found")
        except StorageComposerError:
            return ctx.fail(503, response, "ADMIN_SERVICE_UNAVAILABLE", "Composer admin service is not configured")
        return ctx.ok([AliasResponse.model_validate(a) for a in aliases])

    @router.post(
        "/api/v1/admin/composers/{person_id}/aliases/{alias_id}/move",
        status_code=200,
        tags=["Composers"],
        summary="Move an alias to another composer (admin)",
        description="Mueve el alias (no se borra) y reasigna sus obras al compositor destino. "
        "Exige role=admin; backend: osap-storage con storage:admin.",
        response_model=SuccessEnvelope[MoveAliasResultResponse] | ErrorEnvelope,
        responses={
            200: _shared._resp("Moved alias", _shared._example({})),
            401: _shared._UNAUTHORIZED_401,
            403: _shared._FORBIDDEN_403,
            404: _shared._NOT_FOUND_404,
            **_shared._standard_errors(422),
        },
    )
    def move_alias(
        person_id: str,
        alias_id: int,
        payload: MoveAliasRequest,
        response: Response,
        authorization: str | None = Header(default=None),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            alias = ctx.api.move_alias(authorization, alias_id, payload.from_person_id, payload.target_person_id)
        except UnauthenticatedError:
            return ctx.fail(401, response, "UNAUTHORIZED", "Missing or invalid access token")
        except ForbiddenError:
            return ctx.fail(403, response, "FORBIDDEN", "Admin role required")
        except WorkNotFoundError:
            return ctx.fail(404, response, "NOT_FOUND", "Composer or alias not found")
        except StorageComposerError:
            return ctx.fail(503, response, "ADMIN_SERVICE_UNAVAILABLE", "Composer admin service is not configured")
        return ctx.ok(MoveAliasResultResponse.model_validate(alias))

    @router.post(
        "/api/v1/admin/composers/{person_id}/aliases/{alias_id}/promote",
        status_code=200,
        tags=["Composers"],
        summary="Promote an alias to its own composer (admin)",
        description="Crea un Composer desde el alias y reasigna sus obras. Exige role=admin; "
        "backend: osap-storage con storage:admin.",
        response_model=SuccessEnvelope[PromoteAliasResultResponse] | ErrorEnvelope,
        responses={
            200: _shared._resp("Promoted alias", _shared._example({})),
            401: _shared._UNAUTHORIZED_401,
            403: _shared._FORBIDDEN_403,
            404: _shared._NOT_FOUND_404,
            **_shared._standard_errors(422),
        },
    )
    def promote_alias(
        person_id: str,
        alias_id: int,
        response: Response,
        authorization: str | None = Header(default=None),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            composer = ctx.api.promote_alias(authorization, person_id, alias_id)
        except UnauthenticatedError:
            return ctx.fail(401, response, "UNAUTHORIZED", "Missing or invalid access token")
        except ForbiddenError:
            return ctx.fail(403, response, "FORBIDDEN", "Admin role required")
        except WorkNotFoundError:
            return ctx.fail(404, response, "NOT_FOUND", "Composer or alias not found")
        except StorageComposerError:
            return ctx.fail(503, response, "ADMIN_SERVICE_UNAVAILABLE", "Composer admin service is not configured")
        return ctx.ok(PromoteAliasResultResponse.model_validate(composer))

    @router.post(
        "/api/v1/admin/composers/set-attribution",
        status_code=200,
        tags=["Composers"],
        summary="Convert composers to attribution (admin)",
        description="Las obras de los compositores guardan attribution_type + attribution_note y se "
        "les borra person_id; los compositores se retiran. Exige role=admin; "
        "backend: osap-storage con storage:admin.",
        response_model=SuccessEnvelope[SetAttributionResultResponse] | ErrorEnvelope,
        responses={
            200: _shared._resp("Set attribution", _shared._example({})),
            401: _shared._UNAUTHORIZED_401,
            403: _shared._FORBIDDEN_403,
            **_shared._standard_errors(422),
        },
    )
    def set_attribution(
        payload: SetAttributionRequest,
        response: Response,
        authorization: str | None = Header(default=None),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            result = ctx.api.set_attribution(authorization, payload.person_ids, payload.attribution_type)
        except UnauthenticatedError:
            return ctx.fail(401, response, "UNAUTHORIZED", "Missing or invalid access token")
        except ForbiddenError:
            return ctx.fail(403, response, "FORBIDDEN", "Admin role required")
        except StorageComposerError:
            return ctx.fail(503, response, "ADMIN_SERVICE_UNAVAILABLE", "Composer admin service is not configured")
        return ctx.ok(SetAttributionResultResponse.model_validate(result))

    # --- atribución asistida por IA (propuestas + revisión humana) -------------
    #
    # Gemini solo propone; la asignación efectiva y su auditoría viven en osap-storage.

    @router.post(
        "/api/v1/admin/work-person-ai/propose/{work_id}",
        status_code=200,
        tags=["Work attribution"],
        summary="Propose a work attribution with AI (admin)",
        description="Pide a la IA una propuesta de atribución para la obra y la guarda como "
        "hipótesis pendiente de revisión (nunca asigna). Exige role=admin; backend: "
        "osap-storage con storage:admin. Responde 503 si la IA no está configurada.",
        response_model=SuccessEnvelope[dict[str, object]] | ErrorEnvelope,
        responses={
            200: _shared._resp("Proposal", _shared._example({})),
            401: _shared._UNAUTHORIZED_401,
            403: _shared._FORBIDDEN_403,
            404: _shared._NOT_FOUND_404,
            503: _shared._resp("IA not configured", _shared._example({"code": "AI_NOT_CONFIGURED"})),
        },
    )
    def propose_work_attribution(
        work_id: int,
        response: Response,
        batch_id: str | None = Query(default=None),
        authorization: str | None = Header(default=None),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            return ctx.ok(ctx.api.propose_work_attribution(authorization, work_id, batch_id))
        except UnauthenticatedError:
            return ctx.fail(401, response, "UNAUTHORIZED", "Missing or invalid access token")
        except ForbiddenError:
            return ctx.fail(403, response, "FORBIDDEN", "Admin role required")
        except WorkNotFoundError:
            return ctx.fail(404, response, "NOT_FOUND", "Work not found")
        except AiNotConfiguredError:
            return ctx.fail(503, response, "AI_NOT_CONFIGURED", "IA no configurada")
        except StorageComposerError:
            return ctx.fail(503, response, "ADMIN_SERVICE_UNAVAILABLE", "Storage admin service unavailable")

    @router.get(
        "/api/v1/admin/work-person-ai",
        tags=["Work attribution"],
        summary="List AI attribution proposals (admin)",
        description="Lista propuestas de atribución con filtro por estado "
        "(pending|accepted|rejected|uncertain). Exige role=admin.",
        response_model=SuccessEnvelope[dict[str, object]] | ErrorEnvelope,
        responses={
            200: _shared._resp("Proposals page", _shared._example({"items": [], "total": 0})),
            401: _shared._UNAUTHORIZED_401,
            403: _shared._FORBIDDEN_403,
        },
    )
    def list_work_attribution_proposals(
        response: Response,
        status: str | None = Query(default=None, pattern=r"^(pending|accepted|rejected|uncertain)$"),
        limit: int = Query(default=50, ge=1, le=500),
        offset: int = Query(default=0, ge=0),
        authorization: str | None = Header(default=None),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            return ctx.ok(ctx.api.list_work_attribution_proposals(authorization, status, limit, offset))
        except UnauthenticatedError:
            return ctx.fail(401, response, "UNAUTHORIZED", "Missing or invalid access token")
        except ForbiddenError:
            return ctx.fail(403, response, "FORBIDDEN", "Admin role required")
        except StorageComposerError:
            return ctx.fail(503, response, "ADMIN_SERVICE_UNAVAILABLE", "Storage admin service unavailable")

    @router.get(
        "/api/v1/admin/work-person-ai/{proposal_id}",
        tags=["Work attribution"],
        summary="AI attribution proposal detail (admin)",
        description="Detalle de una propuesta (evidencia y respuesta del modelo incluidos). "
        "Exige role=admin.",
        response_model=SuccessEnvelope[dict[str, object]] | ErrorEnvelope,
        responses={
            200: _shared._resp("Proposal detail", _shared._example({})),
            401: _shared._UNAUTHORIZED_401,
            403: _shared._FORBIDDEN_403,
            404: _shared._NOT_FOUND_404,
        },
    )
    def get_work_attribution_proposal(
        proposal_id: int,
        response: Response,
        authorization: str | None = Header(default=None),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            return ctx.ok(ctx.api.get_work_attribution_proposal(authorization, proposal_id))
        except UnauthenticatedError:
            return ctx.fail(401, response, "UNAUTHORIZED", "Missing or invalid access token")
        except ForbiddenError:
            return ctx.fail(403, response, "FORBIDDEN", "Admin role required")
        except WorkNotFoundError:
            return ctx.fail(404, response, "NOT_FOUND", "Proposal not found")
        except StorageComposerError:
            return ctx.fail(503, response, "ADMIN_SERVICE_UNAVAILABLE", "Storage admin service unavailable")

    @router.post(
        "/api/v1/admin/work-person-ai/{proposal_id}/review",
        status_code=200,
        tags=["Work attribution"],
        summary="Review an AI attribution proposal (admin)",
        description="Acepta, rechaza o marca como dudosa una propuesta. Aceptar es lo único que "
        "asigna la persona (vía canónica de storage) y lo audita. Exige role=admin.",
        response_model=SuccessEnvelope[dict[str, object]] | ErrorEnvelope,
        responses={
            200: _shared._resp("Review result", _shared._example({"id": 1, "status": "accepted"})),
            401: _shared._UNAUTHORIZED_401,
            403: _shared._FORBIDDEN_403,
            404: _shared._NOT_FOUND_404,
            409: _shared._resp(
                "Proposal cannot be accepted", _shared._example({"code": "PROPOSAL_NOT_ASSIGNABLE"})
            ),
            **_shared._standard_errors(422),
        },
    )
    def review_work_attribution_proposal(
        proposal_id: int,
        payload: WorkAiReviewRequest,
        response: Response,
        authorization: str | None = Header(default=None),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        if payload.action not in ("accept", "reject", "uncertain"):
            return ctx.fail(422, response, "VALIDATION_ERROR", "action must be accept|reject|uncertain")
        try:
            return ctx.ok(
                ctx.api.review_work_attribution_proposal(
                    authorization, proposal_id, payload.action, payload.note, payload.reviewed_by
                )
            )
        except UnauthenticatedError:
            return ctx.fail(401, response, "UNAUTHORIZED", "Missing or invalid access token")
        except ForbiddenError:
            return ctx.fail(403, response, "FORBIDDEN", "Admin role required")
        except WorkNotFoundError:
            return ctx.fail(404, response, "NOT_FOUND", "Proposal not found")
        except ProposalNotAssignableError:
            return ctx.fail(409, response, "PROPOSAL_NOT_ASSIGNABLE", "Proposal requires a matched person")
        except AiNotConfiguredError:
            return ctx.fail(503, response, "AI_NOT_CONFIGURED", "IA no configurada")
        except StorageComposerError:
            return ctx.fail(503, response, "ADMIN_SERVICE_UNAVAILABLE", "Storage admin service unavailable")

    return router
