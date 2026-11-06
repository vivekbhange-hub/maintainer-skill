#!/usr/bin/env python3
"""Find likely duplicate issues in `gh issue list --json` output.

    gh issue list --state all --limit 500 --json number,title,body,state,createdAt,labels > issues.json
    python3 dupes.py issues.json                 # all likely pairs
    python3 dupes.py issues.json --issue 412     # candidates for one issue

Similarity is a weighted Jaccard score over normalized word sets: 70% title, 30% the first
600 characters of the body. Error-like tokens (identifiers, codes) are kept, stop words are
dropped. It is a shortlist for a human, not a verdict.

Standard library only. No network. Deterministic.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

STOP = set("""
a an and are as at be been but by can could did do does doing for from had has have how i if in into
is it its just me my not of on or our so some than that the their them then there these they this to
too up us was we were what when where which while who why will with would you your yes no get got
after before also any all only very really still please thanks thank hi hello issue bug problem
error errors work works working doesnt dont cant wont isnt using use used try trying tried when
""".split())

WORD_RE = re.compile(r"[a-z0-9][a-z0-9_.:-]*[a-z0-9]|[a-z0-9]")


def tokens(text: str) -> set[str]:
    text = (text or "").lower()
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)  # drop code blocks: long and noisy
    text = re.sub(r"https?://\S+", " ", text)
    out = set()
    for w in WORD_RE.findall(text.replace("'", "")):
        w = w.strip(".:-")
        if len(w) < 3 or w in STOP or w.isdigit():
            continue
        if len(w) > 4 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        out.add(w)
    return out


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def prepare(issues: list[dict]) -> list[dict]:
    prepared = []
    for it in issues:
        if "number" not in it:
            continue
        prepared.append({
            "number": int(it["number"]),
            "title": it.get("title", ""),
            "state": (it.get("state") or "OPEN").upper(),
            "createdAt": it.get("createdAt", ""),
            "t": tokens(it.get("title", "")),
            "b": tokens((it.get("body") or "")[:600]),
        })
    prepared.sort(key=lambda x: x["number"])
    return prepared


def score(x: dict, y: dict) -> float:
    title = jaccard(x["t"], y["t"])
    body = jaccard(x["b"] | x["t"], y["b"] | y["t"])
    return round(0.7 * title + 0.3 * body, 3)


def find_pairs(issues: list[dict], threshold: float = 0.45, only: int | None = None,
               include_closed_pairs: bool = False) -> list[dict]:
    """Return candidate pairs sorted by score. The older issue is suggested as the canonical one."""
    items = prepare(issues)
    pairs = []
    for i, x in enumerate(items):
        for y in items[i + 1:]:
            if only is not None and only not in (x["number"], y["number"]):
                continue
            if not include_closed_pairs and x["state"] != "OPEN" and y["state"] != "OPEN":
                continue
            s = score(x, y)
            if s < threshold:
                continue
            older, newer = (x, y) if x["number"] < y["number"] else (y, x)
            pairs.append({
                "score": s,
                "keep": older["number"], "keep_title": older["title"], "keep_state": older["state"],
                "duplicate": newer["number"], "duplicate_title": newer["title"], "duplicate_state": newer["state"],
                "shared_words": sorted((x["t"] | x["b"]) & (y["t"] | y["b"]))[:8],
            })
    pairs.sort(key=lambda p: (-p["score"], p["keep"], p["duplicate"]))
    return pairs


def render_markdown(pairs: list[dict], threshold: float) -> str:
    lines = ["# Likely duplicate issues", "",
             f"Similarity threshold {threshold}. Read both issues before closing anything.", ""]
    if not pairs:
        lines.append("No likely duplicates found.")
        return "\n".join(lines) + "\n"
    lines += ["| Score | Keep (older) | Possible duplicate | Shared words |", "|---|---|---|---|"]
    for p in pairs:
        keep = f"#{p['keep']} {p['keep_title']}" + (" (closed)" if p["keep_state"] != "OPEN" else "")
        dup = f"#{p['duplicate']} {p['duplicate_title']}" + (" (closed)" if p["duplicate_state"] != "OPEN" else "")
        lines.append(f"| {p['score']:.2f} | {keep.replace('|', '/')} | {dup.replace('|', '/')} | "
                     f"{', '.join(p['shared_words'])} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Find likely duplicate issues in gh issue list --json output.")
    ap.add_argument("file", nargs="?", help="JSON file from gh issue list --json (default: stdin)")
    ap.add_argument("--threshold", type=float, default=0.45, help="minimum similarity 0..1 (default 0.45)")
    ap.add_argument("--issue", type=int, help="only show pairs involving this issue number")
    ap.add_argument("--include-closed-pairs", action="store_true",
                    help="also compare closed issues with each other")
    ap.add_argument("--format", choices=["markdown", "json"], default="markdown")
    args = ap.parse_args(argv)

    if args.file:
        raw = Path(args.file).read_text(encoding="utf-8-sig")
    else:
        if hasattr(sys.stdin, "reconfigure"):
            sys.stdin.reconfigure(encoding="utf-8")
        raw = sys.stdin.read()
    data = json.loads(raw or "[]")
    if not isinstance(data, list):
        ap.error("expected a JSON array of issues")
    pairs = find_pairs(data, args.threshold, args.issue, args.include_closed_pairs)
    out = json.dumps(pairs, indent=2) + "\n" if args.format == "json" else render_markdown(pairs, args.threshold)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.stdout.write(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
