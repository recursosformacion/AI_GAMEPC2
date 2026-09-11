"""PlatformApi: mixin de compositores (F5.4)."""

from typing import cast

from src.osap.api.contracts import (
    CatalogueRead,
)
from src.osap.api.platform import _support as _support
from src.osap.api.platform.core import PlatformApiCore
from src.osap.application.composer_resolution_engine import ResolutionDecision
from src.osap.application.composers_service import ComposersService
from src.osap.application.use_cases.resolve_works import ResolvedWorkItem, WorkResolveInput
from src.osap.ports.composer_resolver import ResolverRepresentation

VERSION = "3.1"











class ComposersMixin(PlatformApiCore):
    def composers(self) -> ComposersService:
        return self._container.composers_service()

    def list_composers(
        self, q: str | None, limit: int, offset: int, review: str | None = None
    ) -> dict[str, object]:
        return self.composers().list_composers(q, limit, offset, review)

    def get_composer(self, composer_id: str) -> dict[str, object] | None:
        return self.composers().get_composer(composer_id)

    def get_composer_biography(self, composer_id: str) -> dict[str, object] | None:
        return self.composers().get_composer_biography(composer_id)

    def composer_works(self, composer_id: str, limit: int, offset: int) -> dict[str, object]:
        return self.composers().composer_works(composer_id, limit, offset)

    def get_work(self, work_id: str) -> dict[str, object] | None:
        return self.composers().get_work(work_id)

    def merge_composers(self, token: str | None, target_id: str, source_ids: list[str]) -> dict[str, object]:
        return self.composers().merge_composers(token, target_id, source_ids)

    def create_composer(self, token: str | None, name: str) -> dict[str, object]:
        return self.composers().create_composer(token, name)

    def review_composer(self, token: str | None, composer_id: str, review_status: str) -> dict[str, object]:
        return self.composers().review_composer(token, composer_id, review_status)

    def add_alias(self, token: str | None, composer_id: str, alias: str) -> dict[str, object]:
        return self.composers().add_alias(token, composer_id, alias)

    def list_aliases(self, token: str | None, composer_id: str) -> list[dict[str, object]]:
        return self.composers().list_aliases(token, composer_id)

    def move_alias(
        self, token: str | None, alias_id: int, from_composer_id: str, target_composer_id: str
    ) -> dict[str, object]:
        return self.composers().move_alias(token, alias_id, from_composer_id, target_composer_id)

    def promote_alias(self, token: str | None, composer_id: str, alias_id: int) -> dict[str, object]:
        return self.composers().promote_alias(token, composer_id, alias_id)

    def set_attribution(self, token: str | None, composer_ids: list[str], attribution_type: str) -> dict[str, object]:
        return self.composers().set_attribution(token, composer_ids, attribution_type)

    async def resolve_composer(
        self,
        work_title: str,
        composer: str | None = None,
        work_catalog: str | None = None,
        work_year: int | None = None,
        source_provider: str | None = None,
        source_work_id: str | None = None,
        representations: list[dict[str, str]] | None = None,
    ) -> ResolutionDecision:
        reps = [
            ResolverRepresentation(title=r["title"], provider=r["provider"], format=r["format"])
            for r in representations or []
        ]
        use_case = self._container.composer_resolution()
        return await use_case.execute(
            composer=composer,
            work_title=work_title,
            work_catalog=work_catalog,
            work_year=work_year,
            source_provider=source_provider,
            source_work_id=source_work_id,
            representations=reps,
        )

    async def works_resolve(
        self,
        works: list[dict[str, object]],
        concurrency: int = 4,
    ) -> list[ResolvedWorkItem]:
        inputs: list[WorkResolveInput] = []
        for w in works:
            work = cast("dict[str, object]", w.get("work") or {})
            composer = cast("dict[str, object]", w.get("composer") or {})
            source = cast("dict[str, object]", w.get("source") or {})
            inputs.append(
                WorkResolveInput(
                    id=str(w["id"]) if w.get("id") is not None else None,
                    composer=cast("str | None", composer.get("name")) if composer else None,
                    work_title=cast("str | None", work.get("title")),
                    work_catalog=cast("str | None", work.get("catalog")),
                    work_year=cast("int | None", work.get("year")),
                    source_provider=cast("str | None", source.get("provider")) if source else None,
                    source_work_id=cast("str | None", source.get("source_work_id")) if source else None,
                )
            )
        return await self._container.works_resolution().execute(inputs, concurrency)

    # --- resolution sessions (ADR-0033) ---------------------------------------

    def composer_review_stats(self, token: str | None) -> dict[str, int]:
        stats = self.composers().composer_review_stats(token)
        # Estados reales: `reviewed`/`not_reviewed`/`review_required` (puestos por el
        # proceso de biografías) + `correct`/`incorrect` (clasificación manual/IA antigua).
        reviewed = int(stats.get("reviewed") or 0) + int(stats.get("correct") or 0) + int(stats.get("incorrect") or 0)
        not_reviewed = int(stats.get("not_reviewed") or 0)
        review_required = int(stats.get("review_required") or 0)
        total = reviewed + not_reviewed + review_required
        return {
            "total": total,
            "correct": int(stats.get("correct") or 0),
            "incorrect": int(stats.get("incorrect") or 0),
            "reviewed": reviewed,
            "not_reviewed": not_reviewed + review_required,
        }

    def catalogues(self, prefix: str | None = None, composer: str | None = None) -> list[CatalogueRead]:
        rows = self.composers().catalogues(prefix, composer)
        out: list[CatalogueRead] = []
        for row in rows:
            out.append(
                CatalogueRead(
                    id=int(str(row.get("id") or 0)),
                    prefix=str(row.get("prefix") or ""),
                    composer=str(row.get("composer") or ""),
                    catalogue_name=str(row.get("catalogue_name") or ""),
                    creator=str(row.get("creator") or ""),
                    ordering_criterion=str(row.get("ordering_criterion") or ""),
                )
            )
        return out

