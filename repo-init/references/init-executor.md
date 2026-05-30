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
- create `STATUS.md`
- create milestone goal file(s)
- create `acceptance.json`
- create the initial planned task file
- add a foundational decision only when it is explicit or unavoidable

### `plan-ingest`

Use when:

- the user provides one or more authoritative project plan files
- the plan should remain the source of truth

Do:

- preserve the original project source bundle
- extract a concise agent-readable snapshot
- create or supplement `PROJECT.md` as a compatibility layer
- create `STATUS.md`
- create milestone goal file(s)
- create `acceptance.json`
- create the initial planned task file

### `repo-hydrate`

Use when:

- the repository already contains meaningful code or project documentation
- the user wants to add the collaboration layer without reinitializing the project

Do:

- inspect the existing repository
- create only missing collaboration files
- supplement live goal, status, and task tracking
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
6. Create a milestone-goal adaptive plan with no fixed task-count cap.
7. Produce or update `PROJECT.md`.
8. Produce or update `STATUS.md`.
9. Produce or update `DECISIONS.md` if a real initialization decision exists.
10. Create milestone goals, `acceptance.json`, and planned tasks.
11. Emit an initialization report.
12. Stop after initialization and wait for explicit user direction before any implementation work.

The existence of a `Next Step` in `STATUS.md` or a planned task does not authorize the initializer to execute that work in the same turn.

## Failure handling

When the input is incomplete or extraction confidence is low:

- preserve the source material
- create the smallest safe collaboration layer
- record assumptions explicitly
- create a clarification task instead of fabricating project facts
- stop after writing the safe initialization state

When the project is complex enough for multiple planned tasks:

- automatically create a few milestone goal files, usually 2-4
- automatically create as many evidence-backed planned tasks as help human-agent collaboration
- do not impose a fixed minimum or maximum planned-task count
- keep `STATUS.md` pointed at the first active milestone goal and no active task
- keep the recommended starting task explicit without marking it started
- stop after initialization; do not execute any planned task

When multiple sources disagree on key fields:

- keep the current chosen value explicit
- record the conflict rather than flattening it away
- surface clarification questions when the disagreement materially affects initialization

## Feedback-Driven Follow-Through

The generated collaboration layer must preserve room for execution feedback and downstream task adjustment:

- `STATUS.md` should reserve `Latest Feedback`, `Task Impact`, and `Recommended Replan`.
- Goal files should reserve `Observation Ledger` and `Replan History`.
- `acceptance.json` should reserve machine-checkable milestone acceptance checks.
- Task files should reserve `Assumption Checks` and `Downstream Impact`.
- Task-local feedback should flow into the active goal's `Observation Ledger` when it affects future work.
- Task replans may recommend or apply `keep`, `reorder`, `block`, `split`, `supersede`, `revise-acceptance`, or `clarify` when they preserve the active goal.
- Goal, hard-constraint, durable-scope, accepted-success-criteria, and collaboration-contract changes require explicit human confirmation.
- Deleting or weakening `acceptance.json` checks requires explicit human confirmation.
- `DECISIONS.md` should store only durable accepted outcomes, not temporary feedback or unaccepted suggestions.
