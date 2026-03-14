from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from code_graph_core.storage.freshness import current_source_last_modified_at
from code_graph_core.storage.index_paths import graph_path as indexed_graph_path
from code_graph_core.storage.index_paths import metadata_path as indexed_metadata_path
from code_graph_core.storage.index_paths import repo_id_for_path
from code_graph_core.storage.metadata import load_metadata

DEFAULT_WINDOWS_SOURCE_REPO = r"C:\work\india\mssrc"
DEFAULT_WSL_SOURCE_REPO = "/mnt/c/work/india/mssrc"


@dataclass(slots=True)
class IndexedRepoState:
    source_repo_path: str
    repo_id: str
    repo_name: str
    graph_path: str
    metadata_path: str
    indexed_at: str
    source_last_modified_at: str | None
    freshness_status: str
    index_version: str
    languages_detected: list[str]
    stats: dict[str, int]


def normalize_repo_path(raw_path: str) -> Path:
    value = raw_path.strip()
    if not value:
        raise ValueError("Repository path is required.")

    windows_match = re.match(r"^(?P<drive>[a-zA-Z]):[\\/](?P<rest>.*)$", value)
    if windows_match and os.name != "nt":
        drive = windows_match.group("drive").lower()
        rest = windows_match.group("rest").replace("\\", "/")
        return Path(f"/mnt/{drive}/{rest}").resolve(strict=False)

    if os.name == "nt" and value.startswith("/mnt/"):
        parts = Path(value).parts
        if len(parts) >= 4 and len(parts[2]) == 1:
            drive = parts[2].upper()
            rest = Path(*parts[3:])
            return Path(f"{drive}:/{rest}").resolve(strict=False)

    return Path(value).expanduser().resolve(strict=False)


