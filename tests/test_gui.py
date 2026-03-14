from __future__ import annotations

import os
from pathlib import Path

from code_graph_core import index_repo
from code_graph_core.gui import (
    format_search_result,
    format_symbol_context,
    load_existing_index_state,
    normalize_repo_path,
)
from tests.conftest import FIXTURES_ROOT


def test_normalize_repo_path_converts_windows_path_on_posix() -> None:
    repo_path = normalize_repo_path(r"C:\work\india\mssrc")

    if os.name == "nt":
        assert str(repo_path).lower().endswith(r"c:\work\india\mssrc")
    else:
        assert str(repo_path) == "/mnt/c/work/india/mssrc"


def test_format_search_result_is_compact_and_stable() -> None:
    result = {
        "type": "Method",
        "name": "generate_invoice",
        "file_path": "src/billing/service.py",
        "start_line": 5,
        "score": 0.93,
    }

    assert (
        format_search_result(result)
        == "[Method] generate_invoice (src/billing/service.py:5) score=0.93"
    )


def test_format_symbol_context_includes_key_sections() -> None:
    payload = {
        "symbol": {
            "type": "Method",
            "name": "generate_invoice",
            "node_id": "method:src/billing/service.py:BillingService:generate_invoice:5",
            "file_path": "src/billing/service.py",
            "start_line": 5,
            "end_line": 7,
            "containing_class": "BillingService",
            "signature": "def generate_invoice(self, order_id: str):",
        },
        "callers": [
            {
                "name": "create_invoice_handler",
                "file_path": "src/billing/api.py",
                "confidence": 1.0,
            }
        ],
        "callees": [],
        "related_files": ["src/billing/api.py"],
    }

    formatted = format_symbol_context(payload)

    assert "Method generate_invoice" in formatted
    assert "class: BillingService" in formatted
    assert "Callers:" in formatted
    assert "- create_invoice_handler (src/billing/api.py, confidence=1.0)" in formatted
    assert "Callees:" in formatted
    assert "Related files:" in formatted


def test_load_existing_index_state_reads_persisted_index(tmp_path: Path) -> None:
    repo = FIXTURES_ROOT / "py_basic_app"
    result = index_repo(str(repo), index_root=str(tmp_path / "indexes"))

    state = load_existing_index_state(repo.resolve(), tmp_path / "indexes")

    assert state is not None
    assert state.repo_id == result.repo_id
    assert state.graph_path == result.graph_path
    assert state.metadata_path == result.metadata_path
    assert state.stats["file_count"] == 3
