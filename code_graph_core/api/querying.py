from __future__ import annotations

import json
import re
from pathlib import Path

from code_graph_core.storage.index_paths import graph_path as indexed_graph_path
from code_graph_core.storage.index_paths import metadata_path as indexed_metadata_path
from code_graph_core.storage.kuzu_store import KuzuStore
from code_graph_core.storage.metadata import load_metadata

DEFAULT_SEARCH_LIMIT = 10
MAX_SEARCH_LIMIT = 50
MAX_CONTEXT_NEIGHBORS = 10
SEARCHABLE_LABELS = ("Function", "Method", "Class", "Interface", "File")
SYMBOL_LABELS = ("Function", "Method", "Class", "Interface")
CONTEXT_CALL_LABELS = {"Function", "Method"}


def search(
    repo_id: str,
    query: str,
    limit: int = DEFAULT_SEARCH_LIMIT,
    *,
    graph_path: str | None = None,
    index_root: str | None = None,
) -> dict[str, object]:
    bounded_limit = max(1, min(limit, MAX_SEARCH_LIMIT))
    normalized_query = query.strip()
    if not normalized_query:
        return {"results": []}

    reader = _IndexReader(repo_id=repo_id, graph_path=graph_path, index_root=index_root)
    scored_results = []
    for candidate in reader.load_search_candidates():
        ranking = _score_candidate(candidate, normalized_query)
        if ranking is None:
            continue
        scored_results.append((ranking["score"], ranking["reason"], candidate))

    scored_results.sort(
        key=lambda item: (
            -item[0],
            0 if item[2]["type"] != "File" else 1,
            item[2]["file_path"],
            item[2]["name"],
        )
    )

    results = []
    for score, reason, candidate in scored_results[:bounded_limit]:
        results.append(
            {
                "node_id": candidate["node_id"],
                "type": candidate["type"],
                "name": candidate["name"],
                "file_path": candidate["file_path"],
                "start_line": candidate["start_line"],
                "end_line": candidate["end_line"],
                "skill": None,
                "score": round(score, 2),
                "reason": reason,
            }
        )
    return {"results": results}


def get_repo_status(
    repo_id: str,
    *,
    metadata_path: str | None = None,
    index_root: str | None = None,
) -> dict[str, object]:
    resolved_metadata_path = _resolve_metadata_path(
        repo_id=repo_id,
        metadata_path=metadata_path,
        index_root=index_root,
    )
    metadata = load_metadata(resolved_metadata_path)
    return {
        "repo_id": metadata["repo_id"],
        "repo_name": metadata["repo_name"],
        "indexed_at": metadata["indexed_at"],
        "index_version": metadata["index_version"],
        "languages_detected": list(metadata.get("languages_detected", [])),
        "stats": {
            key: int(metadata.get(key, 0))
            for key in (
                "file_count",
                "node_count",
                "edge_count",
                "skill_count",
                "skipped_file_count",
                "parse_error_count",
                "unresolved_import_count",
                "unresolved_call_count",
            )
        },
    }


def get_symbol_context(
    repo_id: str,
    symbol: str,
    file_path: str | None = None,
    *,
    graph_path: str | None = None,
    index_root: str | None = None,
) -> dict[str, object]:
    reader = _IndexReader(repo_id=repo_id, graph_path=graph_path, index_root=index_root)
    candidates = reader.find_symbol_candidates(symbol=symbol, file_path=file_path)

    if not candidates:
        return _error_response(
            code="SYMBOL_NOT_FOUND",
            message=f"No symbol matched '{symbol}'",
        )

    if len(candidates) > 1:
        return {
            "error": {
                "code": "AMBIGUOUS_SYMBOL",
                "message": f"Multiple symbols matched '{symbol}'",
                "details": {
                    "candidates": [
                        {
                            "node_id": candidate["node_id"],
                            "type": candidate["type"],
                            "file_path": candidate["file_path"],
                        }
                        for candidate in candidates[:MAX_CONTEXT_NEIGHBORS]
                    ]
                },
            }
        }

    target = candidates[0]
    callers = reader.load_callers(target["node_id"])
    callees = reader.load_callees(target["node_id"])
    related_files = sorted(
        {
            item["file_path"]
            for item in callers + callees
            if item["file_path"] and item["file_path"] != target["file_path"]
        }
    )

    symbol_payload = {
        "node_id": target["node_id"],
        "type": target["type"],
        "name": target["name"],
        "file_path": target["file_path"],
        "start_line": target["start_line"],
        "end_line": target["end_line"],
        "signature": target["signature"],
        "skill": None,
    }
    if target["type"] == "Method" and target["owner_name"]:
        symbol_payload["containing_class"] = target["owner_name"]

    return {
        "symbol": symbol_payload,
        "callers": callers[:MAX_CONTEXT_NEIGHBORS],
        "callees": callees[:MAX_CONTEXT_NEIGHBORS],
        "related_files": related_files,
    }


