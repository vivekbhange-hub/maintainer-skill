---
name: maintainer-community-files
description: >-
  Writes the community files a repo is missing, tailored to the actual project: CONTRIBUTING.md
  with the real build and test commands, SECURITY.md, GitHub issue forms (bug report, feature
  request, config), a pull request template, a CODEOWNERS suggestion from git history, and a code
  of conduct that links the Contributor Covenant instead of pasting it. Shows every file before
  writing. Use when the user says "add a CONTRIBUTING guide", "set up issue templates", "write a
  security policy", "add a PR template", "make my repo contributor-friendly", or "community files".
argument-hint: "[which files, default: all missing]"
---

# Community files

Generic templates get ignored because they describe some other project. These files work when
they contain this repo's real commands, real folder names, and real people. This skill reads
the repo first and writes only what is missing (or improves what is thin), so a newcomer can go
from clone to passing tests by following CONTRIBUTING.md word for word.

## Steps

1. **Inventory what exists.** Check the root, `.github/`, and `docs/` for: CONTRIBUTING, SECURITY,
   CODE_OF_CONDUCT, SUPPORT, `.github/ISSUE_TEMPLATE/`, `pull_request_template.md`, CODEOWNERS,
   FUNDING.yml. If `maintainer-health` ran, reuse its report. Never overwrite an existing file
   without asking; offer a diff with proposed additions instead.

2. **Extract the real facts.** Read, do not assume:
   - Language and tooling: `package.json` (scripts, packageManager, engines), `pyproject.toml`
     (build backend, tool sections), `Cargo.toml`, `go.mod`, `Makefile`, `justfile`, `tox.ini`, `noxfile.py`.
   - Install, test, lint, format, and build commands, preferring what CI runs
     (`.github/workflows/*.yml` steps). If README and CI disagree, trust CI and note the drift.
   - Supported runtime versions (CI matrix, `engines`, `requires-python`, `rust-version`).
   - Commit style: `git log -n 50 --pretty=%s` (conventional commits or not).
   - Default branch: `gh repo view --json defaultBranchRef,hasDiscussionsEnabled,securityPolicyUrl,isPrivate`.
   - Maintainers: top committers per directory, `git shortlog -sne --since="1 year ago" -- <dir>`.
   Ask the user only for what cannot be found: the security contact email, and whether they use
   GitHub private vulnerability reporting.

3. **Draft CONTRIBUTING.md** with these sections, filled with the facts from step 2:
   - Ways to help (issues, docs, code, triage) and where questions go (Discussions if enabled).
   - Development setup: exact prerequisites with versions, clone, install command.
   - Running tests, lint and format, copied from CI so they pass locally the same way.
   - Making a change: branch naming if any, commit style actually in use, keeping PRs small,
     linking issues with "Fixes #n", updating CHANGELOG if the repo keeps one.
   - What review looks like and how long it usually takes (ask; do not invent an SLA).
   - Link to the code of conduct and license.
   Keep it under about 150 lines. Commands go in code blocks that can be pasted as-is.

4. **Draft SECURITY.md**: supported versions table (derived from tags/releases, confirmed with the
   user), how to report privately (GitHub private vulnerability reporting link
   `https://github.com/<owner>/<repo>/security/advisories/new` and/or the email they give), what
   to include, expected response time only if the user states one, and a request not to open
   public issues for vulnerabilities.

5. **Draft issue forms** in `.github/ISSUE_TEMPLATE/` as YAML forms:
   - `bug_report.yml`: name, description, labels (existing label names from `gh label list`),
     body with `textarea` fields for what happened / expected / steps (with `render` off) and
     `input` or `dropdown` fields for version and OS; mark the essential ones `validations: required: true`.
   - `feature_request.yml`: problem, proposed solution, alternatives considered.
   - `config.yml`: `blank_issues_enabled: false` only if the user wants it, plus `contact_links`
     to Discussions, docs, and the security policy.
   Version dropdown options come from recent tags (`git tag --sort=-v:refname | head -5`).

6. **Draft the PR template** at `.github/pull_request_template.md`: summary, linked issue, a
   checklist with the repo's real test and lint commands, docs/changelog updated, and a
   screenshots line only if the project has UI.

7. **Suggest CODEOWNERS** at `.github/CODEOWNERS`: map top-level directories to the people who
   actually maintain them (from step 2), using GitHub handles. Only include people the user
   confirms; it requests their review automatically, so wrong entries annoy people.

8. **Code of conduct.** Do not paste a code of conduct. Write a short CODE_OF_CONDUCT.md that
   states the project adopts the Contributor Covenant version 2.1, links
   https://www.contributor-covenant.org/version/2/1/code_of_conduct/, and names the enforcement
   contact the user provides. Tell the user that GitHub's "Add file > Create new file" with the
   name CODE_OF_CONDUCT.md offers the full official text if they prefer it inline.

9. **Review and write.** Show a list of files with a one-line purpose each, then the full
   content of each. Write only the approved files. Validate YAML structure by reading it back
   (top-level `name`, `description`, `body` list for forms). Suggest committing on a branch:
   `git checkout -b docs/community-files`; do not commit or push unless asked.

## Decision rules

- Prefer `.github/` for CONTRIBUTING, SECURITY and templates unless the repo keeps docs at root.
- Match the repo's voice and language (British or American spelling, formal or casual).
- If the project is tiny or solo, keep CONTRIBUTING short; say "I'm a solo maintainer, reviews may take a week" if the user agrees.
- Use the repo's real label names in issue forms; propose new ones separately.

## What NOT to do

- Do not invent commands, versions, emails, response times, or maintainers.
- Do not paste the Contributor Covenant or other third-party documents; link them.
- Do not overwrite existing files, commit, push, or create labels without confirmation.
- Do not add FUNDING.yml or sponsor links unless the user asks.

## Hand-off

Re-run `maintainer-health` to see the score change. Once templates exist, `maintainer-triage`
gets better issues to work with.
