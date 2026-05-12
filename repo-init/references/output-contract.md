# Output Contract

Use this reference to decide what a successful initialization must produce.

## Required repository outputs

Create or update these targets:

- `README.md`
- `AGENT.md`
- `PROJECT.md`
- `STATUS.md`
- `DECISIONS.md`
- `REUSE.md`
- `tasks/` with at least one real task file
- `.repo-init/` with normalized intake and initialization report artifacts unless cleanup is explicitly requested

Initialization is complete when these outputs and the initialization report have been produced.

The initializer should then stop unless the user explicitly asks for implementation beyond initialization.

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
- open-source reuse rules
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
- latest feedback with `1-3` high-signal conclusions from the latest execution batch or `none`
- task impact with affected tasks labeled as `keep | reorder | block | split | revise-acceptance | clarify`
- recommended replan containing suggestions only, not already-applied downstream changes
- next step as a single recommended next action
- blockers
- risks
- recently completed
- last updated

### `DECISIONS.md`

Append only when initialization reveals a real project decision.

Do not invent decisions just to populate the file.
Do not store temporary feedback notes or unaccepted replan suggestions here.

### `REUSE.md`

Keep it operational and decision-oriented.

Include:

- when open-source reuse checks are required
- where agents should search
- evaluation criteria for candidate projects
- allowed reuse decisions: `Direct Use`, `Adapt`, `Learn From`, or `Build In-House`
- the required task-file output format for reuse checks
- the rule that build-in-house decisions must explain why existing candidates were rejected

### `tasks/`

Always create actionable task output.

For simple projects:

- create one actionable first task

For complex projects:

- create one coordinating master task
- create `3-7` child tasks for the first wave of work
- keep the master task as the coordination surface for ordering and cross-task risk

For clarification-first projects:

- create one clarification task only
- do not generate speculative child tasks before the missing facts are resolved

Do not create a purely empty placeholder as the only task.

Creating the first task or task set does not authorize immediate execution in the same initialization run.

Task files must include:

- `Assumption Checks` with `Validated`, `Invalidated`, and `Still Open`
- `Downstream Impact` with `Affected Tasks` and `Suggested Follow-up`
- `Open Source Reuse Check` with requirement status, search keywords, candidate projects, decision, and reason

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

If an `Execution Log` entry changes downstream work, mirror that change in `Downstream Impact`; do not leave cross-task impact only in the log.

Complex-project task sets should also satisfy:

- the coordinating master task includes `Child Tasks`, `Recommended Order`, `Replan Triggers`, `Feedback Ledger`, and `Replan Decisions`
- `Feedback Ledger` records date, source task, observation, impacted tasks, and suggested action
- `Replan Decisions` records only explicitly accepted reorder, block, split, clarify, or acceptance-revision outcomes
- child tasks act as task-local feedback inputs and do not directly own global reprioritization
- `STATUS.md` points to the master task as the active task
- `STATUS.md` points to the recommended first child task as the next step
- child tasks remain `todo` until explicit post-initialization execution begins

## Required initialization report fields

The completion report must include:

- selected mode
- source files used
- primary source
- source roles
- complexity assessment
- task decomposition applied
- task decomposition reason
- master task
- child tasks
- recommended start task
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
- the generated task output

## Artifact rule

By default, store intermediate pipeline artifacts under `.repo-init/` in the target repository.

Do not scatter artifacts across multiple ad hoc directories such as `tmp/`, `.tmp/`, `_repo_init_tmp/`, or `repo-init/`.
