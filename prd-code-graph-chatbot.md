# Product Requirements Document
## Local Code Graph Intelligence Core for Chatbot Integration

Status: Implemented v1

## 1. Overview

This product is a clean-room reimplementation of the useful core ideas behind graph-powered code intelligence for AI, without copying product-specific integration surfaces such as MCP, editor hooks, web UI, or evaluation harnesses.

The system indexes a source repository into a local graph representation and exposes graph-derived capabilities directly to a custom chatbot through a small API surface. In addition to symbol and dependency queries, the system must expose `skills` as API resources: compact, generated module-context objects that can be fetched and injected into chatbot prompts on demand.

The product is local-first, embedded, and optimized for chatbot assistance on software repositories. The v1 deliverable should also include a minimal local demo chatbot so the core features can be exercised end to end.

Current v1 implementation notes:

- the in-process Python API is implemented
- the minimal local demo chatbot is implemented as a terminal REPL
- a minimal local desktop GUI is also included as an auxiliary demo surface

## 2. Problem

General-purpose chatbots can search code text but often fail to:

- understand symbol relationships across files
- trace call chains and execution flow
- estimate blast radius before changes
- identify the right module context to load for a task
- stay concise while preserving architectural relevance

The result is unreliable code assistance, especially on medium and large repositories.

## 3. Goals

The product must:

- index a local repository into a graph of symbols and relationships
- support graph-backed search and symbol context retrieval
- support impact analysis over code relationships
- leave room for execution-flow or process-style tracing in a later phase
- generate and serve `skills` as API resources for focused module context
- integrate directly with a custom chatbot without MCP or editor-specific tooling
- run locally with embedded storage

## 4. Non-Goals

The product will not, in v1:

- implement MCP
- implement editor plugins or hooks
- provide a browser UI
- provide a polished end-user chat product beyond a minimal local demo chatbot
- provide hosted or multi-tenant SaaS features
- provide autonomous code modification workflows
- attempt full semantic equivalence with GitNexus
- support every programming language in v1
- ship heuristic process tracing in the initial v1 release
- execute target application code at runtime

## 5. Target Users

- a developer building a private chatbot for codebase assistance
- a local AI workflow that needs architectural context beyond grep
- a tool builder who wants graph-powered repo understanding without GitNexus operational baggage

## 6. Primary Use Cases

1. A user asks the chatbot, “Where does auth token validation happen?”
2. A user asks, “What breaks if I change `UserService.save`?”
3. A user asks, “Show me the flow from HTTP entry point to persistence for checkout.”
4. A user asks, “Give me the skill/module context for billing.”
5. A user asks, “What files and symbols matter for refactoring notifications?”

## 7. Product Principles

- Local first: repository data and graph storage stay local by default.
- Embedded and lightweight: no mandatory long-running infrastructure.
- Minimal surface area: only the APIs required for chatbot integration.
- LLM-ready outputs: responses should be compact, structured, and prompt-friendly.
- Regenerable context: skills and graph artifacts must be refreshable after reindex.

## 8. Functional Requirements

### 8.1 Repository Indexing

The system must:

- accept a local repository path
- walk source files while respecting ignore rules
- detect supported languages by file type and path
- parse source files into symbols and relationships
- persist the resulting graph locally
- support full reindexing

The system should:

- support incremental reindexing in a later phase

### 8.2 Graph Model

The graph must support:

- files
- folders or modules
- functions
- methods
- classes or structs
- interfaces or traits where applicable
- edges for `DEFINES`, `IMPORTS`, `CALLS`, `EXTENDS`, `IMPLEMENTS`, `HAS_METHOD`

The graph may also support:

- namespaces, enums, constructors, properties, type aliases
- process nodes in a later phase
- community or cluster nodes

### 8.3 Search API

The product must expose a search capability that:

- accepts natural language or keyword queries
- returns relevant files and symbols
- prefers structural relevance over raw text frequency where possible
- returns compact summaries for chatbot consumption

V1 may use:

- full-text search only
- or full-text plus simple graph-aware reranking

### 8.4 Symbol Context API

The product must expose symbol context retrieval that returns:

- symbol metadata
- file location
- direct callers
- direct callees
- imports or dependencies where relevant
- owning module or inferred skill

### 8.5 Impact Analysis API

The product must expose impact analysis that returns:

- upstream dependents
- downstream dependencies
- traversal depth
- affected files and symbols
- a lightweight severity summary

### 8.6 Process / Flow API

The product may expose derived flow tracing after the core v1 APIs are stable:

- probable entry points
- multi-step call traces
- terminal nodes or key side effects

This feature is heuristic and reserved for post-v1.0 work rather than a blocker for the initial v1 release.

### 8.7 Skills as API

`Skills` are a core product feature in v1.

The system must generate focused module-context objects from the indexed graph and expose them as API resources.

Each skill should represent a meaningful functional area, such as:

- authentication
- billing
- notifications
- ingestion
- search

Each skill object must contain:

- stable skill name
- human-readable label
- short summary
- key files
- key symbols
- likely entry points
- representative call flows
- related skills or neighboring modules

The system must expose:

- `list_skills(repo_id)`
- `get_skill(repo_id, skill_name)`

The system should expose:

- `refresh_skills(repo_id)` as part of reindex
- skill metadata indicating generation timestamp and graph version

### 8.8 Chatbot Integration Surface

The v1 delivery target is an in-process library API implemented in Python.

A minimal local HTTP API is optional only after the in-process API is stable and only if the chatbot runtime requires out-of-process calls.

The API must be stable and small enough that the chatbot can treat it as a tool layer rather than a full product protocol.