def default_source_repo_path() -> str:
    candidates = [
        Path(DEFAULT_WINDOWS_SOURCE_REPO),
        Path(DEFAULT_WSL_SOURCE_REPO),
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return DEFAULT_WINDOWS_SOURCE_REPO if os.name == "nt" else DEFAULT_WSL_SOURCE_REPO


def format_search_result(result: dict[str, Any]) -> str:
    suffix = f" skill={result['skill']}" if result.get("skill") else ""
    return (
        f"[{result['type']}] {result['name']} "
        f"({result['file_path']}:{result.get('start_line') or '-'}) "
        f"score={result['score']:.2f}{suffix}"
    )


def format_symbol_context(payload: dict[str, Any]) -> str:
    if "error" in payload:
        return json.dumps(payload, indent=2, sort_keys=True)

    symbol = payload["symbol"]
    lines = [
        f"{symbol['type']} {symbol['name']}",
        f"node_id: {symbol['node_id']}",
        f"file: {symbol['file_path']}:{symbol['start_line']}-{symbol['end_line']}",
    ]
    if symbol.get("skill"):
        lines.append(f"skill: {symbol['skill']}")
    if symbol.get("containing_class"):
        lines.append(f"class: {symbol['containing_class']}")
    if symbol.get("signature"):
        lines.append(f"signature: {symbol['signature']}")

    lines.append("")
    lines.append("Callers:")
    if payload["callers"]:
        lines.extend(
            f"- {item['name']} ({item['file_path']}, confidence={item['confidence']:.1f})"
            for item in payload["callers"]
        )
    else:
        lines.append("- none")

    lines.append("")
    lines.append("Callees:")
    if payload["callees"]:
        lines.extend(
            f"- {item['name']} ({item['file_path']}, confidence={item['confidence']:.1f})"
            for item in payload["callees"]
        )
    else:
        lines.append("- none")

    lines.append("")
    lines.append("Dependencies:")
    if payload.get("dependencies"):
        lines.extend(f"- {file_path}" for file_path in payload["dependencies"])
    else:
        lines.append("- none")

    lines.append("")
    lines.append("Related files:")
    if payload["related_files"]:
        lines.extend(f"- {file_path}" for file_path in payload["related_files"])
    else:
        lines.append("- none")

    return "\n".join(lines)


def format_skills_list(payload: dict[str, Any]) -> str:
    if "error" in payload:
        return json.dumps(payload, indent=2, sort_keys=True)
    skills = payload.get("skills", [])
    if not skills:
        return "No skills."
    lines = ["Skills:"]
    for skill in skills:
        lines.append(
            f"- {skill['label']} ({skill['name']}): {skill['summary']} "
            f"[files={skill['file_count']}, symbols={skill['symbol_count']}]"
        )
    return "\n".join(lines)


def format_skill_detail(payload: dict[str, Any]) -> str:
    if "error" in payload:
        return json.dumps(payload, indent=2, sort_keys=True)
    lines = [
        f"{payload['label']} ({payload['name']})",
        f"generated_at: {payload['generated_at']}",
        f"summary: {payload['summary']}",
        "",
        "Key files:",
    ]
    lines.extend(f"- {item}" for item in payload["key_files"] or ["none"])
    lines.append("")
    lines.append("Key symbols:")
    lines.extend(f"- {item}" for item in payload["key_symbols"] or ["none"])
    lines.append("")
    lines.append("Entry points:")
    lines.extend(f"- {item}" for item in payload["entry_points"] or ["none"])
    lines.append("")
    lines.append("Flows:")
    lines.extend(f"- {item}" for item in payload["flows"] or ["none"])
    lines.append("")
    lines.append("Related skills:")
    lines.extend(f"- {item}" for item in payload["related_skills"] or ["none"])
    lines.append("")
    lines.append(json.dumps(payload["stats"], indent=2, sort_keys=True))
    return "\n".join(lines)


def format_impact(payload: dict[str, Any]) -> str:
    if "error" in payload:
        return json.dumps(payload, indent=2, sort_keys=True)
    lines = [
        f"Impact: {payload['target']['name']}",
        f"direction: {payload['direction']}",
        f"severity: {payload['severity']}",
        "",
        json.dumps(payload["summary"], indent=2, sort_keys=True),
        "",
        "By depth:",
    ]
    for depth, items in payload["by_depth"].items():
        lines.append(f"{depth}:")
        if items:
            lines.extend(
                f"- {item['name']} ({item['file_path']}, skill={item['skill'] or 'none'})"
                for item in items
            )
        else:
            lines.append("- none")
    lines.append("")
    lines.append("Affected skills:")
    lines.extend(f"- {item}" for item in payload["affected_skills"] or ["none"])
    return "\n".join(lines)


def format_index_progress(progress: Any) -> str:
    total = int(getattr(progress, "total", 0) or 0)
    current = int(getattr(progress, "current", 0) or 0)
    message = str(getattr(progress, "message", ""))
    phase = str(getattr(progress, "phase", "work")).capitalize()
    if total > 1:
        percent = int((current / total) * 100)
        return f"{phase} {current}/{total} ({percent}%) | {message}"
    return f"{phase} | {message}"


def classify_index_freshness(repo_path: Path, metadata: dict[str, object]) -> str:
    stored_last_modified_at = metadata.get("source_last_modified_at")
    if not stored_last_modified_at:
        return "STALE"

    current_last_modified_at = current_source_last_modified_at(repo_path)
    if current_last_modified_at > str(stored_last_modified_at):
        return "STALE"
    return "CURRENT"


def load_existing_index_state(repo_path: Path, index_root: Path) -> IndexedRepoState | None:
    repo_id = repo_id_for_path(repo_path)
    graph_path = indexed_graph_path(index_root, repo_id)
    metadata_path = indexed_metadata_path(index_root, repo_id)
    if not graph_path.exists() or not metadata_path.exists():
        return None

    metadata = load_metadata(metadata_path)
    stats = {
        key: int(metadata.get(key, 0))
        for key in (
            "edge_count",
            "file_count",
            "node_count",
            "parse_error_count",
            "skill_count",
            "skipped_file_count",
            "unresolved_call_count",
            "unresolved_import_count",
        )
    }
    freshness_status = classify_index_freshness(repo_path, metadata)
    return IndexedRepoState(
        source_repo_path=str(repo_path),
        repo_id=str(metadata["repo_id"]),
        repo_name=str(metadata["repo_name"]),
        graph_path=str(graph_path),
        metadata_path=str(metadata_path),
        indexed_at=str(metadata.get("indexed_at", "")),
        source_last_modified_at=str(metadata.get("source_last_modified_at")) if metadata.get("source_last_modified_at") else None,
        freshness_status=freshness_status,
        index_version=str(metadata.get("index_version", "")),
        languages_detected=[str(item) for item in metadata.get("languages_detected", [])],
        stats=stats,
    )
