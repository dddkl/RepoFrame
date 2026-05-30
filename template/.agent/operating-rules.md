# Operating Rules

## Execution Discipline

- Preserve user-authored source plans by default.
- Keep all updates consistent with the current source confidence.
- Treat low-confidence intake as a clarification problem, not an implementation license.
- Do not begin implementation after initialization unless the user explicitly asks for post-init execution.
- Respect existing repository layout during repo-hydrate work.

## Task Execution

- Before starting a task, confirm it still advances the active goal in `goals/` and the current project definition in `PROJECT.md`.
- Mark a task `in progress` only when execution actually starts.
- Append to the task `Execution Log` only after a meaningful execution batch, milestone, blocker change, status change, or user-directed change of course.
- Do not log every file save, every small refactor, formatting-only edits, or changes already obvious from git history.
- When a task observation affects future work, update the task `Downstream Impact`, the active goal `Observation Ledger`, and `STATUS.md`.
- Before marking a milestone done, run `python repo-init/scripts/lint_acceptance.py --repo .` or the equivalent repository-local command.

## Decisions

- Add to `DECISIONS.md` only when a durable decision is accepted.
- Keep temporary feedback, exploratory notes, and unaccepted replan suggestions in `STATUS.md`, the active goal, or the current task.
