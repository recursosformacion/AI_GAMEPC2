import time

import pytest

from src.osap.domain.arrangement import Arrangement
from src.osap.domain.candidate_representation import CandidateRepresentation
from src.osap.domain.edition import Edition
from src.osap.domain.event import Event
from src.osap.domain.job import Job, JobState, JobSubmission
from src.osap.domain.metrics import MetricRecord
from src.osap.domain.output_format import OutputFormat
from src.osap.domain.pipeline_context import PipelineContext
from src.osap.domain.quality_level import QualityLevel
from src.osap.domain.quality_report import QualityDimension, QualityReport
from src.osap.domain.user_profile import UserProfile
from src.osap.domain.value_objects import (
    ArrangementId,
    CandidateId,
    EditionId,
    JobId,
    ProviderId,
    WorkId,
)
from src.osap.domain.work_descriptor import WorkDescriptor
from src.osap.infrastructure.cache import InMemoryCache
from src.osap.infrastructure.dedup import DuplicateResolver
from src.osap.infrastructure.events import InMemoryEventBus
from src.osap.infrastructure.jobs import InMemoryJobEngine
from src.osap.infrastructure.metrics import InMemoryMetricsCollector
from src.osap.infrastructure.user_profile import InMemoryUserProfileStore


def _work(title: str = "Ave Maria", composer: str = "Franz Schubert") -> WorkDescriptor:
    return WorkDescriptor(work_id=WorkId("w1"), title=title, composer=composer)


class TestIdentityHierarchy:
    def test_work_edition_arrangement(self) -> None:
        work = _work()
        edition = Edition(edition_id=EditionId("e1"), work=work, publisher="Carus", year=2001)
        arrangement = Arrangement(arrangement_id=ArrangementId("a1"), edition=edition, voices=("S", "A", "T", "B"))
        assert arrangement.edition.work == work
        assert arrangement.voices == ("S", "A", "T", "B")


class TestQualityReport:
    def test_dimensions_and_level(self) -> None:
        report = QualityReport(
            dimensions={
                QualityDimension.STRUCTURE: 0.9,
                QualityDimension.NOTATION: 0.8,
                QualityDimension.LYRICS: 0.7,
            }
        )
        assert report.score(QualityDimension.STRUCTURE) == 0.9
        assert report.overall() == pytest.approx(0.8)
        assert report.quality_level() == QualityLevel.FULL_NOTATION

    def test_human_validated(self) -> None:
        report = QualityReport(dimensions={QualityDimension.NOTATION: 1.0, QualityDimension.STRUCTURE: 0.95})
        assert report.quality_level() == QualityLevel.HUMAN_VALIDATED

    def test_invalid_score_raises(self) -> None:
        with pytest.raises(ValueError):
            QualityReport(dimensions={QualityDimension.NOTATION: 1.5})


class TestJob:
    def test_state_machine_and_progress(self) -> None:
        job = Job(job_id=JobId("j1"), type="download", state=JobState.RUNNING, progress=50)
        assert job.state == JobState.RUNNING
        with pytest.raises(ValueError):
            Job(job_id=JobId("j2"), type="x", progress=101)


class TestEventBus:
    def test_publish_and_subscribe(self) -> None:
        bus = InMemoryEventBus()
        received: list[str] = []
        bus.subscribe("ScoreValidated", lambda e: received.append(e.event_type))
        bus.publish(Event(event_type="ScoreValidated"))
        bus.publish(Event(event_type="LibraryStored"))
        assert received == ["ScoreValidated"]
        assert len(bus.published) == 2


class TestMetrics:
    def test_record_and_snapshot(self) -> None:
        collector = InMemoryMetricsCollector()
        collector.record("resolution_time", 1.2, {"provider": "openscore"})
        snapshot = collector.snapshot()
        assert isinstance(snapshot[0], MetricRecord)
        assert snapshot[0].name == "resolution_time"
        assert snapshot[0].tags == {"provider": "openscore"}


class TestCache:
    def test_ttl_and_version(self) -> None:
        cache = InMemoryCache(version="v1")
        cache.set("key", {"data": 1}, ttl_seconds=1)
        assert cache.get("key") == {"data": 1}
        time.sleep(1.1)
        assert cache.get("key") is None

    def test_version_isolation(self) -> None:
        a = InMemoryCache(version="v1")
        b = InMemoryCache(version="v2")
        a.set("k", "x")
        assert b.get("k") is None

    def test_invalidate(self) -> None:
        cache = InMemoryCache()
        cache.set("k", "x")
        cache.invalidate("k")
        assert cache.get("k") is None


class TestUserProfileStore:
    def test_save_and_get(self) -> None:
        store = InMemoryUserProfileStore()
        profile = UserProfile(
            user_id="u1",
            language="ca",
            preferred_formats=(OutputFormat.MUSICXML,),
            min_quality=QualityLevel.FULL_NOTATION,
        )
        store.save(profile)
        assert store.get("u1") == profile
        assert store.get("missing") is None


class TestDuplicateResolver:
    def test_same_work_by_title_composer(self) -> None:
        resolver = DuplicateResolver()
        first = CandidateRepresentation(
            candidate_id=CandidateId("c1"),
            work_descriptor=_work("Ave Maria", "Franz Schubert"),
            provider_id=ProviderId("a"),
            format=OutputFormat.PDF,
        )
        second = CandidateRepresentation(
            candidate_id=CandidateId("c2"),
            work_descriptor=_work("Ave Maria", "F. Schubert"),
            provider_id=ProviderId("b"),
            format=OutputFormat.PDF,
        )
        assert resolver.is_duplicate(first, second) is True

    def test_different_work(self) -> None:
        resolver = DuplicateResolver()
        first = CandidateRepresentation(
            candidate_id=CandidateId("c1"),
            work_descriptor=_work("Ave Maria", "Franz Schubert"),
            provider_id=ProviderId("a"),
            format=OutputFormat.PDF,
        )
        other = CandidateRepresentation(
            candidate_id=CandidateId("c2"),
            work_descriptor=_work("Nocturne", "Franz Schubert"),
            provider_id=ProviderId("b"),
            format=OutputFormat.PDF,
        )
        assert resolver.is_duplicate(first, other) is False


def _await_terminal(engine: InMemoryJobEngine, job_id: JobId, timeout: float = 2.0) -> Job:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job = engine.get(job_id)
        if job and job.state in (JobState.COMPLETED, JobState.FAILED, JobState.CANCELLED):
            return job
        time.sleep(0.02)
    raise AssertionError("job did not reach a terminal state")


class TestJobEngine:
    def test_job_runs_and_completes(self) -> None:
        bus = InMemoryEventBus()
        engine = InMemoryJobEngine(bus)
        engine.register("download", lambda job: None)
        job = engine.submit(JobSubmission(job_id=JobId("j1"), type="download"))
        settled = _await_terminal(engine, job.job_id)
        assert settled.state == JobState.COMPLETED
        assert any(e.event_type == "JobCompleted" for e in bus.published)

    def test_unknown_handler_fails(self) -> None:
        bus = InMemoryEventBus()
        engine = InMemoryJobEngine(bus)
        job = engine.submit(JobSubmission(job_id=JobId("j2"), type="nope"))
        settled = _await_terminal(engine, job.job_id)
        assert settled.state == JobState.FAILED
