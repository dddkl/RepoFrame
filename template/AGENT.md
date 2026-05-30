# AGENT.md

This file is the thin operating index for agents working in this repository.

## Objective

Maintain a stable collaboration loop between human operators and agents by using repository files as persistent working context.

## Source Of Truth

Each file has a single responsibility:

- `README.md`: human-facing entry point
- `AGENT.md`: agent entry point and rule index
- `.agent/*.md`: detailed collaboration rules
- `PROJECT.md`: project facts, goals, scope, and constraints
- `goals/*.md`: milestone goals, observations, planned tasks, and replan history
- `acceptance.json`: machine-checkable milestone acceptance criteria
- `STATUS.md`: current focus, latest feedback, task impact, recommended replan, next step, blockers, and risks
- `DECISIONS.md`: durable accepted decisions and rationale
- `tasks/*.md`: provisional task plans and task-local execution records

Agents must not duplicate the same content across multiple files unless a short cross-reference is necessary.

## Required Reading Order

Before starting substantial work, read in this order:

1. `PROJECT.md`
2. `STATUS.md`
3. `DECISIONS.md`
4. the active milestone goal in `goals/`
5. `acceptance.json`
6. the active task in `tasks/` when one is active

Read `README.md` only when onboarding or validating entry-point documentation.

## Read Detailed Rules When Needed

- Read `.agent/operating-rules.md` before substantial implementation work.
- Read `.agent/replanning.md` before rewriting, splitting, superseding, or reordering tasks.
- Read `.agent/file-contract.md` before changing collaboration files or generated file structure.
- Read `.agent/collaboration-rule-changes.md` before changing the collaboration contract itself.

## Core Invariants

- Preserve user-authored source plans by default.
- Treat low-confidence intake as a clarification problem, not an implementation license.
- Initialization creates the collaboration layer, milestone goals, planned tasks, `acceptance.json`, and report; it does not authorize implementation in the same turn.
- Use tasks as provisional plans toward the active milestone goal; rewrite them when observations show a better route.
- Do not change the goal, hard constraints, durable project scope, accepted success criteria, or collaboration contract without explicit human confirmation.
- Do not delete or weaken `acceptance.json` checks without explicit human confirmation.
- Record durable accepted decisions in `DECISIONS.md`; keep temporary feedback and unaccepted rule-change proposals out of it.
