# Contributing

RepoFrame is intentionally small. Contributions must preserve:

> Iteration observes development. Long Run models execution.

## Prerequisites

- Python 3.10 or newer
- Git
- zero third-party runtime dependencies

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
python -m compileall -q src tests
```

For package verification:

```bash
python -m pip install build
python -m build
python -m pip install --force-reinstall dist/*.whl
repoframe --version
```

## Product boundaries

Iteration must not maintain Goal, DAG, focus, activity, or summary state. Its UI may read Git and request a confirmed Commit operation. Local mode is stored in Git config so switching does not dirty the worktree.

Long Run contains only one Goal, execution nodes, and durable user interventions per snapshot. Do not add owners, deadlines, priorities, percentages, chat transcripts, private reasoning, or a general orchestration language.

RepoFrame operation Agents make semantic proposals. They do not write code, Git, or state. Deterministic Python code validates and applies Graph Patch and runs the fixed Git commands.

## Protocol changes

`src/repoframe/resources/state.schema.json` is the structural contract; `state.py` adds semantic checks.

When changing it:

- preserve v1 reads unless a deliberate breaking release says otherwise;
- keep packaged Schema, Python validation, and fixtures aligned;
- reject unknown fields;
- keep node IDs and completed history stable;
- ensure user intervention text cannot be changed through the API;
- validate a full copied snapshot before atomic replacement;
- use Git for history rather than adding an event log.

## Interactive API

- Bind only to `127.0.0.1`.
- Keep `repoframe view` read-only.
- Keep interactive routes and operation types on explicit allowlists.
- Require the session token and exact Origin/Host validation.
- Never accept arbitrary shell commands, executable templates, Prompts, paths, or JSON Patch.
- Do not expose Agent events, private reasoning, or full internal Prompts.
- Use `shell=False` and pass user text through stdin or structured data.
- Keep at most one RepoFrame-managed operation active.

## Viewer

- Keep assets local and dependency-free.
- Use DOM text APIs for repository content.
- Preserve ETag and invalid-state recovery.
- Keep the graph usable by blank-space drag, keyboard selection, and status text.
- Respect `prefers-reduced-motion`.
- Keep secondary panels below the fixed top bar.
- Treat archived Goal snapshots as read-only.

No real-browser automation is required. Unit and HTTP integration tests are the automated baseline; use an ignored `_test/` repository for manual visual acceptance.

## Agent adapters

Adapters remain thin and semantically identical. Preserve user-authored content outside managed markers. Iteration instructions must reject execution-state maintenance; Long Run instructions should require updates only at meaningful boundaries.

## Pull requests

Describe:

- user-visible behavior;
- protocol compatibility;
- exact tests run;
- Git mutation impact;
- Agent/provider impact;
- loopback security impact;
- packaged-resource impact.
