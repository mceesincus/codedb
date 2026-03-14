# Schema and Contract Pack
## Local Code Graph Intelligence Core for Chatbot Integration

Status: Draft v1
Related docs:

- [`prd-code-graph-chatbot.md`](/mnt/c/work/india/codedb/prd-code-graph-chatbot.md)
- [`tech-spec-code-graph-chatbot.md`](/mnt/c/work/india/codedb/tech-spec-code-graph-chatbot.md)
- [`execution-plan-code-graph-chatbot.md`](/mnt/c/work/india/codedb/execution-plan-code-graph-chatbot.md)

## 1. Purpose

This document turns the PRD, technical spec, and execution plan into build-ready artifacts:

- KuzuDB schema definitions
- API request/response contracts
- fixture repository definitions
- first 10 implementation tickets

The minimal demo chatbot is a delivery requirement, but it should sit on top of these contracts rather than introduce a separate product API.

## 2. Repository Identity

Each indexed repository must have a stable `repo_id`.

Recommended format:

- `repo:{sha256(abs_repo_path)[:16]}`

Stored metadata fields:

- `repo_id`
- `repo_path`
- `repo_name`
- `indexed_at`
- `index_version`
- `languages_detected`
- `file_count`
- `node_count`
- `edge_count`
- `skipped_file_count`
- `parse_error_count`
- `unresolved_import_count`
- `unresolved_call_count`
- `skill_count`

## 3. KuzuDB Schema

Use snake_case field names in the schema so storage fields line up with the API and metadata contracts.

## 3.1 Core Node Tables (v1)

### Repository

```cypher
CREATE NODE TABLE Repository(
  id STRING,
  name STRING,
  repo_path STRING,
  indexed_at STRING,
  index_version STRING,
  PRIMARY KEY (id)
);
```

### Folder

```cypher
CREATE NODE TABLE Folder(
  id STRING,
  repo_id STRING,
  name STRING,
  file_path STRING,
  PRIMARY KEY (id)
);
```

### File

```cypher
CREATE NODE TABLE File(
  id STRING,
  repo_id STRING,
  name STRING,
  file_path STRING,
  language STRING,
  is_test BOOLEAN,
  PRIMARY KEY (id)
);
```

### Function

```cypher
CREATE NODE TABLE Function(
  id STRING,
  repo_id STRING,
  name STRING,
  file_path STRING,
  language STRING,
  start_line INT64,
  end_line INT64,
  signature STRING,
  visibility STRING,
  is_exported BOOLEAN,
  PRIMARY KEY (id)
);
```

### Method

```cypher
CREATE NODE TABLE Method(
  id STRING,
  repo_id STRING,
  name STRING,
  owner_name STRING,
  file_path STRING,
  language STRING,
  start_line INT64,
  end_line INT64,
  signature STRING,
  visibility STRING,
  is_exported BOOLEAN,
  PRIMARY KEY (id)
);
```

### Class

```cypher
CREATE NODE TABLE Class(
  id STRING,
  repo_id STRING,
  name STRING,
  file_path STRING,
  language STRING,
  start_line INT64,
  end_line INT64,
  visibility STRING,
  is_exported BOOLEAN,
  PRIMARY KEY (id)
);
```

### Interface

```cypher
CREATE NODE TABLE Interface(
  id STRING,
  repo_id STRING,
  name STRING,
  file_path STRING,
  language STRING,
  start_line INT64,
  end_line INT64,
  visibility STRING,
  is_exported BOOLEAN,
  PRIMARY KEY (id)
);
```

### ModuleSkill

```cypher
CREATE NODE TABLE ModuleSkill(
  id STRING,
  repo_id STRING,
  name STRING,
  label STRING,
  summary STRING,
  generated_at STRING,
  file_count INT64,
  symbol_count INT64,
  entry_point_count INT64,
  flow_count INT64,
  PRIMARY KEY (id)
);
```

## 3.2 Core Relationship Table (v1)

Use one relationship table for all graph edges.

