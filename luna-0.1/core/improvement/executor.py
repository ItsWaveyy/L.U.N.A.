"""Controlled change execution and rollback for L.U.N.A."""

from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from core.improvement.manager import ImprovementManager
from core.improvement.models import (
    ImprovementPlan,
    PlanStatus,
)
from core.improvement.safety import (
    ImprovementSafetyError,
    ImprovementSafetyPolicy,
)


@dataclass
class FileBackup:
    """Backup information for one file involved in an execution."""

    original_path: Path
    backup_path: Path
    existed: bool


@dataclass
class ExecutionResult:
    """Result of executing an improvement plan."""

    plan_id: str
    success: bool
    changed_files: list[str]
    rolled_back: bool = False
    error: str | None = None


class ChangeExecutor:
    """
    Safely executes approved improvement plans.

    The executor intentionally accepts explicit file contents rather than
    arbitrary commands or executable code.

    Supported actions:
        create
        modify
        delete

    Safety guarantees:
        - Only APPROVED plans may execute.
        - Paths must pass ImprovementSafetyPolicy.
        - A backup is created before destructive operations.
        - Failed executions automatically roll back.
        - No shell commands are executed.
        - No repository code is executed.
    """

    def __init__(
        self,
        repository_root: str | Path,
        *,
        manager: ImprovementManager | None = None,
        safety_policy: ImprovementSafetyPolicy | None = None,
        backup_directory: str | Path = "data/improvement/backups",
    ) -> None:
        self.repository_root = Path(
            repository_root
        ).resolve()

        self.manager = (
            manager
            or ImprovementManager()
        )

        self.safety_policy = (
            safety_policy
            or ImprovementSafetyPolicy(
                self.repository_root
            )
        )

        self.backup_directory = Path(
            backup_directory
        ).resolve()

        self.backup_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

    def execute(
        self,
        plan_id: str,
        *,
        file_contents: dict[str, str] | None = None,
    ) -> ExecutionResult:
        """
        Execute an approved improvement plan.

        file_contents maps repository-relative paths to the exact
        replacement/new file contents.

        Delete operations do not require an entry in file_contents.
        """

        plan = self.manager.require_plan(
            plan_id
        )

        if plan.status != PlanStatus.APPROVED:
            raise ImprovementSafetyError(
                "Only approved improvement plans "
                "can be executed."
            )

        file_contents = dict(
            file_contents or {}
        )

        self.safety_policy.validate_plan(
            plan.changes
        )

        self._validate_requested_contents(
            plan,
            file_contents,
        )

        plan.set_status(
            PlanStatus.EXECUTING
        )
        self.manager.save(plan)

        backups: list[FileBackup] = []
        changed_files: list[str] = []

        execution_directory = Path(
            tempfile.mkdtemp(
                prefix=f"{plan.id}-",
                dir=self.backup_directory,
            )
        )

        try:
            for change in plan.changes:
                safe_path = (
                    self.safety_policy.validate_change(
                        path=change.path,
                        action=change.action,
                    )
                )

                backup = self._backup_file(
                    safe_path,
                    execution_directory,
                )

                backups.append(
                    backup
                )

                self._apply_change(
                    change.action,
                    safe_path,
                    file_contents.get(
                        change.path
                    ),
                )

                changed_files.append(
                    change.path
                )

            plan.set_status(
                PlanStatus.TESTING
            )
            self.manager.save(plan)

            return ExecutionResult(
                plan_id=plan.id,
                success=True,
                changed_files=changed_files,
            )

        except Exception as exc:
            print(
                "[L.U.N.A.] "
                f"Improvement execution failed: {exc}",
                flush=True,
            )

            rollback_error: Exception | None = None

            try:
                self._rollback(
                    backups
                )
            except Exception as rollback_exc:
                rollback_error = rollback_exc
                print(
                    "[L.U.N.A.] "
                    f"Improvement rollback failed: "
                    f"{rollback_exc}",
                    flush=True,
                )

            if rollback_error is None:
                plan.set_status(
                    PlanStatus.ROLLED_BACK
                )
            else:
                plan.set_status(
                    PlanStatus.FAILED
                )

            self.manager.save(plan)

            error_message = str(exc)

            if rollback_error is not None:
                error_message += (
                    f" | Rollback error: "
                    f"{rollback_error}"
                )

            return ExecutionResult(
                plan_id=plan.id,
                success=False,
                changed_files=changed_files,
                rolled_back=(
                    rollback_error is None
                ),
                error=error_message,
            )

        finally:
            shutil.rmtree(
                execution_directory,
                ignore_errors=True,
            )

    def _validate_requested_contents(
        self,
        plan: ImprovementPlan,
        file_contents: dict[str, str],
    ) -> None:
        """Validate that content was supplied for required operations."""

        expected_paths = {
            change.path
            for change in plan.changes
            if change.action in {
                "create",
                "modify",
            }
        }

        supplied_paths = set(
            file_contents
        )

        missing = (
            expected_paths
            - supplied_paths
        )

        if missing:
            raise ImprovementSafetyError(
                "Missing file contents for: "
                + ", ".join(
                    sorted(missing)
                )
            )

        unknown = (
            supplied_paths
            - {
                change.path
                for change in plan.changes
            }
        )

        if unknown:
            raise ImprovementSafetyError(
                "File contents supplied for "
                "paths not included in the plan: "
                + ", ".join(
                    sorted(unknown)
                )
            )

    def _backup_file(
        self,
        path: Path,
        execution_directory: Path,
    ) -> FileBackup:
        """
        Back up an existing file.

        Nonexistent files are recorded so rollback can remove them
        if they are created during the execution.
        """

        relative = path.relative_to(
            self.repository_root
        )

        backup_path = (
            execution_directory
            / relative
        )

        if not path.exists():
            return FileBackup(
                original_path=path,
                backup_path=backup_path,
                existed=False,
            )

        if not path.is_file():
            raise ImprovementSafetyError(
                "Improvement executor can only "
                f"modify files: {relative}"
            )

        backup_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        shutil.copy2(
            path,
            backup_path,
        )

        return FileBackup(
            original_path=path,
            backup_path=backup_path,
            existed=True,
        )

    def _apply_change(
        self,
        action: str,
        path: Path,
        content: str | None,
    ) -> None:
        """Apply one explicitly requested file operation."""

        if action == "create":
            if path.exists():
                raise ImprovementSafetyError(
                    f"Cannot create existing file: "
                    f"{path}"
                )

            if content is None:
                raise ImprovementSafetyError(
                    f"No content supplied for: "
                    f"{path}"
                )

            path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            path.write_text(
                content,
                encoding="utf-8",
            )

            return

        if action == "modify":
            if not path.exists():
                raise ImprovementSafetyError(
                    f"Cannot modify missing file: "
                    f"{path}"
                )

            if not path.is_file():
                raise ImprovementSafetyError(
                    f"Cannot modify non-file path: "
                    f"{path}"
                )

            if content is None:
                raise ImprovementSafetyError(
                    f"No content supplied for: "
                    f"{path}"
                )

            path.write_text(
                content,
                encoding="utf-8",
            )

            return

        if action == "delete":
            if not path.exists():
                raise ImprovementSafetyError(
                    f"Cannot delete missing file: "
                    f"{path}"
                )

            if not path.is_file():
                raise ImprovementSafetyError(
                    f"Cannot delete non-file path: "
                    f"{path}"
                )

            path.unlink()

            return

        raise ImprovementSafetyError(
            f"Unsupported improvement action: "
            f"{action!r}"
        )

    def _rollback(
        self,
        backups: list[FileBackup],
    ) -> None:
        """Restore every file touched during the failed execution."""

        for backup in reversed(
            backups
        ):
            original = backup.original_path

            if backup.existed:
                if not backup.backup_path.exists():
                    raise ImprovementSafetyError(
                        "Backup missing during rollback: "
                        f"{backup.backup_path}"
                    )

                original.parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                shutil.copy2(
                    backup.backup_path,
                    original,
                )

            else:
                if original.exists():
                    if not original.is_file():
                        raise ImprovementSafetyError(
                            "Rollback encountered a "
                            f"non-file path: {original}"
                        )

                    original.unlink()