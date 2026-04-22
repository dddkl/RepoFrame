# AGENT.md

This file defines the operating protocol for agents working in this repository.

## Objective

Maintain a stable collaboration loop between human operators and agents by using the repository files as the persistent working context.

## Source Of Truth

Each file has a single responsibility:

- `README.md`: human-facing entry point
- `AGENT.md`: agent operating rules
- `PROJECT.md`: project facts, goals, scope, and constraints
- `STATUS.md`: current state, next step, blockers, and risks
- `DECISIONS.md`: durable decisions and rationale
- `tasks/*.md`: individual task definitions and execution records

Agents must not duplicate the same content across multiple files unless a short cross-reference is necessary.

## Required Reading Order

Before starting substantial work, read in this order:

1. `PROJECT.md`
2. `STATUS.md`
3. `DECISIONS.md`
4. the relevant file in `tasks/`

Read `README.md` only when onboarding or when validating entry-point documentation.

## Initialization Rules

When this repository is initialized from a single prompt, the agent must:

1. extract structured project metadata
2. decide whether `PROJECT.md` should be generated, supplemented, or preserved
3. create or update `STATUS.md` with the starting state
4. create the first task file in `tasks/`
5. add any important foundational choice to `DECISIONS.md`

If the user prompt is incomplete, the agent should make reasonable assumptions and mark them explicitly in `PROJECT.md` or the task file.

If the repository is initialized from an existing project plan, preserve that source by default and use `PROJECT.md` as the agent-readable compatibility layer.

## Execution Rules

When implementing work:

1. find or create the relevant task file in `tasks/`
2. confirm the task aligns with `PROJECT.md`
3. check `DECISIONS.md` for constraints or prior choices
4. update the current task file when the task status, execution direction, or blocker state materially changes
5. append to the task `Execution Log` only after a meaningful execution batch or milestone
6. update `STATUS.md` before or after major milestones
7. record any important new decision in `DECISIONS.md`

## Update Rules

Update `PROJECT.md` when:

- project goals change
- scope changes
- constraints change
- success criteria change

If `PROJECT.md` contains user-authored source material, preserve the source content unless the user explicitly asks for a rewrite or reformat.

Update `STATUS.md` when:

- the active task changes
- progress reaches a milestone
- a blocker appears or is removed
- the next recommended step changes

Update `DECISIONS.md` when:

- a non-trivial technical choice is made
- an option is rejected for a concrete reason
- a previous decision is reversed

Update a task file when:

- the task is created
- acceptance criteria change
- implementation notes materially affect execution
- the task status changes
- a blocker appears or is removed
- a meaningful batch of related repository changes completes

Update the task `Execution Log` when:

- a milestone is reached
- a task status changes
- a blocker appears or is removed
- a meaningful batch of related repository changes completes
- a user decision materially changes the execution path

Do not update the task `Execution Log` for:

- every file save
- every small refactor or formatting-only edit
- every micro-step inside the same execution batch
- changes that are already obvious from git history and do not affect execution understanding

## Writing Rules

- Prefer concise, explicit statements.
- Separate facts from assumptions.
- Mark unresolved items clearly.
- Keep status short and current.
- Keep decisions append-only when possible.
- Use links instead of repeating long explanations.
- Keep task logs milestone-oriented and batch-oriented rather than change-by-change.

## Anti-Patterns

Do not:

- use `README.md` as a running status log
- store project goals in `STATUS.md`
- store daily task progress in `PROJECT.md`
- put detailed execution history in `DECISIONS.md`
- create ad hoc notes outside `tasks/` for active implementation work without a clear reason
- turn the task `Execution Log` into a file-by-file or save-by-save change ledger
