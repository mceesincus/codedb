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


def list_skills(
    repo_id: str,
    *,
    graph_path: str | None = None,
    index_root: str | None = None,
) -> dict[str, object]:
    reader = _IndexReader(repo_id=repo_id, graph_path=graph_path, index_root=index_root)
    skills = []
    for skill in reader.load_skill_summaries():
        skills.append(
            {
                "name": skill["name"],
                "label": skill["label"],
                "summary": skill["summary"],
                "file_count": skill["file_count"],
                "symbol_count": skill["symbol_count"],
            }
        )
    return {"skills": skills}


def get_skill(
    repo_id: str,
    skill_name: str,
    *,
    graph_path: str | None = None,
    index_root: str | None = None,
) -> dict[str, object]:
    reader = _IndexReader(repo_id=repo_id, graph_path=graph_path, index_root=index_root)
    skill = reader.load_skill_by_name(skill_name)
    if skill is None:
        return _error_response(
            code="SKILL_NOT_FOUND",
            message=f"No skill matched '{skill_name}'",
        )

    files = reader.load_skill_files(skill["node_id"])
    symbols = reader.load_skill_symbols(skill["node_id"])
    related_skills = reader.load_related_skills(skill["node_id"])
    entry_points = [
        symbol["name"]
        for symbol in symbols
        if _is_entry_point_symbol(symbol["file_path"], symbol["type"], symbol["name"])
    ]
    flows = reader.build_skill_flows(skill["name"], symbols)

    return {
        "name": skill["name"],
        "label": skill["label"],
        "summary": skill["summary"],
        "key_files": files[:10],
        "key_symbols": [symbol["name"] for symbol in symbols[:12]],
        "entry_points": entry_points[:10],
        "flows": flows[:5],
        "related_skills": related_skills[:5],
        "generated_at": skill["generated_at"],
        "stats": {
            "file_count": skill["file_count"],
            "symbol_count": skill["symbol_count"],
            "entry_point_count": skill["entry_point_count"],
            "flow_count": skill["flow_count"],
        },
    }


