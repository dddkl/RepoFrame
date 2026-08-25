# Security Policy

## Supported versions

RepoFrame is currently maintained from the latest default branch. The archived `repo-init` skill is unsupported.

## Local viewer security

The RepoFrame viewer is designed for local development:

- it binds only to `127.0.0.1`;
- it exposes a read-only, validated state endpoint;
- it serves only packaged, whitelisted browser assets;
- it rejects state-changing HTTP methods;
- it does not execute commands or connect to an agent.

`.repoframe/state.json` can still contain sensitive project names, constraints, paths, or evidence. Do not expose the viewer through a reverse proxy, tunnel, port-forward, or public network. Treat the state file according to the repository's own confidentiality requirements.

## Reporting a vulnerability

Use GitHub private vulnerability reporting when available. If it is unavailable, open a minimal public issue requesting a private contact path without including exploit details.

Include the affected version, impact, reproduction conditions, and any known mitigation. RepoFrame does not currently operate a bug bounty program.
