from __future__ import annotations

import argparse
import shlex
from pathlib import Path
from typing import Callable

from code_graph_core import (
    get_impact,
    get_repo_status,
    get_skill,
    get_symbol_context,
    index_repo,
    list_skills,
    search,
)
from code_graph_core.gui import (
    IndexedRepoState,
    default_source_repo_path,
    format_impact,
    format_index_progress,
    format_search_result,
    format_skill_detail,
    format_skills_list,
    format_symbol_context,
    load_existing_index_state,
    normalize_repo_path,
)


def format_repl_help() -> str:
    return "\n".join(
        [
            "Commands:",
            "  help",
            "  repo [path]",
            "  index [--force]",
            "  status",
            "  search <query>",
            "  context <symbol> [file_path]",
            "  skills",
            "  skill <name>",
            "  impact <target> [upstream|downstream] [depth]",
            "  exit | quit",
            "",
            "Any unrecognized input runs a search against the active repo.",
        ]
    )


def format_search_payload(payload: dict[str, object]) -> str:
    results = list(payload.get("results", []))
    if not results:
        return "No results."

    lines = ["Search results:"]
    for result in results:
        lines.append(f"- {format_search_result(result)} | {result['reason']}")
    return "\n".join(lines)


def format_repo_summary(repo: IndexedRepoState) -> str:
    return "\n".join(
        [
            f"Repository: {repo.repo_name}",
            f"Repo path: {repo.source_repo_path}",
            f"Repo ID: {repo.repo_id}",
            f"Freshness: {repo.freshness_status}",
            f"Index Version: {repo.index_version or 'unknown'}",
            f"Indexed At: {repo.indexed_at}",
            f"Languages: {', '.join(repo.languages_detected) if repo.languages_detected else 'unknown'}",
            f"Graph Path: {repo.graph_path}",
            "",
            f"Files: {repo.stats.get('file_count', 0)}",
            f"Nodes: {repo.stats.get('node_count', 0)}",
            f"Edges: {repo.stats.get('edge_count', 0)}",
            f"Skills: {repo.stats.get('skill_count', 0)}",
            f"Parse Errors: {repo.stats.get('parse_error_count', 0)}",
            f"Unresolved Imports: {repo.stats.get('unresolved_import_count', 0)}",
            f"Unresolved Calls: {repo.stats.get('unresolved_call_count', 0)}",
        ]
    )


