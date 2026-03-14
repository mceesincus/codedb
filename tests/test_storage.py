from __future__ import annotations

from pathlib import Path

from code_graph_core import index_repo
from code_graph_core.storage.kuzu_store import KuzuStore
from tests.conftest import FIXTURES_ROOT


def test_kuzu_store_bootstraps_expected_tables(tmp_path: Path) -> None:
    repo = FIXTURES_ROOT / "ts_basic_app"
    result = index_repo(str(repo), index_root=str(tmp_path / "indexes"))
    store = KuzuStore(Path(result.graph_path))

    assert store.table_count("Repository") == 1
    assert store.table_count("Folder") >= 3
    assert store.table_count("File") == 4
    assert store.table_count("Function") >= 2

