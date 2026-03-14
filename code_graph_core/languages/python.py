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


class PythonExtractor:
    language = "python"

    def extract(self, parsed_file: ParsedFile) -> ExtractionResult:
        repo_id = self._repo_id(parsed_file)
        source_file = parsed_file.source_file
        result = ExtractionResult(parsed_file=parsed_file)
        root = parsed_file.tree.root_node

        for child in root.children:
            if child.type == "import_statement":
                result.imports.extend(self._extract_import_statement(child, parsed_file))
            elif child.type == "import_from_statement":
                result.imports.append(self._extract_import_from_statement(child, parsed_file))
            elif child.type == "function_definition":
                result.symbols.append(
                    self._make_symbol(
                        node=child,
                        parsed_file=parsed_file,
                        repo_id=repo_id,
                        kind="Function",
                        name_node=child.child_by_field_name("name") or child.children[1],
                        is_exported=True,
                    )
                )
            elif child.type == "class_definition":
                class_name_node = child.child_by_field_name("name") or child.children[1]
                class_name = child_text(class_name_node, parsed_file.source_text)
                class_symbol = self._make_symbol(
                    node=child,
                    parsed_file=parsed_file,
                    repo_id=repo_id,
                    kind="Class",
                    name_node=class_name_node,
                    is_exported=True,
                )
                result.symbols.append(class_symbol)
                result.inheritance.extend(self._extract_class_inheritance(class_symbol.id, child, parsed_file))
                block = child.child_by_field_name("body") or child.children[-1]
                for member in block.children:
                    if member.type == "function_definition":
                        result.symbols.append(
                            self._make_symbol(
                                node=member,
                                parsed_file=parsed_file,
                                repo_id=repo_id,
                                kind="Method",
                                name_node=member.child_by_field_name("name") or member.children[1],
                                is_exported=False,
                                owner_name=class_name,
                            )
                        )

        result.calls.extend(self._extract_calls(parsed_file, result.symbols))
        return result

    def _extract_class_inheritance(
        self,
        source_symbol_id: str,
        node: Node,
        parsed_file: ParsedFile,
    ) -> list[InheritanceRecord]:
        header = compact_signature(node, parsed_file.source_text)
        match = re.search(r"class\s+[A-Za-z_][A-Za-z0-9_]*\((?P<bases>[^)]*)\)", header)
        if match is None:
            return []
        return [
            InheritanceRecord(
                source_symbol_id=source_symbol_id,
                source_kind="Class",
                file_path=parsed_file.source_file.relative_path,
                target_name=base_name,
                target_kind="Class",
                relation_type="EXTENDS",
            )
            for base_name in extract_type_references(match.group("bases"))
            if base_name != "object"
        ]

    def _extract_import_statement(self, node: Node, parsed_file: ParsedFile) -> list[ImportRecord]:
        imports = []
        for child in node.children:
            if child.type == "dotted_name":
                imports.append(
                    ImportRecord(
                        source_file=parsed_file.source_file.relative_path,
                        module_path=child_text(child, parsed_file.source_text),
                    )
                )
        return imports

    def _extract_import_from_statement(self, node: Node, parsed_file: ParsedFile) -> ImportRecord:
        dotted_names = [child for child in node.children if child.type == "dotted_name"]
        module_name = child_text(dotted_names[0], parsed_file.source_text) if dotted_names else ""
        imported_names = [child_text(dotted_names[1], parsed_file.source_text)] if len(dotted_names) > 1 else []
        return ImportRecord(
            source_file=parsed_file.source_file.relative_path,
            module_path=module_name,
            imported_names=imported_names,
        )

    def _extract_calls(self, parsed_file: ParsedFile, symbols: list[ExtractedSymbol]) -> list[CallRecord]:
        by_line = sorted(
            symbols,
            key=lambda item: (item.start_line, -(item.end_line - item.start_line)),
        )
        calls: list[CallRecord] = []
        for node in walk(parsed_file.tree.root_node):
            if node.type == "call":
                start_line = node.start_point.row + 1
                symbol_id = self._symbol_for_line(by_line, start_line)
                function_node = node.child_by_field_name("function") or (node.children[0] if node.children else None)
                target_name = normalize_call_target(child_text(function_node, parsed_file.source_text))
                calls.append(
                    CallRecord(
                        source_symbol_id=symbol_id,
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
        name = child_text(name_node, parsed_file.source_text)
        start_line, end_line = line_span(node)
        file_path = parsed_file.source_file.relative_path
        if kind == "Function":
            symbol_id = f"function:{file_path}:{name}:{start_line}"
        elif kind == "Method":
            symbol_id = f"method:{file_path}:{owner_name}:{name}:{start_line}"
        else:
            symbol_id = f"class:{file_path}:{name}:{start_line}"
        return ExtractedSymbol(
            id=symbol_id,
            kind=kind,
            repo_id=repo_id,
            name=name,
            label=name,
            file_path=file_path,
            language=self.language,
            start_line=start_line,
            end_line=end_line,
            signature=compact_signature(node, parsed_file.source_text),
            visibility="public",
            is_exported=is_exported,
            owner_name=owner_name,
        )

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
