# RepoFrame

RepoFrame is the source repository for `repo-init`, an installable Codex skill that initializes a repository with a small, explicit collaboration layer for humans and agents.

The goal is not to scaffold application code. The goal is to make project state durable: current objective, accepted constraints, planned tasks, machine-checkable acceptance, and handoff context.

## Use It

Use `$repo-init` in Codex. That is the primary interface.

```text
Use $repo-init to initialize this repository: build a TypeScript CLI called ReleasePilot for small release teams. The goal is to automate changelog preparation. Use Node.js, TypeScript, and Vitest. Do not build a web UI in the first phase.
```

You can initialize from plan files:

```text
Use $repo-init to initialize this repository from docs/vision.md and docs/requirements.md. Use docs/vision.md as the primary source.
```

You can also hydrate an existing repository:

```text
Use $repo-init to add the collaboration layer to this existing repository without treating it as a greenfield project.
```

## What It Produces

`repo-init` creates or supplements:

- `README.md`
- `AGENT.md`
- `PROJECT.md`
- `STATUS.md`
- `DECISIONS.md`
- `.agent/` detailed collaboration rules
- `goals/` milestone goal files
- `tasks/` planned task files
- `acceptance.json` machine-checkable milestone acceptance
- `.repo-init/` normalized intake artifacts and `init-report.md`

Every initialization gets one active milestone goal and at least one planned task. Larger projects get a few milestone goals and as many evidence-backed tasks as help collaboration. Initialization stops after writing the collaboration layer; it does not execute the recommended next task.

## Modes

`repo-init` selects one of three modes:

- `greenfield`: start from a prompt in an empty or near-empty repository
- `plan-ingest`: initialize from one or more authoritative project-plan files
- `repo-hydrate`: add collaboration files around an existing codebase or project

The default posture is preserve-first. Existing project plans and user-authored repository files are preserved unless the user explicitly asks for a rewrite.

## Input Support

Supported project-plan inputs:

- `.md`
- `.txt`
- `.docx`
- `.pdf`
- `.html`

Markdown remains the recommended source format. The pipeline is deterministic and text-first; screenshots, scanned pages, embedded images, and diagram-only requirements are less reliable than plain text or Mermaid-style diagrams.

## Install

Copy `repo-init/` into `$CODEX_HOME/skills/repo-init`.

Windows:

```powershell
Copy-Item -LiteralPath .\repo-init -Destination "$env:CODEX_HOME\skills\repo-init" -Recurse -Force
```

## Runtime

Use Python `3.10+`.

Install file-ingest dependencies when needed:

```bash
python -m pip install pypdf python-docx
```

Run the preflight check for fresh environments or file-ingest workflows:

```bash
python "$CODEX_HOME/skills/repo-init/scripts/doctor.py"
```

## CLI Fallback

The deterministic backend is available for debugging and non-Codex use.

Prompt-only:

```bash
python "$CODEX_HOME/skills/repo-init/scripts/initialize_repo.py" \
  --repo . \
  --prompt "Initialize this repository as a TypeScript CLI for release automation."
```

File-based:

```bash
python "$CODEX_HOME/skills/repo-init/scripts/initialize_repo.py" \
  --repo . \
  --source docs/project-plan.docx
```

Validate generated acceptance checks:

```bash
python repo-init/scripts/lint_acceptance.py --repo .
```

Command checks in `acceptance.json` run only when the linter is invoked with `--allow-command-checks`.

## Repository Layout

- `repo-init/`: installable skill source, references, and deterministic scripts
- `repo-init/scripts/initialize_repo.py`: main entry point
- `repo-init/scripts/smoke_initialize_repo.py`: regression smoke test
- `repo-init/references/`: behavior, intake, runtime, and output contracts
- `.github/workflows/ci.yml`: compile and smoke validation

## Validation

For most changes:

```bash
python repo-init/scripts/smoke_initialize_repo.py
```

For runtime checks:

```bash
python repo-init/scripts/doctor.py --format pdf --format docx
```

For output-contract details, read `repo-init/references/output-contract.md`.
