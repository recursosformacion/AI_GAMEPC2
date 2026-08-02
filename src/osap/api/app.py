from __future__ import annotations

import asyncio
import contextlib
import json
import queue
from typing import TYPE_CHECKING, Any, cast

from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.responses import StreamingResponse

from src.osap.api.dto import (
    JobDTO,
    RepresentationDTO,
    WorkDTO,
)
from src.osap.api.dto import (
    ResolveRequest as HttpResolveRequest,
)
from src.osap.application.canonical_metadata import MetadataEnricher
from src.osap.bootstrap.container import Container
from src.osap.bootstrap.wiring import wire
from src.osap.domain.job import Job, JobSubmission
from src.osap.domain.output_format import OutputFormat
from src.osap.domain.resolve_request import ResolveRequest, ResolveRequestBuilder
from src.osap.domain.value_objects import JobId

if TYPE_CHECKING:
    from src.osap.application.work_merge_service import WorkGroup


def create_app(container: Container | None = None) -> FastAPI:
    """Build the OSAP REST API as an HTTP adapter over application services."""
    container = container or wire(Container())
    enricher = MetadataEnricher()
    app = FastAPI(title="OSAP", version="1.0.0")

    _register_resolve_job(container)

    @app.get("/api/v1/health")
    def health() -> dict[str, object]:
        engine = container.work_resolution_engine()
        reports = {r.provider_id.value: r.outcome for r in engine.provider_status(ResolveRequest())}
        return {"status": "ok", "providers": reports}

    @app.get("/api/v1/providers")
    def providers() -> list[dict[str, object]]:
        from src.osap.application.capabilities_dto import CapabilitiesDto

        manager = container.catalog_manager()
        result: list[dict[str, object]] = []
        for c in manager.providers():
            caps = c.capabilities()
            availability = str(caps.metadata.get("availability") or "")
            available = availability != "index_missing"
            result.append(CapabilitiesDto.build(c.provider_id.value, caps, available=available, authenticated=False))
        return result

    @app.get("/api/v1/search")
    def search(query: str | None = None, composer: str | None = None) -> dict[str, object]:
        request = ResolveRequestBuilder()
        if query:
            request = request.text(query)
        if composer:
            request = request.composer(composer)
        domain_request = request.build()
        engine = container.work_resolution_engine()
        ranked = engine.rank(domain_request)
        groups = container.work_merge_service().group(ranked)
        works = [_work_dto(g, enricher) for g in groups]
        return {
            "results": len(ranked),
            "works": len(works),
            "representations": sum(w.representation_count for w in works),
            "providers": sorted({c.provider_id.value for c in ranked}),
            "items": works,
        }

    @app.get("/api/v1/works/{work_id}")
    def work_detail(work_id: str) -> dict[str, object]:
        request = ResolveRequest()
        engine = container.work_resolution_engine()
        groups = container.work_merge_service().group(engine.rank(request))
        for group in groups:
            if group.key == work_id:
                return _preview_dto(group, enricher)
        raise HTTPException(status_code=404, detail="Work not found")

    @app.post("/api/v1/preview")
    def preview(req: HttpResolveRequest) -> dict[str, object]:
        request = _to_request(req)
        engine = container.work_resolution_engine()
        groups = container.work_merge_service().group(engine.rank(request))
        if not groups:
            raise HTTPException(status_code=404, detail="No works found")
        return _preview_dto(groups[0], enricher)

    @app.post("/api/v1/resolve")
    def resolve(req: HttpResolveRequest) -> JobDTO:
        request = _to_request(req)
        job = container.job_engine().submit(
            JobSubmission(
                job_id=JobId(f"job-{abs(hash((request.title, request.composer)))}"),
                type="resolve",
                params={"request": request},
            )
        )
        return JobDTO(job_id=job.job_id.value, type=job.type, state=job.state.value, progress=job.progress)

    @app.get("/api/v1/jobs")
    def jobs() -> list[dict[str, object]]:
        return [_job_dict(j) for j in container.job_engine().jobs()]

    @app.get("/api/v1/jobs/{job_id}")
    def job_detail(job_id: str) -> JobDTO:
        job = container.job_engine().get(JobId(job_id))
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        return JobDTO(
            job_id=job.job_id.value,
            type=job.type,
            state=job.state.value,
            progress=job.progress,
            result=job.result.payload if job.result else {},
        )

    @app.get("/api/v1/events")
    async def events() -> StreamingResponse:
        event_queue: queue.Queue[dict[str, object]] = queue.Queue()
        bus = container.event_bus()

        def on_event(event: object) -> None:
            with contextlib.suppress(Exception):  # noqa: BLE001
                event_queue.put(_event_dict(event))

        bus.subscribe("*", on_event)

        async def stream() -> Any:
            try:
                while True:
                    try:
                        payload = event_queue.get_nowait()
                    except queue.Empty:
                        await asyncio.sleep(0.2)
                        continue
                    yield f"data: {json.dumps(payload)}\n\n"
            finally:
                pass

        return StreamingResponse(stream(), media_type="text/event-stream")

    @app.get("/api/v1/library")
    def library() -> list[dict[str, object]]:
        manager = container.library_manager()
        libraries = manager.available_libraries()
        result: list[dict[str, object]] = []
        for lib_id in libraries:
            result.append({"library_id": lib_id.value, "scores": list(manager.list(lib_id))})
        return result

    @app.get("/api/v1/datasets")
    def datasets() -> list[dict[str, object]]:
        return [
            {
                "dataset_id": d.dataset_id.value,
                "name": d.name,
                "status": d.status.value,
                "expected_size_bytes": d.expected_size_bytes,
                "license": d.license,
            }
            for d in container.dataset_manager().list()
        ]

    @app.get("/api/v1/settings")
    def settings() -> dict[str, object]:
        from src.osap.bootstrap.configuration import Configuration

        config = Configuration()
        return {
            "library_root": config.library_root,
            "default_output_format": config.default_output_format,
            "connectivity_available": config.connectivity_available,
            "imslp_verify_ssl": config.imslp_verify_ssl,
        }

    @app.get("/api/v1/users")
    def users() -> list[dict[str, object]]:
        return []

    @app.get("/api/v1/users/{user_id}")
    def user_detail(user_id: str) -> dict[str, object] | None:
        profile = container.user_profile_store().get(user_id)
        if profile is None:
            raise HTTPException(status_code=404, detail="User not found")
        return {
            "user_id": profile.user_id,
            "language": profile.language,
            "preferred_formats": [f.value for f in profile.preferred_formats],
        }

    @app.websocket("/api/v1/events/ws")
    async def events_ws(websocket: WebSocket) -> None:
        await websocket.accept()
        event_queue: queue.Queue[dict[str, object]] = queue.Queue()
        bus = container.event_bus()

        def on_event(event: object) -> None:
            with contextlib.suppress(Exception):  # noqa: BLE001
                event_queue.put(_event_dict(event))

        bus.subscribe("*", on_event)
        try:
            while True:
                await asyncio.sleep(0.2)
                while True:
                    try:
                        payload = event_queue.get_nowait()
                    except queue.Empty:
                        break
                    await websocket.send_json(payload)
        except Exception:  # noqa: BLE001
            pass

    return app


