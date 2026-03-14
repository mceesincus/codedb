from __future__ import annotations

import os
import shutil
import subprocess
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
        fast_path_files = self._scan_via_find(repo_path)
        if fast_path_files is not None:
            return fast_path_files

        return self._scan_via_walk(repo_path)

    def _scan_via_walk(self, repo_path: Path) -> list[SourceFile]:
        source_files: list[SourceFile] = []

        for current_root, dir_names, file_names in os.walk(repo_path, topdown=True):
            current_root_path = Path(current_root)
            relative_root = current_root_path.relative_to(repo_path)
            relative_parts = relative_root.parts

            dir_names[:] = [
                dir_name
                for dir_name in dir_names
                if not self._is_ignored_dir(dir_name, relative_parts)
            ]

            for file_name in sorted(file_names):
                absolute_path = current_root_path / file_name
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

    def _scan_via_find(self, repo_path: Path) -> list[SourceFile] | None:
        if os.name == "nt":
            return None
        if shutil.which("find") is None:
            return None

        command = ["find", str(repo_path)]
        prune_patterns = sorted(IGNORED_DIRS) + [f"{prefix}*" for prefix in IGNORED_PREFIXES]
        if prune_patterns:
            command.extend(["("])
            for index, pattern in enumerate(prune_patterns):
                if index > 0:
                    command.append("-o")
                command.extend(["-name", pattern])
            command.extend([")", "-type", "d", "-prune", "-o"])

        command.extend(["-type", "f", "("])
        suffixes = sorted(LANGUAGE_BY_SUFFIX)
        for index, suffix in enumerate(suffixes):
            if index > 0:
                command.append("-o")
            command.extend(["-name", f"*{suffix}"])
        command.extend([")", "-print"])

        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            return None

        source_files: list[SourceFile] = []
        for line in completed.stdout.splitlines():
            if not line:
                continue
            absolute_path = Path(line)
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
        source_files.sort(key=lambda item: item.relative_path)
        return source_files

    def _is_ignored_dir(self, dir_name: str, parent_parts: tuple[str, ...]) -> bool:
        for part in (*parent_parts, dir_name):
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
