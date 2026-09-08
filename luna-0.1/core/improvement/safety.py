"""Safety policies for L.U.N.A.'s controlled self-improvement system."""

from __future__ import annotations

from pathlib import Path


class ImprovementSafetyError(Exception):
    """Raised when an improvement operation violates a safety policy."""


class ImprovementSafetyPolicy:
    """
    Defines hard boundaries for L.U.N.A.'s self-improvement system.

    The policy is intentionally conservative.

    Self-improvement may only operate inside the configured
    application repository and may never access secrets,
    virtual environments, Git internals, or arbitrary paths.
    """

    DEFAULT_BLOCKED_DIRECTORIES = {
        ".git",
        "__pycache__",
        ".venv",
        "venv",
        "env",
        ".env",
        "site-packages",
        "node_modules",
    }

    DEFAULT_BLOCKED_FILES = {
        ".env",
        ".env.local",
        ".env.production",
        ".env.development",
        "credentials.json",
        "secrets.json",
        "id_rsa",
        "id_ed25519",
    }

    DEFAULT_ALLOWED_ACTIONS = {
        "create",
        "modify",
        "delete",
    }

    def __init__(
        self,
        repository_root: str | Path,
        *,
        blocked_directories: set[str] | None = None,
        blocked_files: set[str] | None = None,
        allowed_actions: set[str] | None = None,
    ) -> None:
        self.repository_root = Path(
            repository_root
        ).resolve()

        self.blocked_directories = (
            set(blocked_directories)
            if blocked_directories is not None
            else set(self.DEFAULT_BLOCKED_DIRECTORIES)
        )

        self.blocked_files = (
            set(blocked_files)
            if blocked_files is not None
            else set(self.DEFAULT_BLOCKED_FILES)
        )

        self.allowed_actions = (
            set(allowed_actions)
            if allowed_actions is not None
            else set(self.DEFAULT_ALLOWED_ACTIONS)
        )

    def resolve_safe_path(
        self,
        path: str | Path,
    ) -> Path:
        """
        Resolve a path and verify that it remains inside
        the configured repository root.
        """

        candidate = Path(path)

        if not candidate.is_absolute():
            candidate = (
                self.repository_root
                / candidate
            )

        resolved = candidate.resolve()

        try:
            resolved.relative_to(
                self.repository_root
            )
        except ValueError as exc:
            raise ImprovementSafetyError(
                "Improvement operation attempted to "
                "access a path outside the repository root."
            ) from exc

        self.validate_path(
            resolved
        )

        return resolved

    def validate_path(
        self,
        path: str | Path,
    ) -> None:
        """Validate a repository path against hard safety boundaries."""

        candidate = Path(path)

        if candidate.name in self.blocked_files:
            raise ImprovementSafetyError(
                f"Improvement operation is blocked for "
                f"sensitive file: {candidate.name}"
            )

        if candidate.name.startswith(".env"):
            raise ImprovementSafetyError(
                "Improvement operation is blocked for "
                "environment files."
            )

        for part in candidate.parts:
            if part in self.blocked_directories:
                raise ImprovementSafetyError(
                    f"Improvement operation is blocked inside "
                    f"restricted directory: {part}"
                )

    def validate_action(
        self,
        action: str,
    ) -> str:
        """Validate and normalize a requested change action."""

        normalized = (
            action or ""
        ).strip().lower()

        if normalized not in self.allowed_actions:
            raise ImprovementSafetyError(
                f"Unsupported improvement action: {action!r}"
            )

        return normalized

    def validate_change(
        self,
        *,
        path: str | Path,
        action: str,
    ) -> Path:
        """
        Validate both the target path and requested action.

        Returns the resolved safe path.
        """

        safe_path = self.resolve_safe_path(
            path
        )

        self.validate_action(
            action
        )

        return safe_path

    def validate_plan(
        self,
        changes,
    ) -> None:
        """
        Validate all proposed plan changes before execution.

        This method does not modify anything.
        """

        for change in changes:
            self.validate_change(
                path=change.path,
                action=change.action,
            )