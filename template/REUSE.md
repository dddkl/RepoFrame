# REUSE.md

This file defines the open-source reuse gate for technical planning.

## Purpose

Before designing or building a non-trivial technical capability, look for high-quality open-source projects that can be reused, adapted, or studied.

The goal is to avoid unnecessary custom implementation while keeping licensing, maintenance, security, and integration risk visible.

## When Required

Run this check before proposing a technical approach when the task involves:

- a complex feature or subsystem
- a framework, library, or platform choice
- a third-party integration
- infrastructure, auth, payments, search, AI, analytics, queues, scheduling, observability, editors, charts, or workflow engines
- work that is likely to take more than half a day to implement from scratch

If a task is small, project-specific, or mostly content/configuration work, mark the check as not required and explain why.

## Search Targets

Prefer authoritative and auditable sources:

- GitHub repositories
- official documentation
- package registries for the project stack
- trusted ecosystem lists such as curated awesome lists
- open-source implementations from credible teams or comparable products

## Evaluation Criteria

For each candidate, evaluate:

- functional fit
- license compatibility
- maintenance activity
- release recency
- issue and pull request health
- documentation quality
- test and CI signals
- security posture
- integration cost
- adaptation cost
- long-term ownership risk

## Decision Options

Choose one:

- `Direct Use`: use the project as a dependency.
- `Adapt`: fork, wrap, or selectively modify the project.
- `Learn From`: do not depend on it, but use it as a design reference.
- `Build In-House`: implement locally after explaining why existing options do not fit.

## Required Output

Record the reuse check in the relevant task file before implementation starts.

| Candidate | Link | License | Maintained | Fit | Risk | Decision |
|---|---|---|---|---|---|---|
| `<name>` | `<url>` | `<license>` | `<yes/no/unclear>` | `<high/medium/low>` | `<main risk>` | `<decision>` |

## Build In-House Rule

If the decision is `Build In-House`, record:

- why existing projects are not suitable
- the smallest local implementation scope
- whether the local implementation should remain replaceable
- who owns future maintenance risk

## Agent Rules

- Do not propose a from-scratch implementation for reusable technical capabilities before running this check.
- Prefer reuse or adaptation when the candidate is maintained, license-compatible, and cheaper to integrate than to rebuild.
- Prefer a small local implementation when candidates are unmaintained, license-incompatible, overbuilt, insecure, or more expensive to integrate than to build.
- Add any accepted durable reuse decision to `DECISIONS.md`.
