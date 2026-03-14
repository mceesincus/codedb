from __future__ import annotations

import os

from code_graph_core.gui import format_search_result, format_symbol_context, normalize_repo_path


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
