# Engine Gap Closure Plan
## Local Code Graph Intelligence Core for Chatbot Integration

Status: Proposed engine-parity implementation plan

Related docs:

- [prd-code-graph-chatbot.md](/mnt/c/work/india/codedb/prd-code-graph-chatbot.md)
- [tech-spec-code-graph-chatbot.md](/mnt/c/work/india/codedb/tech-spec-code-graph-chatbot.md)
- [schema-and-contract-pack-code-graph-chatbot.md](/mnt/c/work/india/codedb/schema-and-contract-pack-code-graph-chatbot.md)
- [process-tracing-implementation-plan.md](/mnt/c/work/india/codedb/process-tracing-implementation-plan.md)
- [semantic-search-implementation-plan.md](/mnt/c/work/india/codedb/semantic-search-implementation-plan.md)
- [skills-parity-implementation-plan.md](/mnt/c/work/india/codedb/skills-parity-implementation-plan.md)

## 1. Purpose

This document defines a concrete plan for closing the main remaining engine-level parity gaps in this repository.

This plan explicitly excludes:

- rename planning
- multi-repo engine support
- MCP/resources/UI parity

It focuses on the remaining engine capabilities that materially affect code understanding quality.

## 2. Remaining Engine Gaps in Scope

The in-scope gaps are:

1. process tracing API and materialized process graph
2. semantic / hybrid retrieval
3. search quality and retrieval depth
4. change-aware analysis
5. raw graph query API
6. resolution quality improvements
7. graph diagnostics / hygiene queries
8. richer interaction between skills and process data

## 3. Recommended Priority Order

Recommended implementation order:

1. process tracing API and materialized process graph
2. semantic / hybrid retrieval
3. search quality and retrieval depth
4. change-aware analysis
5. raw graph query API
6. resolution quality improvements
7. graph diagnostics / hygiene queries
8. richer skills/process integration

Reason:

- process tracing and semantic retrieval are the largest functional gaps
- search quality benefits immediately from both
- change-aware analysis depends on strong graph and retrieval foundations
- raw query surface and diagnostics are valuable but lower leverage for end-user intelligence quality

## 4. Workstream A: Process Tracing

Use [process-tracing-implementation-plan.md](/mnt/c/work/india/codedb/process-tracing-implementation-plan.md) as the detailed plan.

### Target Outcome

Add:

- `Process` nodes
- ordered process steps
- `get_processes(...)`
- deterministic process ranking and confidence

### Required Acceptance Criteria

- process graph materialized at index time
- bounded process payloads exposed via Python API
- fixture coverage for useful and noisy flows

## 5. Workstream B: Semantic / Hybrid Retrieval

Use [semantic-search-implementation-plan.md](/mnt/c/work/india/codedb/semantic-search-implementation-plan.md) as the detailed plan.

### Target Outcome

Improve search so natural-language queries can find relevant code even without lexical overlap.

### Required Acceptance Criteria

- lexical exact matches still win
- semantic retrieval rescues weak lexical matches
- feature remains local-first and optional

## 6. Workstream C: Search Quality and Retrieval Depth

Even before or alongside embeddings, improve the current search pipeline.

### Planned Improvements

1. improve lexical scoring
   - stronger exact-name bias
   - token-aware matching
   - weak fuzzy matching for near-miss identifiers
2. add graph-aware expansion
   - consider callers/callees for reranking
   - consider skill membership for relevance boosts
   - consider entry-point/process participation once available
3. add result diversification
   - avoid returning many near-identical siblings
4. add score explanations
   - keep `reason` compact but more informative

### Likely Files

- [querying.py](/mnt/c/work/india/codedb/code_graph_core/api/querying.py)

### Acceptance Criteria

- better natural query ranking on fixtures
- less duplication in top search results
- exact identifiers still rank first

## 7. Workstream D: Change-Aware Analysis

Add a graph-aware API for understanding the impact of code changes from a diff or working tree.

### Proposed API

- `detect_changes(repo_id, git_ref=None, working_tree=False, graph_path=None, index_root=None)`

### Core Behavior

1. identify changed files
2. map changed files to symbols
3. traverse impact outward from changed symbols
4. summarize:
   - changed files
   - changed symbols
   - affected symbols
   - affected skills
   - severity

