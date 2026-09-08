"""Controlled self-improvement and planning infrastructure for L.U.N.A."""

from core.improvement.inspector import (
    ModuleInfo,
    RepositoryInspector,
    RepositorySnapshot,
)
from core.improvement.manager import ImprovementManager
from core.improvement.models import (
    ImprovementPlan,
    PlanChange,
    PlanStatus,
)
from core.improvement.planner import PlanningEngine
from core.improvement.safety import (
    ImprovementSafetyError,
    ImprovementSafetyPolicy,
)
from core.improvement.executor import (
    ChangeExecutor,
    ExecutionResult,
    FileBackup,
)
from core.improvement.pipeline import (
    ImprovementPipeline,
    PipelineResult,
)

__all__ = [
    "ImprovementManager",
    "ImprovementPlan",
    "PlanChange",
    "PlanStatus",
    "ModuleInfo",
    "RepositoryInspector",
    "RepositorySnapshot",
    "PlanningEngine",
    "ImprovementSafetyError",
    "ImprovementSafetyPolicy",
    "ChangeExecutor",
    "ExecutionResult",
    "FileBackup",
    "ImprovementPipeline",
    "PipelineResult",
]