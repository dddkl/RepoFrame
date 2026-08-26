# Security Policy

## Supported versions

RepoFrame is maintained from the latest default branch. The archived `repo-init` skill is unsupported.

## Local viewer security

RepoFrame is designed for local development:

- the server binds only to `127.0.0.1`;
- browser routes and assets are explicitly allowlisted;
- all API endpoints are read-only;
- state-changing HTTP methods are rejected;
- no endpoint executes arbitrary shell input or controls an Agent;
- no browser asset connects to an external service.

Iteration invokes a fixed set of read-only Git commands to inspect status, diff statistics, branch, and commit history. Repository paths, branch names, commit subjects, author names, and working-file names are therefore visible to anyone who can access the local Viewer.

Long Run snapshots can additionally contain project names, outcomes, constraints, summaries, file paths, test commands, or commit evidence. Invalid archived snapshots are reported but never executed.

Do not expose RepoFrame through a reverse proxy, tunnel, port forward, container host mapping, or public network. Treat Viewer data according to the repository's confidentiality requirements.

## Reporting a vulnerability

Use GitHub private vulnerability reporting when available. If unavailable, open a minimal public issue requesting a private contact path without including exploit details.

Include the affected version, mode, impact, reproduction conditions, and known mitigation. RepoFrame does not currently operate a bug bounty program.
