"""Plan lifecycle management for L.U.N.A.'s self-improvement system."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from core.improvement.models import (
    ImprovementPlan,
    PlanStatus,
)


class ImprovementManager:
    """
    Owns improvement-plan persistence and approval state.

    Important:
        This manager cannot modify source code.

    Execution will be handled by a separate component later,
    behind explicit approval and safety checks.
    """

    def __init__(
        self,
        plans_directory: str | Path = "data/improvement/plans",
    ) -> None:
        self.plans_directory = Path(
            plans_directory
        )

        self.plans_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

    def _plan_path(
        self,
        plan_id: str,
    ) -> Path:
        return self.plans_directory / (
            f"{plan_id}.json"
        )

    def create_plan(
        self,
        *,
        title: str,
        objective: str,
    ) -> ImprovementPlan:
        title = (title or "").strip()
        objective = (objective or "").strip()

        if not title:
            raise ValueError(
                "Improvement plan title cannot be empty."
            )

        if not objective:
            raise ValueError(
                "Improvement plan objective cannot be empty."
            )

        plan = ImprovementPlan(
            id=uuid.uuid4().hex[:12],
            title=title,
            objective=objective,
        )

        self.save(plan)

        return plan

    def save(
        self,
        plan: ImprovementPlan,
    ) -> None:
        plan.touch()

        path = self._plan_path(plan.id)

        temporary_path = path.with_suffix(
            ".json.tmp"
        )

        temporary_path.write_text(
            json.dumps(
                plan.to_dict(),
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        temporary_path.replace(path)

    def load(
        self,
        plan_id: str,
    ) -> ImprovementPlan | None:
        path = self._plan_path(plan_id)

        if not path.exists():
            return None

        data = json.loads(
            path.read_text(
                encoding="utf-8",
            )
        )

        return ImprovementPlan.from_dict(
            data
        )

    def list_plans(
        self,
    ) -> list[ImprovementPlan]:
        plans: list[ImprovementPlan] = []

        for path in sorted(
            self.plans_directory.glob(
                "*.json"
            )
        ):
            try:
                data = json.loads(
                    path.read_text(
                        encoding="utf-8",
                    )
                )

                plans.append(
                    ImprovementPlan.from_dict(
                        data
                    )
                )

            except Exception as exc:
                print(
                    "[L.U.N.A.] "
                    f"Skipping invalid improvement plan "
                    f"{path.name}: {exc}",
                    flush=True,
                )

        return plans

    def request_approval(
        self,
        plan_id: str,
    ) -> ImprovementPlan:
        plan = self.require_plan(
            plan_id
        )

        if plan.status != PlanStatus.DRAFT:
            raise ValueError(
                "Only draft plans can request approval."
            )

        plan.set_status(
            PlanStatus.AWAITING_APPROVAL
        )

        self.save(plan)

        return plan

    def approve(
        self,
        plan_id: str,
    ) -> ImprovementPlan:
        plan = self.require_plan(
            plan_id
        )

        if (
            plan.status
            != PlanStatus.AWAITING_APPROVAL
        ):
            raise ValueError(
                "Only plans awaiting approval "
                "can be approved."
            )

        plan.set_status(
            PlanStatus.APPROVED
        )

        self.save(plan)

        return plan

    def reject(
        self,
        plan_id: str,
    ) -> ImprovementPlan:
        plan = self.require_plan(
            plan_id
        )

        if plan.status not in {
            PlanStatus.DRAFT,
            PlanStatus.AWAITING_APPROVAL,
        }:
            raise ValueError(
                "This plan can no longer be rejected."
            )

        plan.set_status(
            PlanStatus.REJECTED
        )

        self.save(plan)

        return plan

    def require_plan(
        self,
        plan_id: str,
    ) -> ImprovementPlan:
        plan = self.load(
            plan_id
        )

        if plan is None:
            raise ValueError(
                f"Improvement plan '{plan_id}' "
                "does not exist."
            )

        return plan