def _to_request(req: HttpResolveRequest) -> ResolveRequest:
    builder = ResolveRequestBuilder()
    if req.query:
        builder = builder.text(req.query)
    if req.composer:
        builder = builder.composer(req.composer)
    if getattr(req, "voices", None):
        builder = builder.voices(*req.voices)
    if req.format:
        with contextlib.suppress(ValueError):
            builder = builder.format(OutputFormat(req.format))
    return builder.build()


def _register_resolve_job(container: Container) -> None:
    def handler(submission: JobSubmission) -> None:
        request = cast("ResolveRequest | None", submission.params.get("request"))
        if request is not None:
            container.work_resolution_engine().resolve(request, download=True)

    container.job_engine().register("resolve", handler)


def _job_dict(job: Job) -> dict[str, object]:
    return {
        "job_id": job.job_id.value,
        "type": job.type,
        "state": job.state.value,
        "progress": job.progress,
    }


def _work_dto(group: WorkGroup, enricher: MetadataEnricher) -> WorkDTO:
    cw = enricher.enrich(group)
    return WorkDTO(
        id=cw.work_id,
        title=cw.title,
        display_title=cw.display_title,
        canonical_title=cw.canonical_title,
        canonical_key=cw.canonical_key,
        composer=cw.composer.display_name if cw.composer else None,
        catalog=cw.catalog,
        genre=cw.genre,
        voices=cw.voices,
        duration=cw.duration,
        public_domain=cw.public_domain,
        representation_count=len(cw.representations),
        providers=tuple(sorted({r.provider for r in cw.representations})),
    )


def _preview_dto(group: WorkGroup, enricher: MetadataEnricher) -> dict[str, object]:
    cw = enricher.enrich(group)
    return {
        "work": cw.title,
        "composer": cw.composer.display_name if cw.composer else None,
        "catalog": cw.catalog,
        "representations": [
            RepresentationDTO(provider=r.provider, format=r.format, quality=r.quality, downloadable=r.downloadable)
            for r in cw.representations
        ],
    }


def _event_dict(event: object) -> dict[str, object]:
    from src.osap.domain.event import Event

    if not isinstance(event, Event):
        return {"event_type": str(event)}
    return {
        "event_type": event.event_type,
        "aggregate_id": event.aggregate_id,
        "timestamp": event.timestamp.isoformat(),
        "payload": event.payload,
    }
