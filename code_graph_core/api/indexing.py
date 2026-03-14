from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from code_graph_core.graph.builder import GraphBuilder
from code_graph_core.graph.models import GraphBundle
from code_graph_core.ingestion.parser import ParserRegistry
from code_graph_core.ingestion.scanner import RepositoryScanner
from code_graph_core.ingestion.symbol_extractor import SymbolExtractor
from code_graph_core.storage.index_paths import index_dir_name
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


def index_repo(path: str, index_root: str | None = None) -> IndexResult:
    repo_path = Path(path).resolve()
    scanner = RepositoryScanner()
    source_files = scanner.scan(repo_path)

    parser_registry = ParserRegistry()
    extractor = SymbolExtractor()

    parsed_files = [parser_registry.parse_file(source_file) for source_file in source_files]
    extracted_files = [extractor.extract(parsed_file) for parsed_file in parsed_files]

    graph_bundle: GraphBundle = GraphBuilder().build(repo_path=repo_path, extracted_files=extracted_files)

    output_root = Path(index_root).resolve() if index_root else repo_path / ".code_graph"
    index_dir = output_root / index_dir_name(graph_bundle.repo_id)
    graph_path = index_dir / "graph.kuzu"
    metadata_path = index_dir / "metadata.json"

    store = KuzuStore(graph_path)
    store.reinitialize()
    store.bootstrap()
    store.persist(graph_bundle)

    write_metadata(
        metadata_path,
        metadata_payload(
            graph_bundle=graph_bundle,
            repo_path=repo_path,
            graph_path=graph_path,
        ),
    )

    return IndexResult(
        repo_id=graph_bundle.repo_id,
        repo_name=repo_path.name,
        indexed_at=graph_bundle.indexed_at,
        index_version=graph_bundle.index_version,
        graph_path=str(graph_path),
        metadata_path=str(metadata_path),
        stats=graph_bundle.stats.to_dict(),
    )
