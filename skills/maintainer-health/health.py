#!/usr/bin/env python3
"""Score an open-source repository's health from its files and print a markdown checklist.

Checks (100 points total): README and its key sections, LICENSE, CONTRIBUTING, SECURITY,
CODE_OF_CONDUCT, CI config, tests, issue templates, PR template, changelog, .gitignore,
CODEOWNERS. Every failed check comes with a concrete fix.

Reads the local filesystem only. Standard library only. No network. Deterministic.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "env", "vendor", "dist", "build", "target",
             "__pycache__", ".tox", ".mypy_cache", ".pytest_cache", "site-packages", ".next"}
DOC_DIRS = ("", ".github", "docs")


def _entries(directory: Path) -> dict[str, Path]:
    """Lowercased name -> path for one directory (case-insensitive lookups on every OS)."""
    if not directory.is_dir():
        return {}
    return {p.name.lower(): p for p in directory.iterdir()}


def find_file(root: Path, names: tuple[str, ...], dirs: tuple[str, ...] = DOC_DIRS) -> Path | None:
    for d in dirs:
        entries = _entries(root / d if d else root)
        for n in names:
            hit = entries.get(n.lower())
            if hit is not None and hit.is_file():
                return hit
    return None


def find_by_stem(root: Path, stems: tuple[str, ...], dirs: tuple[str, ...] = DOC_DIRS) -> Path | None:
    """Match files like LICENSE, LICENSE.md, license.txt, LICENSE-MIT, COPYING."""
    for d in dirs:
        for name, path in sorted(_entries(root / d if d else root).items()):
            base = name.split(".", 1)[0]
            if path.is_file() and any(base == s or base.startswith(s + "-") for s in stems):
                return path
    return None


def _walk(root: Path, max_depth: int = 4):
    root_depth = len(root.parts)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith("."))
        if len(Path(dirpath).parts) - root_depth >= max_depth:
            dirnames[:] = []
        yield Path(dirpath), dirnames, sorted(filenames)


TEST_DIR_NAMES = {"test", "tests", "__tests__", "spec", "specs", "testing"}
TEST_FILE_RE = re.compile(
    r"(^test_.*\.py$|.*_test\.py$|.*_test\.go$|.*\.(test|spec)\.(js|jsx|ts|tsx|mjs|cjs)$|.*Test\.java$|.*_spec\.rb$|.*Tests?\.cs$)")


def find_tests(root: Path) -> str | None:
    for dirpath, dirnames, filenames in _walk(root):
        for d in dirnames:
            if d.lower() in TEST_DIR_NAMES:
                return str((dirpath / d).relative_to(root)).replace("\\", "/") + "/"
        for f in filenames:
            if TEST_FILE_RE.match(f):
                return str((dirpath / f).relative_to(root)).replace("\\", "/")
    return None


CI_PATHS = (".gitlab-ci.yml", ".travis.yml", "azure-pipelines.yml", "Jenkinsfile", "bitbucket-pipelines.yml",
            ".circleci/config.yml", ".drone.yml", "appveyor.yml", ".woodpecker.yml")


def find_ci(root: Path) -> str | None:
    wf = root / ".github" / "workflows"
    if wf.is_dir():
        files = sorted(p.name for p in wf.iterdir() if p.suffix.lower() in (".yml", ".yaml"))
        if files:
            return ".github/workflows/" + files[0]
    for rel in CI_PATHS:
        if (root / rel).is_file():
            return rel
    return None


README_SECTIONS = [
    ("install", r"^#{1,6}\s.*\b(install(ation|ing)?|setup|getting started)\b", 5,
     "Add an `## Install` section with the exact command (`pip install ...`, `npm i ...`)."),
    ("usage", r"^#{1,6}\s.*\b(usage|example|examples|quick ?start|how to use|getting started)\b", 5,
     "Add a `## Usage` section with one copy-paste example and its output."),
    ("contributing", r"\bcontribut", 2,
     "Mention how to contribute and link CONTRIBUTING.md."),
    ("license", r"\blicen[cs]e", 3,
     "Add a `## License` line naming the license and linking LICENSE."),
]


def check_repo(root: Path) -> list[dict]:
    """Run every check. Each result: id, label, points, max, passed, evidence, fix."""
    results: list[dict] = []

    def add(cid, label, max_pts, passed, evidence="", fix="", points=None):
        results.append({"id": cid, "label": label, "max": max_pts,
                        "points": max_pts if passed and points is None else (points or 0),
                        "passed": bool(passed), "evidence": evidence, "fix": "" if passed else fix})

    readme = find_by_stem(root, ("readme",), ("", ".github", "docs"))
    text = readme.read_text(encoding="utf-8", errors="replace") if readme else ""
    lines = [l for l in text.splitlines() if l.strip()]
    if readme and len(lines) >= 10:
        add("readme", "README exists and has substance", 10, True, readme.name)
    elif readme:
        add("readme", "README exists and has substance", 10, False, f"{readme.name} has {len(lines)} non-empty lines",
            "Expand the README: what it does, who it is for, install, usage, license.", points=5)
    else:
        add("readme", "README exists and has substance", 10, False, "",
            "Create README.md: one-line purpose, install, usage, contributing, license.")
    for sid, pattern, pts, fix in README_SECTIONS:
        flags = re.IGNORECASE | re.MULTILINE
        hit = bool(text) and re.search(pattern, text, flags) is not None
        add(f"readme-{sid}", f"README covers {sid}", pts, hit, "found" if hit else "", fix)

    lic = find_by_stem(root, ("license", "licence", "copying"), ("",))
    add("license", "LICENSE file", 15, lic is not None, lic.name if lic else "",
        "Add a LICENSE file (https://choosealicense.com). Without one, nobody may legally reuse the code.")

    contrib = find_by_stem(root, ("contributing",))
    add("contributing", "CONTRIBUTING guide", 8, contrib is not None, _rel(root, contrib),
        "Add CONTRIBUTING.md with setup, test command, and PR rules (maintainer-community-files can draft it).")

    security = find_by_stem(root, ("security",))
    add("security", "SECURITY policy", 8, security is not None, _rel(root, security),
        "Add SECURITY.md: supported versions and a private way to report vulnerabilities.")

    coc = find_by_stem(root, ("code_of_conduct", "code-of-conduct"))
    add("code-of-conduct", "Code of conduct", 4, coc is not None, _rel(root, coc),
        "Adopt the Contributor Covenant (https://www.contributor-covenant.org) and add a contact address.")

    ci = find_ci(root)
    add("ci", "Continuous integration", 10, ci is not None, ci or "",
        "Add a CI workflow (e.g. .github/workflows/ci.yml) that runs the tests on every pull request.")

    tests = find_tests(root)
    add("tests", "Automated tests", 10, tests is not None, tests or "",
        "Add a tests/ folder with at least one test and document the test command in CONTRIBUTING.md.")

    tmpl_dir = root / ".github" / "ISSUE_TEMPLATE"
    issue_tmpl = None
    if tmpl_dir.is_dir() and any(p.suffix.lower() in (".md", ".yml", ".yaml") for p in tmpl_dir.iterdir()):
        issue_tmpl = ".github/ISSUE_TEMPLATE/"
    else:
        hit = find_file(root, ("issue_template.md",))
        issue_tmpl = _rel(root, hit) if hit else None
    add("issue-templates", "Issue templates", 5, issue_tmpl is not None, issue_tmpl or "",
        "Add .github/ISSUE_TEMPLATE/ with a bug report and a feature request form.")

    pr = find_file(root, ("pull_request_template.md",))
    if pr is None and (root / ".github" / "PULL_REQUEST_TEMPLATE").is_dir():
        pr = root / ".github" / "PULL_REQUEST_TEMPLATE"
    add("pr-template", "Pull request template", 4, pr is not None, _rel(root, pr),
        "Add .github/pull_request_template.md with a summary, linked issue, and test checklist.")

    changelog = find_by_stem(root, ("changelog", "changes", "history", "news", "releases"), ("", "docs"))
    add("changelog", "Changelog", 6, changelog is not None, _rel(root, changelog),
        "Add CHANGELOG.md in Keep a Changelog format (maintainer-release-notes can generate entries).")

    gi = find_file(root, (".gitignore",), ("",))
    add("gitignore", ".gitignore", 2, gi is not None, ".gitignore" if gi else "",
        "Add a .gitignore for your language (https://github.com/github/gitignore).")

    owners = find_file(root, ("CODEOWNERS",), ("", ".github", "docs"))
    add("codeowners", "CODEOWNERS", 3, owners is not None, _rel(root, owners),
        "Add .github/CODEOWNERS so reviews are requested automatically.")
    return results


def _rel(root: Path, p: Path | None) -> str:
    if p is None:
        return ""
    return str(p.relative_to(root)).replace("\\", "/")


def grade(score: int) -> str:
    for cutoff, letter in ((90, "A"), (75, "B"), (60, "C"), (40, "D")):
        if score >= cutoff:
            return letter
    return "F"


def summarize(results: list[dict]) -> dict:
    total = sum(r["points"] for r in results)
    maximum = sum(r["max"] for r in results)
    score = round(100 * total / maximum) if maximum else 0
    return {"score": score, "points": total, "max": maximum, "grade": grade(score)}


def render_markdown(root: Path, results: list[dict], name: str | None = None) -> str:
    s = summarize(results)
    title = name or root.resolve().name
    out = [f"# Repo health: {title}", "",
           f"**Score: {s['score']}/100 (grade {s['grade']})**", "",
           "| | Check | Points | Evidence |", "|---|---|---|---|"]
    for r in results:
        mark = "[x]" if r["passed"] else "[ ]"
        out.append(f"| {mark} | {r['label']} | {r['points']}/{r['max']} | {r['evidence'] or '-'} |")
    fixes = sorted((r for r in results if not r["passed"]), key=lambda r: -(r["max"] - r["points"]))
    out.append("")
    if fixes:
        out += ["## Fixes, biggest gain first", ""]
        for r in fixes:
            out.append(f"- [ ] **{r['label']}** (+{r['max'] - r['points']}): {r['fix']}")
    else:
        out.append("Every check passes. Nice work.")
    out.append("")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Score a repository's community health and list fixes.")
    ap.add_argument("path", nargs="?", default=".", help="repository root (default: .)")
    ap.add_argument("--format", choices=["markdown", "json"], default="markdown")
    ap.add_argument("--name", help="display name for the report heading")
    ap.add_argument("--min-score", type=int, default=0, help="exit 1 if the score is below this")
    ap.add_argument("-o", "--output", help="write the report to this file")
    args = ap.parse_args(argv)

    root = Path(args.path)
    if not root.is_dir():
        ap.error(f"not a directory: {root}")
    results = check_repo(root)
    s = summarize(results)
    if args.format == "json":
        out = json.dumps({"summary": s, "checks": results}, indent=2) + "\n"
    else:
        out = render_markdown(root, results, args.name)
    if args.output:
        Path(args.output).write_bytes((out).encode("utf-8"))
    else:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        sys.stdout.write(out)
    return 1 if s["score"] < args.min_score else 0


if __name__ == "__main__":
    sys.exit(main())
