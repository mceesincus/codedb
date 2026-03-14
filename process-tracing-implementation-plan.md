# Process Tracing Implementation Plan
## Local Code Graph Intelligence Core for Chatbot Integration

Status: Proposed post-v1 implementation plan

Related docs:

- [prd-code-graph-chatbot.md](/mnt/c/work/india/codedb/prd-code-graph-chatbot.md)
- [tech-spec-code-graph-chatbot.md](/mnt/c/work/india/codedb/tech-spec-code-graph-chatbot.md)
- [schema-and-contract-pack-code-graph-chatbot.md](/mnt/c/work/india/codedb/schema-and-contract-pack-code-graph-chatbot.md)
- [execution-plan-code-graph-chatbot.md](/mnt/c/work/india/codedb/execution-plan-code-graph-chatbot.md)

## 1. Purpose

This document defines a concrete implementation plan for the deferred `process tracing` capability.

In this repository, `process tracing` means a bounded, heuristic flow-tracing layer built on top of the existing code graph. It is not full semantic program execution and it does not attempt to model arbitrary runtime behavior.

## 2. Product Boundary

The feature should answer questions such as:

- `show me the flow for invoice creation`
- `trace checkout from entry point to persistence`
- `what are the main steps from handler to database write`

The feature should not claim to:

- execute code
- fully understand framework magic
- resolve every dynamic dispatch case
- reconstruct every possible runtime path

The implementation target is a deterministic, testable approximation with explicit bounds.

## 3. Target API

Add a new API:

- `get_processes(repo_id, query=None, graph_path=None, index_root=None)`

### 3.1 Input Contract

Request shape:

```json
{
  "repo_id": "repo:abcd1234efgh5678",
  "query": "invoice"
}
```

`query` is optional. If present, it may match:

- an entry-point symbol
- a terminal symbol
- a skill name
- a path/name term

### 3.2 Output Contract

Response shape:

```json
{
  "processes": [
    {
      "process_id": "process:repo:abcd:create_invoice_handler:save_invoice:9af3",
      "label": "Create Invoice Flow",
      "confidence": 0.82,
      "step_count": 4,
      "entry_point": {
        "node_id": "function:src/api/invoice.py:create_invoice_handler:12",
        "name": "create_invoice_handler",
        "file_path": "src/api/invoice.py"
      },
      "terminal": {
        "node_id": "method:src/storage/repository.py:InvoiceRepository:save:20",
        "name": "save",
        "file_path": "src/storage/repository.py"
      },
      "skills": ["billing"],
      "steps": [
        {
          "step": 1,
          "node_id": "function:src/api/invoice.py:create_invoice_handler:12",
          "name": "create_invoice_handler",
          "file_path": "src/api/invoice.py",
          "skill": "billing"
        },
        {
          "step": 2,
          "node_id": "method:src/services/billing.py:BillingService:generate_invoice:33",
          "name": "generate_invoice",
          "file_path": "src/services/billing.py",
          "skill": "billing"
        }
      ]
    }
  ]
}
```

### 3.3 Hard Bounds

To keep the API usable and prompt-friendly:

- max `5` processes returned
- max `8` steps per process
- max traversal depth `6`
- max branching factor `3`

## 4. Implementation Phases

## Phase 1: Contract and Schema

### Goals

- define a stable process object
- extend the graph schema without disturbing current APIs

### Work

1. Add `Process` support to [models.py](/mnt/c/work/india/codedb/code_graph_core/graph/models.py)
2. Extend [schema.py](/mnt/c/work/india/codedb/code_graph_core/graph/schema.py) with:
   - `Process` node table
   - `Process -> Function`
   - `Process -> Method`
   - `Process -> Class`
   - `STEP_IN_PROCESS` relationship usage via `CodeRelation.type`
3. Keep the existing `step` property on `CodeRelation` for ordered process steps

### Acceptance Criteria

- schema bootstraps successfully with `Process`
- process records can be persisted without changing existing query APIs

## Phase 2: Fixture Repos

### Goals

- create deterministic repos that represent useful and noisy flows

### New Fixtures

1. `process_basic_app`
   - handler -> service -> repository
2. `process_jobs_app`
   - job -> service -> notifier
3. `process_branching_app`
   - one entry point with multiple branches
4. `process_noise_app`
   - many utility/helper calls that should not dominate the output

### Acceptance Criteria

- each fixture has a single intended lesson
- expected flows are obvious from the source tree

## Phase 3: Entry-Point Detection

### Goals

- identify likely process starts from the current graph

### New Module

- [process_detector.py](/mnt/c/work/india/codedb/code_graph_core/ingestion/process_detector.py)

### Heuristics

Prefer functions or methods that match one or more of:

- file path includes `api`, `app`, `handlers`, `routes`, `jobs`, `commands`
- exported/top-level function with outbound calls
- names like `main`, `run`, `execute`, `*Handler`, `*_handler`
- relatively low inbound call count and nonzero outbound call count

### Output

Return candidate entry points with:

- `node_id`
- `name`
- `file_path`
- heuristic confidence
- reason tags

### Acceptance Criteria

- expected entry points are found in fixtures
- obvious helpers are not ranked above handlers/jobs

## Phase 4: Flow Construction

### Goals

- derive likely downstream flows from entry points

### Approach

Traverse existing `CALLS` edges downstream:

1. start from a candidate entry point
2. walk forward while tracking visited nodes
3. stop on:
   - cycle
   - depth limit
   - branch limit
   - terminal heuristic

