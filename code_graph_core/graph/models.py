from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from tree_sitter import Tree


NODE_KINDS = {
    "Repository",
    "Folder",
    "File",
    "Function",
    "Method",
    "Class",
    "Interface",
    "ModuleSkill",
}


@dataclass(slots=True)
class SourceFile:
    repo_path: Path
    absolute_path: Path
    relative_path: str
    language: str
    parser_name: str
    is_test: bool


@dataclass(slots=True)
class ParseDiagnostic:
    file_path: str
    message: str
    severity: str = "error"


@dataclass(slots=True)
class ParsedFile:
    source_file: SourceFile
    source_text: str
    tree: Tree
    diagnostics: list[ParseDiagnostic] = field(default_factory=list)


@dataclass(slots=True)
class ImportRecord:
    source_file: str
    module_path: str
    imported_names: list[str] = field(default_factory=list)


@dataclass(slots=True)
class CallRecord:
    source_symbol_id: str | None
    target_name: str
    file_path: str


@dataclass(slots=True)
class InheritanceRecord:
    source_symbol_id: str
    source_kind: str
    file_path: str
    target_name: str
    target_kind: str
    relation_type: str


@dataclass(slots=True)
class ExtractedSymbol:
    id: str
    kind: str
    repo_id: str
    name: str
    label: str
    file_path: str
    language: str
    start_line: int
    end_line: int
    signature: str
    visibility: str
    is_exported: bool
    owner_name: str | None = None

    def to_properties(self) -> dict[str, object]:
        properties: dict[str, object] = {
            "id": self.id,
            "repo_id": self.repo_id,
            "name": self.name,
            "file_path": self.file_path,
            "language": self.language,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "visibility": self.visibility,
            "is_exported": self.is_exported,
        }
        if self.kind in {"Function", "Method"}:
            properties["signature"] = self.signature
        if self.kind == "Method":
            properties["owner_name"] = self.owner_name or ""
        return properties


@dataclass(slots=True)
class ExtractionResult:
    parsed_file: ParsedFile
    symbols: list[ExtractedSymbol] = field(default_factory=list)
    imports: list[ImportRecord] = field(default_factory=list)
    calls: list[CallRecord] = field(default_factory=list)
    inheritance: list[InheritanceRecord] = field(default_factory=list)


@dataclass(slots=True)
class NodeRecord:
    kind: str
    properties: dict[str, object]


@dataclass(slots=True)
class RelationshipRecord:
    from_kind: str
    to_kind: str
    from_id: str
    to_id: str
    type: str
    confidence: float = 1.0
    reason: str = ""
    step: int | None = None


@dataclass(slots=True)
class IndexStats:
    file_count: int = 0
    node_count: int = 0
    edge_count: int = 0
    skill_count: int = 0
    skipped_file_count: int = 0
    parse_error_count: int = 0
    unresolved_import_count: int = 0
    unresolved_call_count: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "file_count": self.file_count,
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "skill_count": self.skill_count,
            "skipped_file_count": self.skipped_file_count,
            "parse_error_count": self.parse_error_count,
            "unresolved_import_count": self.unresolved_import_count,
            "unresolved_call_count": self.unresolved_call_count,
        }


@dataclass(slots=True)
class GraphBundle:
    repo_id: str
    repo_name: str
    repo_path: str
    indexed_at: str
    index_version: str
    nodes: list[NodeRecord]
    relationships: list[RelationshipRecord]
    stats: IndexStats
    imports: list[ImportRecord] = field(default_factory=list)
    calls: list[CallRecord] = field(default_factory=list)
