"""Controlled self-improvement pipeline for L.U.N.A."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from core.improvement.executor import (
    ChangeExecutor,
    ExecutionResult,
)
from core.improvement.inspector import (
    RepositoryInspector,
    RepositorySnapshot,
)
from core.improvement.manager import ImprovementManager
from core.improvement.models import (
    ImprovementPlan,
    PlanStatus,
)
from core.improvement.planner import PlanningEngine
from core.improvement.safety import (
    ImprovementSafetyPolicy,
)


@dataclass
class PipelineResult:
    """Result of a complete improvement pipeline operation."""

    plan: ImprovementPlan
    execution: ExecutionResult | None = None
    tests_passed: bool | None = None
    error: str | None = None


class ImprovementPipeline:
    """
    Coordinates L.U.N.A.'s controlled self-improvement lifecycle.

    Lifecycle:

        inspect
          ↓
        plan
          ↓
        request approval
          ↓
        user approves externally
          ↓
        execute
          ↓
        test
          ↓
        complete / rollback

    The pipeline itself never automatically approves a plan.

    Test execution is supplied by the caller as a safe callback.
    Arbitrary shell commands and repository execution are not supported.
    """

    def __init__(
        self,
        repository_root: str,
        *,
        manager: ImprovementManager | None = None,
        inspector: RepositoryInspector | None = None,
        planner: PlanningEngine | None = None,
        safety_policy: ImprovementSafetyPolicy | None = None,
        executor: ChangeExecutor | None = None,
    ) -> None:
        self.repository_root = repository_root

        self.manager = (
            manager
            or ImprovementManager()
        )

        self.inspector = (
            inspector
            or RepositoryInspector(
                repository_root
            )
        )

        self.planner = (
            planner
            or PlanningEngine(
                repository_root,
                inspector=self.inspector,
                manager=self.manager,
            )
        )

        self.safety_policy = (
            safety_policy
            or ImprovementSafetyPolicy(
                repository_root
            )
        )

        self.executor = (
            executor
            or ChangeExecutor(
                repository_root,
                manager=self.manager,
                safety_policy=self.safety_policy,
            )
        )

    def inspect(
        self,
    ) -> RepositorySnapshot:
        """Inspect the repository without modifying anything."""

        return self.inspector.inspect()

    def create_plan(
        self,
        *,
        title: str,
        objective: str,
        summary: str = "",
        reasoning: str = "",
        changes=None,
        tests=None,
        risks=None,
        rollback_strategy: str = "",
    ) -> ImprovementPlan:
        """Create a draft improvement plan."""

        return self.planner.create_plan(
            title=title,
            objective=objective,
            summary=summary,
            reasoning=reasoning,
            changes=changes,
            tests=tests,
            risks=risks,
            rollback_strategy=rollback_strategy,
        )

    def request_approval(
        self,
        plan_id: str,
    ) -> ImprovementPlan:
        """Move a draft plan into the approval state."""

        return self.manager.request_approval(
            plan_id
        )

    def approve(
        self,
        plan_id: str,
    ) -> ImprovementPlan:
        """
        Approve a plan.

        Approval is intentionally explicit and separate from execution.
        """

        return self.manager.approve(
            plan_id
        )

    def reject(
        self,
        plan_id: str,
    ) -> ImprovementPlan:
        """Reject a draft or awaiting-approval plan."""

        return self.manager.reject(
            plan_id
        )

    def execute(
        self,
        plan_id: str,
        *,
        file_contents: dict[str, str],
    ) -> ExecutionResult:
        """
        Execute an approved plan.

        The plan must already be APPROVED.
        """

        return self.executor.execute(
            plan_id,
            file_contents=file_contents,
        )

    def test(
        self,
        plan_id: str,
        test_callback: Callable[
            [ImprovementPlan],
            bool,
        ],
    ) -> PipelineResult:
        """
        Run a caller-supplied safe test callback.

        The callback must return True for success and False for failure.

        The pipeline does not execute arbitrary commands itself.
        """

        plan = self.manager.require_plan(
            plan_id
        )

        if plan.status != PlanStatus.TESTING:
            raise ValueError(
                "Only plans in the testing state "
                "can be tested."
            )

        try:
            passed = bool(
                test_callback(plan)
            )

        except Exception as exc:
            passed = False
            error = str(exc)

        else:
            error = None

        if passed:
            plan.set_status(
                PlanStatus.COMPLETED
            )
            self.manager.save(plan)

            return PipelineResult(
                plan=plan,
                tests_passed=True,
            )

        plan.set_status(
            PlanStatus.FAILED
        )
        self.manager.save(plan)

        return PipelineResult(
            plan=plan,
            tests_passed=False,
            error=error or "Improvement tests failed.",
        )

    def inspect_and_create_plan(
        self,
        *,
        title: str,
        objective: str,
        summary: str,
        reasoning: str,
        changes=None,
        tests=None,
        risks=None,
        rollback_strategy: str = "",
    ) -> tuple[
        RepositorySnapshot,
        ImprovementPlan,
    ]:
        """
        Perform a read-only inspection followed by draft-plan creation.

        No approval or execution occurs.
        """

        snapshot = self.inspect()

        plan = self.create_plan(
            title=title,
            objective=objective,
            summary=summary,
            reasoning=reasoning,
            changes=changes,
            tests=tests,
            risks=risks,
            rollback_strategy=rollback_strategy,
        )

        plan.metadata[
            "inspected_python_files"
        ] = len(
            snapshot.python_files
        )

        plan.metadata[
            "inspected_modules"
        ] = len(
            snapshot.modules
        )

        plan.metadata[
            "inspected_directories"
        ] = len(
            snapshot.directories
        )

        self.manager.save(
            plan
        )

        return snapshot, plan

    def get_plan(
        self,
        plan_id: str,
    ) -> ImprovementPlan:
        """Retrieve a persisted improvement plan."""

        return self.manager.require_plan(
            plan_id
        )