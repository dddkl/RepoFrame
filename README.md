# RepoFrame

RepoFrame is a local workbench for coding-agent collaboration:

> **Iteration observes development. Long Run models execution.**

Iteration adds almost no bookkeeping. It keeps the Long Run graph in the background and uses Git as the record of rapid human-agent work. Long Run stores one Goal, a gradually expanded execution DAG, and durable user interventions in `.repoframe/state.json`.

RepoFrame is Agent-independent at the state and instruction layer. Its optional semantic operation bridge currently implements Codex CLI only. The package has no Python runtime dependencies, frontend dependencies, database, CDN, Node.js service, cloud account, or remote API.

## Install

RepoFrame requires Python 3.10 or newer and Git.

```bash
python -m pip install .
```

Both command forms are supported:

```bash
repoframe --help
python -m repoframe --help
```

## Start

Initialize lightweight Iteration:

```bash
repoframe init --agents auto
```

Initialize a Long Run Goal:

```bash
repoframe init \
  --goal "Ship authenticated access" \
  --outcome "Users can sign in and reach protected resources" \
  --criterion "Authentication tests pass" \
  --constraint "Do not use an external identity provider" \
  --agents auto
```

Open the read-only workbench:

```bash
repoframe view
```

Enable the typed Commit, Push, mode-switch, and Intervention operations:

```bash
repoframe interact
repoframe interact --port 7331
repoframe interact --no-open
```

Both services bind only to `127.0.0.1`. `view` rejects every write method. `interact` enables only a small authenticated intent API; it is not a shell endpoint or a web chat.

## Unified workbench

The browser has one full-screen Goal canvas.

### Iteration

Iteration appears as a floating card over a frozen, de-emphasized Long Run graph. It does not create or update execution state. The card shows a compact Git change count and, in interactive mode, provides:

- **Commit**
- **Commit & Push**
- **Close**, which returns to Long Run

Commit is a two-step operation:

1. A short-lived, read-only Agent inspects the repository and proposes a subject and optional body.
2. The page shows every changed path. After confirmation, RepoFrame verifies that the working tree did not change, runs `git add -A`, and commits.

All tracked, deleted, renamed, staged, unstaged, and untracked changes are included. The Agent never runs Git mutations. Commit & Push performs an ordinary `git push` after the commit; it never configures an upstream, remote, credential, proxy, or force push. A failed push preserves the local commit.

### Long Run

Long Run renders the execution DAG vertically. Dependencies flow from top to bottom, parallel nodes share a row, and the active node has a moving outer ring. Drag an empty canvas area to pan, and use the mouse wheel to zoom around the pointer.

Graphs larger than 40 nodes default to **Focus** view, which keeps active, unfinished, blocked, nearby, and unresolved-intervention context. **Full graph** renders every node.

The Execution Path selector switches between:

- the current, writable `.repoframe/state.json`;
- optional, read-only snapshots in `.repoframe/goals/*.json`.

Each Goal retains an independent `/long-run/<goal-id>` URL. RepoFrame does not provide Goal assignment, deadlines, priority queues, percentage forecasts, or automatic Goal lifecycle commands.

## Repository-local mode

The current mode is stored in local Git configuration:

```bash
git config --local repoframe.mode iteration
git config --local repoframe.mode long-run
```

This survives server restarts without dirtying the working tree or entering a Commit. If unset, RepoFrame selects Long Run when `.repoframe/state.json` exists and Iteration otherwise.

The operation provider is also repository-local and defaults to Codex:

```bash
git config --local repoframe.agent-provider codex
```

Provider abstraction exists for future integrations. Version 0.3 returns an explicit unsupported diagnostic for Claude or Gemini instead of accepting arbitrary command templates.

## State protocol

New Long Run states use Schema v2:

```json
{
  "$schema": "./state.schema.json",
  "schema_version": 2,
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
  "interventions": [],
  "updated_at": "2026-09-03T08:00:00Z"
}
```

Node states are `pending`, `active`, `done`, `blocked`, and `skipped`. The graph must be acyclic, references must exist, at most one node may be active, and active dependencies must be done or skipped.

Validate the current state:

