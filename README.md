# RepoFrame

RepoFrame is a repository bootstrap template for human and agent collaboration.

This repository now also contains the installable `repo-init` skill source under [`repo-init/`](./repo-init), so the template and the skill can evolve together.

The goal is one-shot initialization: a user provides a prompt or a project-plan file, and the agent creates a working project context with stable documentation, task tracking, and decision logging.

## Repo Init Skill

`repo-init` is an installable Codex skill that bootstraps or hydrates repositories with:

- `README.md`
- `AGENT.md`
- `PROJECT.md`
- `STATUS.md`
- `DECISIONS.md`
- `tasks/`

The skill supports:

- prompt-only initialization
- importing `.md`, `.txt`, `.docx`, `.pdf`, and `.html` project plans
- hydrating an existing repository without rewriting user-owned project material by default

### Install

Copy the skill source into `$CODEX_HOME/skills/repo-init`.

Windows example:

```powershell
Copy-Item -LiteralPath .\repo-init -Destination "$env:CODEX_HOME\skills\repo-init" -Recurse -Force
```

### Runtime

Prefer a Python 3.10+ interpreter.

If Codex bundled workspace Python is available, use that runtime first. Otherwise use a local Python environment with:

```bash
python -m pip install pypdf python-docx
```

Before running the initialization flow, check the runtime with:

```bash
python "$CODEX_HOME/skills/repo-init/scripts/doctor.py"
```

### Command-Line Usage

Use the deterministic orchestrator instead of manually chaining scripts:

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

This writes normalized intermediate artifacts under `.repo-init/` in the target repository and keeps all writes scoped to the `--repo` directory.

## Goal

Use this repository as the starting point for new projects that need:

- clear project definition
- explicit agent operating rules
- persistent status tracking
- lightweight decision records
- task-by-task execution records

## Template Contract

This template standardizes the following files:

- [`AGENT.md`](./AGENT.md): operating protocol for agents
- [`PROJECT.md`](./PROJECT.md): project definition and scope
- [`STATUS.md`](./STATUS.md): current working state
- [`DECISIONS.md`](./DECISIONS.md): durable decision log
- [`tasks/`](./tasks): task records and execution units

The detailed specification lives in [`PROJECT.md`](./PROJECT.md) and [`AGENT.md`](./AGENT.md).

Initialization protocol details live in:

- [`INIT_PROMPT.md`](./INIT_PROMPT.md): user-facing initialization contract
- [`INIT_EXECUTOR_SPEC.md`](./INIT_EXECUTOR_SPEC.md): executor behavior and write policy
- [`INTAKE_SPEC.md`](./INTAKE_SPEC.md): multi-format input intake and extraction contract
- [`repo-init/references/runtime.md`](./repo-init/references/runtime.md): runtime and dependency contract for the installable skill

## Initialization Model

The repository is initialized from a single prompt that should include, at minimum:

- project name
- project type
- target users
- core goal
- preferred stack
- current stage
- constraints

The agent must convert that prompt into structured project metadata and populate the template files.

## Lifecycle

1. Initialize the repository from a prompt.
2. Refine `PROJECT.md` until goals and constraints are stable.
3. Use `tasks/` for all execution work.
4. Keep `STATUS.md` current as the short operational snapshot.
5. Append important architectural or product choices to `DECISIONS.md`.

## Repository Layout

- [`repo-init/`](./repo-init): installable skill source
- [`INIT_PROMPT.md`](./INIT_PROMPT.md): input contract
- [`INIT_EXECUTOR_SPEC.md`](./INIT_EXECUTOR_SPEC.md): initialization behavior contract
- [`INTAKE_SPEC.md`](./INTAKE_SPEC.md): intake and extraction contract
- template root files: the repository structure that initialized projects should receive

## Principles

- Keep static facts and dynamic progress separate.
- Do not duplicate the same information across files.
- Prefer short, durable records over long narrative docs.
- Treat each task file as the unit of execution.
