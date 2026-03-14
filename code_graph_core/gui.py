from __future__ import annotations

import json
import os
import queue
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

try:
    import tkinter as tk
    from tkinter import messagebox, ttk
except ModuleNotFoundError:  # pragma: no cover - depends on runtime Python build
    tk = None
    ttk = None
    messagebox = None


DEFAULT_WINDOWS_SOURCE_REPO = r"C:\work\india\mssrc"
DEFAULT_WSL_SOURCE_REPO = "/mnt/c/work/india/mssrc"


@dataclass(slots=True)
class IndexedRepoState:
    source_repo_path: str
    repo_id: str
    repo_name: str
    graph_path: str
    metadata_path: str
    stats: dict[str, int]


def normalize_repo_path(raw_path: str) -> Path:
    value = raw_path.strip()
    if not value:
        raise ValueError("Repository path is required.")

    windows_match = re.match(r"^(?P<drive>[a-zA-Z]):[\\/](?P<rest>.*)$", value)
    if windows_match and os.name != "nt":
        drive = windows_match.group("drive").lower()
        rest = windows_match.group("rest").replace("\\", "/")
        return Path(f"/mnt/{drive}/{rest}").resolve(strict=False)

    if os.name == "nt" and value.startswith("/mnt/"):
        parts = Path(value).parts
        if len(parts) >= 4 and len(parts[2]) == 1:
            drive = parts[2].upper()
            rest = Path(*parts[3:])
            return Path(f"{drive}:/{rest}").resolve(strict=False)

    return Path(value).expanduser().resolve(strict=False)


