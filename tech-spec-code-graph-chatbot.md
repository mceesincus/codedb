# Technical Specification
## Local Code Graph Intelligence Core for Chatbot Integration

Status: Draft v1
Related PRD: [`prd-code-graph-chatbot.md`](/mnt/c/work/india/codedb/prd-code-graph-chatbot.md)

## 1. Scope

This document defines the technical design for a local-first code graph system intended to power a custom chatbot. It covers:

- repository ingestion
- graph schema
- KuzuDB storage model
- search and query APIs
- impact analysis
- skills generation and skills API
- a reserved post-v1 extension point for process tracing

It explicitly excludes:

- MCP
- editor hooks
- browser UI
- GitNexus compatibility work

## 2. Architecture

### 2.1 High-Level Components

```text
+-------------------+
| Repo Scanner      |
+---------+---------+
          |
          v
+-------------------+
| Parser Layer      |
| Tree-sitter       |
+---------+---------+
          |
          v
+-------------------+
| Symbol Resolver   |
| imports/calls/etc |
+---------+---------+
          |
          v
+-------------------+
| Graph Builder     |
+---------+---------+
          |
          v
+-------------------+
| KuzuDB Store      |
+----+---------+----+
     |         |
     v         v
+---------+  +------------------+
| Query   |  | Skill Generator  |
| Service |  +------------------+
+----+----+
     |
     v
+-------------------+
| Demo Chatbot      |
| / Chatbot Tool API|
+-------------------+
```

### 2.2 Runtime Model

V1 runtime options:

1. In-process library
2. Minimal local HTTP service

Preferred implementation sequence:

1. Build core as an in-process library
2. Add thin HTTP wrapper only if the chatbot runtime needs process isolation

Reason:

- avoids premature protocol design
- keeps testing simple
- avoids “serving baggage” unless needed

## 3. Technology Choices

### 3.1 Language

Recommended implementation language:

- Python

Rationale:

- easy chatbot integration
- easy orchestration and testing
- strong ecosystem for local APIs and CLI wrappers

Alternative:

- TypeScript if your chatbot host and existing stack are already Node-centric

### 3.2 Parser

Use Tree-sitter.

Required v1 grammars:

- TypeScript / JavaScript
- Python

### 3.3 Storage

Use KuzuDB as the embedded graph store.

KuzuDB responsibilities:

- node storage
- relationship storage
- graph traversal queries
- optional full-text lookup if sufficient

Optional adjunct stores:

- local metadata JSON for index status
- optional lightweight search index if Kuzu FTS is insufficient

## 4. Repository Layout

Suggested project layout:

```text
code_graph_core/
  api/
    search.py
    context.py
    impact.py
    skills.py
  ingestion/
    scanner.py
    parser.py
    symbol_extractor.py
    import_resolver.py
    call_resolver.py
    skill_generator.py
  graph/
    schema.py
    builder.py
    models.py
  storage/
    kuzu_store.py
    metadata.py
  languages/
    typescript.py
    python.py
    shared.py
  tests/
    fixtures/
    test_indexing.py
    test_search.py
    test_context.py
    test_impact.py
    test_skills.py
  demo/
    chatbot.py
    intent_router.py
    renderers.py
```

Reserved for post-v1 if process tracing proves worthwhile:

- `api/processes.py`
- `ingestion/process_detector.py`

## 5. Data Model

### 5.1 Node Types

Required node types in v1:

- `Repository`
- `Folder`
- `File`
- `Function`
- `Method`
- `Class`
- `Interface`
- `ModuleSkill`

Optional node types for v1.1:

- `Process`
- `Struct`
- `Trait`
- `Enum`
- `Property`
- `Constructor`
- `TypeAlias`

### 5.2 Relationship Types

Required relationships:

- `CONTAINS`
- `DEFINES`
- `IMPORTS`
- `CALLS`
- `EXTENDS`
- `IMPLEMENTS`
- `HAS_METHOD`
- `BELONGS_TO_SKILL`
- `RELATED_SKILL`