### 8.9 Demo Chatbot

The v1 deliverable must include a minimal local demo chatbot that exercises the core APIs against an indexed repository.

The demo chatbot must:

- run locally without hosted dependencies
- accept free-form user prompts
- choose among the core APIs or simple intent routing to answer repository questions
- render structured results from search, symbol context, impact, repo status, and skills
- make it easy to demonstrate the system end to end on fixture repositories

The current implementation satisfies this requirement primarily through a terminal REPL with rule-based intent routing and conversational follow-up state.

The demo chatbot does not need:

- browser delivery
- multi-user support
- auth
- conversation persistence beyond a local session
- sophisticated agent behavior

### 8.10 Index Status and Diagnostics

The product must expose per-repository status and diagnostics that include:

- index timestamp and version
- detected languages
- file, node, edge, and skill counts
- unresolved import and unresolved call counts
- skipped file and parse error counts

## 9. API Surface

V1 target API surface:

- `index_repo(path)`
- `get_repo_status(repo_id)`
- `search(repo_id, query, limit)`
- `get_symbol_context(repo_id, symbol, file_path?)`
- `get_impact(repo_id, target, direction, depth)`
- `list_skills(repo_id)`
- `get_skill(repo_id, skill_name)`

Optional v1.1 or v2:

- `get_processes(repo_id, query?)`
- `cypher_query(repo_id, query)`
- `detect_changes(repo_id, git_ref or working_tree)`
- `rename_preview(repo_id, symbol, new_name)`

## 10. Skill Object Shape

Illustrative response shape:

```json
{
  "name": "billing",
  "label": "Billing",
  "summary": "Invoice generation, charge orchestration, and payment state updates.",
  "key_files": [
    "src/billing/service.ts",
    "src/billing/invoice.ts",
    "src/payments/gateway.ts"
  ],
  "key_symbols": [
    "BillingService",
    "generateInvoice",
    "capturePayment"
  ],
  "entry_points": [
    "createInvoiceHandler",
    "capturePaymentJob"
  ],
  "flows": [
    "createInvoiceHandler -> BillingService.generateInvoice -> InvoiceRepository.save",
    "capturePaymentJob -> PaymentGateway.capture -> BillingService.markPaid"
  ],
  "related_skills": [
    "orders",
    "notifications"
  ],
  "generated_at": "2026-03-14T00:00:00Z"
}
```

## 11. Supported Languages

V1 recommended language scope:

- TypeScript / JavaScript
- Python

V1.1 candidates:

- Go
- Java
- Ruby

Reason: start where Tree-sitter support and symbol resolution are tractable, then expand after query quality is acceptable.

## 12. Storage Requirements

The product will use embedded graph storage.

Preferred choice:

- KuzuDB

Rationale:

- lightweight embedded deployment
- graph-native query model
- suitable for local traversal and path analysis

The system may supplement KuzuDB with:

- a lightweight metadata store
- optional full-text indexing strategy if needed

## 13. Performance Requirements

V1 targets:

- index a small-to-medium repo locally without external services
- return search/context responses fast enough for interactive chat use
- keep prompt payloads compact and bounded

Initial non-binding targets:

- search/context API median response under 1 second on a warm local index
- impact queries under 2 seconds for common cases
- skill fetch under 300 ms on warm index

## 14. Quality Requirements

The product must prioritize:

- precision of direct symbol resolution
- usefulness of returned context to an LLM
- predictable, bounded output size

The product should avoid:

- returning giant raw subgraphs
- duplicating many near-identical results
- overclaiming confidence when resolution is fuzzy

## 15. Success Metrics

Functional success:

- the chatbot can answer architecture and dependency questions more accurately than plain grep
- users can fetch focused skill context instead of loading whole-repo summaries
- impact analysis highlights the right files and symbols for common refactors

System success:

- indexing succeeds on representative v1 repositories
- API latency is acceptable for interactive chatbot use
- outputs remain concise enough for repeated prompt injection

## 16. Risks

- symbol resolution quality may be poor without language-specific logic
- process inference may be too heuristic to be trusted initially
- skill generation may produce low-quality clusters without good community detection
- graph schema may grow too broad before v1 quality stabilizes
- KuzuDB adoption risk if project requirements later favor relational or search-heavy workloads

## 17. Mitigations

- start with two languages only
- make confidence visible in symbol and impact results
- keep process tracing reserved for post-v1 until the core APIs are proven
- define strict output schemas for chatbot consumption
- treat skills as generated summaries over graph communities, not as free-form prose

## 18. Rollout Plan

### Implemented v1

- index repositories
- build core graph
- expose repo status, search, symbol context, impact
- generate basic skills
- provide a local terminal demo chatbot
- provide a minimal local GUI explorer

### Post-v1 candidates

- improve resolution quality
- improve output bounds and diagnostics
- improve skill generation and related-skill links
- add process inference
- incremental indexing
- richer change analysis
- optional raw graph query surface

## 19. Open Questions

- Should search be graph-aware in v1 or remain simple FTS plus symbol scoring?
- Should skills be generated only from graph communities, or also from directory heuristics?
- How much confidence metadata should be exposed to the model versus hidden internally?
- After the Python library API is stable, is a secondary TypeScript wrapper worth maintaining?

## 20. Appendix: Explicit Exclusions from the Source Inspiration

This product intentionally excludes:

- MCP protocol compatibility
- HTTP serving as a first-class product feature unless needed for chatbot deployment
- editor-specific hooks
- packaged editor skill installation
- browser UI
- benchmark/eval harness

The intended product is the core intelligence layer plus `skills as API`, not a full developer platform.