def default_source_repo_path() -> str:
    candidates = [
        Path(DEFAULT_WINDOWS_SOURCE_REPO),
        Path(DEFAULT_WSL_SOURCE_REPO),
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return DEFAULT_WINDOWS_SOURCE_REPO if os.name == "nt" else DEFAULT_WSL_SOURCE_REPO


def format_search_result(result: dict[str, Any]) -> str:
    return (
        f"[{result['type']}] {result['name']} "
        f"({result['file_path']}:{result.get('start_line') or '-'}) "
        f"score={result['score']:.2f}"
    )


def format_symbol_context(payload: dict[str, Any]) -> str:
    if "error" in payload:
        return json.dumps(payload, indent=2, sort_keys=True)

    symbol = payload["symbol"]
    lines = [
        f"{symbol['type']} {symbol['name']}",
        f"node_id: {symbol['node_id']}",
        f"file: {symbol['file_path']}:{symbol['start_line']}-{symbol['end_line']}",
    ]
    if symbol.get("containing_class"):
        lines.append(f"class: {symbol['containing_class']}")
    if symbol.get("signature"):
        lines.append(f"signature: {symbol['signature']}")

    lines.append("")
    lines.append("Callers:")
    if payload["callers"]:
        lines.extend(
            f"- {item['name']} ({item['file_path']}, confidence={item['confidence']:.1f})"
            for item in payload["callers"]
        )
    else:
        lines.append("- none")

    lines.append("")
    lines.append("Callees:")
    if payload["callees"]:
        lines.extend(
            f"- {item['name']} ({item['file_path']}, confidence={item['confidence']:.1f})"
            for item in payload["callees"]
        )
    else:
        lines.append("- none")

    lines.append("")
    lines.append("Related files:")
    if payload["related_files"]:
        lines.extend(f"- {file_path}" for file_path in payload["related_files"])
    else:
        lines.append("- none")

    return "\n".join(lines)


class CodeGraphGuiApp:
    def __init__(self, root: Any) -> None:
        self.root = root
        self.root.title("Code Graph Explorer")
        self.root.geometry("1180x760")
        self.root.minsize(960, 640)

        self.repo_path_var = tk.StringVar(value=default_source_repo_path())
        self.search_query_var = tk.StringVar()
        self.symbol_var = tk.StringVar()
        self.file_path_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Ready.")

        self.current_repo: IndexedRepoState | None = None
        self.search_results: list[dict[str, Any]] = []
        self._event_queue: queue.Queue[tuple[str, Any]] = queue.Queue()
        self._busy_count = 0

        self._build_ui()
        self.root.after(125, self._poll_events)

    def _build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(2, weight=1)

        header = ttk.Frame(self.root, padding=12)
        header.grid(row=0, column=0, sticky="nsew")
        header.columnconfigure(1, weight=1)

        ttk.Label(header, text="Repository").grid(row=0, column=0, sticky="w", padx=(0, 8))
        repo_entry = ttk.Entry(header, textvariable=self.repo_path_var)
        repo_entry.grid(row=0, column=1, sticky="ew")
        self.index_button = ttk.Button(header, text="Index Repo", command=self._on_index_repo)
        self.index_button.grid(row=0, column=2, sticky="e", padx=(8, 0))

        ttk.Label(header, textvariable=self.status_var).grid(row=1, column=0, columnspan=3, sticky="w", pady=(8, 0))

        controls = ttk.Frame(self.root, padding=(12, 0, 12, 12))
        controls.grid(row=1, column=0, sticky="ew")
        controls.columnconfigure(1, weight=1)
        controls.columnconfigure(4, weight=1)

        ttk.Label(controls, text="Search").grid(row=0, column=0, sticky="w", padx=(0, 8))
        search_entry = ttk.Entry(controls, textvariable=self.search_query_var)
        search_entry.grid(row=0, column=1, sticky="ew")
        search_entry.bind("<Return>", lambda _event: self._on_search())
        self.search_button = ttk.Button(controls, text="Search", command=self._on_search)
        self.search_button.grid(row=0, column=2, padx=(8, 16))

        ttk.Label(controls, text="Symbol").grid(row=0, column=3, sticky="w", padx=(0, 8))
        symbol_entry = ttk.Entry(controls, textvariable=self.symbol_var)
        symbol_entry.grid(row=0, column=4, sticky="ew")
        symbol_entry.bind("<Return>", lambda _event: self._on_load_context())

        ttk.Label(controls, text="File Path").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=(8, 0))
        file_path_entry = ttk.Entry(controls, textvariable=self.file_path_var)
        file_path_entry.grid(row=1, column=1, columnspan=4, sticky="ew", pady=(8, 0))
        file_path_entry.bind("<Return>", lambda _event: self._on_load_context())
        self.context_button = ttk.Button(controls, text="Load Context", command=self._on_load_context)
        self.context_button.grid(row=1, column=5, padx=(8, 0), pady=(8, 0))

        body = ttk.Panedwindow(self.root, orient="horizontal")
        body.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 12))

        left = ttk.Frame(body, padding=8)
        left.columnconfigure(0, weight=1)
        left.rowconfigure(1, weight=1)
        body.add(left, weight=3)

        ttk.Label(left, text="Search Results").grid(row=0, column=0, sticky="w")
        results_frame = ttk.Frame(left)
        results_frame.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(0, weight=1)

        self.results_list = tk.Listbox(results_frame, activestyle="none")
        self.results_list.grid(row=0, column=0, sticky="nsew")
        self.results_list.bind("<<ListboxSelect>>", self._on_select_result)

        results_scrollbar = ttk.Scrollbar(results_frame, orient="vertical", command=self.results_list.yview)
        results_scrollbar.grid(row=0, column=1, sticky="ns")
        self.results_list.config(yscrollcommand=results_scrollbar.set)

        right = ttk.Frame(body, padding=8)
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)
        body.add(right, weight=4)

        ttk.Label(right, text="Context").grid(row=0, column=0, sticky="w")
        self.context_text = tk.Text(right, wrap="word", font=("Courier New", 10))
        self.context_text.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        self.context_text.configure(state="disabled")

    def _on_index_repo(self) -> None:
        try:
            repo_path = self._get_requested_repo_path()
        except ValueError as exc:
            self._show_error(str(exc))
            return

        self._run_background(
            started_message=f"Indexing {repo_path} ...",
            job=lambda: self._index_repo(str(repo_path)),
            success=lambda result: self._handle_index_result(result, str(repo_path)),
        )

    def _on_search(self) -> None:
        query = self.search_query_var.get().strip()
        if not query:
            self._show_error("Enter a search query.")
            return

        self._ensure_indexed_then(lambda repo: self._perform_search(repo, query))

    def _on_load_context(self) -> None:
        symbol = self.symbol_var.get().strip()
        if not symbol:
            self._show_error("Enter a symbol name.")
            return

        file_path = self.file_path_var.get().strip() or None
        self._ensure_indexed_then(lambda repo: self._perform_load_context(repo, symbol, file_path))

    def _on_select_result(self, _event: Any) -> None:
        selection = self.results_list.curselection()
        if not selection:
            return
        result = self.search_results[selection[0]]
        self.symbol_var.set(result["name"])
        self.file_path_var.set(result["file_path"])
        self._on_load_context()

    def _run_background(
        self,
        *,
        started_message: str,
        job: Callable[[], Any],
        success: Callable[[Any], None],
    ) -> None:
        self._set_busy(True)
        self.status_var.set(started_message)

        def worker() -> None:
            try:
                value = job()
            except Exception as exc:  # pragma: no cover - exercised indirectly in GUI runtime
                self._event_queue.put(("error", exc))
            else:
                self._event_queue.put(("success", (success, value)))
            finally:
                self._event_queue.put(("done", None))

        threading.Thread(target=worker, daemon=True).start()

    def _poll_events(self) -> None:
        while True:
            try:
                kind, payload = self._event_queue.get_nowait()
            except queue.Empty:
                break

            if kind == "error":
                self._show_error(str(payload))
            elif kind == "success":
                callback, value = payload
                callback(value)
            elif kind == "done":
                self._set_busy(False)

        self.root.after(125, self._poll_events)

    def _handle_index_result(self, result: Any, source_repo_path: str | None = None) -> None:
        resolved_source_repo_path = source_repo_path or self.repo_path_var.get().strip()
        self.current_repo = IndexedRepoState(
            source_repo_path=resolved_source_repo_path,
            repo_id=result.repo_id,
            repo_name=result.repo_name,
            graph_path=result.graph_path,
            metadata_path=result.metadata_path,
            stats=result.stats,
        )
        self.status_var.set(
            f"Indexed {result.repo_name} | files={result.stats['file_count']} "
            f"nodes={result.stats['node_count']} edges={result.stats['edge_count']}"
        )
        self.search_results = []
        self.results_list.delete(0, tk.END)
        self._render_text(
            "\n".join(
                [
                    f"Repository: {result.repo_name}",
                    f"Repo ID: {result.repo_id}",
                    f"Graph Path: {result.graph_path}",
                    f"Metadata Path: {result.metadata_path}",
                    "",
                    json.dumps(result.stats, indent=2, sort_keys=True),
                ]
            )
        )

    def _handle_search_results(self, response: dict[str, Any]) -> None:
        self.search_results = response["results"]
        self.results_list.delete(0, tk.END)
        for item in self.search_results:
            self.results_list.insert(tk.END, format_search_result(item))
        self.status_var.set(f"Search returned {len(self.search_results)} results.")
        if not self.search_results:
            self._render_text("No results.")

    def _handle_symbol_context(self, response: dict[str, Any]) -> None:
        if "error" in response:
            self.status_var.set(response["error"]["message"])
        else:
            self.status_var.set(f"Loaded context for {response['symbol']['name']}.")
        self._render_text(format_symbol_context(response))

    def _render_text(self, content: str) -> None:
        self.context_text.configure(state="normal")
        self.context_text.delete("1.0", tk.END)
        self.context_text.insert("1.0", content)
        self.context_text.configure(state="disabled")

    def _set_busy(self, is_busy: bool) -> None:
        if is_busy:
            self._busy_count += 1
        else:
            self._busy_count = max(0, self._busy_count - 1)
        state = "disabled" if self._busy_count else "normal"
        self.index_button.configure(state=state)
        self.search_button.configure(state=state)
        self.context_button.configure(state=state)

    def _show_error(self, message: str) -> None:
        self.status_var.set(message)
        self._render_text(message)
        if messagebox is not None:
            messagebox.showerror("Code Graph Explorer", message)

    def _get_requested_repo_path(self) -> Path:
        repo_path = normalize_repo_path(self.repo_path_var.get())
        if not repo_path.exists():
            raise ValueError(f"Repository path does not exist: {repo_path}")
        return repo_path

    def _needs_reindex(self, repo_path: Path) -> bool:
        if self.current_repo is None:
            return True
        return Path(self.current_repo.source_repo_path) != repo_path

    def _ensure_indexed_then(self, callback: Callable[[IndexedRepoState], None]) -> None:
        try:
            repo_path = self._get_requested_repo_path()
        except ValueError as exc:
            self._show_error(str(exc))
            return

        if not self._needs_reindex(repo_path):
            callback(self.current_repo)
            return

        self._run_background(
            started_message=f"Indexing {repo_path} ...",
            job=lambda: self._index_repo(str(repo_path)),
            success=lambda result: self._handle_index_result_and_continue(result, str(repo_path), callback),
        )

    def _handle_index_result_and_continue(
        self,
        result: Any,
        source_repo_path: str,
        callback: Callable[[IndexedRepoState], None],
    ) -> None:
        self._handle_index_result(result, source_repo_path)
        if self.current_repo is not None:
            callback(self.current_repo)

    def _perform_search(self, repo: IndexedRepoState, query: str) -> None:
        self._run_background(
            started_message=f"Searching for '{query}' ...",
            job=lambda: self._search(
                repo.repo_id,
                query,
                graph_path=repo.graph_path,
            ),
            success=self._handle_search_results,
        )

    def _perform_load_context(
        self,
        repo: IndexedRepoState,
        symbol: str,
        file_path: str | None,
    ) -> None:
        self._run_background(
            started_message=f"Loading context for '{symbol}' ...",
            job=lambda: self._get_symbol_context(
                repo.repo_id,
                symbol,
                file_path=file_path,
                graph_path=repo.graph_path,
            ),
            success=self._handle_symbol_context,
        )

    @staticmethod
    def _index_root() -> Path:
        return Path.home() / ".code_graph_gui"

    @staticmethod
    def _index_repo(repo_path: str):
        try:
            from code_graph_core.api.indexing import index_repo
        except ModuleNotFoundError as exc:  # pragma: no cover - depends on runtime environment
            raise RuntimeError(
                "Missing runtime dependency for indexing. Run "
                "`python -m pip install -e .` in `C:\\work\\india\\codedb` first."
            ) from exc
        return index_repo(repo_path, index_root=str(CodeGraphGuiApp._index_root()))

    @staticmethod
    def _search(repo_id: str, query: str, graph_path: str):
        try:
            from code_graph_core.api.querying import search
        except ModuleNotFoundError as exc:  # pragma: no cover - depends on runtime environment
            raise RuntimeError(
                "Missing runtime dependency for search. Run "
                "`python -m pip install -e .` in `C:\\work\\india\\codedb` first."
            ) from exc
        return search(repo_id, query, graph_path=graph_path)

    @staticmethod
    def _get_symbol_context(repo_id: str, symbol: str, file_path: str | None, graph_path: str):
        try:
            from code_graph_core.api.querying import get_symbol_context
        except ModuleNotFoundError as exc:  # pragma: no cover - depends on runtime environment
            raise RuntimeError(
                "Missing runtime dependency for symbol context. Run "
                "`python -m pip install -e .` in `C:\\work\\india\\codedb` first."
            ) from exc
        return get_symbol_context(repo_id, symbol, file_path=file_path, graph_path=graph_path)


def main() -> None:
    if tk is None or ttk is None:
        raise RuntimeError(
            "This Python environment does not include tkinter. "
            "Install a Python build with Tk support to run the GUI client."
        )

    root = tk.Tk()
    style = ttk.Style(root)
    if "vista" in style.theme_names():
        style.theme_use("vista")
    elif "clam" in style.theme_names():
        style.theme_use("clam")

    app = CodeGraphGuiApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
