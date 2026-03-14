# Semantic Search Implementation Plan
## Local Code Graph Intelligence Core for Chatbot Integration

Status: Proposed post-v1 implementation plan

Related docs:

- [prd-code-graph-chatbot.md](/mnt/c/work/india/codedb/prd-code-graph-chatbot.md)
- [tech-spec-code-graph-chatbot.md](/mnt/c/work/india/codedb/tech-spec-code-graph-chatbot.md)
- [schema-and-contract-pack-code-graph-chatbot.md](/mnt/c/work/india/codedb/schema-and-contract-pack-code-graph-chatbot.md)
- [execution-plan-code-graph-chatbot.md](/mnt/c/work/india/codedb/execution-plan-code-graph-chatbot.md)

## 1. Purpose

This document defines a concrete implementation plan for adding semantic, embedding-backed search to the existing local-first code graph system.

In this repository, semantic search means:

- embed code objects and user queries into vectors
- retrieve nearest neighbors by semantic similarity
- combine semantic retrieval with the current lexical and graph-aware ranking

It does not mean:

- replacing the current search API
- adding hosted search infrastructure
- requiring cloud dependencies

The target is a bounded hybrid retrieval system that remains local-first and optional.

## 2. Product Goal

The current search is strongest when the query overlaps with:

- symbol names
- file names
- path terms

Semantic search should improve queries like:

- `where is auth token verification done`
- `code that saves invoice state`
- `retry logic for failed requests`
- `entry point for checkout flow`

These queries often do not match exact symbol names, but they do describe the intent of the code.

## 3. Success Criteria

The feature is successful if:

- semantic queries retrieve the correct symbol or file even when exact names differ
- lexical exact matches still win when the user already knows the symbol name
- retrieval remains fast enough for interactive local use
- the feature can be disabled cleanly

## 4. Design Constraints

- local-first only
- no hosted vector DB
- no mandatory external API dependency
- must preserve existing `search(...)` contract shape
- must degrade gracefully when embeddings are unavailable

## 5. Recommended Architecture

Use a hybrid search pipeline:

1. lexical retrieval from the existing search implementation
2. semantic retrieval from a local vector index
3. result fusion
4. graph-aware reranking

This avoids overcommitting to embeddings while preserving current precision for known identifiers.

## 6. Search Units

Do not embed entire repositories as one blob.

Embed bounded units:

- `Function`
- `Method`
- `Class`
- `Interface`
- optionally `File` summaries for file-level retrieval

Recommended v1.5 unit:

- one vector per symbol-like node

Optional later:

- file-level vectors
- chunked source windows around symbols

## 7. Text to Embed

Each embedded symbol should use a deterministic text representation such as:

```text
type: Method
name: generate_invoice
owner: BillingService
file: src/billing/service.py
signature: def generate_invoice(self, order_id: str):
imports: repository
calls: save
skill: billing
```

Do not embed raw whole-file text by default.

Reason:

- better locality
- lower storage cost
- less noise
- easier incremental rebuild later

## 8. Embedding Backend Options

Preferred order:

1. local sentence-transformers style model
2. local ONNX embedding runtime
3. optional remote API adapter only behind an explicit opt-in

Recommended baseline:

- local model only

Reason:

- consistent with local-first goals
- simpler privacy story
- deterministic offline behavior

## 9. Vector Storage

Use a local vector sidecar, not Kuzu itself, for nearest-neighbor retrieval.

Recommended options:

1. NumPy arrays + brute-force cosine for small/medium repos
2. FAISS local index for larger repos

Recommended initial choice:

- NumPy-based brute-force cosine search

Reason:

- simplest implementation
- enough for early local repo sizes
- easy to test and debug

Add FAISS only if measured latency demands it.

## 10. Proposed File Layout

Add:

```text
code_graph_core/
  embeddings/
    model.py
    encoder.py
    index.py
    payloads.py
  storage/
    vector_store.py
```

Likely responsibilities:

- `model.py`: embedding backend selection and loading
- `encoder.py`: convert symbols/files into embed text
- `index.py`: nearest-neighbor search
- `payloads.py`: deterministic embedding text builders
- `vector_store.py`: persistence of vectors and metadata

## 11. API Surface

Preserve the existing API:

- `search(repo_id, query, limit, ...)`

Extend it with optional configuration:

```python
search(
    repo_id,
    query,
    limit=10,
    graph_path=...,
    semantic=True,
)
```

Optional later:

- `rebuild_embeddings(repo_id)`
- `get_embedding_status(repo_id)`

Those should not be required for the first semantic iteration.

## 12. Hybrid Ranking

The existing search currently ranks using:

- exact node ID match
- exact symbol name match
- prefix match
- substring match
- file path match
- symbol/export bonuses

Keep that behavior.

Add semantic candidates as an additional source, then fuse the rankings.

Recommended fusion:

- Reciprocal Rank Fusion or a simple weighted blend

Suggested initial blend:

- lexical exact/prefix results strongly favored
- semantic similarity used mainly to rescue natural-language queries

