"""Router de votes: voto, estadísticas y admin (F5.5)."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from fastapi import APIRouter, Header, Response

from src.osap.api.contracts import (
    ComposerStatisticsResponse,
    ErrorEnvelope,
    SuccessEnvelope,
    VoteRequest,
    VoteResponse,
    VotesOverviewResponse,
    WorkStatisticsResponse,
)
from src.osap.domain.votes import (
    DuplicateVoteError,
    ForbiddenError,
    InvalidVoteError,
    UnauthenticatedError,
    WorkNotFoundError,
)
from src.osap.infrastructure.persistence.storage_vote_store import StorageUnavailableError

if TYPE_CHECKING:
    from src.osap.api.http.context import HttpContext


def build_votes_router(ctx: HttpContext) -> APIRouter:
    from src.osap.api.http import shared as _shared

    router: APIRouter = APIRouter()

    # --- votes & statistics (v1) --------------------------------------------

    @router.post(
        "/api/v1/works/{work_id}/vote",
        status_code=201,
        tags=["Votes"],
        summary="Vote a work",
        description="Registers a 1..5 vote for a work. Requires authentication; one vote per work and UTC day.",
        response_model=SuccessEnvelope[VoteResponse] | ErrorEnvelope,
        responses={
            201: _shared._VOTE_201,
            401: _shared._UNAUTHORIZED_401,
            403: _shared._FORBIDDEN_403,
            404: _shared._NOT_FOUND_404,
            409: _shared._DUPLICATE_VOTE_409,
            **_shared._standard_errors(422),
        },
    )
    def cast_work_vote(
        work_id: str,
        payload: VoteRequest,
        response: Response,
        authorization: str | None = Header(default=None),
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            ctx.api.require_can_vote(authorization)
            vote = ctx.api.cast_vote(authorization, work_id, payload.vote)
        except UnauthenticatedError:
            return ctx.fail(401, response, "UNAUTHORIZED", "Missing or invalid access token")
        except ForbiddenError:
            return ctx.fail(403, response, "FORBIDDEN", "A verified user role is required to vote")
        except InvalidVoteError:
            return ctx.fail(422, response, "INVALID_VOTE", "Vote must be between 1 and 5")
        except WorkNotFoundError:
            return ctx.fail(404, response, "NOT_FOUND", "Work not found")
        except DuplicateVoteError:
            return ctx.fail(409, response, "DUPLICATE_VOTE", "Already voted for this work today")
        return ctx.ok(
            VoteResponse(
                work_id=vote.work_id,
                vote=vote.vote,
                voted_at=vote.voted_at.isoformat() if vote.voted_at else "",
                vote_day=vote.vote_day or "",
            )
        )

    @router.get(
        "/api/v1/works/{work_id}/statistics",
        tags=["Votes"],
        summary="Work statistics",
        description="Valoración agregada de una obra (proxy de osap-storage).",
        response_model=SuccessEnvelope[WorkStatisticsResponse] | ErrorEnvelope,
        responses={
            200: _shared._WORK_STATS_200,
            404: _shared._NOT_FOUND_404,
            503: _shared._SERVICE_UNAVAILABLE_503,
            **_shared._standard_errors(),
        },
    )
    def work_statistics(work_id: str, response: Response) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            stats = ctx.api.work_statistics(work_id)
        except WorkNotFoundError:
            return ctx.fail(404, response, "NOT_FOUND", "Work not found")
        except StorageUnavailableError:
            return ctx.fail(503, response, "SERVICE_UNAVAILABLE", "Statistics service is not configured")
        return ctx.ok(
            WorkStatisticsResponse(
                work_id=stats.work_id,
                rating=stats.rating,
                adjusted_rating=stats.adjusted_rating,
                vote_count=stats.vote_count,
                work_count=stats.work_count,
                confidence=stats.confidence,
                calculated_at=stats.calculated_at.isoformat() if stats.calculated_at else None,
            )
        )

    @router.get(
        "/api/v1/composers/{composer_id}/statistics",
        tags=["Votes"],
        summary="Composer statistics",
        description="Valoración agregada de un compositor (proxy de osap-storage).",
        response_model=SuccessEnvelope[ComposerStatisticsResponse] | ErrorEnvelope,
        responses={
            200: _shared._COMPOSER_STATS_200,
            404: _shared._NOT_FOUND_404,
            503: _shared._SERVICE_UNAVAILABLE_503,
            **_shared._standard_errors(),
        },
    )
    def composer_statistics(composer_id: str, response: Response) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            stats = ctx.api.composer_statistics(composer_id)
        except WorkNotFoundError:
            return ctx.fail(404, response, "NOT_FOUND", "Composer not found")
        except StorageUnavailableError:
            return ctx.fail(503, response, "SERVICE_UNAVAILABLE", "Statistics service is not configured")
        return ctx.ok(
            ComposerStatisticsResponse(
                composer_id=stats.composer_id,
                rating=stats.rating,
                adjusted_rating=stats.adjusted_rating,
                vote_count=stats.vote_count,
                work_count=stats.work_count,
                confidence=stats.confidence,
                calculated_at=stats.calculated_at.isoformat() if stats.calculated_at else None,
            )
        )

    @router.get(
        "/api/v1/admin/votes",
        tags=["Votes"],
        summary="Votes overview (admin)",
        description="Admin overview: total votes, top works, top composers and last execution.",
        response_model=SuccessEnvelope[VotesOverviewResponse] | ErrorEnvelope,
        responses={
            200: _shared._resp("Votes overview", _shared._example({})),
            401: _shared._UNAUTHORIZED_401,
            403: _shared._FORBIDDEN_403,
        },
    )
    def admin_votes(
        response: Response, authorization: str | None = Header(default=None)
    ) -> SuccessEnvelope[object] | ErrorEnvelope:
        try:
            ctx.api.require_admin(authorization)
        except UnauthenticatedError:
            return ctx.fail(401, response, "UNAUTHORIZED", "Missing or invalid access token")
        except ForbiddenError:
            return ctx.fail(403, response, "FORBIDDEN", "Admin role required")
        try:
            overview = ctx.api.votes_overview()
        except StorageUnavailableError:
            return ctx.fail(503, response, "SERVICE_UNAVAILABLE", "Votes service is not configured")
        top_works = cast("list[dict[str, object]]", overview["top_works"])
        top_composers = cast("list[dict[str, object]]", overview["top_composers"])
        return ctx.ok(
            VotesOverviewResponse(
                total_votes=int(cast("int", overview["total_votes"])),
                top_works=[_shared._work_stats_dto(w) for w in top_works],
                top_composers=[_shared._composer_stats_dto(c) for c in top_composers],
                last_execution=cast("dict[str, object] | None", overview["last_execution"]),
            )
        )


    return router
