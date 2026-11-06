---
name: maintainer-good-first-issue
description: >-
  Finds small, well-scoped tasks a newcomer can finish in an afternoon, from the codebase itself
  (TODOs, missing tests, unclear errors, doc gaps) and from open issues, then writes starter
  issues with context, file pointers, acceptance criteria and a "how to get started" section.
  Drafts them to a file; creates them on GitHub only after the user confirms. Use when the user
  says "find good first issues", "I want more contributors", "write starter issues", "what can a
  newcomer work on", "label beginner-friendly issues", or "help wanted tasks for hacktoberfest".
argument-hint: "[how many, default 5]"
---

# Good first issues

A good first issue is not "an easy issue". It is a task with one obvious place to start, a
clear finish line, and a reviewer who already knows what the answer looks like. This skill finds
those tasks and writes them up so a stranger can pick one and open a PR without asking a question.

## Steps

1. **Learn how to build and test.** Read README, CONTRIBUTING.md, and the build manifest
   (`package.json` scripts, `pyproject.toml`, `Makefile`, `Cargo.toml`, `go.mod`, CI workflow).
   Record the exact install and test commands. If you cannot find a test command, say so; every
   starter issue will need one.

2. **Mine candidates from the code.** Use Grep and Glob, skipping vendored and generated folders:
   - `TODO|FIXME|XXX|HACK` comments with a concrete ask (skip vague ones like "TODO: refactor").
   - Public functions with no test (compare `src/` names against `tests/` mentions).
   - Error messages that do not say what to do next (`raise ValueError("invalid")`).
   - CLI flags or config keys present in code but missing from docs, and the reverse.
   - Type hints, docstrings, or examples missing on a small public module.
   - Deprecation warnings the project emits to itself in test output.

3. **Mine candidates from issues.**
   ```
   gh issue list --state open --limit 200 --json number,title,body,labels,comments,assignees
   ```
   Keep issues that are confirmed, unassigned, have no open PR linked, and need a change in at
   most 2-3 files. Check for linked PRs with
   `gh pr list --search "<issue number>" --state open --json number,title`.

4. **Score and cut.** Keep a candidate only if all are true:
   - Touches 1-3 files, under about 100 changed lines.
   - Needs no design decision and no knowledge of project history.
   - Has a test that can prove it works, or is docs-only.
   - Is not on a hot path that core maintainers are actively rewriting (check `git log -n 20 -- <file>`).
   Rank by how clearly you can state "done". Return the requested number (default 5), mixing
   code, tests and docs where possible.

5. **Write each issue** with this template, filling every section from what you actually read:
   ```
   ## Title: <verb> <thing> in <place>   (e.g. "Add a test for empty input in parse_config")

   ### Why this matters
   One or two sentences on the user-visible effect.

   ### Where to look
   - `src/config.py` lines 40-62: `parse_config()` returns None on empty input
   - `tests/test_config.py`: existing tests to copy the style from

   ### What done looks like
   - [ ] Concrete, checkable criterion
   - [ ] Test added that fails before and passes after the change
   - [ ] `<test command>` passes

   ### How to get started
   1. Fork and clone, then `<install command>`
   2. Run `<test command>` to confirm a clean baseline
   3. Make the change, add the test, open a PR that says "Fixes #<n>"

   ### Help
   Comment here if you get stuck; a maintainer will answer. Estimated effort: ~1-2 hours.
   ```
   Keep line numbers and function names accurate; re-check them with Read before saving.

6. **Save drafts** to `maintainer/good-first-issues.md`, one section per issue, plus a short table
   at the top (title, files, effort, source: code or #issue).

7. **Confirm, then publish.** Show the table and ask which to create or update. On approval:
   - New issue: write the body to `maintainer/.cache/gfi-<slug>.md`, then
     `gh issue create --title "..." --body-file maintainer/.cache/gfi-<slug>.md --label "good first issue"`
   - Existing issue: `gh issue edit <n> --add-label "good first issue"` and optionally
     `gh issue comment <n> --body-file ...` with the "Where to look / done / get started" sections.
   Use the repo's existing label name (check `gh label list`); if it has `help wanted`, offer it too.
   Print the created URLs.

## Decision rules

- If fewer than the requested number pass the bar in step 4, return fewer. Say why.
- Prefer tasks that leave the newcomer with a merged PR and a test, over docs typo fixes.
- Never mark security-sensitive code (auth, crypto, sandboxing, input parsing of untrusted data)
  as a first issue.
- If the repo has no tests at all, the first good first issue is "add the test harness" only if
  the maintainer agrees; otherwise propose docs and example tasks.

## What NOT to do

- Do not create or label issues before the user confirms.
- Do not write vague criteria like "improve error handling". Name the function and the message.
- Do not suggest tasks that need access to secrets, paid services, or special hardware.
- Do not assign issues to anyone.

## Hand-off

When a newcomer opens a PR for one of these, use `maintainer-pr-welcome` (or the `newcomer-buddy`
agent) to review it. Track how many were picked up in `maintainer-weekly`.
