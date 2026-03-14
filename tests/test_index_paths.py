from __future__ import annotations

from code_graph_core.storage.index_paths import index_dir_name


def test_index_dir_name_is_filesystem_safe() -> None:
    assert index_dir_name("repo:43126217451c9661") == "repo__43126217451c9661"
    assert ":" not in index_dir_name("repo:43126217451c9661")
