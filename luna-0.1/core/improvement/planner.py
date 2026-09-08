"""Planning engine for L.U.N.A.'s controlled self-improvement system."""

from __future__ import annotations

from core.improvement.inspector import (
    RepositoryInspector,
    RepositorySnapshot,
)
from core.improvement.manager import ImprovementManager
from core.improvement.models import (
    ImprovementPlan,
    PlanChange,
)


class PlanningEngine:
    """
    Converts repository observations into structured improvement plans.

    This component is intentionally non-destructive.

    It may:
    - inspect repository structure
    - identify architectural areas
    - create improvement plans
    - persist plans

    It may not:
    - modify source code
    - execute repository code
    - install packages
    - run shell commands
    - access secrets
    - approve its own plans
    - execute plans
    """

    def __init__(
        self,
        repository_root: str,
        *,
        inspector: RepositoryInspector | None = None,
        manager: ImprovementManager | None = None,
    ) -> None:
        self.repository_root = repository_root

        self.inspector = inspector or RepositoryInspector(
            repository_root
        )

        self.manager = manager or ImprovementManager()

    def inspect_repository(
        self,
    ) -> RepositorySnapshot:
        """Return the current read-only repository snapshot."""

        return self.inspector.inspect()

    def create_plan(
        self,
        *,
        title: str,
        objective: str,
        summary: str = "",
        reasoning: str = "",
        changes: list[PlanChange] | None = None,
        tests: list[str] | None = None,
        risks: list[str] | None = None,
        rollback_strategy: str = "",
    ) -> ImprovementPlan:
        """
        Create and persist a new improvement plan.

        Creating a plan does not approve or execute it.
        """

        plan = self.manager.create_plan(
            title=title,
            objective=objective,
        )

        plan.summary = (
            summary.strip()
            if summary
            else ""
        )

        plan.reasoning = (
            reasoning.strip()
            if reasoning
            else ""
        )

        plan.changes = list(
            changes or []
        )

        plan.tests = list(
            tests or []
        )

        plan.risks = list(
            risks or []
        )

        plan.rollback_strategy = (
            rollback_strategy.strip()
            if rollback_strategy
            else ""
        )

        self.manager.save(plan)

        return plan

    def plan_architecture_improvement(
        self,
        *,
        title: str,
        objective: str,
        target_paths: list[str],
        summary: str,
        reasoning: str,
        tests: list[str],
        risks: list[str],
        rollback_strategy: str,
        change_action: str = "modify",
        change_reason: str = "Architectural improvement identified by planning analysis.",
        change_risk: str = "medium",
        requires_restart: bool = True,
    ) -> ImprovementPlan:
        """
        Create an architecture-focused improvement plan.

        This helper intentionally requires the proposed paths to be
        supplied explicitly. It does not invent file modifications.
        """

        changes = [
            PlanChange(
                path=path,
                action=change_action,
                summary=summary,
                reason=change_reason,
                risk=change_risk,
                requires_restart=requires_restart,
            )
            for path in target_paths
        ]

        return self.create_plan(
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
        """
        Move a draft plan into the approval state.

        Approval itself is still handled separately by
        ImprovementManager.approve().
        """

        return self.manager.request_approval(
            plan_id
        )

    def summarize_repository(
        self,
    ) -> str:
        """Return a human-readable repository summary."""

        snapshot = self.inspect_repository()

        return self.inspector.summarize(
            snapshot
        )

    def find_module(
        self,
        snapshot: RepositorySnapshot,
        path_fragment: str,
    ) -> list:
        """
        Find modules whose paths contain the supplied fragment.

        This is read-only and useful for future planning logic.
        """

        fragment = (
            path_fragment or ""
        ).strip().lower()

        if not fragment:
            return []

        return [
            module
            for module in snapshot.modules
            if fragment in module.path.lower()
        ]

    def find_modules_importing(
        self,
        snapshot: RepositorySnapshot,
        import_fragment: str,
    ) -> list:
        """
        Find modules that import a matching module/path.

        Matching is intentionally simple in v0.1.
        """

        fragment = (
            import_fragment or ""
        ).strip().lower()

        if not fragment:
            return []

        return [
            module
            for module in snapshot.modules
            if any(
                fragment in imported.lower()
                for imported in module.imports
            )
        ]