---
name: maintainer-health
description: >-
  Audits an open-source repository's health and scores it out of 100: README sections, LICENSE,
  CONTRIBUTING, SECURITY, code of conduct, CI, tests, issue and PR templates, changelog,
  .gitignore and CODEOWNERS, plus live signals from GitHub such as response time and stale PRs.
  Outputs a scored checklist with the fixes ordered by impact. Use when the user says "how
  healthy is my repo", "audit my repo", "is my project ready for contributors", "repo checklist",
  "what is my repo missing", or "score my open source project".
argument-hint: "[path or owner/repo]"
---

# Repo health audit

A quick, honest checkup: what a newcomer, a security researcher, or a company evaluating the
dependency will look for, and what is missing. The file checks are scored by a deterministic
script so the number means the same thing every time; the GitHub activity checks add context
the files cannot show.

## Steps

1. **Locate the repo.** Use the path argument or the current directory. If the user gives
   `owner/repo` and it is not cloned, ask before cloning; shallow-clone into a temp directory
   (`gh repo clone owner/repo <tmp> -- --depth 1`) and say where it went.

2. **Score the files.**
   ```
   python3 "${CLAUDE_SKILL_DIR}/health.py" <path> -o maintainer/health.md
   python3 "${CLAUDE_SKILL_DIR}/health.py" <path> --format json
   ```
   Points (100 total): README exists with substance 10, README sections (install 5, usage 5,
   contributing 2, license 3), LICENSE 15, CONTRIBUTING 8, SECURITY 8, CI 10, tests 10,
   changelog 6, issue templates 5, PR template 4, code of conduct 4, CODEOWNERS 3, .gitignore 2.
   Grades: A 90+, B 75+, C 60+, D 40+, F below. Files are found case-insensitively in the
   root, `.github/` and `docs/`. `--min-score N` exits 1 below N, useful in CI.

3. **Check quality, not just presence.** The script only knows a file exists. Read the ones it
   found and note real problems in a "Quality notes" section:
   - README install command that does not match the package name or manifest.
   - CONTRIBUTING test command that differs from what CI runs.
   - LICENSE that is a placeholder ("Copyright (c) [year] [fullname]") or disagrees with the manifest license field.
   - SECURITY.md with no private reporting channel.
   - CI that never runs the tests (only lint), or that is disabled.
   - Issue templates that are Markdown when the repo would benefit from forms.

4. **Add GitHub activity signals** (if `gh` is available and the repo is on GitHub). Compute,
   do not guess:
   ```
   gh issue list --state open --limit 200 --json number,createdAt,updatedAt,comments,author
   gh pr list --state open --limit 100 --json number,createdAt,updatedAt,isDraft,reviewDecision,author
   gh release list --limit 5
   gh api repos/{owner}/{repo} --jq '{archived,has_discussions,default_branch,pushed_at}'
   ```
   Report: open issues with zero comments older than 14 days, PRs waiting more than 14 days
   for a first review, date of the last release, last push. These are not scored; they appear
   under "Activity" with the counts and the five oldest items.

5. **Write the report.** Keep the script output (score, checklist, fixes ordered by points
   gained) and append "Quality notes" and "Activity". In chat, print the score, grade, and the
   top three fixes with the points each would add, for example:
   ```
   Score 62/100 (C)
   1. Add LICENSE (+15) - without it nobody may legally reuse the code
   2. Add CI running tests on PRs (+10)
   3. Add SECURITY.md (+8)
   ```

6. **Offer the next step**, matched to the gaps:
   - Missing CONTRIBUTING/SECURITY/templates/CODEOWNERS/code of conduct -> `maintainer-community-files`.
   - Missing CHANGELOG -> `maintainer-release-notes` can create one from history.
   - Many untouched issues -> `maintainer-triage`.
   - Stale PRs -> `maintainer-weekly` for a recurring digest.
   - Missing LICENSE -> help pick one with the user (link https://choosealicense.com); never pick for them.
   - No CI -> offer to draft a minimal workflow that runs the existing test command; show it before writing.

## Decision rules

- Score what is there today. Do not round up because something is "in progress".
- A monorepo: run the script at the root, and mention packages that have their own README or LICENSE.
- An archived repo: say so first; most fixes do not apply.
- If the score is already 90+, say so plainly and focus on the quality notes.

## What NOT to do

- Do not create or edit files during the audit. Fixes happen in the hand-off skills, after confirmation.
- Do not report activity numbers you did not compute from gh output.
- Do not compare the repo with other projects or invent benchmarks ("top 10% of repos").
- Do not treat the score as a judgement of the code itself; it measures community readiness.

## Hand-off

Fixes flow to `maintainer-community-files`, `maintainer-release-notes`, and `maintainer-triage`.
Re-run this skill afterwards to show the new score.
