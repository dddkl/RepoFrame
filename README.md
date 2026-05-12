# RepoFrame

RepoFrame is the source repository for `repo-init`, an installable Codex skill that turns a prompt or an existing project plan into a stable human and agent collaboration workspace.

It was inspired by agile development and refined through our own experience with longer-running agent work. The problem it tries to solve is not just "how do we generate project files", but "how do we keep an agent from drifting, keep feedback visible, and let a human rejoin the work without losing the thread".

## Why This Exists

Most bootstrap tools are good at creating a starting structure. RepoFrame is aimed at the layer after that: making the repo legible enough for sustained human-agent collaboration.

`repo-init` does that by:

- generating a visible collaboration layer instead of only scaffolding code
- preserving user-authored plans by default instead of rewriting them unless asked
- separating initialization from execution so a suggested next step is not treated as implicit permission to continue
- keeping feedback, downstream task impact, and replan suggestions explicit in the generated workspace
- decomposing complex projects into a coordinating master task plus child tasks when a single task would be too coarse

If you have worked with agents on larger repositories, the failure mode is usually not "nothing was created". It is silent assumption drift, unclear next steps, and humans having to reconstruct context from scratch. RepoFrame is built to reduce that.

## Recommended Usage

Use `$repo-init` directly in Codex. That is the primary interface.

In normal use, you do not need to run the bundled scripts manually. The CLI is the deterministic backend and a debugging fallback when you want to validate behavior outside the usual skill flow.

## Using The Method Without Codex

Yes, the core idea is usable even without Codex.

RepoFrame is not based on a platform-only trick. The underlying method can be applied with a capable LLM, one good prompt, and the files in [`template/`](./template). What `repo-init` adds on top is the deterministic execution path, input normalization, mode selection, preservation policy, and task decomposition rules.

If you want to apply the method manually, this short prompt is enough to get close to the same collaboration shape:

```text
Use the files in template/ as the target collaboration structure. Read the project context I provide and initialize a collaboration layer around it. Preserve any user-authored project plan by default. Create or update README.md, AGENT.md, PROJECT.md, STATUS.md, DECISIONS.md, REUSE.md, and tasks/.

Rules:
- Separate initialization from execution. Stop after creating the collaboration layer.
- If the project is simple, create one actionable first task.
- If the project is complex, create one coordinating master task and 3-7 child tasks.
- Keep latest feedback, task impact, blockers, risks, and the recommended next step visible in STATUS.md.
- Put durable accepted decisions in DECISIONS.md, not temporary notes.
- If key facts are missing or conflicting, ask clarification questions or produce the smallest safe collaboration layer and record the uncertainty.
```

That manual path can reproduce much of the thinking. The difference is that `repo-init` makes the process more repeatable, less fragile, and easier to audit across repositories.

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

## Initialization Model

RepoFrame supports three practical entry paths:

- `greenfield`: start from a prompt
- `plan-ingest`: initialize from one or more existing plan files
- `repo-hydrate`: add the collaboration layer to an existing repository

Across all three modes, the default posture is preserve-first. If the repository already contains project material, `repo-init` tries to build around it rather than overwrite it.

When intake is incomplete or conflicting, the initializer stays conservative. It records unresolved questions and produces the smallest safe collaboration layer instead of pretending it knows more than it does.

## Input Recommendation And Current Limitation

`repo-init` supports `.md`, `.txt`, `.docx`, `.pdf`, and `.html`, but `Markdown` is still the recommended source format.

This is a current limitation worth stating directly: the skill is built around deterministic, text-first intake. If important requirements only exist inside screenshots, scanned pages, embedded images, or diagram pictures, the initializer becomes less reliable and less auditable.

So even though non-Markdown files are supported, the safer path is:

- prefer `Markdown` whenever you can
- rewrite key requirements from image-heavy documents into text before initialization
- use text-based diagrams such as `Mermaid` for flows, states, and architecture whenever possible

If a document contains critical information that only appears in images, do not assume the skill will interpret that material as well as plain text. In those cases, converting the important parts into Markdown usually gives better results than relying on the original file format alone.

## What The Skill Produces

`repo-init` bootstraps or hydrates a repository with:

- `README.md` for the human-facing repository entry point
- `AGENT.md` for the operational collaboration contract
- `PROJECT.md` for the project definition or compatibility layer around an existing plan
- `STATUS.md` for current focus, latest feedback, task impact, and the recommended next step
- `DECISIONS.md` for durable accepted decisions
- `REUSE.md` for the open-source reuse gate before technical planning
- `tasks/` with actionable task files
- `.repo-init/` with normalized intake artifacts and the initialization report

The task model is intentionally explicit:

- simple projects get one actionable first task
- complex projects get one coordinating master task plus a first wave of child tasks
- clarification-first cases get a clarification task rather than speculative implementation tasks

The feedback loop is explicit as well:

- task-local findings live in each task's `Assumption Checks`, `Downstream Impact`, and `Execution Log`
- cross-task effects flow back to the master task's `Feedback Ledger` on complex projects
- `STATUS.md` keeps the latest high-signal feedback and recommended replan visible at the repo level

## Install

Copy [`repo-init/`](./repo-init) into `$CODEX_HOME/skills/repo-init`.

Windows example:

```powershell
Copy-Item -LiteralPath .\repo-init -Destination "$env:CODEX_HOME\skills\repo-init" -Recurse -Force
```

## Runtime

Use Python `3.10+`.

If Codex bundled workspace Python is available, prefer that runtime. Otherwise install the required packages into your local Python environment:

```bash
python -m pip install pypdf python-docx
```

Before file-ingest workflows, run the preflight check:

```bash
python "$CODEX_HOME/skills/repo-init/scripts/doctor.py"
```

Detailed runtime notes live in [`repo-init/references/runtime.md`](./repo-init/references/runtime.md).

## Debug And CLI Fallback

The bundled CLI is the skill's deterministic execution path. Use it when you are debugging, validating behavior, or running outside the normal Codex skill flow.

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

The CLI keeps writes scoped to the explicit `--repo` target and stores initialization artifacts under `.repo-init/`.

## Repository Layout

- [`repo-init/`](./repo-init) contains the installable skill source and deterministic scripts
- [`template/`](./template) contains example collaboration files that reflect the intended output shape
- [`repo-init/references/`](./repo-init/references) contains the behavior and output contract references

This repository is not just a script dump. It is the source of truth for how the skill should behave, what it should generate, and how that generated workspace is expected to be used.

## Where To Read Next

- [`repo-init/SKILL.md`](./repo-init/SKILL.md) for the operator workflow
- [`repo-init/references/output-contract.md`](./repo-init/references/output-contract.md) for the generated file contract
- [`repo-init/references/init-executor.md`](./repo-init/references/init-executor.md) for execution rules
- [`CONTRIBUTING.md`](./CONTRIBUTING.md) if you want to change the skill or templates

## Repository Purpose In One Line

RepoFrame exists to make repository initialization produce a collaboration frame that humans and agents can keep working from, not just a pile of starter files.