```cypher
CREATE REL TABLE CodeRelation(
  FROM Repository TO Folder,
  FROM Folder TO Folder,
  FROM Folder TO File,
  FROM File TO Function,
  FROM File TO Class,
  FROM File TO Interface,
  FROM Class TO Method,
  FROM File TO File,
  FROM Function TO Function,
  FROM Function TO Method,
  FROM Method TO Function,
  FROM Method TO Method,
  FROM Class TO Class,
  FROM Class TO Interface,
  FROM File TO ModuleSkill,
  FROM Function TO ModuleSkill,
  FROM Method TO ModuleSkill,
  FROM Class TO ModuleSkill,
  FROM Interface TO ModuleSkill,
  FROM ModuleSkill TO ModuleSkill
);
```

Relationship properties:

```text
type STRING
confidence DOUBLE
reason STRING
step INT64
```

Supported `type` values in v1:

- `CONTAINS`
- `DEFINES`
- `IMPORTS`
- `CALLS`
- `EXTENDS`
- `IMPLEMENTS`
- `HAS_METHOD`
- `BELONGS_TO_SKILL`
- `RELATED_SKILL`

Reserved for post-v1.0 process tracing:

- `STEP_IN_PROCESS`

## 3.3 Reserved Post-v1 Schema Extension

Do not create process-tracing tables or edges in the initial v1 schema bootstrap.

### Process

```cypher
CREATE NODE TABLE Process(
  id STRING,
  repo_id STRING,
  name STRING,
  label STRING,
  entry_point_id STRING,
  terminal_id STRING,
  step_count INT64,
  PRIMARY KEY (id)
);
```

When process tracing is introduced later, extend the graph schema to allow:

- `Process -> Function`
- `Process -> Method`
- `Process -> Class`
- `STEP_IN_PROCESS` edges with ordered `step` values

## 3.4 Required Indexes / Lookups

At minimum, queries must support fast lookups by:

- node `id`
- symbol `name`
- `file_path`
- skill `name`

If Kuzu native indexing is not enough for search quality or latency, add an auxiliary name/text lookup structure in application code.

## 4. Deterministic ID Definitions

## 4.1 File and Folder IDs

- `folder:{normalized_path}`
- `file:{normalized_path}`

## 4.2 Symbol IDs

- `function:{normalized_path}:{name}:{start_line}`
- `class:{normalized_path}:{name}:{start_line}`
- `interface:{normalized_path}:{name}:{start_line}`
- `method:{normalized_path}:{owner_name}:{name}:{start_line}`

## 4.3 Skill IDs

- `skill:{repo_id}:{skill_name}`

## 4.4 Process IDs

Reserved for post-v1:

- `process:{repo_id}:{entry_symbol_name}:{terminal_symbol_name}:{short_hash}`

## 5. API Contracts

All APIs should return structured JSON-like objects whether exposed in-process or via HTTP.

Use snake_case in requests and responses. Storage, metadata, and API layers should share the same field names unless a library constraint forces an adapter.

## 5.1 Common Error Contract

```json
{
  "error": {
    "code": "SYMBOL_NOT_FOUND",
    "message": "No symbol matched 'validate_token'",
    "details": {}
  }
}
```

Required error codes:

- `REPO_NOT_FOUND`
- `INDEX_NOT_FOUND`
- `INVALID_REQUEST`
- `SYMBOL_NOT_FOUND`
- `AMBIGUOUS_SYMBOL`
- `SKILL_NOT_FOUND`
- `INTERNAL_ERROR`

## 5.2 `index_repo`

### Request

```json
{
  "path": "/abs/path/to/repo"
}
```

### Response

```json
{
  "repo_id": "repo:abcd1234efgh5678",
  "repo_name": "my-repo",
  "indexed_at": "2026-03-14T10:00:00Z",
  "stats": {
    "file_count": 42,
    "node_count": 210,
    "edge_count": 388,
    "skill_count": 4,
    "skipped_file_count": 1,
    "parse_error_count": 1,
    "unresolved_import_count": 3,
    "unresolved_call_count": 12
  }
}
```

