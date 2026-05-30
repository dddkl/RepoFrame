# File Contract

## Responsibilities

- `PROJECT.md` stores durable project definition, scope, constraints, and compatibility assumptions.
- `goals/*.md` stores milestone goals, human acceptance, planned tasks, observations, and replan history.
- `tasks/*.md` stores provisional task plans, execution records, assumption checks, and downstream impact.
- `acceptance.json` stores machine-checkable milestone acceptance criteria.
- `STATUS.md` stores the current operational snapshot and next recommended step.
- `DECISIONS.md` stores durable accepted decisions only.
- `.agent/*.md` stores detailed collaboration rules.

## Update Rules

- Update `STATUS.md` when active goal, active task, latest feedback, task impact, recommended replan, blocker state, or next step changes.
- Update the active goal when observations change the route to the goal or tasks are created, split, reordered, rewritten, or superseded.
- Update a task when it is created, started, blocked, completed, superseded, or materially changed.
- Add or strengthen `acceptance.json` checks when new machine-checkable acceptance gaps are discovered.
- Do not remove or weaken `acceptance.json` checks without explicit human confirmation.
- Update `PROJECT.md` only when project goals, scope, constraints, or success criteria change with the required human confirmation.

## Storage Rules

- Use links instead of duplicating long explanations across files.
- Keep status short and current.
- Keep task logs milestone-oriented and batch-oriented.
- Do not create ad hoc notes outside `goals/`, `tasks/`, or `.agent/` for active implementation work without a clear reason.
