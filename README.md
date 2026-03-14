# codedb

Milestone 1 scaffolding for a local-first code graph indexing core.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -e . pytest
```

## Run Tests

```bash
.venv/bin/python -m pytest
```

## Index a Repository

```bash
.venv/bin/python - <<'PY'
from code_graph_core import index_repo

result = index_repo("tests/fixtures/py_basic_app")
print(result)
PY
```

The current implementation covers Milestone 2:

- repository scanning with ignore rules
- Tree-sitter parsing for Python and TypeScript/JavaScript
- symbol extraction for files, functions, classes, methods, and interfaces
- basic import and call resolution for direct symbol context
- deterministic IDs
- Kuzu schema bootstrap and persistence
- metadata generation beside the index
- `search(repo_id, query, limit)`
- `get_symbol_context(repo_id, symbol, file_path=None)`

## Query an Indexed Repository

```bash
.venv/bin/python - <<'PY'
from code_graph_core import get_symbol_context, index_repo, search

result = index_repo("tests/fixtures/py_basic_app")

print(search(result.repo_id, "generate_invoice", graph_path=result.graph_path))
print(
    get_symbol_context(
        result.repo_id,
        "generate_invoice",
        file_path="src/billing/service.py",
        graph_path=result.graph_path,
    )
)
PY
```

## Launch the GUI

The repository now includes a minimal desktop client for indexing, search, and symbol context.

```bash
.venv/bin/python -m code_graph_core.gui
```

Or, after reinstalling the editable package:

```bash
code-graph-gui
```

Default source repo:

- Windows: `C:\work\india\mssrc`
- WSL/Linux: `/mnt/c/work/india/mssrc`

If an index already exists under the GUI cache directory, the app loads it automatically on startup for the current repo path.

Runtime note: the GUI uses `tkinter`, so the Python interpreter you run it with must include Tk support.