## 5.3 `get_repo_status`

### Request

```json
{
  "repo_id": "repo:abcd1234efgh5678"
}
```

### Response

```json
{
  "repo_id": "repo:abcd1234efgh5678",
  "repo_name": "my-repo",
  "indexed_at": "2026-03-14T10:00:00Z",
  "index_version": "v1",
  "languages_detected": ["typescript", "python"],
  "stats": {
    "file_count": 42,
    "node_count": 210,
    "edge_count": 388,
    "skill_count": 4,
    "skipped_file_count": 1,
    "parse_error_count": 1,
    "unresolved_import_count": 3,
    "unresolved_call_count": 12
  }
}
```

## 5.4 `search`

### Request

```json
{
  "repo_id": "repo:abcd1234efgh5678",
  "query": "auth token validation",
  "limit": 10
}
```

### Response

```json
{
  "results": [
    {
      "node_id": "function:src/auth/tokens.py:validate_token:18",
      "type": "Function",
      "name": "validate_token",
      "file_path": "src/auth/tokens.py",
      "start_line": 18,
      "end_line": 43,
      "skill": "auth",
      "score": 0.97,
      "reason": "Exact symbol match; linked to auth skill"
    }
  ]
}
```

Constraints:

- `limit` default `10`
- hard cap `50`

## 5.5 `get_symbol_context`

### Request

```json
{
  "repo_id": "repo:abcd1234efgh5678",
  "symbol": "validate_token",
  "file_path": "src/auth/tokens.py"
}
```

### Success Response

```json
{
  "symbol": {
    "node_id": "function:src/auth/tokens.py:validate_token:18",
    "type": "Function",
    "name": "validate_token",
    "file_path": "src/auth/tokens.py",
    "start_line": 18,
    "end_line": 43,
    "signature": "validate_token(token: str) -> TokenPayload",
    "skill": "auth"
  },
  "callers": [
    {
      "node_id": "function:src/auth/service.py:login:55",
      "name": "login",
      "file_path": "src/auth/service.py",
      "confidence": 1.0
    }
  ],
  "callees": [
    {
      "node_id": "function:src/auth/jwt.py:decode_jwt:9",
      "name": "decode_jwt",
      "file_path": "src/auth/jwt.py",
      "confidence": 1.0
    }
  ],
  "related_files": [
    "src/auth/service.py",
    "src/auth/jwt.py"
  ]
}
```

### Ambiguous Response

```json
{
  "error": {
    "code": "AMBIGUOUS_SYMBOL",
    "message": "Multiple symbols matched 'save'",
    "details": {
      "candidates": [
        {
          "node_id": "method:src/users/models.py:User:save:20",
          "type": "Method",
          "file_path": "src/users/models.py"
        },
        {
          "node_id": "method:src/repos/repo.py:Repo:save:14",
          "type": "Method",
          "file_path": "src/repos/repo.py"
        }
      ]
    }
  }
}
```

## 5.6 `get_impact`

### Request

```json
{
  "repo_id": "repo:abcd1234efgh5678",
  "target": "BillingService.generate_invoice",
  "direction": "upstream",
  "depth": 2
}
```

### Response

```json
{
  "target": {
    "name": "generate_invoice",
    "node_id": "method:src/billing/service.py:BillingService:generate_invoice:33",
    "file_path": "src/billing/service.py"
  },
  "direction": "upstream",
  "severity": "HIGH",
  "summary": {
    "affected_symbol_count": 5,
    "affected_file_count": 3,
    "affected_skill_count": 2
  },
  "by_depth": {
    "1": [
      {
        "node_id": "function:src/api/billing.py:create_invoice_handler:12",
        "name": "create_invoice_handler",
        "file_path": "src/api/billing.py",
        "skill": "billing"
      }
    ],
    "2": [
      {
        "node_id": "function:src/jobs/retry.py:retry_invoice_generation:20",
        "name": "retry_invoice_generation",
        "file_path": "src/jobs/retry.py",
        "skill": "jobs"
      }
    ]
  },
  "affected_skills": [
    "billing",
    "jobs"
  ]
}
```