### Terminal Heuristics

Prefer terminals with names like:

- `save`
- `write`
- `publish`
- `send`
- `insert`
- `update`
- `delete`
- `persist`

Also allow terminals when:

- no further callees exist
- path crosses into a persistence/integration-heavy skill

### Deduplication

Deduplicate by normalized:

- entry point
- terminal
- ordered step names

### Acceptance Criteria

- fixture flows are stable across reindex
- duplicate utility-heavy paths are suppressed

## Phase 5: Ranking and Confidence

### Goals

- rank flows so the API returns the most useful ones first

### Ranking Signals

Increase score for:

- starts in likely entry-point files
- stays coherent within one or two skills
- ends at a likely side-effect terminal
- has moderate depth instead of trivial one-step utility calls

Decrease score for:

- utility-only paths
- deeply branching paths
- low-signal helpers
- duplicate terminal patterns

### Confidence Model

Expose a simple `0.0` to `1.0` confidence score derived from:

- entry-point confidence
- terminal confidence
- path cohesion
- branch ambiguity penalty

### Acceptance Criteria

- best expected flow is ranked first in fixtures
- confidence is deterministic across runs

## Phase 6: Index-Time Materialization

### Goals

- persist processes as graph objects during indexing

### Work

Update [builder.py](/mnt/c/work/india/codedb/code_graph_core/graph/builder.py):

1. run process detection after call resolution and skill materialization
2. create `Process` nodes
3. create ordered `STEP_IN_PROCESS` edges with `step`
4. optionally create `Process -> entry_point` and `Process -> terminal` links using existing `CodeRelation`

### Acceptance Criteria

- process nodes appear in Kuzu
- ordered steps are queryable
- indexing stats remain stable and bounded

## Phase 7: Query API

### Goals

- expose process tracing through the public query layer

### Work

Update [querying.py](/mnt/c/work/india/codedb/code_graph_core/api/querying.py):

1. add `get_processes(...)`
2. support optional query filtering by:
   - process label
   - entry-point name
   - terminal name
   - skill name
3. return bounded, compact process objects
4. add error handling aligned with existing contracts

### Acceptance Criteria

- process queries return stable JSON-like payloads
- empty query returns top-ranked processes
- term query narrows results correctly

## Phase 8: Tests

### Coverage Areas

1. entry-point detection
2. flow construction
3. terminal heuristics
4. deduplication
5. branch/depth bounds
6. persisted process schema
7. `get_processes(...)` contract tests
8. noisy fixture suppression tests

### Acceptance Criteria

- fixture expectations pass deterministically
- process outputs remain bounded

## Phase 9: REPL Support

### Goals

- make process tracing demoable in the existing chatbot surface

### Work

Update [repl.py](/mnt/c/work/india/codedb/code_graph_core/repl.py):

- add `processes <query>`
- add natural-language routes:
  - `show flow for <query>`
  - `trace <query>`
  - `show process for <query>`
- add compact process renderers
- reuse existing ambiguity handling if multiple candidate flows match

### Acceptance Criteria

- REPL can display top flows on fixture repos
- chat-style prompts route correctly

## Phase 10: Real-Repo Hardening

### Goals

- test the heuristics outside synthetic fixtures

### Work

Run the feature on a real repo such as `mssrc` and inspect:

- false-positive entry points
- noisy utility flows
- duplicated flows
- overlong or low-value paths

Tune:

- entry-point heuristics
- terminal heuristics
- ranking weights
- bounds

### Acceptance Criteria

- output stays concise
- top flows are at least directionally useful for demo and exploration

## 5. Files Expected to Change

Core code:

- [models.py](/mnt/c/work/india/codedb/code_graph_core/graph/models.py)
- [schema.py](/mnt/c/work/india/codedb/code_graph_core/graph/schema.py)
- [builder.py](/mnt/c/work/india/codedb/code_graph_core/graph/builder.py)
- [querying.py](/mnt/c/work/india/codedb/code_graph_core/api/querying.py)
- [repl.py](/mnt/c/work/india/codedb/code_graph_core/repl.py)

New modules:

- [process_detector.py](/mnt/c/work/india/codedb/code_graph_core/ingestion/process_detector.py)

Tests and fixtures:

- [tests](/mnt/c/work/india/codedb/tests)
- [fixtures](/mnt/c/work/india/codedb/tests/fixtures)

Docs:

- [prd-code-graph-chatbot.md](/mnt/c/work/india/codedb/prd-code-graph-chatbot.md)
- [tech-spec-code-graph-chatbot.md](/mnt/c/work/india/codedb/tech-spec-code-graph-chatbot.md)
- [schema-and-contract-pack-code-graph-chatbot.md](/mnt/c/work/india/codedb/schema-and-contract-pack-code-graph-chatbot.md)
- [execution-plan-code-graph-chatbot.md](/mnt/c/work/india/codedb/execution-plan-code-graph-chatbot.md)

## 6. Recommended Implementation Order

1. contract and schema
2. fixtures
3. entry-point detector
4. bounded flow builder
5. ranking and deduplication
6. index-time materialization
7. query API
8. tests
9. REPL support
10. real-repo hardening
11. doc updates

## 7. Key Constraint

Do not frame this feature as exact runtime truth.

The correct implementation target is:

- deterministic
- bounded
- prompt-friendly
- explicit about heuristics
- useful for code exploration

That is the only realistic way to make `process tracing` shippable in this codebase.
