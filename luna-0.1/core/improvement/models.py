"""Data models for L.U.N.A.'s controlled self-improvement system."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class PlanStatus(str, Enum):
    """Lifecycle states for an improvement plan."""

    DRAFT = "draft"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTING = "executing"
    TESTING = "testing"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class PlanChange:
    """
    One proposed change inside an improvement plan.

    This object describes a change only.
    It does not modify any files.
    """

    path: str
    action: str
    summary: str
    reason: str
    risk: str = "low"
    requires_restart: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
    ) -> "PlanChange":
        return cls(**data)


@dataclass
class ImprovementPlan:
    """
    A structured proposal for improving L.U.N.A.

    Plans are intentionally separated from execution.
    Creating or approving a plan does not itself modify code.
    """

    id: str
    title: str
    objective: str

    status: PlanStatus = PlanStatus.DRAFT

    summary: str = ""
    reasoning: str = ""

    changes: list[PlanChange] = field(default_factory=list)
    tests: list[str] = field(default_factory=list)

    risks: list[str] = field(default_factory=list)
    rollback_strategy: str = ""

    created_at: str = field(
        default_factory=lambda: datetime.now(
            timezone.utc
        ).isoformat()
    )

    updated_at: str = field(
        default_factory=lambda: datetime.now(
            timezone.utc
        ).isoformat()
    )

    metadata: dict[str, Any] = field(default_factory=dict)

    def touch(self) -> None:
        self.updated_at = datetime.now(
            timezone.utc
        ).isoformat()

    def set_status(
        self,
        status: PlanStatus,
    ) -> None:
        self.status = status
        self.touch()

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)

        data["status"] = self.status.value
        data["changes"] = [
            change.to_dict()
            for change in self.changes
        ]

        return data

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
    ) -> "ImprovementPlan":
        payload = dict(data)

        payload["status"] = PlanStatus(
            payload.get(
                "status",
                PlanStatus.DRAFT.value,
            )
        )

        payload["changes"] = [
            PlanChange.from_dict(change)
            for change in payload.get(
                "changes",
                [],
            )
        ]

        return cls(**payload)