Constraints:

- `direction` in `["upstream", "downstream"]`
- `depth` default `2`, max `4`

## 5.7 Reserved Post-v1 `get_processes`

### Request

```json
{
  "repo_id": "repo:abcd1234efgh5678",
  "query": "invoice"
}
```

### Response

```json
{
  "processes": [
    {
      "process_id": "process:repo:abcd:create_invoice_handler:save_invoice:9af3",
      "label": "Create Invoice Flow",
      "step_count": 4,
      "entry_point": "create_invoice_handler",
      "terminal": "save_invoice",
      "skills": ["billing"],
      "steps": [
        {
          "step": 1,
          "name": "create_invoice_handler",
          "file_path": "src/api/billing.py"
        },
        {
          "step": 2,
          "name": "BillingService.generate_invoice",
          "file_path": "src/billing/service.py"
        }
      ]
    }
  ]
}
```

This API is reserved for post-v1.0 work. Keep the contract as a sketch only, and do not make it a blocker for the initial v1 release.

## 5.8 `list_skills`

### Request

```json
{
  "repo_id": "repo:abcd1234efgh5678"
}
```

### Response

```json
{
  "skills": [
    {
      "name": "billing",
      "label": "Billing",
      "summary": "Invoice generation and payment state updates.",
      "file_count": 6,
      "symbol_count": 14
    },
    {
      "name": "notifications",
      "label": "Notifications",
      "summary": "Delivery of email and in-app notification events.",
      "file_count": 4,
      "symbol_count": 8
    }
  ]
}
```

## 5.9 `get_skill`

### Request

```json
{
  "repo_id": "repo:abcd1234efgh5678",
  "skill_name": "billing"
}
```

### Response

```json
{
  "name": "billing",
  "label": "Billing",
  "summary": "Invoice generation and payment state updates.",
  "key_files": [
    "src/billing/service.py",
    "src/billing/invoice.py",
    "src/api/billing.py"
  ],
  "key_symbols": [
    "BillingService",
    "generate_invoice",
    "create_invoice_handler"
  ],
  "entry_points": [
    "create_invoice_handler"
  ],
  "flows": [
    "create_invoice_handler -> BillingService.generate_invoice -> InvoiceRepository.save"
  ],
  "related_skills": [
    "notifications"
  ],
  "generated_at": "2026-03-14T10:00:00Z",
  "stats": {
    "file_count": 6,
    "symbol_count": 14,
    "entry_point_count": 1,
    "flow_count": 1
  }
}
```

## 6. Fixture Repository Definitions

Use only synthetic fixture repos at first.

## 6.1 Fixture A: `ts_basic_app`

Purpose:

- validate TypeScript extraction, imports, calls, and basic skill generation

Suggested tree:

```text
ts_basic_app/
  src/
    auth/
      service.ts
      jwt.ts
      api.ts
    shared/
      logger.ts
```

Required behaviors:

- `api.ts` imports `service.ts`
- `service.ts` imports `jwt.ts`
- `service.ts` calls `decodeJwt`
- one obvious `auth` skill

## 6.2 Fixture B: `py_basic_app`

Purpose:

- validate Python extraction, imports, methods, and context

Suggested tree:

```text
py_basic_app/
  src/
    billing/
      service.py
      repository.py
      api.py
```

Required behaviors:

- `api.py` calls `BillingService.generate_invoice`
- `BillingService.generate_invoice` calls `InvoiceRepository.save`
- one obvious `billing` skill

## 6.3 Fixture C: `ambiguity_app`

Purpose:

- validate symbol ambiguity responses

Suggested tree:

```text
ambiguity_app/
  src/
    users/
      models.py
    repos/
      repo.py
    app.py
```

Required behaviors:

- two different `save` methods
- `app.py` imports one explicitly
- unresolved lookup by `save` alone must return ambiguity

## 6.4 Fixture D: `multi_skill_app`

Purpose:

