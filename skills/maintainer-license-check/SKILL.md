---
name: maintainer-license-check
description: >-
  Checks whether your dependencies' licenses fit your project's license. Reads package.json,
  package-lock.json, requirements files, pyproject.toml, Cargo.toml and go.mod, fills gaps with
  local license tools, and flags conflicts (for example a GPL dependency in an MIT project),
  unknown licenses and copyleft conditions. A first-pass triage, clearly not legal advice. Use
  when the user says "check my dependency licenses", "is this GPL library OK to use", "license
  audit", "can I add this package", "are we license compliant", or "what licenses do we ship".
argument-hint: "[path] [--project-license SPDX]"
---

# Dependency license check

Most license trouble in open source is boring and avoidable: a strong-copyleft package pulled
into a permissive project, a dependency with no license at all, or a "source-available" package
that is not open source. This skill finds those early, explains each flag in one line, and
says what the usual options are. It does not give legal advice and says so in every report.

## Steps

1. **Identify the project license.** Look at `LICENSE*`/`COPYING`, then the `license` field in
   `package.json`, `pyproject.toml` (`[project]` or `[tool.poetry]`), or `Cargo.toml`. If they
   disagree, report the mismatch as a finding and ask which is intended. If there is none, stop
   and say the project itself has no license; suggest choosing one first (link
   https://choosealicense.com) because nothing else can be judged without it.

2. **Gather license data.** The helper reads manifests directly; lockfiles from npm (v2/v3)
   already carry licenses. For other ecosystems, try the local tools that are installed, never
   fetching from the network without asking:
   - npm/yarn/pnpm: `npx --no-install license-checker --json > maintainer/.cache/npm-licenses.json`
   - Python (inside the project's env): `pip-licenses --format=json > maintainer/.cache/py-licenses.json`
   - Rust: `cargo metadata --format-version 1 > maintainer/.cache/cargo-meta.json`
   - Go: `go-licenses report ./... > maintainer/.cache/go-licenses.csv` (module,url,license; the
     helper takes the last column as the license when there is no header)
   If a tool is missing, say which one and continue; the affected packages will show as unknown.

3. **Run the helper.**
   ```
   python3 "${CLAUDE_SKILL_DIR}/license_compat.py" . --licenses maintainer/.cache/npm-licenses.json --licenses maintainer/.cache/py-licenses.json -o maintainer/license-report.md
   python3 "${CLAUDE_SKILL_DIR}/license_compat.py" . --format json
   ```
   Options: `--project-license "MIT"` to override, `--no-scan` to use only the data files,
   `--fail-on conflict` for CI use. It understands SPDX expressions (`MIT OR Apache-2.0` picks the
   most permissive option; `AND` takes the most restrictive), `-or-later`/`-only` variants, and
   `WITH` exceptions such as the Classpath exception.

4. **Read the verdicts.**

   | Verdict | Meaning | Typical action |
   |---|---|---|
   | conflict | The simplified table says these licenses usually cannot be combined as distributed | Replace, isolate, get permission, or relicense; talk to a lawyer before shipping |
   | unknown | No license data, or an unrecognised one | Look at the package's repo; no license means all rights reserved |
   | review | Allowed with conditions: weak copyleft (LGPL, MPL, EPL), AGPL network clause, dev-only conflict | Note the obligation; usually fine as an unmodified library |
   | ok | Permissive | Keep the copyright notices in distributions |

   Dev-only dependencies (tests, linters) that conflict are downgraded to review because they
   are normally not shipped. Say that out loud; it is not true for every distribution model.

5. **Verify the flags by hand.** For every conflict and unknown, open the dependency's LICENSE
   file (in `node_modules/<pkg>/`, site-packages `*.dist-info/`, or `~/.cargo/registry/src/`) and
   confirm the license the metadata claims. Metadata is often wrong or stale. Note dual licenses
   the metadata missed.

6. **Write the report** at `maintainer/license-report.md` (the helper writes the tables; add
   on top): a 3-line summary, each conflict with its dependency path
   (`npm ls <pkg>`, `pipdeptree -r -p <pkg>`, `cargo tree -i <pkg>`, `go mod why <module>`) so the
   maintainer knows which direct dependency pulled it in, and options per conflict. Keep the
   disclaimer at the top.

7. **Offer a CI guard** (only write it if the user wants it): a workflow step running the
   helper with `--fail-on conflict`. Show the YAML first.

## Decision rules

- Treat "UNLICENSED" in npm as proprietary, not as the Unlicense.
- A package with no license file is not "free to use". Report it as unknown, never ok.
- If the project is an application that is never distributed (internal SaaS), copyleft risk is
  different (except AGPL). Mention this when relevant; do not decide it for them.
- Do not guess a license from the package name or popularity.

## What NOT to do

- Do not present any output as legal advice, and do not tell the user they are "compliant".
- Do not remove, replace, or upgrade dependencies without confirmation.
- Do not install license tools globally or fetch from the network without asking.
- Do not paste full license texts into the report; link them.

## Hand-off

New dependencies in a PR: run this before `maintainer-pr-welcome` approves. Before a major
release, run it alongside `maintainer-health`, then `maintainer-release-notes`.
