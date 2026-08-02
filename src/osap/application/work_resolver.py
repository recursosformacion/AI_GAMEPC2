from src.osap.domain.candidate_representation import CandidateRepresentation
from src.osap.domain.errors import ScoreResolutionError
from src.osap.domain.normalization import normalize_name
from src.osap.domain.resolve_request import ResolveRequest
from src.osap.domain.value_objects import WorkId, WorkIdentifier
from src.osap.domain.work_descriptor import WorkDescriptor
from src.osap.ports.work_resolver import IWorkResolver


class WorkResolver(IWorkResolver):
    """Builds and normalizes the identity (WorkDescriptor) behind a request."""

    def resolve(self, request: ResolveRequest) -> WorkDescriptor:
        title = (request.title or request.query or "").strip()
        if not title:
            raise ScoreResolutionError("Cannot resolve a work without a title or query")
        return WorkDescriptor(
            work_id=WorkId(f"work-{abs(hash(title))}"),
            title=title,
            composer=request.composer.strip() if request.composer else None,
            language=request.language,
            genres=tuple(g for g in [request.genre] if g),
            voices=request.voices,
            instrumentation=request.instrumentation,
        )

    def is_same_work(self, first: WorkDescriptor, second: WorkDescriptor) -> bool:
        first_ids = {(i.kind, i.value) for i in first.identifiers}
        second_ids = {(i.kind, i.value) for i in second.identifiers}
        if first_ids and second_ids and first_ids & second_ids:
            return True
        title_match = normalize_name(first.title) == normalize_name(second.title)
        return title_match and self._composers_match(first.composer, second.composer)

    @staticmethod
    def _composers_match(first: str | None, second: str | None) -> bool:
        if first and second:
            return normalize_name(first) == normalize_name(second)
        return True

    @staticmethod
    def normalize_title(title: str) -> str:
        return normalize_name(title)

    @staticmethod
    def normalize_composer(composer: str) -> str:
        return normalize_name(composer)

    def merge_work(self, candidates: tuple[CandidateRepresentation, ...]) -> WorkDescriptor:
        if not candidates:
            raise ScoreResolutionError("Cannot merge an empty set of candidates")
        base = candidates[0].work_descriptor
        aliases: list[str] = []
        for candidate in candidates:
            full_title = candidate.metadata.get("full_title")
            if isinstance(full_title, str):
                aliases.append(full_title)
        identifiers: dict[str, str] = {}
        for candidate in candidates:
            for identifier in candidate.work_descriptor.identifiers:
                identifiers.setdefault(identifier.kind, identifier.value)
        return WorkDescriptor(
            work_id=base.work_id,
            title=base.title,
            subtitle=base.subtitle,
            composer=base.composer,
            lyricist=base.lyricist,
            arranger=base.arranger,
            language=base.language,
            voices=base.voices,
            opus=base.opus,
            catalogue_number=base.catalogue_number,
            genres=base.genres,
            aliases=tuple(dict.fromkeys(aliases)),
            identifiers=tuple(WorkIdentifier(kind, value) for kind, value in identifiers.items()),
            metadata=base.metadata,
        )
