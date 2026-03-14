from __future__ import annotations

import json
import os
from pathlib import Path

from code_graph_core import index_repo
from code_graph_core.client_support import (
    classify_index_freshness,
    format_impact,
    format_index_progress,
    format_search_result,
    format_skill_detail,
    format_skills_list,
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
        "skill": "billing",
    }

    assert (
        format_search_result(result)
        == "[Method] generate_invoice (src/billing/service.py:5) score=0.93 skill=billing"
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
            "skill": "billing",
        },
        "callers": [
            {
                "name": "create_invoice_handler",
                "file_path": "src/billing/api.py",
                "confidence": 1.0,
            }
        ],
        "callees": [],
        "dependencies": ["src/billing/repository.py"],
        "related_files": ["src/billing/api.py"],
    }

    formatted = format_symbol_context(payload)

    assert "Method generate_invoice" in formatted
    assert "skill: billing" in formatted
    assert "class: BillingService" in formatted
    assert "Callers:" in formatted
    assert "- create_invoice_handler (src/billing/api.py, confidence=1.0)" in formatted
    assert "Dependencies:" in formatted
    assert "- src/billing/repository.py" in formatted
    assert "Callees:" in formatted
    assert "Related files:" in formatted


def test_format_skills_list_is_readable() -> None:
    payload = {
        "skills": [
            {
                "name": "billing",
                "label": "Billing",
                "summary": "Billing module spanning 2 files and 3 symbols.",
                "file_count": 2,
                "symbol_count": 3,
            }
        ]
    }

    formatted = format_skills_list(payload)

    assert "Skills:" in formatted
    assert "- Billing (billing): Billing module spanning 2 files and 3 symbols." in formatted


def test_format_skill_detail_includes_sections() -> None:
    payload = {
        "name": "billing",
        "label": "Billing",
        "summary": "Billing module spanning 2 files and 3 symbols.",
        "key_files": ["src/billing/api.ts"],
        "key_symbols": ["createInvoiceHandler"],
        "entry_points": ["createInvoiceHandler"],
        "flows": ["createInvoiceHandler -> BillingService.generateInvoice"],
        "related_skills": ["notifications"],
        "generated_at": "2026-03-14T10:00:00Z",
        "stats": {"file_count": 2, "symbol_count": 3, "entry_point_count": 1, "flow_count": 1},
    }

    formatted = format_skill_detail(payload)

    assert "Billing (billing)" in formatted
    assert "Key files:" in formatted
    assert "Flows:" in formatted
    assert "Related skills:" in formatted


def test_format_impact_includes_summary() -> None:
    payload = {
        "target": {"name": "generateInvoice"},
        "direction": "upstream",
        "severity": "HIGH",
        "summary": {"affected_symbol_count": 3, "affected_file_count": 3, "affected_skill_count": 2},
        "by_depth": {
            "1": [
                {
                    "name": "createInvoiceHandler",
                    "file_path": "src/handlers/invoice.ts",
                    "skill": "handlers",
                }
            ]
        },
        "affected_skills": ["handlers", "jobs"],
    }

    formatted = format_impact(payload)

    assert "Impact: generateInvoice" in formatted
    assert "severity: HIGH" in formatted
    assert "By depth:" in formatted
    assert "- createInvoiceHandler (src/handlers/invoice.ts, skill=handlers)" in formatted


def test_format_index_progress_reports_percent() -> None:
    class Progress:
        phase = "parse"
        current = 5
        total = 20
        message = "Parsing src/example.ts (5/20)"

    formatted = format_index_progress(Progress())

    assert formatted == "Parse 5/20 (25%) | Parsing src/example.ts (5/20)"


def test_load_existing_index_state_reads_persisted_index(tmp_path: Path) -> None:
    repo = FIXTURES_ROOT / "py_basic_app"
    result = index_repo(str(repo), index_root=str(tmp_path / "indexes"))

    state = load_existing_index_state(repo.resolve(), tmp_path / "indexes")

    assert state is not None
    assert state.repo_id == result.repo_id
    assert state.graph_path == result.graph_path
    assert state.metadata_path == result.metadata_path
    assert state.stats["file_count"] == 3
    assert state.freshness_status == "CURRENT"


def test_classify_index_freshness_detects_stale_metadata(tmp_path: Path) -> None:
    repo = FIXTURES_ROOT / "py_basic_app"
    result = index_repo(str(repo), index_root=str(tmp_path / "indexes"))
    metadata_path = Path(result.metadata_path)
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["source_last_modified_at"] = "2000-01-01T00:00:00Z"
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")

    assert classify_index_freshness(repo.resolve(), metadata) == "STALE"
