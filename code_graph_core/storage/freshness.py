from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from code_graph_core.graph.models import SourceFile
from code_graph_core.ingestion.scanner import RepositoryScanner


def timestamp_to_utc_iso(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def latest_source_mtime(source_files: list[SourceFile], repo_path: Path) -> float:
    if source_files:
        return max(source_file.absolute_path.stat().st_mtime for source_file in source_files)
    return repo_path.stat().st_mtime


def source_last_modified_at(source_files: list[SourceFile], repo_path: Path) -> str:
    return timestamp_to_utc_iso(latest_source_mtime(source_files, repo_path))


def current_source_last_modified_at(repo_path: Path) -> str:
    scanner = RepositoryScanner()
    return source_last_modified_at(scanner.scan(repo_path.resolve()), repo_path.resolve())
