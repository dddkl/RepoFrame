# RepoFrame

RepoFrame is the source repository for `repo-init`, an installable Codex skill that initializes repositories from a prompt or an existing project plan.

This repository also includes a [`template/`](./template) directory that shows the collaboration files the skill is designed to generate.

## Recommended Usage

Use `$repo-init` directly in Codex. That is the primary interface.

In normal use, you do not need to run the bundled scripts manually. The CLI exists as a deterministic backend and a debugging fallback.

### Greenfield

```text
Use $repo-init to initialize this repository: build a TypeScript CLI called ReleasePilot for small release teams. The goal is to automate changelog preparation. Use Node.js, TypeScript, and Vitest. Do not build a web UI in the first phase.
```

### Plan Ingest

```text
Use $repo-init to initialize this repository from D:\plans\project-plan.docx. Preserve the original plan by default and create the collaboration layer around it.
```

### Multi-Source Plan Ingest

```text
Use $repo-init to initialize this repository from docs/vision.md and docs/requirements.md. Use docs/vision.md as the primary source.
```

### Repo Hydrate

```text
Use $repo-init to add the collaboration layer to this existing repository without treating it as a greenfield project.
```

## What The Skill Produces

`repo-init` bootstraps or hydrates a repository with:

- `README.md`
- `AGENT.md`
- `PROJECT.md`
- `STATUS.md`
- `DECISIONS.md`
- `tasks/`

It supports:

- prompt-only initialization
- importing multiple project-plan files in one initialization request
- importing `.md`, `.txt`, `.docx`, `.pdf`, and `.html` project plans
- hydrating an existing repository without rewriting user-authored project material by default
- asking for clarification in Codex when conflicts or missing facts materially affect initialization

## Install

Copy [`repo-init/`](./repo-init) into `$CODEX_HOME/skills/repo-init`.

Windows example:

```powershell
Copy-Item -LiteralPath .\repo-init -Destination "$env:CODEX_HOME\skills\repo-init" -Recurse -Force
```

## Runtime

Use Python 3.10 or newer.

If Codex bundled workspace Python is available, prefer that runtime. Otherwise install the required packages into your local Python environment:

```bash
python -m pip install pypdf python-docx
```

Before file-ingest workflows, run the preflight check:

```bash
python "$CODEX_HOME/skills/repo-init/scripts/doctor.py"
```

## Debug / CLI Fallback

The bundled CLI is the skill's deterministic execution path. Use it when debugging, validating, or running outside the normal Codex skill flow.

Run the preflight:

```bash
python "$CODEX_HOME/skills/repo-init/scripts/doctor.py" --format pdf --format docx
```

Run initialization directly:

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

The skill writes repository-local artifacts under `.repo-init/` and keeps all writes scoped to the explicit `--repo` target.

When multiple sources disagree or key facts remain unclear, the skill may first ask the user for clarification in an interactive Codex thread. The CLI path does not block for answers; it continues with the smallest safe collaboration layer and records unresolved questions in the generated workspace.

## Template Examples

The sample collaboration structure lives in [`template/`](./template):

- [`template/AGENT.md`](./template/AGENT.md)
- [`template/PROJECT.md`](./template/PROJECT.md)
- [`template/STATUS.md`](./template/STATUS.md)
- [`template/DECISIONS.md`](./template/DECISIONS.md)
- [`template/tasks/`](./template/tasks)

These files are examples and reference material. They are not runtime inputs required by the skill.

## Skill References

The canonical skill behavior is defined inside [`repo-init/references/`](./repo-init/references):

- [`repo-init/references/init-executor.md`](./repo-init/references/init-executor.md)
- [`repo-init/references/intake.md`](./repo-init/references/intake.md)
- [`repo-init/references/project-compat.md`](./repo-init/references/project-compat.md)
- [`repo-init/references/output-contract.md`](./repo-init/references/output-contract.md)
- [`repo-init/references/runtime.md`](./repo-init/references/runtime.md)

## Repository Contents

- [`repo-init/`](./repo-init): installable skill source
- [`template/`](./template): example collaboration files and task template
- [`OPEN_SOURCE_READINESS.md`](./OPEN_SOURCE_READINESS.md): current release-readiness assessment