Reserved for v1.1+ process tracing:

- `STEP_IN_PROCESS`

### 5.3 Common Node Fields

All nodes should have:

- `id`
- `label`
- `name`
- `repo_id`
- `file_path` where applicable

Symbol-like nodes should also have:

- `start_line`
- `end_line`
- `language`
- `signature`
- `visibility`
- `is_exported`
- `content_hash` optional

### 5.4 Relationship Fields

Relationships should include:

- `type`
- `confidence`
- `reason`
- `created_at` optional

`STEP_IN_PROCESS` should include:

- `step`

## 6. Identity Strategy

Every node ID must be stable across reindex if the underlying symbol identity is unchanged.

Recommended ID format:

- `file:{normalized_path}`
- `function:{normalized_path}:{symbol_name}:{start_line}`
- `method:{normalized_path}:{owner_name}:{symbol_name}:{start_line}`
- `class:{normalized_path}:{class_name}:{start_line}`
- `skill:{repo_id}:{skill_name}`
- `process:{repo_id}:{entry_symbol}:{terminal_symbol}:{hash}` reserved for post-v1

Reason:

- deterministic IDs simplify updates and debugging
- line-based identity is acceptable for v1

## 7. Ingestion Pipeline

### 7.1 Step 1: Scan Repository

Inputs:

- `repo_path`

Outputs:

- normalized list of candidate source files

Responsibilities:

- recursive walk
- ignore `.git`, dependencies, build outputs, caches
- language detection from extension/path

### 7.2 Step 2: Parse Files

For each supported file:

- parse Tree-sitter AST
- extract top-level symbols
- extract symbol ranges
- extract imports
- extract call expressions
- extract class/interface inheritance metadata

Store raw extracted artifacts in memory before graph insertion.

### 7.3 Step 3: Build Symbol Table

Construct a symbol table keyed by:

- file-local name
- exported symbol name
- module importable name
- class-method ownership

The symbol table is the basis for later call resolution.

### 7.4 Step 4: Resolve Imports

Import resolution rules for v1:

1. same-file definitions
2. explicit named imports
3. default imports
4. relative module resolution
5. package-level resolution where tractable

Output:

- `IMPORTS` edges from file to target file or symbol

### 7.5 Step 5: Resolve Calls

Call resolution rules for v1:

1. local definitions
2. imported definitions
3. class receiver-based method resolution
4. fallback to unresolved call record if ambiguity remains

Each resolved call edge must carry:

- confidence score
- reason code, such as:
  - `same_file`
  - `import_scoped`
  - `receiver_resolved`
  - `ambiguous_fallback`

Unresolved calls should not be silently dropped. They should be counted in indexing stats.

### 7.6 Step 6: Graph Assembly

Insert:

- folder/file structure
- symbol nodes
- structural relationships
- dependency/call relationships

### 7.7 Reserved Extension: Process Detection

Process detection is intentionally out of scope for the initial v1 implementation.

When added later, the likely baseline is:

1. find likely entry points
2. traverse outward on `CALLS`
3. stop at depth limit or terminal nodes
4. deduplicate traces by entry-terminal pair

Likely entry point heuristics:

- exported function
- framework route handler naming
- top-level service or command names
- low inbound call count and nonzero outbound calls

This remains a reserved extension so the most heuristic feature does not block indexing or core query quality.

### 7.8 Skill Generation

Skill generation runs after graph assembly.

Inputs:

- graph nodes and relationships

Outputs:

- `ModuleSkill` nodes
- `BELONGS_TO_SKILL` edges
- `RELATED_SKILL` edges
- serialized skill API objects

## 8. Skill Generation Design

### 8.1 Goal

Generate compact module-context units that are useful to a chatbot.

### 8.2 Candidate Grouping Strategies

Preferred order:

1. graph community detection
2. folder/module clustering fallback
3. merged hybrid heuristic

For v1, use a practical hybrid:

- start from dominant directory clusters
- refine with graph connectivity

