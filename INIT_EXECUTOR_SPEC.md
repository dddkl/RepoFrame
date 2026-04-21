# INIT_EXECUTOR_SPEC.md

This file defines the standard behavior of the repository initialization executor.

The executor is responsible for turning an initialization input into a usable collaboration state without unnecessarily rewriting user-owned materials.

## Objective

Produce a coherent project workspace from:

- a single prompt
- a prompt plus source files
- an existing repository with partial documentation

The executor must prioritize preservation, traceability, and low-surprise behavior.

## Core Principle

Initialization is not a document rewrite task by default.

The executor should first classify the input and only then decide what to generate, preserve, or supplement.

## Initialization Modes

### `greenfield`

Use this mode when:

- the user provides only a natural-language prompt
- there is no authoritative project plan yet
- the repository is empty or near-empty

Behavior:

- generate `PROJECT.md` as the primary project definition
- create `STATUS.md`
- create the first task in `tasks/`
- add a foundational decision to `DECISIONS.md` only if one is clear

### `plan-ingest`

Use this mode when:

- the user provides an existing project plan
- the source plan may be `.md`, `.txt`, `.docx`, `.pdf`, `.html`, or another supported format
- the plan should remain the authoritative source

Behavior:

- preserve the original project source by default
- extract a concise agent-readable snapshot
- create or update `PROJECT.md` as a compatibility layer
- create `STATUS.md`
- create the first task in `tasks/`
- add only clearly supported decisions to `DECISIONS.md`

### `repo-hydrate`

Use this mode when:

- the repository already contains code or partial documentation
- the user wants to add the collaboration template without reinitializing the project

Behavior:

- inspect existing repository materials
- create only missing collaboration files
- avoid changing established project documents unless needed for linkage or snapshotting
- set `STATUS.md` to the current next step rather than pretending the project is new

## Mode Selection Rules

Select the initialization mode in this order:

1. If the user provides an existing project plan or an authoritative source file, use `plan-ingest`.
2. Else if the repository already contains a meaningful codebase or partial project documentation, use `repo-hydrate`.
3. Else use `greenfield`.

If multiple signals exist, prefer preservation over generation.

## Write Policy

The executor must classify each target file before writing:

- `create`: the file does not exist and should be created
- `supplement`: the file exists but needs a compatible section or snapshot
- `preserve`: the file exists and must remain unchanged except for explicit user-approved rewrite
- `rewrite`: the file may be replaced because the user explicitly requested restructuring

Default policy by file:

- `README.md`: supplement
- `AGENT.md`: create or supplement
- `PROJECT.md`: create, supplement, or preserve depending on source mode
- `STATUS.md`: create or update
- `DECISIONS.md`: create or append
- `tasks/*.md`: create

## `PROJECT.md` Policy

`PROJECT.md` has special handling.

### Case 1: No prior project plan

Generate `PROJECT.md` from the initialization input.

### Case 2: User-authored plan already exists

Do not rewrite the plan by default.

Instead:

- preserve the original file
- set `Source Mode` to `user-authored` or `mixed`
- record the original source path
- add a concise snapshot of extracted facts
- use `PROJECT.md` as the agent-readable entry point

### Case 3: User explicitly requests reformatting

The executor may rewrite or reorganize `PROJECT.md`, but should still preserve the original source in a referenced file when practical.

## Standard Output Flow

The executor should follow this sequence:

1. Discover inputs.
2. Run intake and text extraction if needed.
3. Select initialization mode.
4. Decide per-file write policy.
5. Produce or update `PROJECT.md`.
6. Produce or update `STATUS.md`.
7. Produce or update `DECISIONS.md` if applicable.
8. Create the first actionable task in `tasks/`.
9. Emit an initialization report.

## Initialization Report

The executor should report:

- selected mode
- source files used
- files created
- files preserved
- assumptions made
- warnings or unresolved questions

This report may be returned in the agent response or written to a dedicated artifact if the workflow later requires it.

## Decision Recording Rule

The executor should not invent unnecessary decisions at initialization time.

Record a decision only when:

- the user explicitly specified it
- the repository already implies it
- the executor must choose between materially different approaches and the choice affects future work

## Failure Handling

If the input cannot be fully understood:

- preserve all user inputs
- generate the smallest safe collaboration state
- record assumptions explicitly
- create a clarification task instead of forcing a rewrite

## Future Skill Boundary

This specification is intended to be implementable as a skill later.

The future skill should treat this file as the behavioral contract for mode selection, write policy, and output sequencing.
