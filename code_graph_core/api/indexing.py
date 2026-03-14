from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from code_graph_core.graph.builder import GraphBuilder
from code_graph_core.graph.models import GraphBundle
from code_graph_core.ingestion.parser import ParserRegistry
from code_graph_core.ingestion.scanner import RepositoryScanner
from code_graph_core.ingestion.symbol_extractor import SymbolExtractor
from code_graph_core.storage.index_paths import graph_path as indexed_graph_path
from code_graph_core.storage.index_paths import metadata_path as indexed_metadata_path
from code_graph_core.storage.kuzu_store import KuzuStore
from code_graph_core.storage.metadata import metadata_payload, write_metadata


@dataclass(slots=True)
class IndexResult:
    repo_id: str
    repo_name: str
    indexed_at: str
    index_version: str
    graph_path: str
    metadata_path: str
    stats: dict[str, int]


@dataclass(slots=True)
class IndexProgress:
    phase: str
    current: int
    total: int
    message: str


def index_repo(
    path: str,
    index_root: str | None = None,
    *,
    progress_callback: Callable[[IndexProgress], None] | None = None,
) -> IndexResult:
    repo_path = Path(path).resolve()
    scanner = RepositoryScanner()
    _emit_progress(progress_callback, phase="scan", current=0, total=1, message=f"Scanning {repo_path} ...")
    source_files = scanner.scan(repo_path)
    _emit_progress(
        progress_callback,
        phase="scan",
        current=1,
        total=1,
        message=f"Discovered {len(source_files)} source files.",
    )

    parser_registry = ParserRegistry()
    extractor = SymbolExtractor()

    parsed_files = []
    parse_total = max(len(source_files), 1)
    for index, source_file in enumerate(source_files, start=1):
        parsed_files.append(parser_registry.parse_file(source_file))
        _emit_progress(
            progress_callback,
            phase="parse",
            current=index,
            total=parse_total,
            message=f"Parsing {source_file.relative_path} ({index}/{parse_total})",
        )

    extracted_files = []
    extract_total = max(len(parsed_files), 1)
    for index, parsed_file in enumerate(parsed_files, start=1):
        extracted_files.append(extractor.extract(parsed_file))
        _emit_progress(
            progress_callback,
            phase="extract",
            current=index,
            total=extract_total,
            message=f"Extracting symbols from {parsed_file.source_file.relative_path} ({index}/{extract_total})",
        )

    _emit_progress(progress_callback, phase="graph", current=0, total=1, message="Building graph ...")
    graph_bundle: GraphBundle = GraphBuilder().build(repo_path=repo_path, extracted_files=extracted_files)
    _emit_progress(
        progress_callback,
        phase="graph",
        current=1,
        total=1,
        message=f"Built graph with {len(graph_bundle.nodes)} nodes and {len(graph_bundle.relationships)} edges.",
    )

    output_root = Path(index_root).resolve() if index_root else repo_path / ".code_graph"
    graph_path = indexed_graph_path(output_root, graph_bundle.repo_id)
    metadata_path = indexed_metadata_path(output_root, graph_bundle.repo_id)

    store = KuzuStore(graph_path)
    store.reinitialize()
    store.bootstrap()
    _emit_progress(progress_callback, phase="persist", current=0, total=1, message="Persisting graph ...")
    store.persist(graph_bundle)
    _emit_progress(progress_callback, phase="persist", current=1, total=1, message="Graph persisted.")

    _emit_progress(progress_callback, phase="metadata", current=0, total=1, message="Writing metadata ...")
    write_metadata(
        metadata_path,
        metadata_payload(
            graph_bundle=graph_bundle,
            repo_path=repo_path,
            graph_path=graph_path,
            source_files=source_files,
        ),
    )
    _emit_progress(progress_callback, phase="metadata", current=1, total=1, message="Metadata written.")

    return IndexResult(
        repo_id=graph_bundle.repo_id,
        repo_name=repo_path.name,
        indexed_at=graph_bundle.indexed_at,
        index_version=graph_bundle.index_version,
        graph_path=str(graph_path),
        metadata_path=str(metadata_path),
        stats=graph_bundle.stats.to_dict(),
    )


def _emit_progress(
    progress_callback: Callable[[IndexProgress], None] | None,
    *,
    phase: str,
    current: int,
    total: int,
    message: str,
) -> None:
    if progress_callback is None:
        return
    progress_callback(IndexProgress(phase=phase, current=current, total=total, message=message))
