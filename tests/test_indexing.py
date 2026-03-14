from __future__ import annotations

from pathlib import Path

from code_graph_core import index_repo
from code_graph_core.storage.kuzu_store import KuzuStore
from code_graph_core.storage.metadata import load_metadata
from tests.conftest import FIXTURES_ROOT


def test_index_repo_persists_graph_and_metadata(tmp_path: Path) -> None:
    repo = FIXTURES_ROOT / "py_basic_app"
    result = index_repo(str(repo), index_root=str(tmp_path / "indexes"))

    metadata = load_metadata(Path(result.metadata_path))
    store = KuzuStore(Path(result.graph_path))

    assert result.repo_id.startswith("repo:")
    assert ":" not in Path(result.graph_path).parent.name
    assert metadata["repo_id"] == result.repo_id
    assert metadata["file_count"] == 3
    assert metadata["node_count"] == result.stats["node_count"]
    assert metadata["source_last_modified_at"]
    assert metadata["unresolved_import_count"] == 0
    assert metadata["unresolved_call_count"] == 0
    assert store.table_count("Repository") == 1
    assert store.table_count("File") == 3
    assert store.table_count("Class") >= 1
    assert store.table_count("Method") >= 1


def test_index_repo_handles_parse_errors_without_crashing(tmp_path: Path) -> None:
    repo = FIXTURES_ROOT / "broken_app"
    result = index_repo(str(repo), index_root=str(tmp_path / "indexes"))

    metadata = load_metadata(Path(result.metadata_path))
    assert result.stats["file_count"] == 1
    assert metadata["parse_error_count"] == 1


def test_index_repo_does_not_count_external_runtime_calls_as_unresolved(tmp_path: Path) -> None:
    repo = tmp_path / "runtime_calls_app"
    source_dir = repo / "src"
    source_dir.mkdir(parents=True)
    (source_dir / "app.py").write_text(
        "\n".join(
            [
                "print('boot')",
                "",
                "def run():",
                "    print('hello')",
                "",
            ]
        ),
        encoding="utf-8",
    )

    result = index_repo(str(repo), index_root=str(tmp_path / "indexes"))

    assert result.stats["unresolved_call_count"] == 0


def test_index_repo_does_not_count_top_level_local_calls_as_unresolved(tmp_path: Path) -> None:
    repo = tmp_path / "script_entrypoint_app"
    source_dir = repo / "src"
    source_dir.mkdir(parents=True)
    (source_dir / "app.py").write_text(
        "\n".join(
            [
                "def run():",
                "    return 'ok'",
                "",
                "run()",
                "",
            ]
        ),
        encoding="utf-8",
    )

    result = index_repo(str(repo), index_root=str(tmp_path / "indexes"))

    assert result.stats["unresolved_call_count"] == 0


def test_index_repo_does_not_count_external_module_imports_as_unresolved(tmp_path: Path) -> None:
    repo = tmp_path / "external_imports_app"
    source_dir = repo / "src"
    source_dir.mkdir(parents=True)
    (source_dir / "app.py").write_text(
        "\n".join(
            [
                "import json",
                "import os",
                "",
                "def run():",
                "    return os.path.basename('demo')",
                "",
            ]
        ),
        encoding="utf-8",
    )

    result = index_repo(str(repo), index_root=str(tmp_path / "indexes"))

    assert result.stats["unresolved_import_count"] == 0


def test_index_repo_persists_extends_and_implements_edges(tmp_path: Path) -> None:
    repo = FIXTURES_ROOT / "inheritance_app"
    result = index_repo(str(repo), index_root=str(tmp_path / "indexes"))
    store = KuzuStore(Path(result.graph_path))

    extends_result = store.connection.execute(
        """
        MATCH (source)-[r:CodeRelation]->(target)
        WHERE r.type = 'EXTENDS'
        RETURN source.name AS source_name, target.name AS target_name
        ORDER BY source_name, target_name;
        """
    )
    implements_result = store.connection.execute(
        """
        MATCH (source)-[r:CodeRelation]->(target)
        WHERE r.type = 'IMPLEMENTS'
        RETURN source.name AS source_name, target.name AS target_name
        ORDER BY source_name, target_name;
        """
    )

    extends_rows = [tuple(row) for row in extends_result.get_all()]
    implements_rows = [tuple(row) for row in implements_result.get_all()]

    assert ("Dog", "Animal") in extends_rows
    assert ("SpecialReader", "FileReader") in extends_rows
    assert ("StreamReader", "Reader") in extends_rows
    assert ("FileReader", "StreamReader") in implements_rows
    assert ("SpecialReader", "StreamReader") in implements_rows