### Constraints

- keep git integration local and optional
- degrade gracefully if no git metadata is available

### Likely Files

- [querying.py](/mnt/c/work/india/codedb/code_graph_core/api/querying.py)
- new helper module under `code_graph_core/ingestion/` or `code_graph_core/storage/`

### Acceptance Criteria

- static diff-based impact works on synthetic repos
- output is bounded and stable
- no dependency on hosted git services

## 8. Workstream E: Raw Graph Query API

Expose a supported low-level graph query surface for advanced use.

### Proposed API

- `cypher_query(repo_id, query, graph_path=None, index_root=None)`

### Constraints

- read-only only
- bounded row count
- no schema mutation
- no writes, deletes, or arbitrary unsafe operations

### Use Cases

- debugging graph quality
- advanced repo analysis
- validating process/skill materialization

### Acceptance Criteria

- users can run safe read-only queries
- output is normalized and bounded
- API is clearly documented as advanced/internal-use oriented

## 9. Workstream F: Resolution Quality

The current graph exists, but resolution still has room to improve materially.

### Priorities

1. import resolution
   - alias handling
   - more default-import coverage
   - broader relative module resolution cases
2. call resolution
   - receiver-based method resolution
   - constructor/class instantiation patterns
   - better imported symbol disambiguation
3. inheritance-aware resolution
   - use `EXTENDS`/`IMPLEMENTS` to improve method lookup
4. framework-aware heuristics where practical
   - only if tightly scoped and well-tested

### Acceptance Criteria

- unresolved-call noise remains low
- direct context quality improves on real repos
- no broad regression in indexing speed

## 10. Workstream G: Graph Diagnostics and Hygiene Queries

Add read-only diagnostic APIs that help users understand graph quality and code hygiene.

### Candidate APIs

- `get_graph_diagnostics(repo_id, ...)`
- `find_orphaned_symbols(repo_id, ...)`
- `find_unreferenced_exports(repo_id, ...)`
- `find_dependency_hotspots(repo_id, ...)`

### Core Value

- debug graph quality
- identify dead code
- surface architecture hotspots

### Acceptance Criteria

- outputs remain bounded
- diagnostics clearly separate graph-quality issues from code-quality findings

## 11. Workstream H: Skills and Process Integration

This should happen after process tracing exists.

### Improvements

1. use process participation to improve skill summaries
2. use process entry points to improve skill entry-point selection
3. use materialized processes to generate better representative skill flows
4. use process overlap to improve related-skill ranking

### Goal

Make skills more architectural and less directory-derived.

### Acceptance Criteria

- skill flows become more representative
- related-skill ranking improves
- skill summaries better reflect actual workflows

## 12. Execution Phases

## Phase 1

- process tracing
- semantic retrieval

## Phase 2

- search quality improvements
- resolution quality improvements

## Phase 3

- change-aware analysis
- raw graph query API

## Phase 4

- diagnostics APIs
- skills/process integration

## 13. Testing Strategy

Every workstream should have:

1. unit tests
2. fixture contract tests
3. bounded-output assertions
4. real-repo hardening on `mssrc` or equivalent

Avoid implementing any workstream without fixture-first coverage.

## 14. Documentation Strategy

Update the main spec set only after each workstream stabilizes:

- [prd-code-graph-chatbot.md](/mnt/c/work/india/codedb/prd-code-graph-chatbot.md)
- [tech-spec-code-graph-chatbot.md](/mnt/c/work/india/codedb/tech-spec-code-graph-chatbot.md)
- [schema-and-contract-pack-code-graph-chatbot.md](/mnt/c/work/india/codedb/schema-and-contract-pack-code-graph-chatbot.md)
- [execution-plan-code-graph-chatbot.md](/mnt/c/work/india/codedb/execution-plan-code-graph-chatbot.md)

Do not mark parity complete until:

- the Python APIs exist
- the outputs are bounded and deterministic
- the feature works on both fixtures and a real repo

## 15. Key Constraint

Do not chase product-surface parity before engine-quality parity.

The correct target is:

- stronger graph fidelity
- stronger retrieval quality
- stronger bounded Python APIs

That is the fastest path to meaningful engine-level parity in this repository.
