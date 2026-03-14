from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path, PurePosixPath

from code_graph_core.graph.models import (
    ExtractionResult,
    GraphBundle,
    IndexStats,
    NodeRecord,
    RelationshipRecord,
)


class GraphBuilder:
    index_version = "v1"

    def build(self, repo_path: Path, extracted_files: list[ExtractionResult]) -> GraphBundle:
        repo_id = f"repo:{sha256(str(repo_path).encode('utf-8')).hexdigest()[:16]}"
        indexed_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")

        nodes: list[NodeRecord] = [
            NodeRecord(
                kind="Repository",
                properties={
                    "id": repo_id,
                    "name": repo_path.name,
                    "repo_path": str(repo_path),
                    "indexed_at": indexed_at,
                    "index_version": self.index_version,
                },
            )
        ]
        relationships: list[RelationshipRecord] = []

        folder_ids: dict[str, str] = {}
        file_nodes: dict[str, NodeRecord] = {}
        file_to_symbols: defaultdict[str, list[tuple[str, str]]] = defaultdict(list)
        class_ids: dict[tuple[str, str], str] = {}
        class_to_methods: defaultdict[str, list[str]] = defaultdict(list)

        root_folder_id = self._folder_id(".")
        folder_ids["."] = root_folder_id
        nodes.append(
            NodeRecord(
                kind="Folder",
                properties={
                    "id": root_folder_id,
                    "repo_id": repo_id,
                    "name": repo_path.name,
                    "file_path": ".",
                },
            )
        )
        relationships.append(
            RelationshipRecord(
                from_kind="Repository",
                to_kind="Folder",
                from_id=repo_id,
                to_id=root_folder_id,
                type="CONTAINS",
                reason="filesystem_root",
            )
        )

        imports = []
        calls = []

        for extracted in extracted_files:
            source_file = extracted.parsed_file.source_file
            imports.extend(extracted.imports)
            calls.extend(extracted.calls)

            file_id = self._file_id(source_file.relative_path)
            file_nodes[source_file.relative_path] = NodeRecord(
                kind="File",
                properties={
                    "id": file_id,
                    "repo_id": repo_id,
                    "name": Path(source_file.relative_path).name,
                    "file_path": source_file.relative_path,
                    "language": source_file.language,
                    "is_test": source_file.is_test,
                },
            )

            for folder_path in self._folder_paths(source_file.relative_path):
                if folder_path not in folder_ids:
                    folder_ids[folder_path] = self._folder_id(folder_path)
                    nodes.append(
                        NodeRecord(
                            kind="Folder",
                            properties={
                                "id": folder_ids[folder_path],
                                "repo_id": repo_id,
                                "name": PurePosixPath(folder_path).name,
                                "file_path": folder_path,
                            },
                        )
                    )
                    parent_path = str(PurePosixPath(folder_path).parent)
                    parent_path = "." if parent_path == "." else parent_path
                    parent_id = folder_ids[parent_path]
                    relationships.append(
                        RelationshipRecord(
                            from_kind="Folder",
                            to_kind="Folder",
                            from_id=parent_id,
                            to_id=folder_ids[folder_path],
                            type="CONTAINS",
                            reason="filesystem",
                        )
                    )

            folder_path = str(PurePosixPath(source_file.relative_path).parent)
            folder_path = "." if folder_path == "." else folder_path
            relationships.append(
                RelationshipRecord(
                    from_kind="Folder",
                    to_kind="File",
                    from_id=folder_ids[folder_path],
                    to_id=file_id,
                    type="CONTAINS",
                    reason="filesystem",
                )
            )

            for symbol in extracted.symbols:
                nodes.append(NodeRecord(kind=symbol.kind, properties=symbol.to_properties()))
                file_to_symbols[source_file.relative_path].append((symbol.kind, symbol.id))
                if symbol.kind == "Class":
                    class_ids[(symbol.file_path, symbol.name)] = symbol.id
                if symbol.kind == "Method" and symbol.owner_name:
                    class_id = class_ids.get((symbol.file_path, symbol.owner_name))
                    if class_id is None:
                        continue
                    class_to_methods[class_id].append(symbol.id)

        nodes.extend(file_nodes.values())

        for file_path, symbol_refs in file_to_symbols.items():
            file_id = self._file_id(file_path)
            for symbol_kind, symbol_id in symbol_refs:
                if symbol_kind == "Method":
                    continue
                relationships.append(
                    RelationshipRecord(
                        from_kind="File",
                        to_kind=symbol_kind,
                        from_id=file_id,
                        to_id=symbol_id,
                        type="DEFINES",
                        reason="ast",
                    )
                )

        for class_id, method_ids in class_to_methods.items():
            for method_id in method_ids:
                relationships.append(
                    RelationshipRecord(
                        from_kind="Class",
                        to_kind="Method",
                        from_id=class_id,
                        to_id=method_id,
                        type="HAS_METHOD",
                        reason="ast",
                    )
                )

        stats = IndexStats(
            file_count=len(extracted_files),
            node_count=len(nodes),
            edge_count=len(relationships),
            parse_error_count=sum(1 for item in extracted_files if item.parsed_file.diagnostics),
        )

        return GraphBundle(
            repo_id=repo_id,
            repo_name=repo_path.name,
            repo_path=str(repo_path),
            indexed_at=indexed_at,
            index_version=self.index_version,
            nodes=nodes,
            relationships=relationships,
            stats=stats,
            imports=imports,
            calls=calls,
        )

    @staticmethod
    def _folder_paths(file_path: str) -> list[str]:
        parent = PurePosixPath(file_path).parent
        if str(parent) == ".":
            return []
        current = PurePosixPath(".")
        folders: list[str] = []
        for part in parent.parts:
            current = current / part if str(current) != "." else PurePosixPath(part)
            folders.append(str(current))
        return folders

    @staticmethod
    def _folder_id(folder_path: str) -> str:
        return f"folder:{folder_path}"

    @staticmethod
    def _file_id(file_path: str) -> str:
        return f"file:{file_path}"
