# Execution Plan
## Local Code Graph Intelligence Core for Chatbot Integration

Status: Implemented v1
Related docs:

- [`prd-code-graph-chatbot.md`](/mnt/c/work/india/codedb/prd-code-graph-chatbot.md)
- [`tech-spec-code-graph-chatbot.md`](/mnt/c/work/india/codedb/tech-spec-code-graph-chatbot.md)

## 1. Objective

Build a minimal, local-first code graph system for chatbot integration with these v1 capabilities:

- index a local repository
- persist a graph in KuzuDB
- inspect repo status and indexing diagnostics
- search symbols/files
- fetch symbol context
- run impact analysis
- generate and serve skills as API objects
- demonstrate the features through a minimal local chatbot

Do not build:

- MCP
- editor hooks
- browser UI
- hosted services

## 2. Delivery Strategy

Deliver in four milestones:

1. Core indexing and graph persistence
2. Search and symbol context APIs
3. Impact analysis and skills API
4. Demo chatbot, hardening, and optional thin HTTP wrapper

Current implementation status:

1. Milestone 1 completed
2. Milestone 2 completed
3. Milestone 3 completed
4. Milestone 4 completed for the in-process demo surfaces and hardening path

Still deferred post-v1:

- optional thin HTTP wrapper
- process tracing APIs

Historical note:

- the milestone, work-breakdown, and ticket sections below are retained as the original delivery plan
- they should now be read as implemented v1 history unless a section explicitly says post-v1 or deferred

Guiding rule:

- only add process tracing after the core query surfaces are stable
- keep any process API contract reserved for post-v1.0 so it does not expand the initial delivery scope
- ship the first implementation as a Python in-process library, with any HTTP wrapper deferred to the last milestone

## 3. Milestone Plan

## Milestone 1: Core Indexing and Graph Persistence

Goal:

- ingest a repository and store a usable graph in KuzuDB

### 3.1 Deliverables

- repo scanner
- ignore rules
- language detection for TypeScript/JavaScript and Python
- Tree-sitter parsing
- symbol extraction for files, functions, methods, classes, interfaces
- graph schema
- KuzuDB persistence
- index metadata file

### 3.2 Tasks

1. Create project skeleton
- create a Python package layout from the technical spec
- wire `pytest`
- add formatting/linting baseline

2. Implement scanner
- recursive file discovery
- path normalization
- ignore rules for `.git`, dependency directories, build outputs, caches
- file-to-language mapping

3. Implement parser abstraction
- load Tree-sitter grammars
- parse a file into AST
- capture parse errors and skip safely

4. Implement symbol extraction
- TypeScript/JavaScript:
  - files
  - functions
  - classes
  - methods
  - imports
- Python:
  - files
  - functions
  - classes
  - methods
  - imports

5. Implement graph models
- node model
- relationship model
- deterministic IDs

6. Implement Kuzu schema and storage
- node tables
- `CodeRelation`
- insert/update strategy
- metadata persistence

7. Implement `index_repo(path)`
- orchestrate scan → parse → extract → graph build → persist

### 3.3 Acceptance Criteria

- indexing a small fixture repo completes successfully
- Kuzu contains the expected file and symbol nodes
- extracted symbols have deterministic IDs
- metadata file is written with index and diagnostic counts
- unsupported or broken files do not crash the run

### 3.4 Test Coverage

- scanner tests
- ignore rule tests
- parser smoke tests
- symbol extraction tests for TypeScript and Python fixtures
- Kuzu persistence smoke test

## Milestone 2: Search and Symbol Context

Goal:

- make the graph useful to a chatbot for exploration

### 3.5 Deliverables

- search API
- symbol context API
- bounded, LLM-friendly response format

### 3.6 Tasks

1. Implement query helpers
- lookup by node ID
- lookup by exact name
- lookup by file path

2. Implement search candidate retrieval
- exact symbol matches
- prefix/name matches
- file path matches
- optional text search fallback

3. Implement search ranking
- exact symbol name first
- exported symbols above non-exported
- symbols over plain files when relevant
- include skill/module hints later if available