Reason:

- simpler and more predictable than full community detection
- good enough for early skills quality

### 8.3 Skill Selection Rules

A skill should be created only if a cluster has:

- at least `N` symbols, recommended `N = 3`
- enough internal cohesion
- a meaningful label candidate

### 8.4 Skill Labeling

Labeling priority:

1. dominant directory/module name
2. dominant exported class/function family
3. fallback synthetic label

Skill names should be:

- stable
- lowercase
- kebab-case

### 8.5 Skill Contents

Each skill object should include:

- `name`
- `label`
- `summary`
- `key_files`
- `key_symbols`
- `entry_points`
- `flows`
- `related_skills`
- `generated_at`
- `stats`

Summary generation in v1 should be deterministic and template-driven, not LLM-generated.

## 9. KuzuDB Schema

### 9.1 Tables

Define node tables for:

- `Repository`
- `Folder`
- `File`
- `Function`
- `Method`
- `Class`
- `Interface`
- `ModuleSkill`

Define relationship table:

- `CodeRelation`

Optional:

- `SkillMaterialization` table if skill objects are persisted as blobs
- `Process` table and `STEP_IN_PROCESS` usage in a later phase

### 9.2 Recommended Minimal Node Fields

Use snake_case field names in both persisted metadata and API-facing contracts so query code does not need to translate between storage and response shapes.

Example:

```text
File(
  id STRING,
  name STRING,
  repo_id STRING,
  file_path STRING,
  language STRING
)

Function(
  id STRING,
  name STRING,
  repo_id STRING,
  file_path STRING,
  start_line INT64,
  end_line INT64,
  signature STRING,
  is_exported BOOLEAN
)

ModuleSkill(
  id STRING,
  name STRING,
  repo_id STRING,
  label STRING,
  summary STRING
)
```

Relationship fields:

```text
CodeRelation(
  from,
  to,
  type STRING,
  confidence DOUBLE,
  reason STRING,
  step INT64
)
```

### 9.3 Query Indexing

Need indexes on:

- `id`
- `name`
- `file_path`
- skill `name`

If Kuzu text search is inadequate, add an auxiliary search structure outside the graph.

## 10. Search Design

### 10.1 V1 Search Strategy

V1 search may be two-stage:

1. text or name-based candidate retrieval
2. graph-aware reranking

Ranking signals:

- exact symbol name matches
- file path matches
- exported symbols
- symbols with high structural degree
- symbols tied to matching skills

### 10.2 Search Output Contract

Search response should contain:

- result type
- display name
- file path
- line range
- short reason or relevance explanation
- associated skill if known

Example:

```json
{
  "results": [
    {
      "type": "Function",
      "name": "validate_token",
      "file_path": "src/auth/tokens.py",
      "start_line": 18,
      "end_line": 43,
      "reason": "Exact symbol name match, linked to auth skill",
      "skill": "auth"
    }
  ]
}
```

## 11. Symbol Context Design

### 11.1 Input

- symbol name
- optional file path
- optional exact node ID later

### 11.2 Output

- symbol metadata
- direct callers
- direct callees
- imports/dependencies
- containing skill
- containing file

Bound results:

- max callers
- max callees
- max related files

## 12. Impact Analysis Design

### 12.1 Traversal

Impact analysis traverses:

- upstream: what depends on target
- downstream: what target depends on

Traversal uses relationship filters:

- `CALLS`
- `IMPORTS`
- `EXTENDS`
- `IMPLEMENTS`
- `HAS_METHOD`

### 12.2 Output

Return:

- target
- direction
- depth-labeled affected symbols
- affected files
- affected skills
- severity summary

Severity heuristic:

- `HIGH` if many direct callers or cross-skill spread
- `MEDIUM` for moderate multi-file spread
- `LOW` for local-only impact

## 13. Process API Design

Process tracing is reserved for post-v1.0 work and must not block the core indexing, search, context, impact, or skills surfaces.

API returns:

- process name
- step sequence
- involved files
- involved skills

