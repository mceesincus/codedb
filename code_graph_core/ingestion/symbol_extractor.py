from __future__ import annotations

from code_graph_core.graph.models import ExtractionResult, ParsedFile
from code_graph_core.languages.python import PythonExtractor
from code_graph_core.languages.typescript import TypeScriptExtractor


class SymbolExtractor:
    def __init__(self) -> None:
        self._extractors = {
            "python": PythonExtractor(),
            "typescript": TypeScriptExtractor(),
            "javascript": TypeScriptExtractor(),
        }

    def extract(self, parsed_file: ParsedFile) -> ExtractionResult:
        extractor = self._extractors[parsed_file.source_file.language]
        return extractor.extract(parsed_file)

