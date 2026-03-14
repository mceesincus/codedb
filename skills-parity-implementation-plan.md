# Skills Parity Implementation Plan
## Local Code Graph Intelligence Core for Chatbot Integration

Status: Proposed engine-parity implementation plan

Related docs:

- [prd-code-graph-chatbot.md](/mnt/c/work/india/codedb/prd-code-graph-chatbot.md)
- [tech-spec-code-graph-chatbot.md](/mnt/c/work/india/codedb/tech-spec-code-graph-chatbot.md)
- [schema-and-contract-pack-code-graph-chatbot.md](/mnt/c/work/india/codedb/schema-and-contract-pack-code-graph-chatbot.md)
- [execution-plan-code-graph-chatbot.md](/mnt/c/work/india/codedb/execution-plan-code-graph-chatbot.md)

## 1. Purpose

This document defines a concrete implementation plan for improving `skills` so the engine is closer to GitNexus-style module-context quality while remaining local-first and Python-API-first.

This plan is intentionally scoped to engine-level parity only:

- improve skill generation quality
- improve skill graph materialization
- improve `list_skills(...)` and `get_skill(...)` output quality
- do not implement MCP/resources/UI as part of this plan

## 2. Current State

This repository already supports:

- deterministic skill generation at index time
- `ModuleSkill` nodes
- `BELONGS_TO_SKILL` edges
- `RELATED_SKILL` edges
- `list_skills(repo_id)`
- `get_skill(repo_id, skill_name)`

Current limitations:

- directory-first grouping dominates clustering
- summaries are generic templates
- related-skill ranking is simple connectivity
- flows are shallow and call-only
- skill labels are adequate but not especially expressive

## 3. Parity Target

The target is engine-level parity for skill usefulness, not UI parity.

The improved engine should produce skills that are:

- more semantically coherent
- less tied to raw folder boundaries
- better labeled
- better ranked
- more useful as prompt-injection context

The parity boundary ends at:

- graph materialization
- Python API output

## 4. Skill Quality Goals

The system should improve in these areas:

1. clustering quality
2. label quality
3. summary quality
4. entry-point quality
5. representative flow quality
6. related-skill quality
7. stability across reindex

## 5. Non-Goals

This plan does not include:

- MCP skill resources
- UI for browsing skills
- LLM-generated summaries by default
- free-form autonomous skill authoring

## 6. Proposed Design

Use a hybrid skill-generation approach:

1. directory/module seed clusters
2. graph-connectivity refinement
3. call/import cohesion scoring
4. entry-point and public-surface weighting

This preserves deterministic behavior while improving quality over pure directory grouping.

## 7. Clustering Plan

## Phase 1: Seed Clusters

Start with the current directory-first grouping as an initial partition.

For each candidate skill:

- gather files
- gather symbols
- gather public/API entry points
- gather cross-cluster imports and calls

## Phase 2: Connectivity Refinement

Split or merge seed clusters using:

- internal call density
- internal import density
- cross-cluster call ratio
- shared entry-point surface

Rules:

- merge tiny clusters that are strongly coupled
- split large clusters with weak internal connectivity
- avoid creating clusters below a minimum useful size

Recommended baseline thresholds:

- minimum `3` symbols
- minimum `2` files unless single-file module is clearly meaningful

## Phase 3: Stability Controls

To keep skill names stable across reindex:

- prefer dominant directory/module name when still valid
- only rename if connectivity strongly favors a new cluster identity
- keep deterministic tie-breaking

## 8. Labeling Plan

Skill label priority:

1. dominant module or directory
2. dominant exported class/function family
3. stable fallback synthetic label

Skill names should remain:

- lowercase
- kebab-case
- deterministic

The label should be human-readable and concise.

## 9. Summary Generation Plan

Continue using deterministic summaries by default.

Improve summary inputs:

- dominant file paths
- dominant symbol families
- dominant responsibilities inferred from calls/imports
- likely entry points

Example style:

- `Billing workflows for invoice generation, persistence, and payment status updates.`
- `Notification delivery logic for email sending and event fanout.`

Do not use free-form LLM generation in the baseline implementation.

## 10. Entry-Point Detection for Skills

The current entry-point logic is too narrow.

