from src.osap.application.work_resolution_engine import WorkResolutionEngine
from src.osap.domain.resolve_request import ResolveRequest
from src.osap.domain.resolve_result import ResolveResult


class ResolveWorkUseCase:
    def __init__(self, engine: WorkResolutionEngine) -> None:
        self.engine = engine

    def execute(self, request: ResolveRequest, download: bool = False) -> ResolveResult:
        return self.engine.resolve(request, download=download)
