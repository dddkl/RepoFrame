# Runtime Contract

Use this reference to keep `repo-init` deterministic across fresh environments.

## Required Python

Use Python 3.10 or newer.

Prefer the bundled Codex workspace Python when it is available. If bundled Python is not available, use a local Python interpreter with the required packages installed.

## Required Packages

`repo-init` requires:

- `pypdf`
- `python-docx`

Install them with:

```bash
python -m pip install pypdf python-docx
```

## Preflight Rule

Before running the initialization flow, run:

```bash
python "$CODEX_HOME/skills/repo-init/scripts/doctor.py"
```

If the runtime is missing required packages, stop and fix the environment before initializing a repository.

## Stable Entry Point

Use `scripts/initialize_repo.py` as the primary execution path.

Do not manually chain the lower-level scripts unless you are debugging the intake or policy pipeline.

## Artifact Path Rule

The default artifact directory is:

```text
<repo>/.repo-init/
```

This directory stores:

- `raw-intake.json`
- `intake.json`
- `mode.json`
- `policy.json`
- extracted text snapshots
- `init-report.md`

## Workspace Isolation Rule

Always pass `--repo <path>` explicitly to `initialize_repo.py`.

The script should only write:

- inside the target repository passed via `--repo`
- inside the repository's `.repo-init/` artifact directory

Do not rely on the current working directory as the target repository.
