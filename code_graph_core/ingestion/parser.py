from __future__ import annotations

from tree_sitter_language_pack import get_parser

from code_graph_core.graph.models import ParseDiagnostic, ParsedFile, SourceFile


class ParserRegistry:
    def __init__(self) -> None:
        self._parsers: dict[str, object] = {}

    def parse_file(self, source_file: SourceFile) -> ParsedFile:
        parser = self._get_parser(source_file.parser_name)
        source_text = source_file.absolute_path.read_text(encoding="utf-8")
        tree = parser.parse(source_text.encode("utf-8"))
        diagnostics = []
        if tree.root_node.has_error:
            diagnostics.append(
                ParseDiagnostic(
                    file_path=source_file.relative_path,
                    message="Tree-sitter reported parse errors.",
                )
            )
        return ParsedFile(source_file=source_file, source_text=source_text, tree=tree, diagnostics=diagnostics)

    def _get_parser(self, parser_name: str):
        if parser_name not in self._parsers:
            self._parsers[parser_name] = get_parser(parser_name)
        return self._parsers[parser_name]

