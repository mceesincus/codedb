from __future__ import annotations

from pathlib import Path

from code_graph_core.repl import CodeGraphRepl, format_repl_help, format_search_payload
from tests.conftest import FIXTURES_ROOT


def test_format_repl_help_lists_supported_commands() -> None:
    formatted = format_repl_help()

    assert "repo [path]" in formatted
    assert "context <symbol> [file_path]" in formatted
    assert "Any unrecognized input runs a search" in formatted


def test_format_search_payload_is_readable() -> None:
    payload = {
        "results": [
            {
                "type": "Function",
                "name": "create_service",
                "file_path": "src/billing/service.py",
                "start_line": 12,
                "score": 0.98,
                "reason": "Exact symbol match",
            }
        ]
    }

    formatted = format_search_payload(payload)

    assert "Search results:" in formatted
    assert "[Function] create_service (src/billing/service.py:12) score=0.98" in formatted
    assert "Exact symbol match" in formatted


def test_repl_bare_query_falls_back_to_search(tmp_path: Path) -> None:
    output: list[str] = []
    repl = CodeGraphRepl(
        repo_path=str(FIXTURES_ROOT / "py_basic_app"),
        index_root=tmp_path / "indexes",
        output=output.append,
        show_progress=False,
    )

    response = repl.execute_line("create_service")

    assert "Search results:" in response
    assert "create_service" in response


def test_repl_context_command_returns_symbol_context(tmp_path: Path) -> None:
    output: list[str] = []
    repl = CodeGraphRepl(
        repo_path=str(FIXTURES_ROOT / "py_basic_app"),
        index_root=tmp_path / "indexes",
        output=output.append,
        show_progress=False,
    )

    response = repl.execute_line("context generate_invoice src/billing/service.py")

    assert "Method generate_invoice" in response
    assert "BillingService" in response
    assert "Callers:" in response


def test_repl_skills_and_impact_commands_use_existing_apis(tmp_path: Path) -> None:
    output: list[str] = []
    skills_repl = CodeGraphRepl(
        repo_path=str(FIXTURES_ROOT / "multi_skill_app"),
        index_root=tmp_path / "indexes",
        output=output.append,
        show_progress=False,
    )
    impact_repl = CodeGraphRepl(
        repo_path=str(FIXTURES_ROOT / "impact_app"),
        index_root=tmp_path / "indexes",
        output=output.append,
        show_progress=False,
    )

    skills_response = skills_repl.execute_line("skills")
    impact_response = impact_repl.execute_line("impact generateInvoice upstream 2")

    assert "Skills:" in skills_response
    assert "billing" in skills_response
    assert "Impact: generateInvoice" in impact_response
    assert "severity:" in impact_response
