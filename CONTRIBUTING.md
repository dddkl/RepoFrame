# Contributing

Thanks for contributing to RepoFrame.

This repository is the source for the `repo-init` Codex skill. Most changes affect a deterministic initialization pipeline, so contributions should optimize for explicit behavior, compatibility, and validation rather than cleverness.

## Before You Start

- Read `repo-init/SKILL.md` to understand the intended operator workflow.
- Read `repo-init/references/output-contract.md` before changing generated files or initialization behavior.
- Read `repo-init/references/runtime.md` before changing runtime assumptions or dependency handling.

## Development Prerequisites

- Python `3.10+`
- Packages:
  - `pypdf`
  - `python-docx`

Install local dependencies with:

```bash
python -m pip install pypdf python-docx
```

For fresh environments, run the preflight check before file-ingest work:

```bash
python repo-init/scripts/doctor.py
```

## Validation

Run the validations that match your change.

Minimum validation for most changes:

```bash
python -m py_compile repo-init/scripts/initialize_repo.py repo-init/scripts/project_text.py repo-init/scripts/init_summary.py repo-init/scripts/init_task_plan.py repo-init/scripts/init_render.py repo-init/scripts/init_output.py repo-init/scripts/build_source_bundle.py
python repo-init/scripts/smoke_initialize_repo.py
```

If you change file-ingest logic, also run:

```bash
python repo-init/scripts/doctor.py --format pdf --format docx
```

If you change document contracts or generated templates:

- update the matching references in `repo-init/references/`
- update the sample files in `template/`
- confirm the generated output still matches the documented contract

## Change Expectations

- Preserve existing CLI entry points unless the change explicitly requires a breaking change.
- Preserve `.repo-init/*.json` compatibility unless the change is intentionally schema-level and documented.
- Keep `initialize_repo.py` deterministic and explicit.
- Prefer shared low-level helpers over duplicating parsing logic across scripts.
- Do not silently loosen preservation rules for user-authored project plans.
- Do not treat a suggested `Next Step` as permission to auto-execute implementation work during initialization.

## Pull Requests

Good pull requests usually include:

- a short explanation of the problem
- a clear summary of the behavior change
- the exact validation commands you ran
- contract/template updates when generated output changed
- notes on compatibility risk if the change touches mode selection, write policy, or task decomposition

If a change is intentionally behavior-changing, call that out explicitly in the PR description.
