# Repository Guidelines

## Project Structure & Module Organization

This repository is currently document-first. The root contains the core planning artifacts for the code graph chatbot project:

- `prd-code-graph-chatbot.md` for product requirements
- `tech-spec-code-graph-chatbot.md` for implementation design
- `schema-and-contract-pack-code-graph-chatbot.md` for storage and API contracts
- `execution-plan-code-graph-chatbot.md` and `code_graph_chatbot_plan.md` for sequencing and delivery notes

Keep related documents close together in the repository root unless a future reorganization introduces `docs/` or source directories. Prefer one artifact per file.

## Build, Test, and Development Commands

There is no build or runtime entrypoint checked in yet. Current work is limited to authoring and reviewing Markdown documents.

- `rg --files` lists the working set quickly
- `rg '^#' *.md` reviews document structure and heading depth
- `sed -n '1,80p' <file>` previews a file without opening an editor
- `npx markdownlint-cli "**/*.md"` optionally lint-checks Markdown if Node tooling is available

Use these commands before submitting changes to confirm scope and formatting.

## Coding Style & Naming Conventions

Write Markdown with short sections, descriptive ATX headings, and fenced code blocks for commands, schemas, or examples. Keep prose direct and implementation-oriented.

Use existing file naming patterns:

- kebab-case for major artifacts, for example `tech-spec-code-graph-chatbot.md`
- underscores only when continuing an established name, such as `code_graph_chatbot_plan.md`

When adding new specs, use topic-first names that stay easy to scan in `rg --files`.

## Testing Guidelines

Validation here is editorial rather than executable. Check for:

- consistent terminology across PRD, tech spec, schema pack, and execution plan
- valid internal file references
- matching API, schema, and milestone names across documents
- clean Markdown formatting with no broken code fences or heading jumps

## Commit & Pull Request Guidelines

This checkout does not include `.git`, so no local commit history is available to mirror. Use concise imperative commit subjects such as `Add API contract notes` or `Refine KuzuDB schema section`.

For pull requests, include:

- a short summary of the document changes
- affected files and why they changed
- any open questions, assumptions, or follow-up work
