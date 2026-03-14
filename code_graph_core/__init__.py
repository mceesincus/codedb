from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from code_graph_core.api.indexing import IndexResult

__all__ = ["IndexResult", "get_symbol_context", "index_repo", "search"]


def index_repo(*args, **kwargs):
    from code_graph_core.api.indexing import index_repo as _index_repo

    return _index_repo(*args, **kwargs)


def search(*args, **kwargs):
    from code_graph_core.api.querying import search as _search

    return _search(*args, **kwargs)


def get_symbol_context(*args, **kwargs):
    from code_graph_core.api.querying import get_symbol_context as _get_symbol_context

    return _get_symbol_context(*args, **kwargs)


def __getattr__(name: str):
    if name == "IndexResult":
        from code_graph_core.api.indexing import IndexResult as _IndexResult

        return _IndexResult
    raise AttributeError(name)
