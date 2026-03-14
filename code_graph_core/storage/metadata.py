from __future__ import annotations

import json
from pathlib import Path

from code_graph_core.graph.models import GraphBundle


def metadata_payload(graph_bundle: GraphBundle, repo_path: Path, graph_path: Path) -> dict[str, object]:
    payload: dict[str, object] = {
        "repo_id": graph_bundle.repo_id,
        "repo_path": str(repo_path),
        "repo_name": graph_bundle.repo_name,
        "graph_path": str(graph_path),
        "indexed_at": graph_bundle.indexed_at,
        "index_version": graph_bundle.index_version,
        "languages_detected": sorted(
            {
                node.properties["language"]
                for node in graph_bundle.nodes
                if node.kind == "File"
            }
        ),
    }
    payload.update(graph_bundle.stats.to_dict())
    return payload


def write_metadata(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def load_metadata(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))

