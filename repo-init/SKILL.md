---
name: repo-init
description: Initialize repositories from a natural-language prompt or an existing project plan, including Markdown, text, DOCX, PDF, and HTML inputs. Use when Codex needs to bootstrap or hydrate a repo with README.md, AGENT.md, PROJECT.md, STATUS.md, DECISIONS.md, and tasks/, while preserving user-authored project plans by default.
---

# Repo Init Skill

Initialize a repository into a stable human and agent collaboration workspace.

Default behavior is non-destructive: preserve user-authored project plans unless the user explicitly asks for a rewrite or reformat.

Use the deterministic single-entry workflow in `scripts/initialize_repo.py` instead of manually composing the lower-level scripts except during debugging.

## When to use

- Initialize a new repository from a single prompt.
- Import an existing project plan into the RepoFrame collaboration template.
- Add `README.md`, `AGENT.md`, `PROJECT.md`, `STATUS.md`, `DECISIONS.md`, and `tasks/` to an existing repository.
- Normalize plan intake from `.md`, `.txt`, `.docx`, `.pdf`, `.html`, or prompt-only input before deciding what to write.

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
- prompt plus a local project-plan file
- existing repository hydration

2. Check the runtime first.
Use the doctor script before initialization:

```bash
python "$CODEX_HOME/skills/repo-init/scripts/doctor.py"
```

If the runtime is missing dependencies, stop and fix the environment first. See `references/runtime.md`.

3. Run the deterministic entry point.
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

4. Review the repository-local artifacts.
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

5. Use the low-level scripts only for debugging.
The low-level scripts remain available when you need to inspect one stage in isolation:
- `extract_project_source.py`
- `normalize_project_intake.py`
- `classify_init_mode.py`
- `plan_write_policy.py`
- `render_init_report.py`

## Operating rules

- Preserve user-authored project plans by default.
- Use `initialize_repo.py` as the default execution path.
- Use `doctor.py` before file-ingest workflows when the runtime may be fresh.
- Treat `PROJECT.md` as a compatibility layer when a prior plan already exists.
- Separate extraction from interpretation; do not infer initialization mode inside the extraction step.
- Prefer the smallest safe collaboration state when intake confidence is low.
- Create a clarification task instead of inventing missing project facts.
- Keep all writes inside the explicit `--repo` target and that repository's `.repo-init/` artifact directory.

## Reference map

- `references/init-executor.md`: mode selection, write policy, and initialization flow
- `references/intake.md`: supported formats, normalized intake schema, and provenance rules
- `references/project-compat.md`: `PROJECT.md` compatibility behavior and source modes
- `references/output-contract.md`: required repository outputs and initialization report fields
- `references/runtime.md`: runtime, dependency, artifact-path, and isolation rules

## Script map

- `scripts/doctor.py`: verify Python version and required runtime dependencies
- `scripts/initialize_repo.py`: run the end-to-end deterministic initialization flow
- `scripts/extract_project_source.py`: extract text and metadata from prompt or local project-plan files
- `scripts/normalize_project_intake.py`: convert raw extraction into the normalized intake schema
- `scripts/classify_init_mode.py`: classify `greenfield`, `plan-ingest`, or `repo-hydrate`
- `scripts/plan_write_policy.py`: compute per-file write actions
- `scripts/render_init_report.py`: produce a standard initialization report

## Validation

- Run `quick_validate.py` after editing the skill folder.
- Smoke-test prompt-only, file-ingest, and hydrate flows with the bundled scripts.
- If file extraction is weak, preserve the source and generate warnings rather than forcing a rewrite.