class _IndexReader:
    def __init__(
        self,
        *,
        repo_id: str,
        graph_path: str | None,
        index_root: str | None,
    ) -> None:
        self.repo_id = repo_id
        resolved_graph_path = self._resolve_graph_path(repo_id=repo_id, graph_path=graph_path, index_root=index_root)
        self.store = KuzuStore(resolved_graph_path)

    def load_search_candidates(self) -> list[dict[str, object]]:
        candidates: list[dict[str, object]] = []
        for label in SEARCHABLE_LABELS:
            candidates.extend(self._load_nodes(label))
        return candidates

    def find_symbol_candidates(self, symbol: str, file_path: str | None) -> list[dict[str, object]]:
        symbol_query = symbol.strip()
        exact_matches = []
        for candidate in self._load_symbol_nodes():
            if candidate["node_id"] == symbol_query or candidate["name"] == symbol_query:
                exact_matches.append(candidate)

        if file_path is not None:
            exact_matches = [candidate for candidate in exact_matches if candidate["file_path"] == file_path]

        exact_matches.sort(key=lambda item: (item["file_path"], item["type"], item["node_id"]))
        return exact_matches

    def load_callers(self, node_id: str) -> list[dict[str, object]]:
        rows = self._rows(
            f"""
            MATCH (caller)-[r:CodeRelation]->(callee)
            WHERE r.type = 'CALLS' AND callee.id = {self._literal(node_id)}
            RETURN caller AS node, r.confidence AS confidence
            ORDER BY caller.file_path, caller.name;
            """
        )
        return [
            self._related_symbol_payload(row["node"], row["confidence"])
            for row in rows
            if row["node"].get("_label") in CONTEXT_CALL_LABELS
        ]

    def load_callees(self, node_id: str) -> list[dict[str, object]]:
        rows = self._rows(
            f"""
            MATCH (caller)-[r:CodeRelation]->(callee)
            WHERE r.type = 'CALLS' AND caller.id = {self._literal(node_id)}
            RETURN callee AS node, r.confidence AS confidence
            ORDER BY callee.file_path, callee.name;
            """
        )
        return [
            self._related_symbol_payload(row["node"], row["confidence"])
            for row in rows
            if row["node"].get("_label") in CONTEXT_CALL_LABELS
        ]

    def _load_symbol_nodes(self) -> list[dict[str, object]]:
        symbols: list[dict[str, object]] = []
        for label in SYMBOL_LABELS:
            symbols.extend(self._load_nodes(label))
        return symbols

    def _load_nodes(self, label: str) -> list[dict[str, object]]:
        rows = self._rows(
            f"""
            MATCH (n:{label})
            WHERE n.repo_id = {self._literal(self.repo_id)}
            RETURN n AS node
            ORDER BY n.file_path, n.name;
            """
        )
        return [self._normalize_node(row["node"]) for row in rows]

    def _rows(self, query: str) -> list[dict[str, object]]:
        result = self.store.connection.execute(query)
        columns = result.get_column_names()
        return [dict(zip(columns, row, strict=False)) for row in result.get_all()]

    @staticmethod
    def _normalize_node(node: dict[str, object]) -> dict[str, object]:
        return {
            "node_id": node["id"],
            "type": node["_label"],
            "name": node.get("name") or "",
            "file_path": node.get("file_path") or "",
            "start_line": node.get("start_line"),
            "end_line": node.get("end_line"),
            "signature": node.get("signature"),
            "owner_name": node.get("owner_name") or None,
            "is_exported": bool(node.get("is_exported")) if node.get("is_exported") is not None else False,
        }

    @staticmethod
    def _related_symbol_payload(node: dict[str, object], confidence: float) -> dict[str, object]:
        return {
            "node_id": node["id"],
            "name": node.get("name") or "",
            "file_path": node.get("file_path") or "",
            "confidence": confidence,
        }

    @staticmethod
    def _literal(value: object) -> str:
        if value is None:
            return "NULL"
        return json.dumps(value)

    @staticmethod
    def _resolve_graph_path(repo_id: str, graph_path: str | None, index_root: str | None) -> Path:
        if graph_path is not None:
            return Path(graph_path).resolve()

        candidates: list[Path] = []
        cwd = Path.cwd().resolve()
        if index_root is not None:
            root = Path(index_root).resolve()
            candidates.append(indexed_graph_path(root, repo_id))
            candidates.append(root / repo_id / "graph.kuzu")
        candidates.append(indexed_graph_path(cwd / ".code_graph", repo_id))
        candidates.append(cwd / ".code_graph" / repo_id / "graph.kuzu")
        candidates.append(indexed_graph_path(cwd, repo_id))
        candidates.append(cwd / repo_id / "graph.kuzu")

        for candidate in candidates:
            if candidate.exists():
                return candidate
        raise FileNotFoundError(f"Could not locate graph for repo_id '{repo_id}'")