def get_impact(
    repo_id: str,
    target: str,
    direction: str,
    depth: int = 2,
    *,
    graph_path: str | None = None,
    index_root: str | None = None,
) -> dict[str, object]:
    bounded_depth = max(1, min(depth, 4))
    if direction not in {"upstream", "downstream"}:
        return _error_response(
            code="INVALID_DIRECTION",
            message=f"Unsupported direction '{direction}'",
        )

    reader = _IndexReader(repo_id=repo_id, graph_path=graph_path, index_root=index_root)
    candidates = reader.find_target_candidates(target)
    if not candidates:
        return _error_response(
            code="SYMBOL_NOT_FOUND",
            message=f"No symbol matched '{target}'",
        )
    if len(candidates) > 1:
        return {
            "error": {
                "code": "AMBIGUOUS_SYMBOL",
                "message": f"Multiple symbols matched '{target}'",
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

    target_node = candidates[0]
    by_depth, affected_skills = reader.traverse_impact(target_node["node_id"], direction=direction, depth=bounded_depth)
    affected_symbol_count = sum(len(nodes) for nodes in by_depth.values())
    affected_file_count = len({node["file_path"] for nodes in by_depth.values() for node in nodes})
    severity = _impact_severity(affected_symbol_count)

    return {
        "target": {
            "name": target_node["name"],
            "node_id": target_node["node_id"],
            "file_path": target_node["file_path"],
        },
        "direction": direction,
        "severity": severity,
        "summary": {
            "affected_symbol_count": affected_symbol_count,
            "affected_file_count": affected_file_count,
            "affected_skill_count": len(affected_skills),
        },
        "by_depth": {str(depth_key): nodes for depth_key, nodes in by_depth.items()},
        "affected_skills": affected_skills,
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

    def load_skill_summaries(self) -> list[dict[str, object]]:
        rows = self._rows(
            f"""
            MATCH (s:ModuleSkill)
            WHERE s.repo_id = {self._literal(self.repo_id)}
            RETURN s AS node
            ORDER BY s.name;
            """
        )
        return [self._normalize_skill_node(row["node"]) for row in rows]

    def load_skill_by_name(self, skill_name: str) -> dict[str, object] | None:
        for skill in self.load_skill_summaries():
            if skill["name"] == skill_name:
                return skill
        return None

    def load_skill_files(self, skill_id: str) -> list[str]:
        rows = self._rows(
            f"""
            MATCH (f:File)-[r:CodeRelation]->(s:ModuleSkill)
            WHERE r.type = 'BELONGS_TO_SKILL' AND s.id = {self._literal(skill_id)}
            RETURN f.file_path AS file_path
            ORDER BY f.file_path;
            """
        )
        return [str(row["file_path"]) for row in rows]

    def load_skill_symbols(self, skill_id: str) -> list[dict[str, object]]:
        symbols: list[dict[str, object]] = []
        for label in SYMBOL_LABELS:
            rows = self._rows(
                f"""
                MATCH (n:{label})-[r:CodeRelation]->(s:ModuleSkill)
                WHERE r.type = 'BELONGS_TO_SKILL' AND s.id = {self._literal(skill_id)}
                RETURN n AS node
                ORDER BY n.file_path, n.start_line, n.name;
                """
            )
            symbols.extend(self._normalize_symbol_node(row["node"]) for row in rows)
        symbols.sort(key=lambda item: (item["file_path"], item["start_line"] or 0, item["display_name"]))
        return symbols

    def load_related_skills(self, skill_id: str) -> list[str]:
        rows = self._rows(
            f"""
            MATCH (s:ModuleSkill)-[r:CodeRelation]->(related:ModuleSkill)
            WHERE r.type = 'RELATED_SKILL' AND s.id = {self._literal(skill_id)}
            RETURN related.name AS name
            ORDER BY related.name;
            """
        )
        return sorted({str(row["name"]) for row in rows})

    def find_target_candidates(self, target: str) -> list[dict[str, object]]:
        target_query = target.strip()
        matches = []
        for symbol in self._load_symbol_nodes():
            qualified_name = (
                f"{symbol['owner_name']}.{symbol['name']}"
                if symbol["owner_name"]
                else symbol["name"]
            )
            if target_query in {symbol["node_id"], symbol["name"], qualified_name}:
                matches.append(symbol)
        matches.sort(key=lambda item: (item["file_path"], item["type"], item["node_id"]))
        return matches

    def traverse_impact(
        self,
        start_node_id: str,
        *,
        direction: str,
        depth: int,
    ) -> tuple[dict[int, list[dict[str, object]]], list[str]]:
        adjacency = self.load_call_graph(direction)
        skill_by_node = self.load_skill_memberships()
        node_lookup = {
            node["node_id"]: self._normalize_symbol_node(
                {
                    "id": node["node_id"],
                    "_label": node["type"],
                    "name": node["name"],
                    "file_path": node["file_path"],
                    "start_line": node["start_line"],
                    "end_line": node["end_line"],
                    "signature": node["signature"],
                    "owner_name": node["owner_name"],
                    "is_exported": node["is_exported"],
                }
            )
            for node in self._load_symbol_nodes()
        }
        visited = {start_node_id}
        frontier = [start_node_id]
        by_depth: dict[int, list[dict[str, object]]] = {}
        affected_skills: set[str] = set()

        for current_depth in range(1, depth + 1):
            next_frontier: list[str] = []
            layer: list[dict[str, object]] = []
            for node_id in frontier:
                for neighbor_id in adjacency.get(node_id, []):
                    if neighbor_id in visited:
                        continue
                    visited.add(neighbor_id)
                    next_frontier.append(neighbor_id)
                    node = node_lookup.get(neighbor_id)
                    if node is None:
                        continue
                    skill_name = skill_by_node.get(neighbor_id)
                    if skill_name:
                        affected_skills.add(skill_name)
                    layer.append(
                        {
                            "node_id": node["node_id"],
                            "name": node["display_name"],
                            "file_path": node["file_path"],
                            "skill": skill_name,
                        }
                    )
            if not layer:
                break
            by_depth[current_depth] = sorted(layer, key=lambda item: (item["file_path"], item["name"]))
            frontier = next_frontier

        return by_depth, sorted(affected_skills)

    def build_skill_flows(self, skill_name: str, symbols: list[dict[str, object]]) -> list[str]:
        adjacency = self.load_call_graph("downstream")
        skill_by_node = self.load_skill_memberships()
        entry_points = [
            symbol
            for symbol in symbols
            if _is_entry_point_symbol(symbol["file_path"], symbol["type"], symbol["name"])
        ]
        flows: list[str] = []
        for entry_point in entry_points:
            steps = [entry_point["display_name"]]
            current_id = entry_point["node_id"]
            visited = {current_id}
            for _ in range(4):
                candidates = [
                    node_id
                    for node_id in adjacency.get(current_id, [])
                    if skill_by_node.get(node_id) in {skill_name, skill_by_node.get(current_id)}
                ]
                if not candidates:
                    break
                next_id = sorted(candidates)[0]
                if next_id in visited:
                    break
                visited.add(next_id)
                match = next((symbol for symbol in symbols if symbol["node_id"] == next_id), None)
                if match is None:
                    node = self._load_node_by_id(next_id)
                    if node is None:
                        break
                    steps.append(node["display_name"])
                else:
                    steps.append(match["display_name"])
                current_id = next_id
            if len(steps) > 1:
                flows.append(" -> ".join(steps))
        return sorted(set(flows))

    def load_call_graph(self, direction: str) -> dict[str, list[str]]:
        rows = self._rows(
            """
            MATCH (caller)-[r:CodeRelation]->(callee)
            WHERE r.type = 'CALLS'
            RETURN caller.id AS source_id, callee.id AS target_id;
            """
        )
        adjacency: dict[str, list[str]] = {}
        for row in rows:
            source_id = str(row["source_id"])
            target_id = str(row["target_id"])
            key = target_id if direction == "upstream" else source_id
            value = source_id if direction == "upstream" else target_id
            adjacency.setdefault(key, []).append(value)
        return {node_id: sorted(set(neighbors)) for node_id, neighbors in adjacency.items()}

    def load_skill_memberships(self) -> dict[str, str]:
        memberships: dict[str, str] = {}
        for label in ("File",) + SYMBOL_LABELS:
            rows = self._rows(
                f"""
                MATCH (n:{label})-[r:CodeRelation]->(s:ModuleSkill)
                WHERE r.type = 'BELONGS_TO_SKILL'
                RETURN n.id AS node_id, s.name AS skill_name;
                """
            )
            for row in rows:
                memberships[str(row["node_id"])] = str(row["skill_name"])
        return memberships

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
    def _normalize_symbol_node(node: dict[str, object]) -> dict[str, object]:
        payload = _IndexReader._normalize_node(node)
        payload["display_name"] = (
            f"{payload['owner_name']}.{payload['name']}"
            if payload["owner_name"]
            else payload["name"]
        )
        return payload

    @staticmethod
    def _normalize_skill_node(node: dict[str, object]) -> dict[str, object]:
        return {
            "node_id": node["id"],
            "name": node.get("name") or "",
            "label": node.get("label") or "",
            "summary": node.get("summary") or "",
            "generated_at": node.get("generated_at") or "",
            "file_count": int(node.get("file_count") or 0),
            "symbol_count": int(node.get("symbol_count") or 0),
            "entry_point_count": int(node.get("entry_point_count") or 0),
            "flow_count": int(node.get("flow_count") or 0),
        }

    def _load_node_by_id(self, node_id: str) -> dict[str, object] | None:
        for node in self._load_symbol_nodes():
            if node["node_id"] == node_id:
                return self._normalize_symbol_node(
                    {
                        "id": node["node_id"],
                        "_label": node["type"],
                        "name": node["name"],
                        "file_path": node["file_path"],
                        "start_line": node["start_line"],
                        "end_line": node["end_line"],
                        "signature": node["signature"],
                        "owner_name": node["owner_name"],
                        "is_exported": node["is_exported"],
                    }
                )
        return None

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


def _is_entry_point_symbol(file_path: str, kind: str, name: str) -> bool:
    file_name = Path(file_path).name
    if kind != "Function":
        return False
    return (
        file_name.startswith("api.")
        or file_name.startswith("app.")
        or "/handlers/" in f"/{file_path}/"
        or name.endswith("_handler")
        or name.endswith("Handler")
    )


def _impact_severity(affected_symbol_count: int) -> str:
    if affected_symbol_count >= 4:
        return "HIGH"
    if affected_symbol_count >= 2:
        return "MEDIUM"
    return "LOW"
