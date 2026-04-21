# INIT_PROMPT.md

This file defines the input contract for repository initialization.

Initialization input may be:

- a single natural-language prompt
- a prompt plus one or more project source files
- an existing repository with partial project documentation

## Recommended Prompt Shape

The prompt should express the following information in natural language:

- what the project is
- who it serves
- what outcome it must achieve
- what stack or platform is preferred
- what constraints or boundaries already exist
- what stage the project is in now

If the user already has a project plan, they may provide the plan file instead of restating everything in the prompt.

## Minimal Prompt Example

```text
Initialize this repository as a SaaS web application called FlowLedger for small finance teams.
Its goal is to track recurring cash operations and produce a simple weekly dashboard.
Use Next.js, TypeScript, PostgreSQL, and Tailwind.
The current stage is prototype.
Do not build a mobile app yet.
Keep the architecture simple for one developer and agent collaboration.
```

## Agent Output Contract

After reading the initialization prompt, the agent should produce at least:

1. a generated or preserved-compatible `PROJECT.md`
2. a populated `STATUS.md`
3. an initial accepted or proposed entry in `DECISIONS.md` if a foundational choice is clear
4. one first task in `tasks/`, typically for project setup or scope clarification

The exact behavior depends on the initialization mode defined in `INIT_EXECUTOR_SPEC.md`.

## Validation Rules

A repository initialization is valid when:

- every required template file exists
- `PROJECT.md` contains project-specific content rather than placeholders only
- `STATUS.md` names an active or next task
- `tasks/` contains at least one real task file
- there is no major contradiction between `PROJECT.md`, `STATUS.md`, and `DECISIONS.md`
- any user-provided project source remains preserved unless rewrite was explicitly requested

## Non-Goals

This prompt does not need to specify every implementation detail.

The initialization step is meant to create a coherent starting state, not a full specification of the finished product.
