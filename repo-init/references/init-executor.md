# Init Executor

Use this reference to decide how repository initialization should behave after intake has been normalized.

## Objective

Turn initialization input into a usable collaboration state without rewriting user-owned materials by default.

## Initialization modes

### `greenfield`

Use when:

- the input is prompt-only
- there is no authoritative project plan yet
- the repository is empty or near-empty

Do:

- generate `PROJECT.md`
- create `REUSE.md`
- create `STATUS.md`
- create the first task file
- add a foundational decision only when it is explicit or unavoidable

### `plan-ingest`

Use when:

- the user provides one or more authoritative project plan files
- the plan should remain the source of truth

Do:

- preserve the original project source bundle
- extract a concise agent-readable snapshot
- create or supplement `PROJECT.md` as a compatibility layer
- create or update `REUSE.md`
- create `STATUS.md`
- create the first task file

### `repo-hydrate`

Use when:

- the repository already contains meaningful code or project documentation
- the user wants to add the collaboration layer without reinitializing the project

Do:

- inspect the existing repository
- create only missing collaboration files
- create or update `REUSE.md`
- supplement live status and task tracking
- avoid replacing established project documents

## Mode-selection order

1. If the intake source is an authoritative file, select `plan-ingest`.
2. Else if the repository already has meaningful code or project documentation, select `repo-hydrate`.
3. Else select `greenfield`.

Prefer preservation over generation when signals conflict.

## Write-policy vocabulary

- `create`: the target does not exist and should be created
- `supplement`: the target exists and should be updated compatibly
- `preserve`: the target exists and should remain unchanged unless the user asks for a rewrite
- `rewrite`: the target may be replaced because the user explicitly requested restructuring

## Standard output flow

1. Discover sources.
2. Run intake extraction, normalization, and bundle merging.
3. Classify the initialization mode.
4. Compute per-file write policy.
5. Assess repository complexity from intake plus repository summary.
6. Choose between a single first task or a decomposed task set.
7. Produce or update `PROJECT.md`.
8. Produce or update `STATUS.md`.
9. Produce or update `DECISIONS.md` if a real initialization decision exists.
10. Produce or update `REUSE.md`.
11. Create the first actionable task or task set.
12. Emit an initialization report.
13. Stop after initialization and wait for explicit user direction before any implementation work.

The existence of a `Next Step` in `STATUS.md` or a concrete first task does not authorize the initializer to execute that work in the same turn.

## Failure handling

When the input is incomplete or extraction confidence is low:

- preserve the source material
- create the smallest safe collaboration layer
- record assumptions explicitly
- create a clarification task instead of fabricating project facts
- stop after writing the safe initialization state

When the project is complex enough for decomposition:

- automatically create one coordinating master task
- automatically create `3-7` child tasks for the first wave of work
- keep `STATUS.md` pointed at the master task
- keep the recommended child task explicit without marking it started
- stop after initialization; do not execute any child task

When multiple sources disagree on key fields:

- keep the current chosen value explicit
- record the conflict rather than flattening it away
- surface clarification questions when the disagreement materially affects initialization

## Feedback-Driven Follow-Through

The generated collaboration layer must preserve room for execution feedback and downstream task adjustment:

- `STATUS.md` should reserve `Latest Feedback`, `Task Impact`, and `Recommended Replan`.
- Task files should reserve `Assumption Checks` and `Downstream Impact`.
- Task files should reserve `Open Source Reuse Check` so reusable technical capabilities are evaluated before implementation.
- For decomposed work, child-task feedback should flow into the coordinating master task's `Feedback Ledger`.
- `Replan Decisions` should contain only explicitly accepted downstream adjustments.
- Agent suggestions may recommend `keep`, `reorder`, `block`, `split`, `revise-acceptance`, or `clarify`, but should not directly rewrite untouched task status or acceptance criteria until the change is explicitly accepted.
- `DECISIONS.md` should store only durable accepted outcomes, not temporary feedback or unaccepted suggestions.
