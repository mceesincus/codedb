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

The current implementation covers Milestone 1:

- repository scanning with ignore rules
- Tree-sitter parsing for Python and TypeScript/JavaScript
- symbol extraction for files, functions, classes, methods, and interfaces
- deterministic IDs
- Kuzu schema bootstrap and persistence
- metadata generation beside the index
