from __future__ import annotations

from pathlib import Path, PurePosixPath

from code_graph_core.graph.models import SourceFile


LANGUAGE_BY_SUFFIX = {
    ".py": ("python", "python"),
    ".ts": ("typescript", "typescript"),
    ".tsx": ("typescript", "typescript"),
    ".js": ("javascript", "javascript"),
    ".jsx": ("javascript", "javascript"),
}

IGNORED_DIRS = {
    ".git",
    ".hg",
    ".idea",
    ".mypy_cache",
    ".pytest_cache",
    ".venv",
    ".vscode",
    "__pycache__",
    "build",
    "coverage",
    "dist",
    "node_modules",
    "venv",
}

IGNORED_PREFIXES = (".code_graph",)


class RepositoryScanner:
    def scan(self, repo_path: Path) -> list[SourceFile]:
        repo_path = repo_path.resolve()
        source_files: list[SourceFile] = []

        for absolute_path in sorted(repo_path.rglob("*")):
            if absolute_path.is_dir():
                continue
            if self._is_ignored(absolute_path, repo_path):
                continue
            suffix = absolute_path.suffix.lower()
            if suffix not in LANGUAGE_BY_SUFFIX:
                continue

            language, parser_name = LANGUAGE_BY_SUFFIX[suffix]
            relative_path = PurePosixPath(absolute_path.relative_to(repo_path).as_posix()).as_posix()
            source_files.append(
                SourceFile(
                    repo_path=repo_path,
                    absolute_path=absolute_path,
                    relative_path=relative_path,
                    language=language,
                    parser_name=parser_name,
                    is_test=self._is_test_file(relative_path),
                )
            )

        return source_files

    def _is_ignored(self, path: Path, repo_path: Path) -> bool:
        relative_parts = path.relative_to(repo_path).parts
        for part in relative_parts[:-1]:
            if part in IGNORED_DIRS:
                return True
            if any(part.startswith(prefix) for prefix in IGNORED_PREFIXES):
                return True
        return False

    @staticmethod
    def _is_test_file(relative_path: str) -> bool:
        name = Path(relative_path).name
        return (
            "/tests/" in f"/{relative_path}/"
            or name.startswith("test_")
            or name.endswith("_test.py")
            or ".test." in name
            or ".spec." in name
        )

