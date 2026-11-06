# Changelog

All notable changes to this project are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2026-11-07

### Added
- `maintainer-triage` skill: classifies open issues, confirms duplicates, drafts labels and replies.
- `maintainer-good-first-issue` skill: finds well-scoped starter tasks and writes newcomer-ready issues.
- `maintainer-release-notes` skill: Keep a Changelog entry, release notes, contributor credits, semver bump.
- `maintainer-pr-welcome` skill: kind, specific reviews for first-time contributors.
- `maintainer-license-check` skill: dependency license compatibility triage (not legal advice).
- `maintainer-community-files` skill: CONTRIBUTING, SECURITY, issue forms, PR template, CODEOWNERS, code of conduct link.
- `maintainer-health` skill: scored repo health checklist with fixes ordered by impact.
- `maintainer-weekly` skill: weekly digest of waiting PRs, unanswered issues, stale items and newcomers to thank.
- Agents: `triage-captain`, `release-manager`, `newcomer-buddy`.
- Helper scripts `dupes.py`, `changelog.py`, `license_compat.py`, `health.py` with unit tests.

[Unreleased]: https://github.com/vivekbhange-hub/maintainer-skill/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/vivekbhange-hub/maintainer-skill/releases/tag/v1.0.0
