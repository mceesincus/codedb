from __future__ import annotations

from pathlib import Path

from code_graph_core import get_symbol_context, index_repo, search
from tests.conftest import FIXTURES_ROOT


def test_search_prefers_exact_symbol_match_over_loose_path_match(tmp_path: Path) -> None:
    repo = FIXTURES_ROOT / "py_basic_app"
    result = index_repo(str(repo), index_root=str(tmp_path / "indexes"))

    response = search(result.repo_id, "create_service", graph_path=result.graph_path)

    assert response["results"]
    first_result = response["results"][0]
    assert first_result["name"] == "create_service"
    assert first_result["type"] == "Function"
    assert "Exact symbol match" in first_result["reason"]


def test_get_symbol_context_returns_direct_callers_and_callees_for_python_fixture(tmp_path: Path) -> None:
    repo = FIXTURES_ROOT / "py_basic_app"
    result = index_repo(str(repo), index_root=str(tmp_path / "indexes"))

    response = get_symbol_context(
        result.repo_id,
        "generate_invoice",
        file_path="src/billing/service.py",
        graph_path=result.graph_path,
    )

    assert response["symbol"]["node_id"].startswith("method:src/billing/service.py:BillingService:generate_invoice:")
    assert response["symbol"]["containing_class"] == "BillingService"
    assert response["callers"] == [
        {
            "node_id": "function:src/billing/api.py:create_invoice_handler:4",
            "name": "create_invoice_handler",
            "file_path": "src/billing/api.py",
            "confidence": 1.0,
        }
    ]
    assert response["callees"] == [
        {
            "node_id": "method:src/billing/repository.py:InvoiceRepository:save:2",
            "name": "save",
            "file_path": "src/billing/repository.py",
            "confidence": 1.0,
        }
    ]
    assert response["related_files"] == [
        "src/billing/api.py",
        "src/billing/repository.py",
    ]


def test_get_symbol_context_returns_direct_callers_and_callees_for_typescript_fixture(tmp_path: Path) -> None:
    repo = FIXTURES_ROOT / "ts_basic_app"
    result = index_repo(str(repo), index_root=str(tmp_path / "indexes"))

    response = get_symbol_context(
        result.repo_id,
        "validateToken",
        file_path="src/auth/service.ts",
        graph_path=result.graph_path,
    )

    assert response["callers"] == [
        {
            "node_id": "function:src/auth/api.ts:loginHandler:3",
            "name": "loginHandler",
            "file_path": "src/auth/api.ts",
            "confidence": 1.0,
        }
    ]
    assert response["callees"] == [
        {
            "node_id": "function:src/auth/jwt.ts:decodeJwt:1",
            "name": "decodeJwt",
            "file_path": "src/auth/jwt.ts",
            "confidence": 1.0,
        }
    ]


def test_get_symbol_context_returns_structured_ambiguity_response(tmp_path: Path) -> None:
    repo = FIXTURES_ROOT / "ambiguity_app"
    result = index_repo(str(repo), index_root=str(tmp_path / "indexes"))

    response = get_symbol_context(result.repo_id, "save", graph_path=result.graph_path)

    assert response["error"]["code"] == "AMBIGUOUS_SYMBOL"
    assert response["error"]["message"] == "Multiple symbols matched 'save'"
    assert response["error"]["details"]["candidates"] == [
        {
            "node_id": "method:src/repos/repo.py:Repo:save:2",
            "type": "Method",
            "file_path": "src/repos/repo.py",
        },
        {
            "node_id": "method:src/users/models.py:User:save:2",
            "type": "Method",
            "file_path": "src/users/models.py",
        },
    ]
