from __future__ import annotations

from code_graph_core.ingestion.parser import ParserRegistry
from code_graph_core.ingestion.scanner import RepositoryScanner
from code_graph_core.ingestion.symbol_extractor import SymbolExtractor
from tests.conftest import FIXTURES_ROOT


def test_typescript_extraction_finds_classes_functions_and_methods() -> None:
    repo = FIXTURES_ROOT / "ts_basic_app"
    scanner = RepositoryScanner()
    parser = ParserRegistry()
    extractor = SymbolExtractor()

    service_file = next(item for item in scanner.scan(repo) if item.relative_path == "src/auth/service.ts")
    extraction = extractor.extract(parser.parse_file(service_file))

    symbol_names = {(symbol.kind, symbol.name) for symbol in extraction.symbols}
    assert ("Class", "AuthService") in symbol_names
    assert ("Method", "validateToken") in symbol_names
    assert ("Function", "buildAuthService") in symbol_names
    assert extraction.imports[0].module_path == "./jwt"


def test_python_extraction_finds_classes_functions_and_methods() -> None:
    repo = FIXTURES_ROOT / "py_basic_app"
    scanner = RepositoryScanner()
    parser = ParserRegistry()
    extractor = SymbolExtractor()

    service_file = next(item for item in scanner.scan(repo) if item.relative_path == "src/billing/service.py")
    extraction = extractor.extract(parser.parse_file(service_file))

    symbol_names = {(symbol.kind, symbol.name) for symbol in extraction.symbols}
    assert ("Class", "BillingService") in symbol_names
    assert ("Method", "generate_invoice") in symbol_names
    assert ("Function", "create_service") in symbol_names
    assert extraction.imports[0].module_path == "repository"

