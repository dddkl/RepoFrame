# Output Contract

Use this reference to decide what a successful initialization must produce.

## Required repository outputs

Create or update these targets:

- `README.md`
- `AGENT.md`
- `PROJECT.md`
- `STATUS.md`
- `DECISIONS.md`
- `goals/` with milestone goal files
- `acceptance.json` with machine-checkable milestone acceptance criteria
- `tasks/` with at least one real task file
- `.agent/` with detailed generated collaboration rules
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

Keep it as a thin operational index.

Include:

- source-of-truth responsibilities
- reading order
- conditional links to detailed rules in `.agent/`
- core invariants only

### `.agent/`

Always create generated detailed rule files under `.agent/`.

Include:

- `operating-rules.md`
- `replanning.md`
- `file-contract.md`
- `collaboration-rule-changes.md`

Preserve unrelated user-authored files under `docs/`. Preserve user-authored `.agent` files unless they are empty, templates, or already managed by RepoFrame.

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
- active goal and optional active task
- task impact with affected tasks labeled as `keep | reorder | block | split | supersede | revise-acceptance | clarify`
- recommended replan with the next route toward the active goal
- next step as a single recommended next action
- blockers
- risks
- recently completed
- last updated

### `DECISIONS.md`

Append only when initialization reveals a real project decision.

Do not invent decisions just to populate the file.
Do not store temporary feedback notes or unaccepted replan suggestions here.

### `goals/`

Always create at least one milestone goal file.

Simple or clarification-first projects should start with one active milestone goal. Complex projects should create a few milestone goals, usually 2-4, without introducing a nested goal hierarchy.

Goal files must include:

- final outcome
- human acceptance
- machine acceptance reference to `acceptance.json`
- constraints
- current strategy
- planned tasks
- recommended start
- observation ledger
- replan history

The active milestone goal is the stable target during execution. Tasks are allowed to change as observations reveal a better route. `STATUS.md` should point to exactly one active milestone by default.

### `acceptance.json`

Always create `acceptance.json` unless an existing user-authored acceptance file must be preserved.

The acceptance file must include:

- `version`
- `managed_by`
- `active_goal`
- `active_goal_file`
- `goals`
- machine-checkable `checks`

Supported initial check types should stay small and stable:

- `files_exist`
- `files_absent`
- `required_text`
- `forbidden_text`
- `markdown_headings`
- `json_path_equals`
- `command`

Command checks must not execute unless the linter is invoked with explicit command-check permission.

Agents may add or strengthen checks when new machine-checkable acceptance gaps are discovered. Agents must not delete or weaken checks without explicit human confirmation.

### `tasks/`

Always create actionable planned task output.

For simple projects:

- create one planned starting task

For complex projects:

- create as many evidence-backed planned tasks as help human-agent collaboration
- do not enforce a fixed minimum or maximum task count
- do not create filler tasks just to increase count

For clarification-first projects:

- create one clarification task only
- do not generate speculative implementation tasks before the missing facts are resolved

Do not create a purely empty placeholder as the only task.

Creating planned tasks does not authorize immediate execution in the same initialization run.

Task files must include:

- `Goal` metadata pointing at the active goal file
- `Assumption Checks` with `Validated`, `Invalidated`, and `Still Open`
- `Downstream Impact` with `Affected Tasks` and `Suggested Follow-up`

Task files should also define an `Execution Log` policy that is milestone-oriented and batch-oriented.

The `Execution Log` should capture:

- task planning
- task status changes
- milestone completion
- blocker appearance or removal
- applied task replans
- meaningful batches of related repository changes

The `Execution Log` should not capture:

- every file save
- every micro-step
- formatting-only noise
- change-by-change duplication of git history

If an `Execution Log` entry changes downstream work, mirror that change in `Downstream Impact`; do not leave cross-task impact only in the log.

Task replanning should satisfy:

- planned and in-progress tasks may be rewritten, split, reordered, or superseded when observations show a better route to the active goal
- completed task logs and historical observations remain append-only
- the active goal `Observation Ledger` records date, source task, observation, impacted tasks, and suggested action
- the active goal `Replan History` records applied task replans and accepted higher-level replans
- `STATUS.md` points to the active goal and uses `none` for active task after initialization
- planned tasks remain `planned` until explicit post-initialization execution begins

## Required initialization report fields

The completion report must include:

- selected mode
- source files used
- primary source
- source roles
- complexity assessment
- adaptive task planning applied
- adaptive task planning reason
- active goal file
- milestone goals
- acceptance file
- planned tasks
- task count
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
- the generated goal output
- the generated task output

## Artifact rule

By default, store intermediate pipeline artifacts under `.repo-init/` in the target repository.

Do not scatter artifacts across multiple ad hoc directories such as `tmp/`, `.tmp/`, `_repo_init_tmp/`, or `repo-init/`.
