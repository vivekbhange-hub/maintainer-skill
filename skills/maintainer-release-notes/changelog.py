#!/usr/bin/env python3
"""Turn git log output into a Keep a Changelog entry and a semver bump suggestion.

Accepted input (file argument or stdin):

1. Record format (recommended, keeps commit bodies so BREAKING CHANGE footers are seen):
     git log v1.2.0..HEAD --no-merges --pretty=format:'%h%x1f%an%x1f%s%x1f%b%x1e'
2. Tab format:   git log v1.2.0..HEAD --pretty=format:'%h%x09%an%x09%s'
3. One-line:     git log v1.2.0..HEAD --oneline

Conventional commits (feat:, fix(scope)!:, ...) are mapped exactly. Other messages are
classified with a small keyword heuristic and marked as guessed in the JSON output.

Standard library only. No network. Deterministic for a given input and --date.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import sys
from pathlib import Path

SECTIONS = ["Added", "Changed", "Deprecated", "Removed", "Fixed", "Security"]

# Conventional commit type -> Keep a Changelog section. None means internal (hidden by default).
CC_TYPES = {
    "feat": "Added",
    "feature": "Added",
    "fix": "Fixed",
    "bugfix": "Fixed",
    "perf": "Changed",
    "refactor": "Changed",
    "revert": "Changed",
    "deprecate": "Deprecated",
    "remove": "Removed",
    "security": "Security",
    "sec": "Security",
    "docs": None,
    "doc": None,
    "chore": None,
    "ci": None,
    "build": None,
    "test": None,
    "tests": None,
    "style": None,
}

CC_RE = re.compile(r"^(?P<type>[A-Za-z]+)(?:\((?P<scope>[^)]*)\))?(?P<bang>!)?:\s*(?P<desc>.+)$")
BREAKING_RE = re.compile(r"^BREAKING[ -]CHANGE:\s*(?P<note>.*)$", re.MULTILINE)
PR_RE = re.compile(r"\(#(\d+)\)|(?<![\w/])#(\d+)\b")
HASH_RE = re.compile(r"^[0-9a-f]{7,40}$")
MERGE_RE = re.compile(r"^Merge (pull request|branch|remote-tracking branch)\b", re.IGNORECASE)
RELEASE_RE = re.compile(r"^(chore\(release\)|release\b|bump version\b|v?\d+\.\d+\.\d+$)", re.IGNORECASE)
SECURITY_HINT = re.compile(r"\b(security|cve-\d{4}-\d+|vulnerab\w*|xss|csrf|injection)\b", re.IGNORECASE)

# Heuristic for non-conventional messages: first matching rule wins.
KEYWORD_RULES = [
    ("Security", re.compile(r"\b(security|cve-\d{4}|vulnerab\w*)\b", re.IGNORECASE)),
    ("Removed", re.compile(r"^(remove[sd]?|delete[sd]?|drop(s|ped)?)\b", re.IGNORECASE)),
    ("Deprecated", re.compile(r"^deprecat\w*\b", re.IGNORECASE)),
    ("Fixed", re.compile(r"^(fix(e[sd])?|bug|resolve[sd]?|correct(s|ed)?|patch(es|ed)?|hotfix)\b", re.IGNORECASE)),
    ("Added", re.compile(r"^(add(s|ed)?|implement(s|ed)?|introduce[sd]?|new|support(s|ed)?|create[sd]?|allow(s|ed)?)\b", re.IGNORECASE)),
    ("Internal", re.compile(r"^(docs?|readme|typo|ci|test(s|ing)?|lint|format(ting)?|chore|wip|merge)\b", re.IGNORECASE)),
]

BOT_RE = re.compile(r"(\[bot\]$|^dependabot|^renovate|^github-actions)", re.IGNORECASE)


def parse_log(text: str) -> list[dict]:
    """Split raw git log text into commit dicts with hash, author, subject, body."""
    commits: list[dict] = []
    text = text.replace("\r\n", "\n")
    if "\x1e" in text or "\x1f" in text:
        for record in text.split("\x1e"):
            record = record.strip("\n")
            if not record.strip():
                continue
            parts = record.split("\x1f")
            parts += [""] * (4 - len(parts))
            commits.append({
                "hash": parts[0].strip(),
                "author": parts[1].strip(),
                "subject": parts[2].strip(),
                "body": parts[3].strip(),
            })
        return commits
    for line in text.split("\n"):
        if not line.strip():
            continue
        if "\t" in line:
            parts = line.split("\t")
            parts += [""] * (3 - len(parts))
            commits.append({"hash": parts[0].strip(), "author": parts[1].strip(),
                            "subject": "\t".join(parts[2:]).strip(), "body": ""})
            continue
        first, _, rest = line.strip().partition(" ")
        if HASH_RE.match(first) and rest:
            commits.append({"hash": first, "author": "", "subject": rest.strip(), "body": ""})
        else:
            commits.append({"hash": "", "author": "", "subject": line.strip(), "body": ""})
    return commits


def classify(commit: dict) -> dict:
    """Return the commit enriched with section, breaking flag, scope, description and PR refs."""
    subject = commit["subject"]
    body = commit.get("body", "")
    out = dict(commit)
    out.update({"section": None, "breaking": False, "scope": "", "description": subject,
                "conventional": False, "guessed": False, "skip": False, "prs": [],
                "breaking_note": ""})

    if MERGE_RE.match(subject) or RELEASE_RE.match(subject):
        out["skip"] = True

    out["prs"] = sorted({int(a or b) for a, b in PR_RE.findall(subject + "\n" + body)})

    m = CC_RE.match(subject)
    if m and (m.group("type").lower() in CC_TYPES or m.group("bang")):
        ctype = m.group("type").lower()
        out["conventional"] = True
        out["scope"] = (m.group("scope") or "").strip()
        out["description"] = m.group("desc").strip()
        out["section"] = CC_TYPES.get(ctype, "Changed")
        if out["section"] == "Fixed" and SECURITY_HINT.search(out["description"] + " " + out["scope"]):
            out["section"] = "Security"
        if m.group("bang"):
            out["breaking"] = True
    else:
        out["guessed"] = True
        out["section"] = "Changed"
        for section, rx in KEYWORD_RULES:
            if rx.search(subject):
                out["section"] = None if section == "Internal" else section
                break

    bm = BREAKING_RE.search(body)
    if bm:
        out["breaking"] = True
        out["breaking_note"] = bm.group("note").strip()
    if out["breaking"] and out["section"] is None:
        out["section"] = "Changed"  # a breaking change is never internal
    # Strip a trailing "(#123)" from the description; the PR is listed separately.
    out["description"] = re.sub(r"\s*\(#\d+\)\s*$", "", out["description"]).strip()
    if out["description"]:
        out["description"] = out["description"][0].upper() + out["description"][1:]
    return out


def parse_version(v: str) -> tuple[int, int, int]:
    m = re.match(r"^v?(\d+)\.(\d+)\.(\d+)", (v or "").strip())
    if not m:
        raise ValueError(f"not a semver version: {v!r}")
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def suggest_bump(entries: list[dict], current: str | None = None) -> dict:
    """Pick major/minor/patch/none. Pre-1.0 projects get minor for breaking changes."""
    visible = [e for e in entries if not e["skip"]]
    breaking = any(e["breaking"] for e in visible)
    added = any(e["section"] == "Added" for e in visible)
    other = any(e["section"] in ("Changed", "Deprecated", "Removed", "Fixed", "Security") for e in visible)
    if breaking:
        bump, reason = "major", "at least one breaking change"
    elif added:
        bump, reason = "minor", "new features, no breaking changes"
    elif other:
        bump, reason = "patch", "fixes or changes only"
    else:
        bump, reason = "none", "no user-facing changes found"
    result = {"bump": bump, "reason": reason, "current": current, "next": None}
    if current:
        major, minor, patch = parse_version(current)
        if bump == "major" and major == 0:
            result["bump"] = bump = "minor"
            result["reason"] += " (pre-1.0: breaking changes bump the minor version)"
        if bump == "major":
            nxt = (major + 1, 0, 0)
        elif bump == "minor":
            nxt = (major, minor + 1, 0)
        elif bump == "patch":
            nxt = (major, minor, patch + 1)
        else:
            nxt = None
        if nxt:
            prefix = "v" if current.strip().startswith("v") else ""
            result["next"] = prefix + ".".join(str(n) for n in nxt)
    return result


COAUTHOR_RE = re.compile(r"^Co-authored-by:\s*(?P<name>[^<\n]+?)\s*(<[^>]*>)?\s*$", re.IGNORECASE | re.MULTILINE)


def contributors(entries: list[dict], include_bots: bool = False) -> list[str]:
    """Authors and Co-authored-by names in first-seen order, bots removed unless asked."""
    seen: list[str] = []
    for e in entries:
        names = [e.get("author", "").strip()]
        names += [m.group("name").strip() for m in COAUTHOR_RE.finditer(e.get("body", ""))]
        for name in names:
            if not name or name in seen:
                continue
            if not include_bots and BOT_RE.search(name):
                continue
            seen.append(name)
    return seen


def build(text: str, current: str | None = None, include_internal: bool = False,
          include_bots: bool = False) -> dict:
    entries = [classify(c) for c in parse_log(text)]
    groups: dict[str, list[dict]] = {s: [] for s in SECTIONS}
    internal: list[dict] = []
    for e in entries:
        if e["skip"]:
            continue
        if e["section"] is None:
            internal.append(e)
        else:
            groups[e["section"]].append(e)
    return {
        "entries": entries,
        "groups": groups,
        "internal": internal,
        "breaking": [e for e in entries if e["breaking"] and not e["skip"]],
        "contributors": contributors(entries, include_bots),
        "bump": suggest_bump(entries, current),
        "include_internal": include_internal,
    }


def _line(e: dict, repo_url: str | None) -> str:
    text = e["description"]
    if e["scope"]:
        text = f"**{e['scope']}:** {text}"
    if e["breaking"]:
        text = "**BREAKING:** " + text
    refs = []
    for pr in e["prs"]:
        refs.append(f"[#{pr}]({repo_url.rstrip('/')}/pull/{pr})" if repo_url else f"#{pr}")
    if refs:
        text += " (" + ", ".join(refs) + ")"
    elif e["hash"]:
        text += f" ({e['hash'][:7]})"
    return f"- {text}"


def render_markdown(result: dict, version: str | None = None, date: str | None = None,
                    repo_url: str | None = None) -> str:
    version = version or result["bump"].get("next")
    if version:
        header = f"## [{version.lstrip('v')}] - {date or _dt.date.today().isoformat()}"
    else:
        header = "## [Unreleased]"
    lines = [header, ""]
    if result["breaking"]:
        lines.append("> Breaking changes in this release:")
        for e in result["breaking"]:
            note = e["breaking_note"] or e["description"]
            lines.append(f"> - {note}")
        lines.append("")
    any_section = False
    for section in SECTIONS:
        items = result["groups"][section]
        if not items:
            continue
        any_section = True
        lines.append(f"### {section}")
        lines.extend(_line(e, repo_url) for e in items)
        lines.append("")
    if result["include_internal"] and result["internal"]:
        lines.append("### Internal")
        lines.extend(_line(e, repo_url) for e in result["internal"])
        lines.append("")
    if not any_section and not (result["include_internal"] and result["internal"]):
        lines.append("_No user-facing changes._")
        lines.append("")
    b = result["bump"]
    lines.append("<!-- maintainer-release-notes: suggested bump = "
                 f"{b['bump']} ({b['reason']})"
                 + (f", {b['current']} -> {b['next']}" if b.get("next") else "") + " -->")
    if result["contributors"]:
        lines.append("<!-- contributors: " + ", ".join(result["contributors"]) + " -->")
    return "\n".join(lines).rstrip() + "\n"


def render_json(result: dict) -> str:
    def slim(e: dict) -> dict:
        return {k: e[k] for k in ("hash", "author", "subject", "section", "scope", "description",
                                  "breaking", "breaking_note", "conventional", "guessed", "prs")}
    payload = {
        "bump": result["bump"],
        "contributors": result["contributors"],
        "sections": {s: [slim(e) for e in result["groups"][s]] for s in SECTIONS},
        "internal": [slim(e) for e in result["internal"]],
        "breaking": [slim(e) for e in result["breaking"]],
        "skipped": [e["subject"] for e in result["entries"] if e["skip"]],
        "guessed_count": sum(1 for e in result["entries"] if e["guessed"] and not e["skip"]),
    }
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Group git log output into a Keep a Changelog entry and suggest a semver bump.")
    p.add_argument("logfile", nargs="?", help="git log output file (default: stdin)")
    p.add_argument("--current", help="current released version, e.g. 1.4.2 or v1.4.2")
    p.add_argument("--version", help="version for the heading (default: the suggested next version)")
    p.add_argument("--date", help="release date YYYY-MM-DD (default: today)")
    p.add_argument("--repo-url", help="https://github.com/owner/repo, turns #123 into links")
    p.add_argument("--include-internal", action="store_true",
                   help="also list docs/chore/ci/test commits under an Internal heading")
    p.add_argument("--include-bots", action="store_true", help="keep bot authors in contributors")
    p.add_argument("--format", choices=["markdown", "json"], default="markdown")
    p.add_argument("-o", "--output", help="write to this file instead of stdout")
    args = p.parse_args(argv)

    if args.logfile:
        text = Path(args.logfile).read_text(encoding="utf-8", errors="replace")
    else:
        if hasattr(sys.stdin, "reconfigure"):
            sys.stdin.reconfigure(encoding="utf-8", errors="replace")
        text = sys.stdin.read()
    try:
        result = build(text, args.current, args.include_internal, args.include_bots)
    except ValueError as exc:
        p.error(str(exc))
    out = render_json(result) if args.format == "json" else render_markdown(
        result, args.version, args.date, args.repo_url)
    if args.output:
        Path(args.output).write_bytes((out).encode("utf-8"))
    else:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        sys.stdout.write(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
