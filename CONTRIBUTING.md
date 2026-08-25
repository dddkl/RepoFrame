# Contributing

RepoFrame is intentionally small. Contributions should preserve its role as an agent-agnostic state protocol and local visualization tool rather than adding workflow policy.

## Prerequisites

- Python 3.10 or newer
- No third-party runtime dependencies

Create a local editable installation when needed:

```bash
python -m pip install -e .
```

## Validate changes

Run the complete standard-library test suite:

```bash
python -m unittest discover -s tests -v
```

Build and install the package when changing packaging or resources:

```bash
python -m pip install build
python -m build
python -m pip install --force-reinstall dist/*.whl
repoframe --version
```

For viewer changes, initialize a temporary repository with a branching DAG, run `repoframe view`, and inspect the active, done, blocked, pending, and skipped states at desktop and narrow widths.

## Protocol changes

`src/repoframe/resources/state.schema.json` is the public structural contract. The Python validator adds semantic DAG checks that JSON Schema cannot express conveniently.

When changing the protocol:

- keep the packaged Schema and Python validator aligned;
- add tests that fail before the implementation change;
- do not reinterpret an existing `schema_version` incompatibly;
- reject unknown fields instead of letting state grow into an unbounded log;
- keep `state.json` the only execution-state source of truth.

## Product boundaries

- Prefer the Python standard library and bundled browser assets.
- Do not add a framework for a behavior that can remain a small function.
- Keep agent adapters thin and semantically identical.
- Preserve user-authored content outside RepoFrame managed markers.
- Treat the viewer as read-only until a separately designed intent API exists.
- Do not record private model reasoning, chat history, or per-save activity.

## Pull requests

Describe the user-visible behavior, protocol compatibility impact, and exact verification commands. Changes to the Schema, validation semantics, adapter discovery, local HTTP boundary, or package data should be called out explicitly.