4. Implement `search(repo_id, query, limit)`
- compact result schema
- bounded result count

5. Implement `get_symbol_context(repo_id, symbol, file_path?)`
- resolve a single symbol
- return callers
- return callees
- return file info
- return containing class if applicable

6. Add ambiguity handling
- if multiple matches, return candidates instead of fabricating one result

### 3.7 Acceptance Criteria

- chatbot can retrieve useful search results for known symbols
- exact symbol match outranks loose file text match
- symbol context returns direct callers and direct callees correctly for fixtures
- ambiguous symbol requests produce structured ambiguity responses

### 3.8 Test Coverage

- search ranking tests
- search contract tests
- symbol context tests
- ambiguity resolution tests

## Milestone 3: Impact Analysis and Skills API

Goal:

- expose structural reasoning and focused module context

### 3.9 Deliverables

- impact analysis API
- deterministic skill generation
- `list_skills`
- `get_skill`

### 3.10 Tasks

1. Implement graph traversal helpers
- upstream traversal
- downstream traversal
- depth-limited traversal
- edge-type filtering

2. Implement `get_impact(repo_id, target, direction, depth)`
- affected symbols grouped by depth
- affected files
- affected skills
- severity summary

3. Implement skill clustering baseline
- directory-first grouping
- merge strongly connected neighboring groups if needed
- minimum cluster size threshold

4. Implement skill labeling
- label from dominant module/folder
- fallback naming
- stable kebab-case skill name

5. Implement skill summarization
- deterministic templated summary
- no LLM dependency

6. Implement skill materialization
- persist skill objects at index time
- create `ModuleSkill` nodes
- create `BELONGS_TO_SKILL`
- create `RELATED_SKILL`

7. Implement `list_skills(repo_id)`
- summary list only

8. Implement `get_skill(repo_id, skill_name)`
- full skill object

### 3.11 Acceptance Criteria

- impact analysis identifies direct dependents correctly on fixtures
- traversal depth is reflected correctly in output
- at least one representative fixture repo produces meaningful skills
- `list_skills` and `get_skill` return compact, stable, prompt-ready objects
- related skills are generated when cross-cluster connectivity exists

### 3.12 Test Coverage

- impact traversal tests
- severity heuristic tests
- skill generation tests
- skill labeling tests
- skills API contract tests

## Milestone 4: Hardening and Integration Surface

Goal:

- make the system usable in a real chatbot workflow

### 3.13 Deliverables

- minimal local demo chatbot
- stable in-process API
- optional thin local HTTP wrapper
- improved diagnostics
- performance tuning

### 3.14 Tasks

1. Add repo status API
- `get_repo_status(repo_id)`
- index timestamp
- counts
- unresolved symbol stats

2. Build demo chatbot
- terminal-based local chat loop
- lightweight intent routing to core APIs
- compact renderers for search, context, impact, skills, and repo status
- demo script and usage notes for fixture repos

3. Improve indexing diagnostics
- unresolved import count
- unresolved call count
- skipped file count

4. Add output bounding
- caller/callee caps
- impact caps
- skill object size caps

5. Add performance tuning
- parser reuse
- batched inserts
- query path tuning

6. Add optional thin HTTP wrapper
- only if chatbot needs out-of-process calls
- keep one-to-one parity with in-process APIs

### 3.15 Acceptance Criteria

- demo chatbot can answer representative fixture questions by calling the core APIs
- APIs are stable and documented
- outputs remain bounded under larger fixture repos
- repo status exposes enough diagnostics to debug indexing quality
- optional HTTP wrapper does not add new business logic

## 4. Detailed Work Breakdown

## 4.1 Foundation

Tasks:

- initialize Python project
- add dependency management
- add CI or local test command
- create fixture repo directories

Dependency:

- none

## 4.2 Scanner and Parser

Tasks:

- path normalization
- ignore config
- file language mapping
- Tree-sitter loader
- parser error handling

Dependency:

- foundation complete

## 4.3 Extractors

Tasks:

- TypeScript extractor
- Python extractor
- import extraction
- method ownership extraction

Dependency:

- scanner and parser complete

## 4.4 Resolver

Tasks:

