from __future__ import annotations

from pathlib import Path

from code_graph_core import (
    get_impact,
    get_repo_status,
    get_skill,
    get_symbol_context,
    index_repo,
    list_skills,
    search,
)
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


def test_get_repo_status_returns_metadata_summary(tmp_path: Path) -> None:
    repo = FIXTURES_ROOT / "py_basic_app"
    result = index_repo(str(repo), index_root=str(tmp_path / "indexes"))

    response = get_repo_status(result.repo_id, metadata_path=result.metadata_path)

    assert response["repo_id"] == result.repo_id
    assert response["repo_name"] == "py_basic_app"
    assert response["index_version"] == "v1"
    assert response["languages_detected"] == ["python"]
    assert response["stats"]["file_count"] == 3


def test_list_skills_and_get_skill_return_stable_skill_objects(tmp_path: Path) -> None:
    repo = FIXTURES_ROOT / "multi_skill_app"
    result = index_repo(str(repo), index_root=str(tmp_path / "indexes"))

    listed = list_skills(result.repo_id, graph_path=result.graph_path)
    detail = get_skill(result.repo_id, "billing", graph_path=result.graph_path)

    assert [skill["name"] for skill in listed["skills"]] == ["auth", "billing", "notifications"]
    assert detail["name"] == "billing"
    assert "src/billing/api.ts" in detail["key_files"]
    assert "createInvoiceHandler" in detail["entry_points"]
    assert "notifications" in detail["related_skills"]
    assert detail["stats"]["file_count"] == 2
    assert detail["stats"]["symbol_count"] >= 2
    assert detail["flows"]


def test_get_impact_groups_upstream_results_by_depth(tmp_path: Path) -> None:
    repo = FIXTURES_ROOT / "impact_app"
    result = index_repo(str(repo), index_root=str(tmp_path / "indexes"))

    response = get_impact(
        result.repo_id,
        "generateInvoice",
        direction="upstream",
        depth=2,
        graph_path=result.graph_path,
    )

    assert response["target"]["name"] == "generateInvoice"
    assert response["direction"] == "upstream"
    assert sorted(node["name"] for node in response["by_depth"]["1"]) == [
        "createInvoiceHandler",
        "retryInvoiceGeneration",
    ]
    assert response["by_depth"]["2"] == [
        {
            "node_id": "function:src/app.ts:runInvoice:3",
            "name": "runInvoice",
            "file_path": "src/app.ts",
            "skill": "app",
        }
    ]