class CodeGraphRepl:
    def __init__(
        self,
        *,
        repo_path: str | None = None,
        index_root: str | Path | None = None,
        output: Callable[[str], None] | None = None,
        show_progress: bool = True,
    ) -> None:
        self.repo_path = normalize_repo_path(repo_path or default_source_repo_path())
        self.index_root = Path(index_root).expanduser().resolve(strict=False) if index_root else self._default_index_root()
        self.output = output or print
        self.show_progress = show_progress
        self.current_repo: IndexedRepoState | None = None
        self.should_exit = False
        self._progress_buckets: dict[str, int] = {}

        if self.repo_path.exists():
            self.current_repo = load_existing_index_state(self.repo_path, self.index_root)

    def run(self) -> None:
        self.output("Code Graph REPL")
        self.output(f"Repo: {self.repo_path}")
        if self.current_repo is not None:
            self.output(
                f"Loaded cached index for {self.current_repo.repo_name} "
                f"({self.current_repo.freshness_status})."
            )
        self.output("Type `help` for commands.")

        while not self.should_exit:
            try:
                line = input("code-graph> ")
            except EOFError:
                self.output("")
                break

            response = self.execute_line(line)
            if response:
                self.output(response)

    def execute_line(self, line: str) -> str:
        raw_line = line.strip()
        if not raw_line:
            return ""

        try:
            parts = shlex.split(raw_line)
        except ValueError as exc:
            return f"Error: {exc}"

        if not parts:
            return ""

        command = parts[0].lower()
        args = parts[1:]

        handlers: dict[str, Callable[[list[str], str], str]] = {
            "help": self._handle_help,
            "repo": self._handle_repo,
            "index": self._handle_index,
            "status": self._handle_status,
            "search": self._handle_search,
            "context": self._handle_context,
            "skills": self._handle_skills,
            "skill": self._handle_skill,
            "impact": self._handle_impact,
            "exit": self._handle_exit,
            "quit": self._handle_exit,
        }

        handler = handlers.get(command)
        if handler is None:
            return self._run_search(raw_line)
        return handler(args, raw_line)

    def _handle_help(self, _args: list[str], _raw_line: str) -> str:
        return format_repl_help()

    def _handle_repo(self, args: list[str], _raw_line: str) -> str:
        if not args:
            lines = [f"Repo: {self.repo_path}", f"Index root: {self.index_root}"]
            if self.current_repo is not None and Path(self.current_repo.source_repo_path) == self.repo_path:
                lines.append("")
                lines.append(format_repo_summary(self.current_repo))
            else:
                lines.append("No cached index loaded.")
            return "\n".join(lines)

        self.repo_path = normalize_repo_path(" ".join(args))
        self.current_repo = None
        if self.repo_path.exists():
            self.current_repo = load_existing_index_state(self.repo_path, self.index_root)

        lines = [f"Repo set to {self.repo_path}"]
        if not self.repo_path.exists():
            lines.append("Path does not exist.")
        elif self.current_repo is None:
            lines.append("No cached index found.")
        else:
            lines.append(f"Loaded cached index ({self.current_repo.freshness_status}).")
        return "\n".join(lines)

    def _handle_index(self, args: list[str], _raw_line: str) -> str:
        force = any(arg == "--force" for arg in args)
        repo = self._ensure_indexed(force=force)
        return format_repo_summary(repo)

    def _handle_status(self, _args: list[str], _raw_line: str) -> str:
        repo = self._ensure_indexed()
        return format_repo_summary(repo)

    def _handle_search(self, args: list[str], _raw_line: str) -> str:
        if not args:
            return "Error: search requires a query."
        return self._run_search(" ".join(args))

    def _handle_context(self, args: list[str], _raw_line: str) -> str:
        if not args:
            return "Error: context requires a symbol name."

        symbol = args[0]
        file_path = " ".join(args[1:]) or None
        repo = self._ensure_indexed()
        payload = get_symbol_context(
            repo.repo_id,
            symbol,
            file_path=file_path,
            graph_path=repo.graph_path,
        )
        return format_symbol_context(payload)

    def _handle_skills(self, _args: list[str], _raw_line: str) -> str:
        repo = self._ensure_indexed()
        payload = list_skills(repo.repo_id, graph_path=repo.graph_path)
        return format_skills_list(payload)

    def _handle_skill(self, args: list[str], _raw_line: str) -> str:
        if not args:
            return "Error: skill requires a skill name."
        repo = self._ensure_indexed()
        payload = get_skill(repo.repo_id, " ".join(args), graph_path=repo.graph_path)
        return format_skill_detail(payload)

    def _handle_impact(self, args: list[str], _raw_line: str) -> str:
        if not args:
            return "Error: impact requires a target symbol."

        target = args[0]
        direction = args[1] if len(args) >= 2 else "upstream"
        try:
            depth = int(args[2]) if len(args) >= 3 else 2
        except ValueError:
            return "Error: impact depth must be an integer."

        repo = self._ensure_indexed()
        payload = get_impact(
            repo.repo_id,
            target,
            direction,
            depth,
            graph_path=repo.graph_path,
        )
        return format_impact(payload)

    def _handle_exit(self, _args: list[str], _raw_line: str) -> str:
        self.should_exit = True
        return "Bye."

    def _run_search(self, query: str) -> str:
        repo = self._ensure_indexed()
        payload = search(repo.repo_id, query, graph_path=repo.graph_path)
        return format_search_payload(payload)

    def _ensure_indexed(self, *, force: bool = False) -> IndexedRepoState:
        if not self.repo_path.exists():
            raise ValueError(f"Repository path does not exist: {self.repo_path}")

        if not force and self.current_repo is not None:
            if Path(self.current_repo.source_repo_path) == self.repo_path and self.current_repo.freshness_status == "CURRENT":
                return self.current_repo

        if not force:
            existing = load_existing_index_state(self.repo_path, self.index_root)
            if existing is not None and existing.freshness_status == "CURRENT":
                self.current_repo = existing
                return existing

        self._progress_buckets.clear()
        self.output(f"Indexing {self.repo_path} ...")
        result = index_repo(
            str(self.repo_path),
            index_root=str(self.index_root),
            progress_callback=self._handle_progress,
        )
        self.current_repo = load_existing_index_state(self.repo_path, self.index_root)
        if self.current_repo is None:
            raise RuntimeError(f"Indexed repo {result.repo_id} but failed to reload metadata.")

        payload = get_repo_status(self.current_repo.repo_id, metadata_path=self.current_repo.metadata_path)
        self.current_repo.index_version = str(payload.get("index_version", self.current_repo.index_version))
        self.current_repo.languages_detected = [str(item) for item in payload.get("languages_detected", [])]
        self.current_repo.stats = {
            key: int(value)
            for key, value in dict(payload.get("stats", {})).items()
        }
        return self.current_repo

    def _handle_progress(self, progress: object) -> None:
        if not self.show_progress:
            return

        phase = str(getattr(progress, "phase", "work"))
        total = int(getattr(progress, "total", 0) or 0)
        current = int(getattr(progress, "current", 0) or 0)

        should_emit = total <= 1 or current in {0, 1, total}
        if total > 1:
            bucket = min(10, (current * 10) // total)
            if self._progress_buckets.get(phase) != bucket:
                self._progress_buckets[phase] = bucket
                should_emit = True

        if should_emit:
            self.output(format_index_progress(progress))

    @staticmethod
    def _default_index_root() -> Path:
        return Path.home() / ".code_graph_gui"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Minimal terminal client for the code graph APIs.")
    parser.add_argument("--repo", default=default_source_repo_path(), help="Repository path to use.")
    parser.add_argument(
        "--index-root",
        default=str(CodeGraphRepl._default_index_root()),
        help="Directory for persisted indexes.",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    repl = CodeGraphRepl(repo_path=args.repo, index_root=args.index_root)
    repl.run()


if __name__ == "__main__":
    main()
