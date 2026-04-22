# Output Contract

Use this reference to decide what a successful initialization must produce.

## Required repository outputs

Create or update these targets:

- `README.md`
- `AGENT.md`
- `PROJECT.md`
- `STATUS.md`
- `DECISIONS.md`
- `tasks/` with at least one real task file
- `.repo-init/` with normalized intake and initialization report artifacts unless cleanup is explicitly requested

## Required content by file

### `README.md`

Keep it human-facing.

Include:

- repository purpose
- initialization model
- collaboration contract summary
- where the detailed rules live

### `AGENT.md`

Keep it operational.

Include:

- source-of-truth responsibilities
- reading order
- initialization rules
- execution and update rules
- task-log update granularity rules
- anti-patterns

### `PROJECT.md`

Use one of two modes:

- structured project definition when the plan is generated
- compatibility layer when the source plan is user-authored

In compatibility mode, include:

- source mode
- source path or primary source
- source bundle summary when multiple files were used
- rewrite policy
- concise project snapshot
- conflicts and unresolved questions when they exist

### `STATUS.md`

Always create or update it.

Include:

- current focus
- current state
- next step
- blockers
- risks
- recently completed
- last updated

### `DECISIONS.md`

Append only when initialization reveals a real project decision.

Do not invent decisions just to populate the file.

### `tasks/`

Create at least one actionable task file.

The first task should usually be:

- repository setup
- scope clarification
- implementation kickoff

Do not create a purely empty placeholder as the only task.

Task files should also define an `Execution Log` policy that is milestone-oriented and batch-oriented.

The `Execution Log` should capture:

- task creation
- task status changes
- milestone completion
- blocker appearance or removal
- meaningful batches of related repository changes

The `Execution Log` should not capture:

- every file save
- every micro-step
- formatting-only noise
- change-by-change duplication of git history

## Required initialization report fields

The completion report must include:

- selected mode
- source files used
- primary source
- source roles
- files created
- files supplemented
- files preserved
- assumptions
- conflicts
- clarification questions
- warnings

## Consistency rule

Do not leave contradictions between:

- `PROJECT.md`
- `STATUS.md`
- `DECISIONS.md`
- the first task file

## Artifact rule

By default, store intermediate pipeline artifacts under `.repo-init/` in the target repository.

Do not scatter artifacts across multiple ad hoc directories such as `tmp/`, `.tmp/`, `_repo_init_tmp/`, or `repo-init/`.
