from __future__ import annotations

from code_graph_core.ingestion.scanner import RepositoryScanner
from tests.conftest import FIXTURES_ROOT


def test_scanner_discovers_supported_files_and_ignores_noise() -> None:
    scanner = RepositoryScanner()
    files = scanner.scan(FIXTURES_ROOT / "ts_basic_app")
    relative_paths = [item.relative_path for item in files]

    assert relative_paths == [
        "src/auth/api.ts",
        "src/auth/jwt.ts",
        "src/auth/service.ts",
        "src/shared/logger.ts",
    ]


def test_scanner_marks_test_files() -> None:
    scanner = RepositoryScanner()
    files = scanner.scan(FIXTURES_ROOT / "scanner_app")
    tests = {item.relative_path: item.is_test for item in files}

    assert tests["src/example.py"] is False
    assert tests["tests/test_example.py"] is True