- symbol table
- same-file resolution
- explicit import resolution
- receiver-based method resolution
- unresolved symbol accounting

Dependency:

- extractors complete

## 4.5 Graph Persistence

Tasks:

- schema creation
- node insertion
- relationship insertion
- metadata persistence

Dependency:

- graph model complete

## 4.6 Query APIs

Tasks:

- search
- context
- impact
- skills
- repo status

Dependency:

- graph persistence complete

## 4.7 Quality Layer

Tasks:

- bounded outputs
- confidence scoring
- heuristics tuning
- fixture expansion

Dependency:

- query APIs complete

## 5. Suggested Issue Backlog

Recommended initial issue list:

1. Bootstrap Python package skeleton and tests
2. Add repository scanner with ignore rules
3. Add Tree-sitter parser loader for TypeScript and Python
4. Extract file/function/class/method symbols for TypeScript
5. Extract file/function/class/method symbols for Python
6. Build deterministic symbol IDs
7. Implement Kuzu schema and storage bootstrap
8. Implement `index_repo(path)`
9. Implement exact and fuzzy symbol lookup helpers
10. Implement `search(repo_id, query, limit)`
11. Implement `get_symbol_context`
12. Implement same-file and import-scoped call resolution
13. Implement upstream/downstream graph traversal
14. Implement `get_impact`
15. Implement directory-first skill clustering
16. Implement skill materialization and storage
17. Implement `list_skills`
18. Implement `get_skill`
19. Implement repo status and diagnostics
20. Build minimal demo chatbot
21. Add optional HTTP wrapper

## 6. Recommended Fixture Repositories

Create very small synthetic fixture repos instead of testing against large real repos first.

### Fixture A: TypeScript basic

Should include:

- imported function call
- class method call
- two modules
- one obvious skill cluster

### Fixture B: Python basic

Should include:

- local module imports
- class and method relationships
- top-level orchestration function

### Fixture C: Ambiguity

Should include:

- same symbol name in two files
- import-based disambiguation requirement

### Fixture D: Multi-module app

Should include:

- auth
- billing
- notifications

This fixture is for skills generation and cross-skill relationships.

### Fixture E: Impact traversal

Should include:

- one shared service called by multiple upstream entry points
- one downstream repository or persistence layer
- a clean depth-2 upstream impact scenario

## 7. Acceptance Demo Scenarios

The system is ready for a first real demo when all of these work on a fixture repo:

1. `index_repo(path)` succeeds
2. `get_repo_status(repo_id)` returns index counts and diagnostics
3. the demo chatbot can answer a repo-status question
4. the demo chatbot can answer a search question such as `auth`
5. the demo chatbot can answer a symbol-context question such as `validate_token`
6. the demo chatbot can answer an impact question for `BillingService.generate_invoice`
7. the demo chatbot can list skills like `auth`, `billing`, `notifications`
8. the demo chatbot can return the `billing` skill with key files, symbols, and representative flows

## 8. Quality Gates

Before moving from one milestone to the next:

### Gate 1

- all milestone tests pass
- fixture coverage exists
- no unbounded response payloads

### Gate 2

- search and context are accurate enough for manual chatbot trials
- ambiguity handling is explicit

### Gate 3

- skills are useful enough that a human would actually inject them into a prompt
- impact output is not obviously noisy on fixtures

## 9. Risks by Milestone

### Milestone 1 Risk

- extraction logic drifts into too many languages too early

Mitigation:

- stay with TypeScript/Python only

### Milestone 2 Risk

- search results feel like grep with extra steps

Mitigation:

- prioritize symbol-aware ranking and exact matches

### Milestone 3 Risk

- skills become low-quality directory summaries

Mitigation:

- require graph signals, entry points, and representative symbols

### Milestone 4 Risk

- optional HTTP wrapper expands scope

Mitigation:

- thin wrapper only, no additional business logic

## 10. Recommended Next Step

The planning artifacts are now sufficient to begin implementation.

Immediate next step:

1. scaffold the Python project
2. implement Milestone 1 from this plan
3. start with Tickets 1 through 10 in the schema-and-contract pack
