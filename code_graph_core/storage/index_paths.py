from __future__ import annotations

import re
from hashlib import sha256
from pathlib import Path


def index_dir_name(repo_id: str) -> str:
    return re.sub(r'[^A-Za-z0-9._-]+', "__", repo_id).strip("._-") or "index"


def repo_id_for_path(repo_path: str | Path) -> str:
    resolved = Path(repo_path).resolve()
    return f"repo:{sha256(str(resolved).encode('utf-8')).hexdigest()[:16]}"


def index_dir(root: str | Path, repo_id: str) -> Path:
    return Path(root).resolve() / index_dir_name(repo_id)


def graph_path(root: str | Path, repo_id: str) -> Path:
    return index_dir(root, repo_id) / "graph.kuzu"


def metadata_path(root: str | Path, repo_id: str) -> Path:
    return index_dir(root, repo_id) / "metadata.json"
