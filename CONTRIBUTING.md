# Contributing

RepoFrame is intentionally small. Contributions must preserve its two product semantics:

> Iteration observes development. Long Run models execution.

## Prerequisites

- Python 3.10 or newer
- Git
- no third-party runtime dependencies

For local development:

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
python -m compileall -q src tests
```

When package metadata or resources change:

```bash
python -m pip install build
python -m build
python -m pip install --force-reinstall dist/*.whl
repoframe --version
```

## Mode boundaries

Iteration must remain usable without `.repoframe/state.json`. Its API reads current Git facts and must not stage, commit, reset, check out, write repository files, or duplicate activity into RepoFrame storage. Avoid adding semantic fields that an Agent would need to keep current during a fast conversation.

Long Run may use explicit execution state, but only for a Goal and meaningful DAG stages. It must not grow owners, deadlines, priority queues, percentages, private reasoning, chat transcripts, or orchestration policy.

The two modes may share visual components and the loopback server, but not their state assumptions. Tests should prove that Iteration works in a Git repository with no state file.

## Protocol changes

`src/repoframe/resources/state.schema.json` is the Long Run structural contract. The Python validator adds semantic DAG checks.

When changing it:

- keep packaged Schema, Python validation, and tests aligned;
- do not reinterpret an existing `schema_version` incompatibly;
- reject unknown fields;
- do not add a mode to each Goal or Node;
- keep each snapshot independent and limited to one Goal;
- let Git provide history and recovery rather than adding an event log.

## Viewer and API changes

- Bind only to `127.0.0.1`.
- Keep routes and packaged assets on explicit allowlists.
- Keep browser endpoints read-only until a separately designed intent API exists.
- Escape project data through DOM text APIs; do not build executable markup from repository content.
- Preserve ETag behavior and invalid-state recovery.
- Keep Iteration Git commands fixed and read-only.
- Respect `prefers-reduced-motion` and avoid status meaning that depends only on color.

## Agent adapters

Adapters must remain thin and semantically identical. Preserve user-authored content outside RepoFrame markers. Iteration instructions must not imply state maintenance; Long Run instructions should only require updates at meaningful boundaries.

## Pull requests

Describe the user-visible mode, protocol compatibility impact, exact commands run, and any effect on Git inspection, state validation, adapter files, loopback security, or packaged resources.
