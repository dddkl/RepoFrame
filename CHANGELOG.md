# Changelog

All notable changes to this repository should be recorded here.

This file is intentionally lightweight. It tracks repository-level changes that matter to users, contributors, or maintainers.

## [Unreleased]

### Added

- contribution guidance for local development, validation, and PR expectations
- a security policy for coordinated vulnerability reporting
- GitHub issue templates and a pull request template
- a minimal CI workflow that runs syntax and smoke validation
- a standard-library smoke validation script for the initialization flow

### Changed

- `initialize_repo.py` was split into thinner orchestration plus focused helper modules under `repo-init/scripts/`
