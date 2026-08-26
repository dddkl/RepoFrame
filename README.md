# RepoFrame

RepoFrame gives local coding-agent collaboration two deliberately different modes:

> **Iteration observes development. Long Run models execution.**

Iteration is a Git-oriented view for fast human–Agent work with almost no bookkeeping. Long Run is a Goal-oriented execution view for autonomous work that must survive interruption or handoff. RepoFrame is local-first, Agent-independent, read-only in the browser, and has no Python runtime dependencies.

## Install

RepoFrame requires Python 3.10 or newer.

```bash
python -m pip install .
```

The package exposes both `repoframe` and `python -m repoframe`.

## Two modes

| | Iteration | Long Run |
| --- | --- | --- |
| Purpose | Rapid human–Agent iteration | Longer autonomous execution |
| Primary source | Git working tree and history | `.repoframe/state.json` |
| Goal and DAG | None | Goal + gradually expanded DAG |
| Agent maintenance | None | Meaningful stage changes only |
| Recovery | Repository and Git | State, repository, and Git |

RepoFrame does not copy Git activity into a second log. It does not maintain current-focus fields, per-save summaries, private reasoning, owners, deadlines, percentages, or orchestration controls.

## Iteration

Initialize RepoFrame without a Goal:

```bash
repoframe init --agents auto
repoframe view
```

This creates only the shared resources needed to explain the modes and support a future Long Run:

```text
.repoframe/
├── state.schema.json
└── instructions.md
```

It does **not** create `state.json`. Open [`http://127.0.0.1:7331/iteration`](http://127.0.0.1:7331/iteration) to see:

- current branch and working-tree status;
- changed, staged, unstaged, and untracked files;
- aggregate additions and deletions from Git diff statistics;
- latest commit;
- recent commit activity.

The page reads Git on demand through a local, read-only API. Agents work normally and do not update RepoFrame state during Iteration.

## Long Run

Create a Long Run when work needs durable execution context:

```bash
repoframe init \
  --goal "Ship authenticated access" \
  --outcome "Users can sign in and reach protected resources" \
  --criterion "Authentication tests pass" \
  --constraint "Do not use an external identity provider" \
  --agents auto
```

This additionally creates `.repoframe/state.json`. Validate it after meaningful updates:

```bash
repoframe validate
repoframe validate --json
```

Open [`http://127.0.0.1:7331/long-run`](http://127.0.0.1:7331/long-run). Each Goal has an independent URL such as `/long-run/ship-auth`; the Execution Path selector switches between available Goals without combining their DAGs.

The Agent should expand the DAG from actual progress rather than plan the entire Goal up front. State changes belong at meaningful stage boundaries and immediately on blocking, material replanning, or handoff. Completing the Goal ends its execution path.

### Long Run state protocol

The v1 schema remains intentionally small:

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
      "title": "Inspect authentication boundaries",
      "status": "done",
      "depends_on": [],
      "summary": "Session and route boundaries are understood.",
      "evidence": ["src/auth/session.py"]
    },
    {
      "id": "implement-auth",
      "title": "Implement authentication flow",
      "status": "active",
      "depends_on": ["inspect-auth"]
    }
  ],
  "updated_at": "2026-08-26T08:00:00Z"
}
```

Node states are `pending`, `active`, `done`, `blocked`, and `skipped`. A snapshot may contain at most one active node. Dependencies must exist, active-node dependencies must be complete, and the graph must be acyclic. No mode field is added to Goal or Node.

### Multiple Goal views

`.repoframe/state.json` is the current Long Run. The Viewer can also discover optional, read-only snapshots placed directly in:

```text
.repoframe/goals/*.json
```

Every snapshot uses the same v1 schema and receives its own `/long-run/<goal-id>` page. Invalid snapshots are reported without preventing valid Goals from rendering. RepoFrame does not provide Goal lifecycle, assignment, scheduling, or concurrency commands; Git remains responsible for history. The CLI does not create the archive directory automatically.

## Agent adapters

`repoframe init --agents` adds one small, managed block to instruction files already understood by supported products:

| Selection | Instruction file |
| --- | --- |
| `codex` | `AGENTS.md` |
| `cursor` | `AGENTS.md` |
| `claude` | `CLAUDE.md` |
| `gemini` | `GEMINI.md` |
| `copilot` | `.github/copilot-instructions.md` |

Values are `auto`, `all`, `none`, or a comma-separated selection. `auto` detects existing files and falls back to `AGENTS.md`. Content outside RepoFrame markers is preserved. All adapters share the same semantics: Iteration does not maintain execution state; Long Run reads and updates it sparingly.

## Local viewer and API

```bash
repoframe view
repoframe view --port 7331
repoframe view --no-open
```

The server binds only to `127.0.0.1` and provides these read-only endpoints:

| Endpoint | Purpose |
| --- | --- |
| `GET /api/v1/iteration` | Git working changes and commit activity |
| `GET /api/v1/goals` | Valid Long Run Goal summaries and snapshot diagnostics |
| `GET /api/v1/goals/<goal-id>` | One validated Goal and DAG |
| `GET /api/v1/state` | Backward-compatible current-state endpoint |
| `GET /healthz` | Process health |

Responses use ETags. The page polls locally and skips unchanged payloads. Static assets are packaged; there is no CDN, database, Web framework, external network request, state editor, shell endpoint, or Agent-control endpoint.

The Git API invokes only fixed, read-only Git inspection commands. It never stages, commits, resets, checks out, or modifies repository files.

## Configuration boundary

Version 0.2 does not need `.repoframe/config.json` and does not create one. If global UI configuration becomes necessary, it belongs in `config.json`; Long Run execution state remains in state snapshots. UI preferences must not inflate Goal or Node records.

## Non-goals

RepoFrame is not:

- a task manager or Agent orchestrator;
- an Agent skill, plugin, SDK, or MCP server;
- a cloud synchronization or remote monitoring service;
- a recorder of private reasoning, chat history, or every edit;
- a replacement for source code, tests, Git, or durable project documentation.

## Development

```bash
python -m unittest discover -s tests -v
python -m compileall -q src tests
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for mode boundaries and compatibility rules.

## Legacy

The former `repo-init` Codex skill is archived and no longer maintained:

- branch: `codex/legacy-repo-init-skill`
- tag: `repo-init-skill-v1-final`

The old implementation is intentionally absent from the default branch.

## License

RepoFrame is available under the MIT License.
