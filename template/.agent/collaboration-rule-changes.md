# Collaboration Rule Changes

## Authority

- Treat collaboration rules as project infrastructure, not normal task content.
- If the user directly requests a rule change, update the relevant `.agent/*.md` file.
- Adjust `AGENT.md` only when the thin index, reading order, or core invariants change.
- Record accepted collaboration-rule changes in `DECISIONS.md`.

## Proposals

- If an agent observes rule friction without a direct user request, record the proposed rule change in the active goal or `STATUS.md`.
- Wait for explicit human acceptance before changing the collaboration contract.
- Do not bury rule-change proposals inside ordinary task logs only.

## Boundary

- Task replans are highly autonomous when they preserve the active goal.
- Collaboration-contract changes are not autonomous; they require explicit user instruction or accepted confirmation.
