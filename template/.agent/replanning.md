# Replanning Rules

## Autonomy

- Tasks are provisional plans toward the active goal.
- Agents may create, split, reorder, rewrite, or supersede planned and in-progress tasks when observations show a better route to the goal.
- Agents may revise task acceptance criteria when the revision preserves the active goal and reflects execution evidence.
- Completed task logs and historical observations are append-only; do not rewrite history to make the new plan look clean.
- Milestone goals should stay few and human-readable; create a new milestone only when it clarifies a major project phase.

## Human Confirmation Required

- Changing the goal statement requires explicit human confirmation.
- Changing hard constraints requires explicit human confirmation.
- Changing durable project scope requires explicit human confirmation.
- Changing accepted success criteria requires explicit human confirmation.
- Deleting or weakening `acceptance.json` checks requires explicit human confirmation.
- Changing the collaboration contract requires explicit human confirmation or a direct user request.

## Replan Records

- Record high-signal observations in the active goal `Observation Ledger`.
- Record applied task replans in the active goal `Replan History`.
- Update `STATUS.md` when active task, task impact, blockers, or next step changes.
- Keep `DECISIONS.md` for durable accepted project decisions, not ordinary task replans.
