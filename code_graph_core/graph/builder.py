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
        symbols_by_file: defaultdict[str, list] = defaultdict(list)
        symbol_kinds: dict[str, str] = {}
        node_file_paths: dict[str, str] = {}
        node_names: dict[str, str] = {}
        node_owner_names: dict[str, str | None] = {}
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
            node_file_paths[file_id] = source_file.relative_path
            node_names[file_id] = Path(source_file.relative_path).name
            node_owner_names[file_id] = None

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
                symbols_by_file[source_file.relative_path].append(symbol)
                symbol_kinds[symbol.id] = symbol.kind
                node_file_paths[symbol.id] = symbol.file_path
                node_names[symbol.id] = symbol.name
                node_owner_names[symbol.id] = symbol.owner_name
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

        import_relationships, imported_files_by_source, imported_symbols_by_source, unresolved_import_count = (
            self._resolve_imports(
                imports=imports,
                file_nodes=file_nodes,
                symbols_by_file=symbols_by_file,
            )
        )
        relationships.extend(import_relationships)

        call_relationships, unresolved_call_count = self._resolve_calls(
            calls=calls,
            symbols_by_file=symbols_by_file,
            symbol_kinds=symbol_kinds,
            imported_files_by_source=imported_files_by_source,
            imported_symbols_by_source=imported_symbols_by_source,
        )
        relationships.extend(call_relationships)

        skill_nodes, skill_relationships, skill_count = self._materialize_skills(
            repo_id=repo_id,
            indexed_at=indexed_at,
            file_nodes=file_nodes,
            symbols_by_file=symbols_by_file,
            node_file_paths=node_file_paths,
            node_names=node_names,
            node_owner_names=node_owner_names,
            structural_relationships=import_relationships + call_relationships,
        )
        nodes.extend(skill_nodes)
        relationships.extend(skill_relationships)

        stats = IndexStats(
            file_count=len(extracted_files),
            node_count=len(nodes),
            edge_count=len(relationships),
            skill_count=skill_count,
            parse_error_count=sum(1 for item in extracted_files if item.parsed_file.diagnostics),
            unresolved_import_count=unresolved_import_count,
            unresolved_call_count=unresolved_call_count,
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

    def _resolve_imports(
        self,
        imports: list,
        file_nodes: dict[str, NodeRecord],
        symbols_by_file: defaultdict[str, list],
    ) -> tuple[list[RelationshipRecord], dict[str, set[str]], dict[str, dict[str, list[str]]], int]:
        relationships: list[RelationshipRecord] = []
        relationship_keys: set[tuple[str, str, str, str]] = set()
        imported_files_by_source: defaultdict[str, set[str]] = defaultdict(set)
        imported_symbols_by_source: defaultdict[str, defaultdict[str, list[str]]] = defaultdict(
            lambda: defaultdict(list)
        )
        unresolved_import_count = 0

        for record in imports:
            target_file = self._resolve_module_path(
                source_file=record.source_file,
                module_path=record.module_path,
                file_nodes=file_nodes,
            )
            if target_file is None:
                unresolved_import_count += max(1, len(record.imported_names))
                continue

            imported_files_by_source[record.source_file].add(target_file)
            self._add_relationship(
                relationships=relationships,
                relationship_keys=relationship_keys,
                relationship=RelationshipRecord(
                    from_kind="File",
                    to_kind="File",
                    from_id=self._file_id(record.source_file),
                    to_id=self._file_id(target_file),
                    type="IMPORTS",
                    reason="module_resolved",
                ),
            )

            if not record.imported_names:
                continue

            for imported_name in record.imported_names:
                matches = [
                    symbol
                    for symbol in symbols_by_file.get(target_file, [])
                    if symbol.name == imported_name
                ]
                if not matches:
                    unresolved_import_count += 1
                    continue
                for symbol in matches:
                    imported_symbols_by_source[record.source_file][imported_name].append(symbol.id)
                    self._add_relationship(
                        relationships=relationships,
                        relationship_keys=relationship_keys,
                        relationship=RelationshipRecord(
                            from_kind="File",
                            to_kind=symbol.kind,
                            from_id=self._file_id(record.source_file),
                            to_id=symbol.id,
                            type="IMPORTS",
                            reason="named_import",
                        ),
                    )

        return (
            relationships,
            {key: set(value) for key, value in imported_files_by_source.items()},
            {
                source_file: {
                    symbol_name: list(symbol_ids)
                    for symbol_name, symbol_ids in names.items()
                }
                for source_file, names in imported_symbols_by_source.items()
            },
            unresolved_import_count,
        )

    def _resolve_calls(
        self,
        calls: list,
        symbols_by_file: defaultdict[str, list],
        symbol_kinds: dict[str, str],
        imported_files_by_source: dict[str, set[str]],
        imported_symbols_by_source: dict[str, dict[str, list[str]]],
    ) -> tuple[list[RelationshipRecord], int]:
        relationships: list[RelationshipRecord] = []
        relationship_keys: set[tuple[str, str, str, str]] = set()
        unresolved_call_count = 0

        for call in calls:
            if call.source_symbol_id is None:
                unresolved_call_count += 1
                continue

            same_file_matches = [symbol.id for symbol in symbols_by_file.get(call.file_path, []) if symbol.name == call.target_name]
            explicit_import_matches = imported_symbols_by_source.get(call.file_path, {}).get(call.target_name, [])
            imported_file_matches = [
                symbol.id
                for imported_file in imported_files_by_source.get(call.file_path, set())
                for symbol in symbols_by_file.get(imported_file, [])
                if symbol.name == call.target_name
            ]

            resolution = self._pick_call_target(
                same_file_matches=same_file_matches,
                explicit_import_matches=explicit_import_matches,
                imported_file_matches=imported_file_matches,
            )
            if resolution is None:
                unresolved_call_count += 1
                continue

            target_id, reason = resolution
            target_kind = symbol_kinds.get(target_id)
            source_kind = symbol_kinds.get(call.source_symbol_id)
            if target_kind is None or source_kind is None:
                unresolved_call_count += 1
                continue

            self._add_relationship(
                relationships=relationships,
                relationship_keys=relationship_keys,
                relationship=RelationshipRecord(
                    from_kind=source_kind,
                    to_kind=target_kind,
                    from_id=call.source_symbol_id,
                    to_id=target_id,
                    type="CALLS",
                    confidence=1.0,
                    reason=reason,
                ),
            )

        return relationships, unresolved_call_count

    @staticmethod
    def _pick_call_target(
        same_file_matches: list[str],
        explicit_import_matches: list[str],
        imported_file_matches: list[str],
    ) -> tuple[str, str] | None:
        for matches, reason in (
            (same_file_matches, "same_file"),
            (explicit_import_matches, "import_scoped"),
            (imported_file_matches, "import_scoped"),
        ):
            unique_matches = sorted(set(matches))
            if len(unique_matches) == 1:
                return unique_matches[0], reason
            if len(unique_matches) > 1:
                return None
        return None

    @staticmethod
    def _resolve_module_path(
        source_file: str,
        module_path: str,
        file_nodes: dict[str, NodeRecord],
    ) -> str | None:
        if not module_path:
            return None

        source_parent = PurePosixPath(source_file).parent
        candidate_paths: list[str] = []

        if module_path.startswith("."):
            base_path = source_parent.joinpath(module_path).as_posix()
            candidate_paths.extend(
                [
                    f"{base_path}.py",
                    f"{base_path}.ts",
                    f"{base_path}.js",
                    f"{base_path}/__init__.py",
                    f"{base_path}/index.ts",
                    f"{base_path}/index.js",
                ]
            )
        else:
            module_relpath = module_path.replace(".", "/")
            candidate_paths.extend(
                [
                    source_parent.joinpath(f"{module_relpath}.py").as_posix(),
                    source_parent.joinpath(module_relpath, "__init__.py").as_posix(),
                    source_parent.joinpath(f"{module_relpath}.ts").as_posix(),
                    source_parent.joinpath(f"{module_relpath}.js").as_posix(),
                    source_parent.joinpath(module_relpath, "index.ts").as_posix(),
                    source_parent.joinpath(module_relpath, "index.js").as_posix(),
                ]
            )

        normalized_candidates = []
        for candidate in candidate_paths:
            normalized = GraphBuilder._normalize_posix_path(candidate)
            normalized_candidates.append(normalized)

        for candidate in normalized_candidates:
            if candidate in file_nodes:
                return candidate
        return None

    @staticmethod
    def _normalize_posix_path(path_value: str) -> str:
        parts: list[str] = []
        for part in PurePosixPath(path_value).parts:
            if part in {"", "."}:
                continue
            if part == "..":
                if parts:
                    parts.pop()
                continue
            parts.append(part)
        return str(PurePosixPath(*parts)) if parts else "."

    @staticmethod
    def _add_relationship(
        relationships: list[RelationshipRecord],
        relationship_keys: set[tuple[str, str, str, str]],
        relationship: RelationshipRecord,
    ) -> None:
        key = (
            relationship.from_id,
            relationship.to_id,
            relationship.type,
            relationship.reason,
        )
        if key in relationship_keys:
            return
        relationship_keys.add(key)
        relationships.append(relationship)

    def _materialize_skills(
        self,
        *,
        repo_id: str,
        indexed_at: str,
        file_nodes: dict[str, NodeRecord],
        symbols_by_file: defaultdict[str, list],
        node_file_paths: dict[str, str],
        node_names: dict[str, str],
        node_owner_names: dict[str, str | None],
        structural_relationships: list[RelationshipRecord],
    ) -> tuple[list[NodeRecord], list[RelationshipRecord], int]:
        skill_files: defaultdict[str, list[str]] = defaultdict(list)
        skill_symbols: defaultdict[str, list] = defaultdict(list)
        node_skill_names: dict[str, str] = {}

        for file_path in sorted(file_nodes):
            skill_name = self._skill_name_for_file(file_path)
            skill_files[skill_name].append(file_path)
            node_skill_names[self._file_id(file_path)] = skill_name
            for symbol in symbols_by_file.get(file_path, []):
                skill_symbols[skill_name].append(symbol)
                node_skill_names[symbol.id] = skill_name

        skill_nodes: list[NodeRecord] = []
        relationships: list[RelationshipRecord] = []
        relationship_keys: set[tuple[str, str, str, str]] = set()
        skill_ids = {skill_name: self._skill_id(repo_id, skill_name) for skill_name in skill_files}

        for skill_name in sorted(skill_files):
            files = sorted(skill_files[skill_name])
            symbols = sorted(skill_symbols.get(skill_name, []), key=lambda item: (item.file_path, item.start_line, item.name))
            entry_points = [
                symbol
                for symbol in symbols
                if self._is_entry_point_symbol(symbol.file_path, symbol.kind, symbol.name)
            ]
            flow_count = sum(
                1
                for symbol in entry_points
                if self._build_flow(
                    symbol.id,
                    structural_relationships,
                    node_names=node_names,
                    node_owner_names=node_owner_names,
                    node_skill_names=node_skill_names,
                    root_skill_name=skill_name,
                )
            )
            label = self._skill_label(skill_name)
            skill_nodes.append(
                NodeRecord(
                    kind="ModuleSkill",
                    properties={
                        "id": skill_ids[skill_name],
                        "repo_id": repo_id,
                        "name": skill_name,
                        "label": label,
                        "summary": self._skill_summary(label, len(files), len(symbols)),
                        "generated_at": indexed_at,
                        "file_count": len(files),
                        "symbol_count": len(symbols),
                        "entry_point_count": len(entry_points),
                        "flow_count": flow_count,
                    },
                )
            )

            for file_path in files:
                self._add_relationship(
                    relationships,
                    relationship_keys,
                    RelationshipRecord(
                        from_kind="File",
                        to_kind="ModuleSkill",
                        from_id=self._file_id(file_path),
                        to_id=skill_ids[skill_name],
                        type="BELONGS_TO_SKILL",
                        reason="directory_first",
                    ),
                )

            for symbol in symbols:
                self._add_relationship(
                    relationships,
                    relationship_keys,
                    RelationshipRecord(
                        from_kind=symbol.kind,
                        to_kind="ModuleSkill",
                        from_id=symbol.id,
                        to_id=skill_ids[skill_name],
                        type="BELONGS_TO_SKILL",
                        reason="directory_first",
                    ),
                )

        for relationship in structural_relationships:
            from_skill = node_skill_names.get(relationship.from_id)
            to_skill = node_skill_names.get(relationship.to_id)
            if from_skill is None or to_skill is None or from_skill == to_skill:
                continue
            self._add_relationship(
                relationships,
                relationship_keys,
                RelationshipRecord(
                    from_kind="ModuleSkill",
                    to_kind="ModuleSkill",
                    from_id=skill_ids[from_skill],
                    to_id=skill_ids[to_skill],
                    type="RELATED_SKILL",
                    reason=f"cross_skill_{relationship.type.lower()}",
                ),
            )
            self._add_relationship(
                relationships,
                relationship_keys,
                RelationshipRecord(
                    from_kind="ModuleSkill",
                    to_kind="ModuleSkill",
                    from_id=skill_ids[to_skill],
                    to_id=skill_ids[from_skill],
                    type="RELATED_SKILL",
                    reason=f"cross_skill_{relationship.type.lower()}",
                ),
            )

        return skill_nodes, relationships, len(skill_nodes)

    @staticmethod
    def _skill_name_for_file(file_path: str) -> str:
        parts = PurePosixPath(file_path).parts
        if len(parts) >= 3 and parts[0] == "src":
            base = parts[1]
        elif len(parts) == 2 and parts[0] == "src":
            base = PurePosixPath(file_path).stem
        elif len(parts) >= 2:
            base = parts[-2]
        else:
            base = PurePosixPath(file_path).stem
        normalized = base.replace("_", "-").replace(" ", "-").lower()
        return normalized or "root"

    @staticmethod
    def _skill_label(skill_name: str) -> str:
        return " ".join(part.capitalize() for part in skill_name.split("-"))

    @staticmethod
    def _skill_summary(label: str, file_count: int, symbol_count: int) -> str:
        return f"{label} module spanning {file_count} files and {symbol_count} symbols."

    @staticmethod
    def _skill_id(repo_id: str, skill_name: str) -> str:
        return f"skill:{repo_id}:{skill_name}"

    @staticmethod
    def _is_entry_point_symbol(file_path: str, kind: str, name: str) -> bool:
        file_name = PurePosixPath(file_path).name
        if kind != "Function":
            return False
        return (
            file_name.startswith("api.")
            or file_name.startswith("app.")
            or "/handlers/" in f"/{file_path}/"
            or name.endswith("_handler")
            or name.endswith("Handler")
        )

    @staticmethod
    def _build_flow(
        start_id: str,
        structural_relationships: list[RelationshipRecord],
        *,
        node_names: dict[str, str],
        node_owner_names: dict[str, str | None],
        node_skill_names: dict[str, str],
        root_skill_name: str,
    ) -> str | None:
        outgoing_by_node: defaultdict[str, list[str]] = defaultdict(list)
        for relationship in structural_relationships:
            if relationship.type != "CALLS":
                continue
            outgoing_by_node[relationship.from_id].append(relationship.to_id)

        steps = [GraphBuilder._flow_label(start_id, node_names, node_owner_names)]
        current_id = start_id
        visited = {start_id}
        for _ in range(4):
            candidates = sorted(
                {
                    node_id
                    for node_id in outgoing_by_node.get(current_id, [])
                    if node_skill_names.get(node_id) in {root_skill_name, node_skill_names.get(current_id)}
                }
            )
            if not candidates:
                break
            next_id = candidates[0]
            if next_id in visited:
                break
            visited.add(next_id)
            steps.append(GraphBuilder._flow_label(next_id, node_names, node_owner_names))
            current_id = next_id

        if len(steps) <= 1:
            return None
        return " -> ".join(steps)

    @staticmethod
    def _flow_label(node_id: str, node_names: dict[str, str], node_owner_names: dict[str, str | None]) -> str:
        owner_name = node_owner_names.get(node_id)
        name = node_names.get(node_id, node_id)
        if owner_name:
            return f"{owner_name}.{name}"
        return name
