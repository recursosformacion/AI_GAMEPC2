from src.osap.domain.candidate_representation import CandidateRepresentation
from src.osap.domain.music_query_normalizer import MusicQueryNormalizer
from src.osap.domain.work_descriptor import WorkDescriptor
from src.osap.ports.duplicate_resolver import IDuplicateResolver


class DuplicateResolver(IDuplicateResolver):
    """Determines if two candidates are the same work using content-based
    signals only (never the provider): normalized title, composer, duration,
    instrumentation and checksums."""

    def is_duplicate(self, first: CandidateRepresentation, second: CandidateRepresentation) -> bool:
        if first.checksum and second.checksum and first.checksum == second.checksum:
            return True
        if not MusicQueryNormalizer.matches(first.work_descriptor.title, second.work_descriptor.title):
            return False
        return self._composers_agree(first.work_descriptor, second.work_descriptor)

    def canonical(self, candidate: CandidateRepresentation) -> WorkDescriptor:
        work = candidate.work_descriptor
        return WorkDescriptor(
            work_id=work.work_id,
            title=work.title,
            composer=work.composer,
            language=work.language,
            voices=work.voices,
            identifiers=work.identifiers,
        )

    @staticmethod
    def _composers_agree(first: WorkDescriptor, second: WorkDescriptor) -> bool:
        if first.composer and second.composer:
            return MusicQueryNormalizer.matches(first.composer, second.composer)
        return True
