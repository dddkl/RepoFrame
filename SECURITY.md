# Security Policy

## Supported versions

RepoFrame is maintained from the latest default branch. The archived `repo-init` skill is unsupported.

## Local service

RepoFrame is a local development tool:

- both services bind only to `127.0.0.1`;
- browser routes and assets are allowlisted;
- `repoframe view` rejects all state-changing HTTP methods;
- `repoframe interact` accepts only mode, Commit, Push, cancel, and Intervention intents;
- interactive writes require a random per-process token and exact Origin/Host checks;
- no endpoint accepts an arbitrary shell command, executable template, Prompt, file path, JSON Patch, or state document;
- browser assets make no external network requests.

Do not expose RepoFrame through a reverse proxy, tunnel, port forward, container host mapping, or public network.

## Repository and state data

The Viewer exposes local Git branch names, commit subjects, author names, paths, change statistics, Goal outcomes, constraints, summaries, evidence, and user interventions to the local browser. Treat the service according to the repository's confidentiality requirements.

The session token is injected into the locally served page. It is not stored on disk or logged. Requests from another Origin are rejected even if they guess an endpoint.

## Git mutations

Commit confirmation runs `git add -A`, so every tracked and untracked working-tree change is included. Review the displayed file list before confirming, especially for secrets and generated files.

RepoFrame:

- verifies that the working tree still matches the proposal;
- does not reset or check out files;
- does not roll back a failed hook by overwriting the index;
- uses ordinary `git push`;
- never force-pushes;
- never creates or changes remotes, upstreams, credentials, or proxy configuration;
- preserves a local Commit when Push fails.

## Operation Agent

The Codex provider runs an ephemeral, read-only, Schema-constrained `codex exec` process. It may inspect the repository and Git but cannot write through its sandbox. RepoFrame applies state changes and Git commands separately.

At most one operation is active. Intervention analysis may use at most two read-only workers. Their output is transient and is not exposed as private reasoning.

RepoFrame cannot detect unrelated Agent processes started in a terminal, editor, or another service. Users must avoid external concurrent writes when using interactive operations.

## Reporting a vulnerability

Use GitHub private vulnerability reporting when available. Otherwise open a minimal public issue requesting a private contact path without exploit details.

Include the affected version, mode, impact, reproduction conditions, and known mitigation. RepoFrame does not currently operate a bug bounty program.
