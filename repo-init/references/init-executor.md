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
- create the first task file
- add a foundational decision only when it is explicit or unavoidable

### `plan-ingest`

Use when:

- the user provides an authoritative project plan file
- the plan should remain the source of truth

Do:

- preserve the original project source
- extract a concise agent-readable snapshot
- create or supplement `PROJECT.md` as a compatibility layer
- create `STATUS.md`
- create the first task file

### `repo-hydrate`

Use when:

- the repository already contains meaningful code or project documentation
- the user wants to add the collaboration layer without reinitializing the project

Do:

- inspect the existing repository
- create only missing collaboration files
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
2. Run intake extraction and normalization.
3. Classify the initialization mode.
4. Compute per-file write policy.
5. Produce or update `PROJECT.md`.
6. Produce or update `STATUS.md`.
7. Produce or update `DECISIONS.md` if a real initialization decision exists.
8. Create the first actionable task file.
9. Emit an initialization report.

## Failure handling

When the input is incomplete or extraction confidence is low:

- preserve the source material
- create the smallest safe collaboration layer
- record assumptions explicitly
- create a clarification task instead of fabricating project facts