- validate skills generation and related skills

Suggested tree:

```text
multi_skill_app/
  src/
    auth/
      api.py
      service.py
    billing/
      api.py
      service.py
    notifications/
      service.py
      email.py
```

Required behaviors:

- auth and billing each have clear entry points
- billing calls notifications for invoice events
- `billing` should relate to `notifications`

## 6.5 Fixture E: `impact_app`

Purpose:

- validate depth-grouped impact analysis

Suggested tree:

```text
impact_app/
  src/
    handlers/
      invoice.py
    services/
      billing.py
    jobs/
      retries.py
    storage/
      repository.py
```

Required behaviors:

- handler calls service
- retry job calls service
- service calls repository
- upstream impact from service should surface handler and retry job

## 7. First 10 Implementation Tickets

## Ticket 1: Bootstrap project skeleton

Goal:

- create package layout, dependency management, and test runner

Acceptance criteria:

- project installs locally
- tests can run
- empty package imports successfully

## Ticket 2: Implement repository scanner

Goal:

- recursively discover supported source files with ignore rules

Acceptance criteria:

- ignores `.git`, dependency folders, caches, and build outputs
- detects TypeScript/JavaScript and Python files
- returns normalized relative paths

## Ticket 3: Add Tree-sitter parser loader

Goal:

- parse TypeScript/JavaScript and Python files behind one abstraction

Acceptance criteria:

- parser returns AST for valid fixture files
- parse failures are surfaced as structured diagnostics

## Ticket 4: Extract symbols for TypeScript

Goal:

- extract files, functions, classes, methods, and imports from TypeScript fixtures

Acceptance criteria:

- nodes extracted from `ts_basic_app`
- deterministic IDs generated
- import records captured

## Ticket 5: Extract symbols for Python

Goal:

- extract files, functions, classes, methods, and imports from Python fixtures

Acceptance criteria:

- nodes extracted from `py_basic_app`
- deterministic IDs generated
- import records captured

## Ticket 6: Implement Kuzu schema bootstrap

Goal:

- create all core v1 node tables and the core relationship table

Acceptance criteria:

- a fresh Kuzu database initializes cleanly
- schema creation is idempotent

## Ticket 7: Implement graph persistence

Goal:

- insert repository, file, symbol, and structural relationships into Kuzu

Acceptance criteria:

- indexed fixture repos are queryable
- metadata file written with counts

## Ticket 8: Implement import and basic call resolution

Goal:

- resolve same-file and import-scoped calls

Acceptance criteria:

- `CALLS` edges appear for `ts_basic_app` and `py_basic_app`
- unresolved calls are counted, not dropped silently

## Ticket 9: Implement `search` and `get_symbol_context`

Goal:

- expose first chatbot-useful APIs

Acceptance criteria:

- exact symbol search works
- ambiguity response works
- direct callers/callees returned correctly

## Ticket 10: Implement skills generation and skills APIs

Goal:

- produce deterministic module-context objects and expose them

Acceptance criteria:

- `list_skills` works on `multi_skill_app`
- `get_skill("billing")` returns key files, symbols, entry points, and related skills

## 8. Recommended Response Size Bounds

To keep outputs LLM-friendly:

- `search`: max 10 results by default
- `get_symbol_context`: max 10 callers, 10 callees
- `get_impact`: max 25 affected symbols unless explicitly expanded
- `get_skill`: max 10 key files, 12 key symbols, 5 flows, 5 related skills

## 9. Versioning

Index version should be explicit in metadata:

- `index_version = "v1"`

Any schema change that invalidates existing Kuzu data should bump:

- `index_version`

## 10. Implementation Notes

- Keep summary and skill text deterministic and template-based in v1.
- Do not block early milestones on process tracing.
- Do not add languages beyond TypeScript/JavaScript and Python until search/context quality is acceptable.
- Keep the HTTP layer optional and thin.
- Build the minimal demo chatbot as a terminal client that consumes the same core APIs defined here.

This pack is sufficient to begin implementation without further product ambiguity.
