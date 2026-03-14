from __future__ import annotations

import re


def index_dir_name(repo_id: str) -> str:
    return re.sub(r'[^A-Za-z0-9._-]+', "__", repo_id).strip("._-") or "index"
