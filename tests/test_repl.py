from __future__ import annotations

from pathlib import Path

from code_graph_core.repl import (
    CodeGraphRepl,
    SymbolReference,
    format_definition_payload,
    format_overview_payload,
    format_repl_help,
    format_search_payload,
    infer_repl_command,
)
from tests.conftest import FIXTURES_ROOT


def test_format_repl_help_lists_supported_commands() -> None:
    formatted = format_repl_help()

    assert "repo [path]" in formatted
    assert "context <symbol> [file_path]" in formatted
    assert "Natural-language prompts are also routed" in formatted
    assert "Any other input runs a search" in formatted


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


def test_format_definition_payload_is_compact() -> None:
    payload = {
        "symbol": {
            "type": "Function",
            "name": "create_service",
            "file_path": "src/billing/service.py",
            "start_line": 10,
            "end_line": 11,
            "signature": "def create_service():",
        }
    }

    formatted = format_definition_payload(payload)

    assert "Function create_service" in formatted
    assert "Defined at: src/billing/service.py:10-11" in formatted
    assert "Signature: def create_service():" in formatted


def test_format_overview_payload_includes_context_and_impact_summary() -> None:
    context_payload = {
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
        "callers": [{"name": "create_invoice_handler"}],
        "callees": [{"name": "save"}],
        "related_files": ["src/billing/api.py"],
    }
    impact_payload = {
        "severity": "LOW",
        "summary": {
            "affected_symbol_count": 1,
            "affected_file_count": 1,
            "affected_skill_count": 1,
        },
        "affected_skills": ["billing"],
    }

    formatted = format_overview_payload(context_payload, impact_payload)

    assert "Method generate_invoice" in formatted
    assert "Direct callers: 1" in formatted
    assert "Direct callees: 1" in formatted
    assert "Upstream impact: 1 symbols, 1 files, 1 skills" in formatted


def test_infer_repl_command_routes_common_natural_language_prompts() -> None:
    assert infer_repl_command("what calls generateInvoice?") == (
        "impact",
        ["generateInvoice", "upstream", "1"],
    )
    assert infer_repl_command("what does generateInvoice call?") == (
        "impact",
        ["generateInvoice", "downstream", "1"],
    )
    assert infer_repl_command("show context for generate_invoice in src/billing/service.py") == (
        "context",
        ["generate_invoice", "src/billing/service.py"],
    )
    assert infer_repl_command("where is generate_invoice defined?") == (
        "where",
        ["generate_invoice"],
    )
    assert infer_repl_command("what is generate_invoice?") == (
        "overview",
        ["generate_invoice"],
    )
    assert infer_repl_command("list skills") == ("skills", [])
    assert infer_repl_command("show skill billing") == ("skill", ["billing"])
    assert infer_repl_command("what is the repo status?") == ("status", [])


def test_infer_repl_command_uses_last_symbol_for_follow_ups() -> None:
    last_symbol = SymbolReference(
        name="generate_invoice",
        node_id="method:src/billing/service.py:BillingService:generate_invoice:5",
        file_path="src/billing/service.py",
        symbol_type="Method",
    )

    assert infer_repl_command("show callers", last_symbol=last_symbol) == (
        "impact",
        [last_symbol.node_id, "upstream", "1"],
    )
    assert infer_repl_command("downstream too", last_symbol=last_symbol) == (
        "impact",
        [last_symbol.node_id, "downstream", "1"],
    )
    assert infer_repl_command("show context", last_symbol=last_symbol) == (
        "context",
        [last_symbol.node_id, last_symbol.file_path],
    )
    assert infer_repl_command("where is it defined", last_symbol=last_symbol) == (
        "where",
        [last_symbol.node_id],
    )
    assert infer_repl_command("what is it", last_symbol=last_symbol) == (
        "overview",
        [last_symbol.node_id],
    )


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


def test_repl_natural_language_prompt_routes_to_impact(tmp_path: Path) -> None:
    output: list[str] = []
    repl = CodeGraphRepl(
        repo_path=str(FIXTURES_ROOT / "impact_app"),
        index_root=tmp_path / "indexes",
        output=output.append,
        show_progress=False,
    )

    response = repl.execute_line("what calls generateInvoice?")

    assert "Impact: generateInvoice" in response
    assert "direction: upstream" in response


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


def test_repl_where_command_returns_definition_location(tmp_path: Path) -> None:
    output: list[str] = []
    repl = CodeGraphRepl(
        repo_path=str(FIXTURES_ROOT / "py_basic_app"),
        index_root=tmp_path / "indexes",
        output=output.append,
        show_progress=False,
    )

    response = repl.execute_line("where generate_invoice")

    assert "Method generate_invoice" in response
    assert "Defined at: src/billing/service.py:5-7" in response


def test_repl_overview_command_combines_context_and_impact(tmp_path: Path) -> None:
    output: list[str] = []
    repl = CodeGraphRepl(
        repo_path=str(FIXTURES_ROOT / "impact_app"),
        index_root=tmp_path / "indexes",
        output=output.append,
        show_progress=False,
    )

    response = repl.execute_line("what is generateInvoice?")

    assert "Function generateInvoice" in response
    assert "Defined at: src/services/billing.ts:3-5" in response
    assert "Upstream impact:" in response


def test_repl_follow_up_prompt_uses_last_symbol(tmp_path: Path) -> None:
    output: list[str] = []
    repl = CodeGraphRepl(
        repo_path=str(FIXTURES_ROOT / "py_basic_app"),
        index_root=tmp_path / "indexes",
        output=output.append,
        show_progress=False,
    )

    first = repl.execute_line("context generate_invoice src/billing/service.py")
    second = repl.execute_line("show callers")

    assert "Method generate_invoice" in first
    assert "Impact: generate_invoice" in second
    assert "direction: upstream" in second


def test_repl_ambiguity_selection_resolves_numbered_choice(tmp_path: Path) -> None:
    output: list[str] = []
    repl = CodeGraphRepl(
        repo_path=str(FIXTURES_ROOT / "ambiguity_app"),
        index_root=tmp_path / "indexes",
        output=output.append,
        show_progress=False,
    )

    prompt = repl.execute_line("context save")
    resolved = repl.execute_line("1")

    assert "Choose one:" in prompt
    assert "1. Method in src/repos/repo.py" in prompt
    assert "2. Method in src/users/models.py" in prompt
    assert "Method save" in resolved
    assert "src/repos/repo.py" in resolved


def test_repl_overview_ambiguity_selection_uses_numbered_choice(tmp_path: Path) -> None:
    output: list[str] = []
    repl = CodeGraphRepl(
        repo_path=str(FIXTURES_ROOT / "ambiguity_app"),
        index_root=tmp_path / "indexes",
        output=output.append,
        show_progress=False,
    )

    prompt = repl.execute_line("what is save?")
    resolved = repl.execute_line("2")

    assert "Choose one:" in prompt
    assert "Method save" in resolved
    assert "src/users/models.py" in resolved


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
