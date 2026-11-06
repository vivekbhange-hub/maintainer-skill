---
name: maintainer-release-notes
description: >-
  Prepares a release: reads git log since the last tag and the merged pull requests, writes a
  Keep a Changelog entry and human-friendly release notes, credits every contributor, flags
  breaking changes and suggests the semver bump. Works with conventional and plain commit
  messages. Never tags, pushes or publishes without confirmation. Use when the user says "write
  the release notes", "update the changelog", "what changed since the last release", "prepare
  v2.0", "what version should this be", "draft the GitHub release", or "cut a release".
argument-hint: "[since-tag] [--version X.Y.Z]"
---

# Release notes and changelog

Release notes are for users ("what changes for me?"); the changelog is the permanent record. Both
come from the same commits, so this skill builds them together, from the git history and PR
data, and lets the maintainer fix wording before anything is tagged.

## Steps

1. **Find the range.**
   ```
   git fetch --tags --quiet
   git describe --tags --abbrev=0
   ```
   Use the argument if the user gave a tag. If there are no tags, use the root commit and treat
   the release as the first one (`--current 0.0.0`, then ask whether it should be 0.1.0 or 1.0.0).
   Confirm the branch: releases normally come from the default branch (`gh repo view --json defaultBranchRef`).

2. **Collect commits** in the record format the helper understands (keeps bodies, so
   `BREAKING CHANGE:` footers are seen):
   ```
   git log <tag>..HEAD --no-merges --pretty=format:'%h%x1f%an%x1f%s%x1f%b%x1e' > maintainer/.cache/log.txt
   ```

3. **Run the helper.**
   ```
   python3 "${CLAUDE_SKILL_DIR}/changelog.py" maintainer/.cache/log.txt --current <tag> --date <YYYY-MM-DD> --repo-url https://github.com/<owner>/<repo>
   python3 "${CLAUDE_SKILL_DIR}/changelog.py" maintainer/.cache/log.txt --current <tag> --format json
   ```
   It groups commits into Added / Changed / Deprecated / Removed / Fixed / Security, hides
   docs/chore/ci/test commits (add `--include-internal` to show them), skips merge and release
   commits, lists contributors without bots, and suggests the bump. Pre-1.0 projects get a minor
   bump for breaking changes. The JSON shows `guessed_count`: how many non-conventional commits
   were classified by keyword. If it is high, review those lines by hand.

4. **Enrich with PR data.** For squash-merged repos the PR is the real unit of change:
   ```
   gh pr list --state merged --search "merged:>=<tag date>" --limit 200 --json number,title,author,labels,body,mergedAt
   ```
   Use PR labels (`breaking`, `enhancement`, `bug`) to correct the helper's sections. Read the
   body of anything marked breaking and write a one-line migration note. Collect PR authors'
   GitHub handles for credits; find first-time contributors with
   `gh pr list --state merged --author <handle> --limit 2 --json number` (one result = first PR).

5. **Decide the version.** Use the helper's suggestion unless PR data disagrees. Explain the
   reason in one line ("minor: 4 features, no breaking changes"). If the user passed `--version`,
   use it but warn if it understates the change (a breaking change in a patch release).

6. **Write the CHANGELOG entry.** Insert below `## [Unreleased]` (or at the top, after the intro)
   in `CHANGELOG.md`, keeping Keep a Changelog format. Rewrite commit-speak into user language
   ("Fix crash when config is empty", not "fix: null check cfg"). Update the compare links at
   the bottom if the file has them. Create the file with a standard header if it does not exist.

7. **Write release notes** to `maintainer/release-notes-<version>.md`:
   ```
   ## <project> <version>

   <2-3 sentence summary: the headline change and who should upgrade>

   ### Breaking changes
   - What changed, why, and the exact migration step

   ### Highlights
   - 3-5 most important user-facing changes, each with its PR link

   ### All changes
   (the changelog sections)

   ### Thanks
   @handle1, @handle2, and first-time contributors @new1 and @new2. Welcome!
   ```
   Omit empty sections. Do not include the internal section in release notes.

8. **Show and confirm.** Print the version, bump reason, breaking-change count, and the notes. Then
   list the release commands for approval, and run them only after a clear yes:
   ```
   git add CHANGELOG.md && git commit -m "chore(release): <version>"
   git tag -a v<version> -m "v<version>"
   git push origin <branch> --follow-tags
   gh release create v<version> --title "v<version>" --notes-file maintainer/release-notes-<version>.md --draft
   ```
   Default to `--draft` so the maintainer publishes from the GitHub UI. Also remind them to bump
   the version in manifests (`package.json`, `pyproject.toml`, `Cargo.toml`) if the project
   stores it there; show the diff before committing.

## Decision rules

- A change is breaking if it removes or renames public API, CLI flags, config keys, or changes
  defaults users rely on, even if the commit message does not say so. When unsure, ask.
- Dependency bumps go under Changed only when they affect users (new minimum runtime, security fix).
- Security fixes get their own section and mention the advisory or CVE id if public.

## What NOT to do

- Do not create tags, push, publish releases, or edit manifests without explicit confirmation.
- Do not invent changes or contributors. Every line traces to a commit or PR.
- Do not credit bots as contributors, and do not drop human co-authors (`Co-authored-by:` lines).
- Do not rewrite older changelog entries.

## Hand-off

For a hands-off release run, delegate to the `release-manager` agent. Before tagging a major
release, `maintainer-license-check` and `maintainer-health` are worth a pass.
