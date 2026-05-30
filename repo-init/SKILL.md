---
name: repo-init
description: Initialize repositories from a natural-language prompt or one or more existing project-plan files, including Markdown, text, DOCX, PDF, and HTML inputs. Use when Codex needs to bootstrap or hydrate a repo with README.md, AGENT.md, PROJECT.md, STATUS.md, DECISIONS.md, goals/, tasks/, and .agent/, while preserving user-authored project plans by default.
---

# Repo Init Skill

Initialize a repository into a stable human and agent collaboration workspace.

Default behavior is non-destructive: preserve user-authored project plans unless the user explicitly asks for a rewrite or reformat.

Use the deterministic single-entry workflow in `scripts/initialize_repo.py` instead of manually composing the lower-level scripts except during debugging.

## When to use

- Initialize a new repository from a single prompt.
- Import one or more existing project-plan files into the RepoFrame collaboration template.
- Add `README.md`, `AGENT.md`, `PROJECT.md`, `STATUS.md`, `DECISIONS.md`, `goals/`, `tasks/`, and `.agent/` to an existing repository.
- Normalize plan intake from `.md`, `.txt`, `.docx`, `.pdf`, `.html`, or prompt-only input before deciding what to write.
- Accept multiple source files and treat the first one as authoritative by default when the user does not explicitly name a primary source.
- Create a milestone-goal adaptive plan: a few milestone goals for larger projects plus as many evidence-backed planned tasks as help human-agent collaboration.

## Skill path

User-installed skills live under `$CODEX_HOME/skills` (default: `~/.codex/skills`).

Installed path for this skill:

```text
$CODEX_HOME/skills/repo-init
```

## Workflow

1. Identify the input source.
Treat the request as one of three entry modes:
- prompt only
- prompt plus one or more local project-plan files
- existing repository hydration

2. Check the runtime first.
Use the doctor script before initialization:

```bash
python "$CODEX_HOME/skills/repo-init/scripts/doctor.py"
```

If the runtime is missing dependencies, stop and fix the environment first. See `references/runtime.md`.

3. Build the source bundle when files are involved.
Use the bundle builder when the user supplies multiple files, or when the prompt appears to mention file paths:

```bash
python "$CODEX_HOME/skills/repo-init/scripts/build_source_bundle.py" \
  --repo . \
  --prompt "Initialize this repository from docs/vision.md and docs/requirements.md. Use docs/vision.md as the primary source." \
  --source docs/vision.md \
  --source docs/requirements.md \
  --primary-source docs/vision.md \
  --artifacts-dir .repo-init
```

If the bundle contains `clarification_questions`, ask the user before proceeding when you are working interactively in Codex. If the user does not answer, continue conservatively and let the generated workspace record the unresolved questions.

4. Run the deterministic entry point.
Always pass the target repository explicitly with `--repo`. Do not rely on the current working directory to decide where files should be written.

Prompt-only example:

```bash
python "$CODEX_HOME/skills/repo-init/scripts/initialize_repo.py" \
  --repo . \
  --prompt "Initialize this repository as a TypeScript CLI for release automation."
```

File-based example:

```bash
python "$CODEX_HOME/skills/repo-init/scripts/initialize_repo.py" \
  --repo . \
  --source docs/project-plan.docx
```

Multi-file example:

```bash
python "$CODEX_HOME/skills/repo-init/scripts/initialize_repo.py" \
  --repo . \
  --prompt "Initialize this repository from docs/vision.md and docs/requirements.md. Use docs/vision.md as the primary source." \
  --source docs/vision.md \
  --source docs/requirements.md \
  --primary-source docs/vision.md
```

5. Review the repository-local artifacts.
The initialization pipeline stores normalized artifacts under:

```text
.repo-init/
```

Review:
- `.repo-init/raw-intake.json`
- `.repo-init/intake.json`
- `.repo-init/mode.json`
- `.repo-init/policy.json`
- `.repo-init/init-report.md`

6. Stop after initialization unless the user explicitly asks to continue.
Initialization is complete once the collaboration files, milestone goals, `acceptance.json`, planned tasks, and initialization report exist.

Default completion behavior:
- summarize what was created or preserved
- point the user to `STATUS.md`, the active milestone goal, `acceptance.json`, the recommended starting task, and `.repo-init/init-report.md`
- stop and wait for the next instruction

