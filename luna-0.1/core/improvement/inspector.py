"""Read-only repository inspection for L.U.N.A.'s self-improvement system."""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ModuleInfo:
    """Information about one inspected Python module."""

    path: str
    imports: list[str] = field(default_factory=list)
    classes: list[str] = field(default_factory=list)
    functions: list[str] = field(default_factory=list)


@dataclass
class RepositorySnapshot:
    """Read-only snapshot of the L.U.N.A. application repository."""

    root: str
    python_files: list[str] = field(default_factory=list)
    modules: list[ModuleInfo] = field(default_factory=list)
    directories: list[str] = field(default_factory=list)
    ignored_paths: list[str] = field(default_factory=list)
    excluded_paths: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "root": self.root,
            "python_files": self.python_files,
            "modules": [
                {
                    "path": module.path,
                    "imports": module.imports,
                    "classes": module.classes,
                    "functions": module.functions,
                }
                for module in self.modules
            ],
            "directories": self.directories,
            "ignored_paths": self.ignored_paths,
            "excluded_paths": self.excluded_paths,
        }


class RepositoryInspector:
    """
    Read-only inspector for L.U.N.A.'s application repository.

    The inspector only reads repository structure and Python syntax.
    It never executes repository code or modifies repository files.
    """

    DEFAULT_EXCLUDED_DIRECTORIES = {
        ".git",
        "__pycache__",
        ".venv",
        "venv",
        "env",
        ".env",
        "site-packages",
        "node_modules",
    }

    DEFAULT_EXCLUDED_FILES = {
        ".env",
        ".env.local",
        ".env.production",
        ".env.development",
        "credentials.json",
        "secrets.json",
    }

    def __init__(
        self,
        repository_root: str | Path,
        *,
        excluded_directories: set[str] | None = None,
        excluded_files: set[str] | None = None,
    ) -> None:
        self.repository_root = Path(
            repository_root
        ).resolve()

        self.excluded_directories = (
            set(excluded_directories)
            if excluded_directories is not None
            else set(self.DEFAULT_EXCLUDED_DIRECTORIES)
        )

        self.excluded_files = (
            set(excluded_files)
            if excluded_files is not None
            else set(self.DEFAULT_EXCLUDED_FILES)
        )

    def inspect(self) -> RepositorySnapshot:
        """
        Inspect the repository and return a structural snapshot.

        This method:
        - discovers directories
        - discovers Python files
        - parses Python files with AST
        - records imports, classes, and functions
        - records excluded paths

        It does not execute repository code.
        """

        if not self.repository_root.exists():
            raise FileNotFoundError(
                f"Repository root does not exist: "
                f"{self.repository_root}"
            )

        if not self.repository_root.is_dir():
            raise NotADirectoryError(
                f"Repository root is not a directory: "
                f"{self.repository_root}"
            )

        snapshot = RepositorySnapshot(
            root=str(self.repository_root)
        )

        self._walk_repository(
            snapshot
        )

        snapshot.python_files.sort()
        snapshot.directories.sort()
        snapshot.ignored_paths.sort()
        snapshot.excluded_paths.sort()

        snapshot.modules.sort(
            key=lambda module: module.path
        )

        return snapshot

    def _walk_repository(
        self,
        snapshot: RepositorySnapshot,
    ) -> None:
        for path in self.repository_root.rglob("*"):
            relative = path.relative_to(
                self.repository_root
            )

            if self._contains_excluded_directory(
                relative
            ):
                snapshot.excluded_paths.append(
                    str(relative)
                )
                continue

            if path.is_dir():
                snapshot.directories.append(
                    str(relative)
                )
                continue

            if not path.is_file():
                continue

            if path.name in self.excluded_files:
                snapshot.excluded_paths.append(
                    str(relative)
                )
                continue

            if path.name.startswith(".env"):
                snapshot.excluded_paths.append(
                    str(relative)
                )
                continue

            if path.suffix == ".py":
                snapshot.python_files.append(
                    str(relative)
                )

                module = self._inspect_python_file(
                    path
                )

                if module is not None:
                    snapshot.modules.append(
                        module
                    )

    def _contains_excluded_directory(
        self,
        relative_path: Path,
    ) -> bool:
        return any(
            part in self.excluded_directories
            for part in relative_path.parts
        )

    def _inspect_python_file(
        self,
        path: Path,
    ) -> ModuleInfo | None:
        try:
            source = path.read_text(
                encoding="utf-8"
            )

        except (OSError, UnicodeDecodeError) as exc:
            print(
                "[L.U.N.A.] "
                f"RepositoryInspector: unable to read "
                f"{path}: {exc}",
                flush=True,
            )
            return None

        try:
            tree = ast.parse(
                source,
                filename=str(path),
            )

        except SyntaxError as exc:
            print(
                "[L.U.N.A.] "
                f"RepositoryInspector: syntax error in "
                f"{path}: {exc}",
                flush=True,
            )
            return ModuleInfo(
                path=str(
                    path.relative_to(
                        self.repository_root
                    )
                )
            )

        relative_path = str(
            path.relative_to(
                self.repository_root
            )
        )

        imports: set[str] = set()
        classes: list[str] = []
        functions: list[str] = []

        for node in ast.walk(tree):
            if isinstance(
                node,
                ast.Import,
            ):
                for alias in node.names:
                    imports.add(
                        alias.name
                    )

            elif isinstance(
                node,
                ast.ImportFrom,
            ):
                if node.module:
                    imports.add(
                        node.module
                    )

            elif isinstance(
                node,
                ast.ClassDef,
            ):
                classes.append(
                    node.name
                )

            elif isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                ),
            ):
                functions.append(
                    node.name
                )

        return ModuleInfo(
            path=relative_path,
            imports=sorted(imports),
            classes=sorted(set(classes)),
            functions=sorted(set(functions)),
        )

    def summarize(
        self,
        snapshot: RepositorySnapshot | None = None,
    ) -> str:
        """
        Produce a compact human-readable summary.

        If no snapshot is supplied, the repository is inspected first.
        """

        if snapshot is None:
            snapshot = self.inspect()

        lines = [
            "L.U.N.A. Repository Inspection",
            f"Root: {snapshot.root}",
            "",
            f"Python files: {len(snapshot.python_files)}",
            f"Directories: {len(snapshot.directories)}",
            f"Excluded paths: {len(snapshot.excluded_paths)}",
            f"Python modules parsed: {len(snapshot.modules)}",
            "",
            "Python modules:",
        ]

        for module in snapshot.modules:
            lines.append(
                f"- {module.path}"
            )

            if module.classes:
                lines.append(
                    "  Classes: "
                    + ", ".join(module.classes)
                )

            if module.functions:
                lines.append(
                    "  Functions: "
                    + ", ".join(module.functions)
                )

            if module.imports:
                lines.append(
                    "  Imports: "
                    + ", ".join(module.imports)
                )

        return "\n".join(
            lines
        )