Improve it by considering:

- API/handler/job file placement
- exported/top-level functions
- low inbound, high outbound symbols
- symbols that sit on cluster boundaries

Entry points should drive:

- skill summaries
- representative flows
- ranking inside `get_skill(...)`

## 11. Representative Flows

Current flows are shallow and call-only.

Improve them by:

- preferring entry-point-originated flows
- staying mostly within a skill
- allowing controlled cross-skill terminal handoff
- suppressing utility-only paths

Recommended bounds:

- max `5` flows per skill
- max `5` steps per flow

If process tracing lands later, skill flows should reuse process-aware paths where available.

## 12. Related-Skill Ranking

Current related skills are mostly any cross-skill connectivity.

Improve ranking using:

- cross-skill call count
- cross-skill import count
- shared flows
- boundary entry-point interactions

Return the strongest neighbors first.

Recommended output bound:

- max `5` related skills

## 13. API Contract Stability

Preserve the existing Python APIs:

- `list_skills(repo_id, ...)`
- `get_skill(repo_id, skill_name, ...)`

Do not break the current response shape.

Allowed improvements:

- better ordering
- better summary text
- better flow quality
- more stable related-skill ranking

Optional later additions:

- `refresh_skills(repo_id)`
- `get_skill_graph(repo_id, skill_name)`

Those are not required for parity.

## 14. Index-Time Workflow

During indexing:

1. build base graph
2. compute seed skill clusters
3. refine clusters with connectivity analysis
4. label and summarize skills
5. compute entry points and representative flows
6. compute related-skill scores
7. materialize `ModuleSkill` nodes and edges

This should remain deterministic.

## 15. Data and Graph Changes

The current schema is mostly sufficient.

Possible additions if needed:

- optional cluster score metadata on `ModuleSkill`
- optional relatedness score metadata on `RELATED_SKILL`

Only add new fields if query behavior clearly benefits.

Avoid schema churn unless necessary.

## 16. Suggested Code Changes

Likely files to update:

- [builder.py](/mnt/c/work/india/codedb/code_graph_core/graph/builder.py)
- [querying.py](/mnt/c/work/india/codedb/code_graph_core/api/querying.py)

Likely new modules:

- [skill_clustering.py](/mnt/c/work/india/codedb/code_graph_core/ingestion/skill_clustering.py)
- [skill_labeling.py](/mnt/c/work/india/codedb/code_graph_core/ingestion/skill_labeling.py)
- [skill_flows.py](/mnt/c/work/india/codedb/code_graph_core/ingestion/skill_flows.py)

## 17. Fixture Plan

Add fixtures designed to break naive directory grouping:

1. `cross_cutting_skill_app`
   - one concern spread across multiple folders
2. `overmerged_skill_app`
   - one folder containing two weakly related subdomains
3. `related_skills_app`
   - clear neighboring modules with asymmetric coupling
4. `entrypoint_skill_app`
   - multiple candidate entry points, only some should dominate

These should test quality rather than just existence.

## 18. Test Plan

Add tests for:

1. cluster merge behavior
2. cluster split behavior
3. label stability
4. summary determinism
5. entry-point selection
6. representative flow quality
7. related-skill ordering
8. API contract stability

## 19. Hardening Plan

After fixture tests, run on a real repo and evaluate:

- overly broad skills
- missing cross-cutting skills
- weak labels
- low-value related skills
- repetitive flows

Tune heuristics using measured examples, not only synthetic fixtures.

## 20. Rollout Order

1. fixture design
2. clustering refinement
3. label improvements
4. summary improvements
5. entry-point improvements
6. representative flow improvements
7. related-skill ranking improvements
8. API validation
9. real-repo hardening
10. doc updates

## 21. Recommended Initial Scope

For the first quality pass, do only this:

- hybrid directory + connectivity clustering
- improved deterministic labeling
- better entry-point selection
- better related-skill ordering

That should produce the biggest quality jump without adding excessive complexity.

## 22. Key Constraint

Do not let skills become opaque heuristic blobs.

The correct target is:

- deterministic
- inspectable
- compact
- stable across reindex
- useful for prompt context

That is the safest way to approach engine-level skill parity in this repository.