Do not:
- start implementing the recommended starting task automatically
- create extra scaffolding beyond the initialization contract unless the user explicitly asked for it
- treat the suggested `Next Step` in `STATUS.md` as permission to execute it in the same turn

7. Use the low-level scripts only for debugging.
The low-level scripts remain available when you need to inspect one stage in isolation:
- `build_source_bundle.py`
- `extract_project_source.py`
- `normalize_project_intake.py`
- `classify_init_mode.py`
- `plan_write_policy.py`
- `render_init_report.py`

## Operating rules

- Preserve user-authored project plans by default.
- Use `initialize_repo.py` as the default execution path.
- Use `doctor.py` before file-ingest workflows when the runtime may be fresh.
- Let multi-file intake default to prompt order unless the user explicitly identifies a primary source.
- When `clarification_questions` exist and you are in an interactive Codex thread, ask the user before finalizing if the conflict materially affects initialization.
- Treat `PROJECT.md` as a compatibility layer when a prior plan already exists.
- Separate extraction from interpretation; do not infer initialization mode inside the extraction step.
- Prefer the smallest safe collaboration state when intake confidence is low.
- Create a clarification task instead of inventing missing project facts.
- Always create at least one milestone goal under `goals/`.
- For complex projects, create a few milestone goals rather than a deep goal hierarchy.
- Create `acceptance.json` for machine-checkable milestone acceptance.
- For complex projects, create as many evidence-backed planned tasks as help collaboration; do not impose a fixed task-count cap.
- Keep `STATUS.md` pointed at the active goal and `none` for active task until a task is explicitly started.
- When a task hits a milestone, blocker change, acceptance change, invalidated assumption, or user-directed change, update that task's `Assumption Checks` and `Downstream Impact` before closing the execution batch.
- When task-local feedback affects unfinished work, update the active goal `Observation Ledger` plus `STATUS.md` `Latest Feedback`, `Task Impact`, and `Recommended Replan`.
- Treat planned tasks as provisional; rewrite, split, reorder, or supersede them when observations show a better route to the active goal.
- Do not change the goal, hard constraints, durable project scope, accepted success criteria, or collaboration contract without explicit human confirmation.
- Do not delete or weaken `acceptance.json` checks without explicit human confirmation.
- Record only durable accepted adjustments in `DECISIONS.md`; keep temporary feedback and replan suggestions out of it.
- Keep all writes inside the explicit `--repo` target and that repository's `.repo-init/` artifact directory.
- Treat initialization as complete when the collaboration layer and initialization report have been written.
- Do not begin implementation after initialization unless the user explicitly asks for post-init execution.

## Reference map

- `references/init-executor.md`: mode selection, write policy, and initialization flow
- `references/intake.md`: supported formats, normalized intake schema, and provenance rules
- `references/project-compat.md`: `PROJECT.md` compatibility behavior and source modes
- `references/output-contract.md`: required repository outputs and initialization report fields
- `references/runtime.md`: runtime, dependency, artifact-path, and isolation rules

## Script map

- `scripts/doctor.py`: verify Python version and required runtime dependencies
- `scripts/build_source_bundle.py`: extract, normalize, and merge multiple project-plan sources
- `scripts/initialize_repo.py`: run the end-to-end deterministic initialization flow
- `scripts/extract_project_source.py`: extract text and metadata from prompt or local project-plan files
- `scripts/normalize_project_intake.py`: convert raw extraction into the normalized intake schema
- `scripts/classify_init_mode.py`: classify `greenfield`, `plan-ingest`, or `repo-hydrate`
- `scripts/plan_write_policy.py`: compute per-file write actions
- `scripts/render_init_report.py`: produce a standard initialization report
- `scripts/lint_acceptance.py`: lint `acceptance.json` machine-checkable milestone criteria

## Validation

- Run `scripts/smoke_initialize_repo.py` after editing the skill folder.
- Smoke-test prompt-only, file-ingest, multi-file ingest, conflict, and hydrate flows with the bundled scripts.
- Run `lint_acceptance.py --repo <initialized-repo>` when validating generated milestone acceptance output.
- If file extraction is weak, preserve the source and generate warnings rather than forcing a rewrite.