```bash
repoframe validate
repoframe validate --json
```

### v1 compatibility

RepoFrame continues to read and validate Schema v1 snapshots. Viewing, validating, or changing UI mode does not rewrite them. A current v1 state is upgraded atomically to v2 only when its first user intervention is created. Historical snapshots may remain v1 indefinitely.

## User interventions

Select a node in the current Long Run Goal and choose **Add intervention**. The original user text is stored as an immutable intervention node connected to its target by a dashed edge.

Intervention states are:

- `open`
- `resolving`
- `incorporated`
- `needs_user`

The Codex operation provider may:

1. produce a Graph Patch directly;
2. launch at most two independent, read-only analysis workers;
3. request more user input.

Workers cannot write code, Git, or state. The coordinator returns a constrained Graph Patch. RepoFrame applies it to an in-memory copy, runs full protocol and DAG validation, allows one repair attempt, and atomically replaces the state only when valid.

Graph Patch may add nodes or update unfinished nodes. It cannot delete nodes, change IDs, modify the user's original intervention, or rewrite done/skipped history. Objections to completed work produce corrective successor nodes instead.

Submitting the intervention authorizes automatic application of a valid patch. It does not authorize code changes; the normal Long Run Agent later executes the revised route.

## Operation Agent boundary

Codex operations use:

- `codex exec --ephemeral`;
- a read-only sandbox;
- no approval prompts;
- an explicit JSON output Schema;
- stdin for Prompt input;
- temporary output files that are removed after the call.

RepoFrame does not take over the user's normal Codex, Claude Code, Gemini CLI, Cursor, or Copilot conversation. Its busy state covers only processes started by the current RepoFrame interactive service. External Agent sessions remain the user's responsibility.

## Agent instruction adapters

`repoframe init --agents` updates small managed blocks in instruction files already recognized by supported products:

| Selection | Instruction file |
| --- | --- |
| `codex` | `AGENTS.md` |
| `cursor` | `AGENTS.md` |
| `claude` | `CLAUDE.md` |
| `gemini` | `GEMINI.md` |
| `copilot` | `.github/copilot-instructions.md` |

Values are `auto`, `all`, `none`, or a comma-separated selection. Content outside RepoFrame markers is preserved. Adapters direct every Agent to the same mode contract; they do not install plugins, skills, hooks, or orchestration systems.

## Local API

Read endpoints:

| Endpoint | Purpose |
| --- | --- |
| `GET /api/v1/iteration` | Git working-tree facts |
| `GET /api/v1/goals` | Goal summaries and snapshot diagnostics |
| `GET /api/v1/goals/<goal-id>` | One validated Goal |
| `GET /api/v1/state` | Current state |
| `GET /api/v1/runtime` | Mode, provider, capability, and active-operation status |
| `GET /api/v1/operations/<id>` | One operation result |
| `GET /healthz` | Process health |

Interactive-only writes:

| Endpoint | Purpose |
| --- | --- |
| `POST /api/v1/mode` | Switch Iteration or Long Run |
| `POST /api/v1/operations` | Start one typed operation |
| `POST /api/v1/operations/<id>/cancel` | Cancel the current operation |

Interactive writes require a per-process random token plus exact Origin and Host checks. There is no CORS permission, generic Prompt endpoint, arbitrary JSON Patch, arbitrary state write, or arbitrary command route.

## Non-goals

RepoFrame is not:

- a task manager or general Agent orchestrator;
- a web chat or replacement for an Agent's own UI;
- a concurrent multi-writer system;
- a recorder of private reasoning, chat history, or every edit;
- a cloud service, editor extension, plugin, skill, SDK, or MCP server;
- a replacement for source code, tests, Git, or durable project documentation.

## Development

```bash
python -m unittest discover -s tests -v
python -m compileall -q src tests
python -m pip install .
repoframe --help
```

The disposable manual-acceptance project belongs in `_test/`, which is ignored by Git. Automated tests do not require Node.js or a real browser.

## Legacy

The former `repo-init` Codex skill is archived and unmaintained:

- branch: `codex/legacy-repo-init-skill`
- tag: `repo-init-skill-v1-final`

## License

RepoFrame is available under the MIT License.