Rule:

- exact lexical symbol matches must still outrank semantic guesses

## 13. Index-Time Workflow

During indexing:

1. build the current code graph as today
2. enumerate symbol nodes to embed
3. create deterministic embed payloads
4. run embeddings
5. persist vectors and vector metadata beside graph metadata

The vector sidecar should be keyed by:

- `repo_id`
- `index_version`
- embedding model identifier
- source timestamp or content fingerprint

## 14. Query-Time Workflow

For `search(...)` with semantic mode enabled:

1. run current lexical search
2. embed the query
3. retrieve top semantic candidates
4. merge lexical and semantic candidates
5. apply graph-aware reranking
6. return the existing result schema

Add semantic-specific `reason` text when applicable, for example:

- `Semantic similarity match`
- `Hybrid lexical + semantic match`

## 15. Configuration

Add a small local configuration surface:

- embeddings enabled or disabled
- model name/path
- max semantic candidates
- fusion weights

Keep config local and file-based or environment-based.

Do not introduce a large config system.

## 16. Persistence Design

Recommended sidecar layout under the existing index root:

```text
<index_root>/
  <repo_dir>/
    graph.kuzu/
    metadata.json
    embeddings/
      vectors.npy
      ids.json
      config.json
```

Required metadata:

- embedding model identifier
- embedding dimension
- vector count
- generated_at
- repo_id
- index_version

## 17. Failure and Fallback Behavior

If embeddings are unavailable:

- search still works lexically
- no indexing failure for the main graph
- metadata should record semantic index as unavailable or stale

If semantic retrieval fails at query time:

- return lexical results only
- do not fail the entire search request

## 18. Testing Plan

## Phase 1: Unit Tests

Add tests for:

- deterministic embedding payload generation
- query fusion logic
- semantic score normalization
- fallback behavior when the model is unavailable

## Phase 2: Fixture Tests

Add semantic-search-specific fixtures where lexical search is weak:

1. `semantic_auth_app`
   - symbol names use `jwt`, `decode`, `claims`
   - queries use `token verification`
2. `semantic_billing_app`
   - symbol names use `persist`, `capture`, `mark_paid`
   - queries use `save invoice state`
3. `semantic_retry_app`
   - symbol names use `backoff`, `requeue`
   - queries use `retry failed requests`

## Phase 3: Contract Tests

Verify:

- result shape is unchanged
- `reason` reflects semantic contribution when used
- exact lexical matches still rank first

## 19. Performance Plan

Measure:

- embedding generation time during indexing
- warm query latency
- memory footprint of vectors

Initial target:

- semantic search adds acceptable local latency for small/medium repos
- exact lexical search remains fast

Do not optimize prematurely with FAISS until brute-force local retrieval is measured.

## 20. Rollout Order

1. define payload builder
2. add embedding backend abstraction
3. add local vector sidecar persistence
4. build semantic retrieval
5. fuse with lexical search
6. add tests and fixtures
7. harden on a real repo
8. update docs

## 21. Files Expected to Change

Core:

- [querying.py](/mnt/c/work/india/codedb/code_graph_core/api/querying.py)
- [indexing.py](/mnt/c/work/india/codedb/code_graph_core/api/indexing.py)
- [metadata.py](/mnt/c/work/india/codedb/code_graph_core/storage/metadata.py)

New modules:

- [model.py](/mnt/c/work/india/codedb/code_graph_core/embeddings/model.py)
- [encoder.py](/mnt/c/work/india/codedb/code_graph_core/embeddings/encoder.py)
- [index.py](/mnt/c/work/india/codedb/code_graph_core/embeddings/index.py)
- [payloads.py](/mnt/c/work/india/codedb/code_graph_core/embeddings/payloads.py)
- [vector_store.py](/mnt/c/work/india/codedb/code_graph_core/storage/vector_store.py)

Tests and fixtures:

- [tests](/mnt/c/work/india/codedb/tests)
- [fixtures](/mnt/c/work/india/codedb/tests/fixtures)

Docs:

- [README.md](/mnt/c/work/india/codedb/README.md)
- [prd-code-graph-chatbot.md](/mnt/c/work/india/codedb/prd-code-graph-chatbot.md)
- [tech-spec-code-graph-chatbot.md](/mnt/c/work/india/codedb/tech-spec-code-graph-chatbot.md)
- [schema-and-contract-pack-code-graph-chatbot.md](/mnt/c/work/india/codedb/schema-and-contract-pack-code-graph-chatbot.md)

## 22. Recommended Initial Scope

For the first implementation, do only this:

- symbol-level embeddings
- local embedding model
- NumPy cosine similarity
- hybrid lexical + semantic fusion
- no separate semantic APIs

That is enough to prove value without overcomplicating the architecture.

## 23. Key Constraint

Do not let semantic retrieval replace exact structural search.

The correct target is:

- lexical precision first
- semantic recall second
- graph-aware reranking on top

That is the safest way to improve search quality in this codebase.
