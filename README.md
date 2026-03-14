# codedb

Implemented v1 for a local-first code graph indexing core and demo chatbot surface.

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

The current implementation covers the implemented v1 surface:

- repository scanning with ignore rules
- Tree-sitter parsing for Python and TypeScript/JavaScript
- symbol extraction for files, functions, classes, methods, and interfaces
- basic import and call resolution for direct symbol context
- inheritance edges for `EXTENDS` and `IMPLEMENTS`
- deterministic IDs
- Kuzu schema bootstrap and persistence
- metadata generation beside the index
- `get_repo_status(repo_id)`
- `search(repo_id, query, limit)`
- `get_symbol_context(repo_id, symbol, file_path=None)`
- `get_impact(repo_id, target, direction, depth=2)`
- `list_skills(repo_id)`
- `get_skill(repo_id, skill_name)`
- minimal terminal REPL chatbot

## Query an Indexed Repository

```bash
.venv/bin/python - <<'PY'
from code_graph_core import get_symbol_context, index_repo, search

result = index_repo("tests/fixtures/py_basic_app")

results = search(result.repo_id, "<symbol-query>", graph_path=result.graph_path)
print(results)

# After search returns a real symbol from your repo, pass its exact name and
# optional file path into get_symbol_context(...).
print(
    get_symbol_context(
        result.repo_id,
        "<symbol-name>",
        file_path="<relative/path/from/search/results>",
        graph_path=result.graph_path,
    )
)
PY
```

## Launch the REPL

The repository also includes a minimal terminal client over the same APIs.

```bash
.venv/bin/python -m code_graph_core.repl
```

Or, after reinstalling the editable package:

```bash
code-graph-repl
```

Commands:

- `help`
- `repo [path]`
- `index [--force]`
- `status`
- `search <query>`
- `context <symbol> [file_path]`
- `skills`
- `skill <name>`
- `impact <target> [upstream|downstream] [depth]`

For a new codebase, start with `search <query>` to discover real symbol names and file paths.
The REPL also routes a few common chat-style prompts such as `what calls <symbol>?`, `show context for <symbol>`, and `list skills`.
Any other input falls back to `search`.