Process output should remain compact and avoid full graph dumps.

## 14. Skills API Design

### 14.1 `list_skills(repo_id)`

Returns:

- skill name
- label
- short summary
- counts for files and symbols

### 14.2 `get_skill(repo_id, skill_name)`

Returns full skill object:

- summary
- key files
- key symbols
- entry points
- flows
- related skills

### 14.3 Materialization

Two implementation options:

1. generate skills on every request
2. materialize skills at index time

Recommended:

- materialize at index time
- reload from Kuzu or metadata on request

Reason:

- lower latency
- deterministic outputs
- simpler chatbot integration

## 15. Demo Chatbot Design

The demo chatbot is a thin local client over the same in-process Python APIs used by tests and any later integrations.

Requirements:

- no business logic beyond lightweight intent routing and response rendering
- no hidden access path that bypasses the public core APIs
- terminal-first UX, such as a REPL or simple CLI loop
- easy switching between fixture repos for demos

Suggested flow:

1. user selects or indexes a repository
2. user enters a question
3. lightweight routing maps the question to one of:
   - `get_repo_status`
   - `search`
   - `get_symbol_context`
   - `get_impact`
   - `list_skills`
   - `get_skill`
4. chatbot prints compact structured output plus a short natural-language summary

Keep the demo deterministic where possible. The purpose is feature demonstration, not autonomous reasoning.

## 16. Metadata and Index State

Store per-repo metadata:

- `repo_id`
- source path
- last indexed timestamp
- supported languages found
- counts of files, nodes, edges
- skipped file count
- parse error count
- unresolved import count
- unresolved call count
- skill count
- index version

Recommended storage:

- JSON metadata file adjacent to KuzuDB

## 17. Error Handling

The system must degrade gracefully:

- unsupported files are skipped
- parse failures are recorded, not fatal by default
- unresolved symbols do not abort indexing
- partial indexing stats remain inspectable

API errors must be structured:

```json
{
  "error": {
    "code": "SYMBOL_NOT_FOUND",
    "message": "No symbol matched 'validateToken'",
    "details": {}
  }
}
```

## 18. Testing Strategy

### 18.1 Unit Tests

Need unit tests for:

- file scanning and ignore rules
- symbol extraction
- import resolution
- call resolution
- skill generation
- impact traversal

### 18.2 Fixture Tests

Create small synthetic repos for:

- TypeScript imports and methods
- Python modules and classes
- ambiguous call resolution
- cross-module skill generation
- depth-grouped impact traversal

### 18.3 Contract Tests

API contract tests for:

- search
- symbol context
- impact
- skills list/get

### 18.4 Quality Tests

Manual goldens for:

- expected top search results
- expected callers/callees
- expected skill membership

### 18.5 Demo Smoke Tests

Need at least one smoke test that verifies the demo chatbot can:

- load or select a fixture repository
- route a representative question to the correct core API
- render a bounded answer without crashing

## 19. Implementation Phases

### Phase A

- repo scanner
- parser integration
- symbol extraction
- basic graph insert

### Phase B

- import and call resolution
- context API
- search API

### Phase C

- impact API
- skill generation
- skills API

### Phase D

- demo chatbot
- output quality tuning
- latency tuning
- optional HTTP wrapper

## 20. Open Decisions

- Kuzu-only search versus Kuzu plus external lightweight text index
- exact community detection versus directory-first skill generation
- whether skill objects live only in graph rows or also in a cached JSON materialization
- whether a secondary TypeScript wrapper is needed after the Python library API stabilizes

## 21. Recommended Build Order

1. Implement TypeScript/Python parsing for two languages
2. Implement graph schema and Kuzu persistence
3. Implement symbol context API
4. Implement search API
5. Implement impact API
6. Implement deterministic skill generation
7. Add the minimal demo chatbot on top of the stable core APIs
8. Add process tracing only after the above is stable

This order minimizes risk and gets chatbot-usable value early while keeping the most heuristic feature, process tracing, from blocking the core product.
