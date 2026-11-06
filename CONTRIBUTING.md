# Contributing to maintainer-skill

Thanks for helping make open-source maintenance less of a grind. This pack is plain Markdown
plus a few standard-library Python scripts, so you can contribute without installing anything
beyond Python 3.9+.

## Ways to help

- **Report a bug.** Tell us which skill or script, what you asked, what happened, and what you expected.
  For scripts, include the exact command and a trimmed input sample (remove anything private).
- **Improve a skill.** If Claude did something unhelpful while following a SKILL.md, the fix is usually
  a clearer step, a decision rule, or a new item under "What NOT to do".
- **Extend a helper.** New license aliases, commit-message patterns, health checks, or CI providers are welcome.
- **Share a real-world case** where the triage, duplicate detection, or changelog grouping got it wrong.
  These make the best test cases.

## Layout

```
.claude-plugin/        marketplace.json and plugin.json
skills/<name>/         SKILL.md plus optional helper script
agents/                subagent definitions
tests/                 unittest suite (stdlib only)
```

## Development

```
git clone https://github.com/vivekbhange-hub/maintainer-skill
cd maintainer-skill
python -m unittest discover -s tests -v
```

The tests must pass on Windows and Linux. Use `pathlib`, open files with `encoding="utf-8"`, and do not
depend on line endings.

## Rules for changes

1. **Skills**: the frontmatter `name` must equal the folder name (`maintainer-<something>`). The
   `description` says what the skill does, then "Use when the user says ..." with realistic phrases,
   in under about 900 characters. Keep the body between 60 and 200 lines with numbered steps, concrete
   output paths, decision rules, a "What NOT to do" section, and a hand-off to the next skill.
2. **Anything that writes to GitHub** (labels, comments, reviews, issues, releases, tags, pushes) must be
   drafted first and run only after the user confirms. PRs that remove a confirmation step will not be merged.
3. **Helper scripts**: Python 3.9+, standard library only, no network calls, deterministic output,
   `argparse` with `--help`. Every script needs `tests/test_<script>.py`; load scripts with `tests/_load.py`.
4. **Agents**: least-privilege `tools`. Review-only agents do not get Write or Edit.
5. **Writing**: plain, direct English. No filler words, no emoji, no claims you cannot back up. Link
   third-party documents (such as the Contributor Covenant) instead of pasting them.
6. Add a line to `CHANGELOG.md` under `## [Unreleased]`.

## Pull requests

Keep PRs focused on one change. Describe what you changed and how you tested it (the test command output,
or the prompt you used in Claude Code and what came back). First-time contributors are very welcome. If
something in this guide is unclear, that is a bug: open an issue.

## Code of conduct

This project follows the [Contributor Covenant, version 2.1](https://www.contributor-covenant.org/version/2/1/code_of_conduct/).
Be kind, assume good intent, and keep discussion about the work.
