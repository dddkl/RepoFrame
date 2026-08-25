# RepoFrame

RepoFrame makes a coding agent's progress visible and resumable.

It is a local-first, agent-agnostic execution-state protocol with a zero-runtime-dependency Python CLI and a read-only DAG viewer. RepoFrame records one goal and the meaningful stages leading to it. It does not prescribe how an agent should think or turn project work into a heavyweight task-management process.

## Install

RepoFrame requires Python 3.10 or newer.

```bash
python -m pip install .
```

For isolated command-line installation from a checkout:

```bash
pipx install .
```

The package exposes both `repoframe` and `python -m repoframe`.

## Quick start

Initialize a repository:

```bash
repoframe init \
  --goal "Ship authenticated access" \
  --outcome "Users can sign in and reach protected resources" \
  --criterion "Authentication tests pass" \
  --constraint "Do not use an external identity provider" \
  --agents auto
```

This creates:

```text
.repoframe/
├── state.json
├── state.schema.json
└── instructions.md
```

Validate state after an agent changes it:

```bash
repoframe validate
repoframe validate --json
```

Open the local viewer:

```bash
repoframe view
```

The viewer binds only to `127.0.0.1`, opens `http://127.0.0.1:7331/`, and updates when `.repoframe/state.json` changes. Use `--no-open` to start it without opening a browser or `--port` to choose a different loopback port.

## State protocol

`state.json` is the sole execution-state source of truth. Git supplies history and recovery.

```json
{
  "$schema": "./state.schema.json",
  "schema_version": 1,
  "goal": {
    "id": "ship-auth",
    "title": "Ship authenticated access",
    "outcome": "Users can sign in and reach protected resources",
    "success_criteria": ["Authentication tests pass"],
    "constraints": ["Do not use an external identity provider"],
    "status": "active"
  },
  "nodes": [
    {
      "id": "inspect-auth",
      "title": "Inspect existing authentication boundaries",
      "status": "done",
      "depends_on": [],
      "summary": "Session and route boundaries are documented.",
      "evidence": ["src/auth/session.py"]
    },
    {
      "id": "implement-auth",
      "title": "Implement the authentication flow",
      "status": "active",
      "depends_on": ["inspect-auth"]
    }
  ],
  "updated_at": "2026-08-25T08:00:00Z"
}
```

Node states are `pending`, `active`, `done`, `blocked`, and `skipped`. A snapshot may contain at most one active node. Dependencies must refer to existing nodes, active-node dependencies must be complete, and the graph must remain acyclic. The bundled JSON Schema documents the structural contract; `repoframe validate` also enforces semantic DAG rules.

## Agent adapters

RepoFrame's core is independent of any agent product. `repoframe init --agents` only adds a small managed section to instruction files that an agent already understands.

| Selection | Instruction file |
| --- | --- |
| `codex` | `AGENTS.md` |
| `cursor` | `AGENTS.md` |
| `claude` | `CLAUDE.md` |
| `gemini` | `GEMINI.md` |
| `copilot` | `.github/copilot-instructions.md` |

Available values are `auto`, `all`, `none`, or a comma-separated selection. `auto` detects existing instruction files and falls back to `AGENTS.md` when none exist. Managed markers make updates idempotent, and content outside those markers is preserved.

Compatibility means different supported agents can take turns continuing the same goal. Version 0.1 assumes one writer at a time; it does not implement concurrent state merging.

## Viewer boundary

The browser UI is deliberately read-only. It serves packaged HTML, CSS, and JavaScript through a standard-library HTTP server and reads validated state from `GET /api/v1/state`. It has no CDN, database, external network dependency, state editor, shell access, or agent-control endpoint.

Future HTML-to-agent interaction can be added through an explicit, versioned intent API. It should not turn the existing state endpoint into arbitrary browser-driven file mutation.

## Non-goals

RepoFrame is not:

- an agent skill, plugin, SDK, or MCP server;
- a task manager or orchestration framework;
- a cloud synchronization service;
- a replacement for source code, tests, Git, or durable project documentation;
- a recorder of private reasoning or every file edit.

## Development

Run the tests:

```bash
python -m unittest discover -s tests -v
```

Build installable artifacts:

```bash
python -m pip install build
python -m build
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for protocol and compatibility rules.

## Legacy

The former `repo-init` Codex skill is archived and no longer maintained:

- branch: `codex/legacy-repo-init-skill`
- tag: `repo-init-skill-v1-final`

The old implementation is intentionally absent from the default branch.

## License

RepoFrame is available under the MIT License.