def _score_candidate(candidate: dict[str, object], query: str) -> dict[str, object] | None:
    normalized_query = query.lower()
    name = str(candidate["name"]).lower()
    file_path = str(candidate["file_path"]).lower()
    terms = [term for term in re.split(r"\s+", normalized_query) if term]

    score = 0.0
    reasons: list[str] = []

    if candidate["node_id"] == query:
        score = 1.0
        reasons.append("Exact node ID match")
    elif name == normalized_query:
        score = 0.98
        reasons.append("Exact symbol match" if candidate["type"] != "File" else "Exact file name match")
    elif name.startswith(normalized_query):
        score = 0.9
        reasons.append("Prefix name match")
    elif normalized_query in name:
        score = 0.78
        reasons.append("Substring name match")
    elif file_path == normalized_query:
        score = 0.76
        reasons.append("Exact file path match")
    elif file_path.endswith(normalized_query):
        score = 0.7
        reasons.append("Suffix file path match")
    else:
        matched_terms = sum(1 for term in terms if term in name or term in file_path)
        if matched_terms == 0:
            return None
        score = 0.45 + (0.05 * matched_terms)
        reasons.append("Term match across name/path")

    if candidate["type"] != "File":
        score += 0.03
        reasons.append("Symbol result")
    if candidate["is_exported"]:
        score += 0.02
        reasons.append("Exported")

    return {"score": min(score, 1.0), "reason": "; ".join(reasons)}


def _error_response(code: str, message: str) -> dict[str, object]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": {},
        }
    }


def _resolve_metadata_path(repo_id: str, metadata_path: str | None, index_root: str | None) -> Path:
    if metadata_path is not None:
        return Path(metadata_path).resolve()

    candidates: list[Path] = []
    cwd = Path.cwd().resolve()
    if index_root is not None:
        root = Path(index_root).resolve()
        candidates.append(indexed_metadata_path(root, repo_id))
        candidates.append(root / repo_id / "metadata.json")
    candidates.append(indexed_metadata_path(cwd / ".code_graph", repo_id))
    candidates.append(cwd / ".code_graph" / repo_id / "metadata.json")
    candidates.append(indexed_metadata_path(cwd, repo_id))
    candidates.append(cwd / repo_id / "metadata.json")

    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"Could not locate metadata for repo_id '{repo_id}'")
