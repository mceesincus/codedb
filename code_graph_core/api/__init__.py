from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from code_graph_core.api.indexing import IndexResult

__all__ = [
    "IndexResult",
    "get_impact",
    "get_repo_status",
    "get_skill",
    "get_symbol_context",
    "index_repo",
    "list_skills",
    "search",
]


def index_repo(*args, **kwargs):
    from code_graph_core.api.indexing import index_repo as _index_repo

    return _index_repo(*args, **kwargs)


def search(*args, **kwargs):
    from code_graph_core.api.querying import search as _search

    return _search(*args, **kwargs)


def get_repo_status(*args, **kwargs):
    from code_graph_core.api.querying import get_repo_status as _get_repo_status

    return _get_repo_status(*args, **kwargs)


def list_skills(*args, **kwargs):
    from code_graph_core.api.querying import list_skills as _list_skills

    return _list_skills(*args, **kwargs)


def get_skill(*args, **kwargs):
    from code_graph_core.api.querying import get_skill as _get_skill

    return _get_skill(*args, **kwargs)


def get_impact(*args, **kwargs):
    from code_graph_core.api.querying import get_impact as _get_impact

    return _get_impact(*args, **kwargs)


def get_symbol_context(*args, **kwargs):
    from code_graph_core.api.querying import get_symbol_context as _get_symbol_context

    return _get_symbol_context(*args, **kwargs)


def __getattr__(name: str):
    if name == "IndexResult":
        from code_graph_core.api.indexing import IndexResult as _IndexResult

        return _IndexResult
    raise AttributeError(name)
