from __future__ import annotations

from hashlib import sha256

from tree_sitter import Node

import re

from code_graph_core.graph.models import (
    CallRecord,
    ExtractedSymbol,
    ExtractionResult,
    ImportRecord,
    InheritanceRecord,
    ParsedFile,
)
from code_graph_core.languages.shared import (
    child_text,
    compact_signature,
    extract_type_references,
    line_span,
    normalize_call_target,
    walk,
)


class TypeScriptExtractor:
    def extract(self, parsed_file: ParsedFile) -> ExtractionResult:
        repo_id = self._repo_id(parsed_file)
        result = ExtractionResult(parsed_file=parsed_file)

        for child in parsed_file.tree.root_node.children:
            if child.type == "import_statement":
                result.imports.append(self._extract_import(child, parsed_file))
                continue

            node, is_exported = self._unwrap_export(child)
            if node is None:
                continue

            if node.type == "function_declaration":
                name_node = node.child_by_field_name("name") or node.children[1]
                result.symbols.append(
                    self._make_symbol(
                        node=node,
                        parsed_file=parsed_file,
                        repo_id=repo_id,
                        kind="Function",
                        name_node=name_node,
                        is_exported=is_exported,
                    )
                )
            elif node.type == "class_declaration":
                class_name_node = node.child_by_field_name("name") or node.children[1]
                class_name = child_text(class_name_node, parsed_file.source_text)
                result.symbols.append(
                    self._make_symbol(
                        node=node,
                        parsed_file=parsed_file,
                        repo_id=repo_id,
                        kind="Class",
                        name_node=class_name_node,
                        is_exported=is_exported,
                    )
                )
                class_symbol = result.symbols[-1]
                result.inheritance.extend(self._extract_class_relationships(class_symbol.id, node, parsed_file))
                body = node.child_by_field_name("body") or node.children[-1]
                for member in body.children:
                    if member.type == "method_definition":
                        name_node = member.child_by_field_name("name")
                        if name_node is None:
                            continue
                        result.symbols.append(
                            self._make_symbol(
                                node=member,
                                parsed_file=parsed_file,
                                repo_id=repo_id,
                                kind="Method",
                                name_node=name_node,
                                is_exported=is_exported,
                                owner_name=class_name,
                            )
                        )
            elif node.type == "interface_declaration":
                name_node = node.child_by_field_name("name") or node.children[1]
                result.symbols.append(
                    self._make_symbol(
                        node=node,
                        parsed_file=parsed_file,
                        repo_id=repo_id,
                        kind="Interface",
                        name_node=name_node,
                        is_exported=is_exported,
                    )
                )
                interface_symbol = result.symbols[-1]
                result.inheritance.extend(
                    self._extract_interface_relationships(interface_symbol.id, node, parsed_file)
                )

        result.calls.extend(self._extract_calls(parsed_file, result.symbols))
        return result

    def _extract_class_relationships(
        self,
        source_symbol_id: str,
        node: Node,
        parsed_file: ParsedFile,
    ) -> list[InheritanceRecord]:
        header = compact_signature(node, parsed_file.source_text)
        relationships: list[InheritanceRecord] = []

        extends_match = re.search(r"\bextends\s+(?P<targets>.+?)(?:\bimplements\b|\{)", header)
        if extends_match is not None:
            for target_name in extract_type_references(extends_match.group("targets")):
                relationships.append(
                    InheritanceRecord(
                        source_symbol_id=source_symbol_id,
                        source_kind="Class",
                        file_path=parsed_file.source_file.relative_path,
                        target_name=target_name,
                        target_kind="Class",
                        relation_type="EXTENDS",
                    )
                )

        implements_match = re.search(r"\bimplements\s+(?P<targets>.+?)(?:\{)?$", header)
        if implements_match is not None:
            for target_name in extract_type_references(implements_match.group("targets")):
                relationships.append(
                    InheritanceRecord(
                        source_symbol_id=source_symbol_id,
                        source_kind="Class",
                        file_path=parsed_file.source_file.relative_path,
                        target_name=target_name,
                        target_kind="Interface",
                        relation_type="IMPLEMENTS",
                    )
                )

        return relationships

    def _extract_interface_relationships(
        self,
        source_symbol_id: str,
        node: Node,
        parsed_file: ParsedFile,
    ) -> list[InheritanceRecord]:
        header = compact_signature(node, parsed_file.source_text)
        extends_match = re.search(r"\bextends\s+(?P<targets>.+?)(?:\{)?$", header)
        if extends_match is None:
            return []
        return [
            InheritanceRecord(
                source_symbol_id=source_symbol_id,
                source_kind="Interface",
                file_path=parsed_file.source_file.relative_path,
                target_name=target_name,
                target_kind="Interface",
                relation_type="EXTENDS",
            )
            for target_name in extract_type_references(extends_match.group("targets"))
        ]

    def _extract_import(self, node: Node, parsed_file: ParsedFile) -> ImportRecord:
        module_node = next((child for child in node.children if child.type == "string"), None)
        import_clause = next((child for child in node.children if child.type == "import_clause"), None)
        imported_names: list[str] = []
        if import_clause is not None:
            for named_child in import_clause.named_children:
                imported_names.extend(self._normalize_import_names(child_text(named_child, parsed_file.source_text)))
        return ImportRecord(
            source_file=parsed_file.source_file.relative_path,
            module_path=child_text(module_node, parsed_file.source_text).strip("\"'"),
            imported_names=imported_names,
        )

    def _extract_calls(self, parsed_file: ParsedFile, symbols: list[ExtractedSymbol]) -> list[CallRecord]:
        by_line = sorted(
            symbols,
            key=lambda item: (item.start_line, -(item.end_line - item.start_line)),
        )
        calls: list[CallRecord] = []
        for node in walk(parsed_file.tree.root_node):
            if node.type == "call_expression":
                start_line = node.start_point.row + 1
                source_symbol_id = self._symbol_for_line(by_line, start_line)
                function_node = node.child_by_field_name("function") or (node.children[0] if node.children else None)
                target_name = normalize_call_target(child_text(function_node, parsed_file.source_text))
                calls.append(
                    CallRecord(
                        source_symbol_id=source_symbol_id,
                        target_name=target_name,
                        file_path=parsed_file.source_file.relative_path,
                    )
                )
        return calls

    def _make_symbol(
        self,
        node: Node,
        parsed_file: ParsedFile,
        repo_id: str,
        kind: str,
        name_node: Node,
        is_exported: bool,
        owner_name: str | None = None,
    ) -> ExtractedSymbol:
        file_path = parsed_file.source_file.relative_path
        name = child_text(name_node, parsed_file.source_text)
        start_line, end_line = line_span(node)
        if kind == "Function":
            symbol_id = f"function:{file_path}:{name}:{start_line}"
        elif kind == "Method":
            symbol_id = f"method:{file_path}:{owner_name}:{name}:{start_line}"
        elif kind == "Interface":
            symbol_id = f"interface:{file_path}:{name}:{start_line}"
        else:
            symbol_id = f"class:{file_path}:{name}:{start_line}"

        return ExtractedSymbol(
            id=symbol_id,
            kind=kind,
            repo_id=repo_id,
            name=name,
            label=name,
            file_path=file_path,
            language=parsed_file.source_file.language,
            start_line=start_line,
            end_line=end_line,
            signature=compact_signature(node, parsed_file.source_text),
            visibility="exported" if is_exported else "local",
            is_exported=is_exported,
            owner_name=owner_name,
        )

    @staticmethod
    def _unwrap_export(node: Node) -> tuple[Node | None, bool]:
        if node.type == "export_statement":
            for child in node.children:
                if child.type not in {"export", "default"}:
                    return child, True
            return None, True
        return node, False

    @staticmethod
    def _repo_id(parsed_file: ParsedFile) -> str:
        return f"repo:{sha256(str(parsed_file.source_file.repo_path).encode('utf-8')).hexdigest()[:16]}"

    @staticmethod
    def _symbol_for_line(symbols: list[ExtractedSymbol], line: int) -> str | None:
        candidates = [
            symbol
            for symbol in symbols
            if symbol.start_line <= line <= symbol.end_line
        ]
        if not candidates:
            return None
        best_match = min(candidates, key=lambda item: (item.end_line - item.start_line, item.start_line))
        return best_match.id

    @staticmethod
    def _normalize_import_names(raw_name: str) -> list[str]:
        cleaned = raw_name.strip()
        if cleaned.startswith("{") and cleaned.endswith("}"):
            cleaned = cleaned[1:-1]
        if not cleaned:
            return []
        names: list[str] = []
        for chunk in cleaned.split(","):
            token = chunk.strip()
            if not token:
                continue
            if " as " in token:
                token = token.split(" as ", 1)[1].strip()
            names.append(token)
        return names
