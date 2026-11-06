#!/usr/bin/env python3
"""Flag dependency licenses that may not fit your project's license.

NOT LEGAL ADVICE. This is a first-pass triage tool built on a simplified compatibility
table. It tells you where to look, not what the law says. Ask a lawyer for real decisions.

What it reads (from a repo path, all optional):
  package.json            project license; dependency names
  package-lock.json       per-package licenses (lockfile v2/v3), dev flag
  requirements*.txt       dependency names
  pyproject.toml          project license; PEP 621 and Poetry dependencies
  Cargo.toml              package license; dependency names
  go.mod                  require lines
  LICENSE / COPYING       project license guessed from the text when no manifest says it

Extra license data (--licenses FILE, repeatable) fills in what manifests lack:
  * license-checker JSON   {"pkg@1.0.0": {"licenses": "MIT"}}
  * pip-licenses JSON      [{"Name": "requests", "License": "Apache 2.0"}]
  * cargo metadata JSON    {"packages": [{"name": "serde", "license": "MIT OR Apache-2.0"}]}
  * simple JSON map        {"pkg": "MIT"}
  * CSV                    name,license   (header row optional)

Standard library only. No network. Deterministic.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
from pathlib import Path

DISCLAIMER = ("This report is an automated first pass, not legal advice. License compatibility "
              "depends on how you distribute and combine code. Confirm anything flagged with "
              "the dependency's actual license text, and with a lawyer for commercial decisions.")

PERMISSIVE, WEAK, STRONG, RESTRICTED, UNKNOWN = "permissive", "weak-copyleft", "strong-copyleft", "restricted", "unknown"
RANK = {PERMISSIVE: 0, WEAK: 1, STRONG: 2, RESTRICTED: 3, UNKNOWN: 4}

# Canonical SPDX-style id -> category.
CATEGORY = {
    "MIT": PERMISSIVE, "MIT-0": PERMISSIVE, "X11": PERMISSIVE, "ISC": PERMISSIVE,
    "BSD-2-Clause": PERMISSIVE, "BSD-3-Clause": PERMISSIVE, "BSD": PERMISSIVE, "0BSD": PERMISSIVE,
    "Apache-2.0": PERMISSIVE, "Zlib": PERMISSIVE, "BSL-1.0": PERMISSIVE, "Unlicense": PERMISSIVE,
    "CC0-1.0": PERMISSIVE, "WTFPL": PERMISSIVE, "PSF-2.0": PERMISSIVE, "Python-2.0": PERMISSIVE,
    "BlueOak-1.0.0": PERMISSIVE, "Unicode-DFS-2016": PERMISSIVE, "Unicode-3.0": PERMISSIVE,
    "CC-BY-4.0": PERMISSIVE, "Artistic-2.0": PERMISSIVE, "PostgreSQL": PERMISSIVE, "NCSA": PERMISSIVE,
    "LGPL-2.1": WEAK, "LGPL-3.0": WEAK, "MPL-2.0": WEAK, "EPL-1.0": WEAK, "EPL-2.0": WEAK,
    "CDDL-1.0": WEAK, "CDDL-1.1": WEAK, "CPL-1.0": WEAK, "MS-RL": WEAK,
    "GPL-2.0": STRONG, "GPL-3.0": STRONG, "AGPL-3.0": STRONG, "EUPL-1.2": STRONG, "OSL-3.0": STRONG,
    "CC-BY-SA-4.0": STRONG,
    "SSPL-1.0": RESTRICTED, "BUSL-1.1": RESTRICTED, "Elastic-2.0": RESTRICTED,
    "CC-BY-NC-4.0": RESTRICTED, "Commons-Clause": RESTRICTED, "Proprietary": RESTRICTED,
}

# Lowercased aliases (after stripping punctuation noise) -> canonical id.
ALIASES = {
    "mit": "MIT", "mit license": "MIT", "the mit license": "MIT", "expat": "MIT", "mit-0": "MIT-0",
    "isc": "ISC", "isc license": "ISC",
    "bsd": "BSD", "bsd license": "BSD", "new bsd": "BSD-3-Clause", "new bsd license": "BSD-3-Clause",
    "bsd-3-clause": "BSD-3-Clause", "bsd 3-clause": "BSD-3-Clause", "3-clause bsd": "BSD-3-Clause",
    "bsd-2-clause": "BSD-2-Clause", "bsd 2-clause": "BSD-2-Clause", "simplified bsd": "BSD-2-Clause",
    "0bsd": "0BSD",
    "apache-2.0": "Apache-2.0", "apache 2.0": "Apache-2.0", "apache 2": "Apache-2.0", "apache-2": "Apache-2.0",
    "apache license 2.0": "Apache-2.0", "apache license, version 2.0": "Apache-2.0",
    "apache software license": "Apache-2.0", "apache license version 2.0": "Apache-2.0", "asl 2.0": "Apache-2.0",
    "zlib": "Zlib", "bsl-1.0": "BSL-1.0", "boost": "BSL-1.0", "boost software license 1.0": "BSL-1.0",
    "unlicense": "Unlicense", "the unlicense": "Unlicense", "cc0-1.0": "CC0-1.0", "cc0": "CC0-1.0",
    "public domain": "CC0-1.0", "wtfpl": "WTFPL",
    "psf": "PSF-2.0", "psf-2.0": "PSF-2.0", "python software foundation license": "PSF-2.0",
    "python-2.0": "Python-2.0", "blueoak-1.0.0": "BlueOak-1.0.0",
    "unicode-dfs-2016": "Unicode-DFS-2016", "unicode-3.0": "Unicode-3.0", "cc-by-4.0": "CC-BY-4.0",
    "artistic-2.0": "Artistic-2.0", "postgresql": "PostgreSQL", "ncsa": "NCSA", "x11": "X11",
    "lgpl": "LGPL-2.1", "lgpl-2.1": "LGPL-2.1", "lgplv2": "LGPL-2.1", "lgplv2.1": "LGPL-2.1", "lgpl-2.0": "LGPL-2.1",
    "lgpl-3.0": "LGPL-3.0", "lgplv3": "LGPL-3.0", "gnu lesser general public license v3": "LGPL-3.0",
    "mpl-2.0": "MPL-2.0", "mpl 2.0": "MPL-2.0", "mozilla public license 2.0": "MPL-2.0",
    "epl-1.0": "EPL-1.0", "epl-2.0": "EPL-2.0", "eclipse public license 2.0": "EPL-2.0",
    "cddl-1.0": "CDDL-1.0", "cddl-1.1": "CDDL-1.1", "cpl-1.0": "CPL-1.0", "ms-rl": "MS-RL",
    "gpl": "GPL-2.0", "gpl-2.0": "GPL-2.0", "gplv2": "GPL-2.0", "gpl v2": "GPL-2.0", "gpl2": "GPL-2.0",
    "gpl-3.0": "GPL-3.0", "gplv3": "GPL-3.0", "gpl v3": "GPL-3.0", "gpl3": "GPL-3.0",
    "gnu general public license v3": "GPL-3.0", "gnu general public license v2": "GPL-2.0",
    "agpl-3.0": "AGPL-3.0", "agplv3": "AGPL-3.0", "agpl": "AGPL-3.0",
    "gnu affero general public license v3": "AGPL-3.0",
    "eupl-1.2": "EUPL-1.2", "osl-3.0": "OSL-3.0", "cc-by-sa-4.0": "CC-BY-SA-4.0",
    "sspl": "SSPL-1.0", "sspl-1.0": "SSPL-1.0", "busl-1.1": "BUSL-1.1", "bsl-1.1": "BUSL-1.1",
    "business source license 1.1": "BUSL-1.1", "elastic-2.0": "Elastic-2.0", "elastic license 2.0": "Elastic-2.0",
    "cc-by-nc-4.0": "CC-BY-NC-4.0", "commons clause": "Commons-Clause",
    "unlicensed": "Proprietary", "proprietary": "Proprietary", "commercial": "Proprietary",
    "see license in license": "UNKNOWN", "see license": "UNKNOWN", "other": "UNKNOWN",
}


def normalize(raw: str) -> tuple[str, str]:
    """Return (canonical id, variant) for one license token. variant is 'only', 'or-later' or ''."""
    s = (raw or "").strip().strip('"').strip()
    if not s:
        return "UNKNOWN", ""
    variant = ""
    low = s.lower()
    if low.endswith("-or-later") or low.endswith("+") or "or later" in low or "or any later" in low:
        variant = "or-later"
    elif low.endswith("-only") or low.endswith(" only"):
        variant = "only"
    core = re.sub(r"(-or-later|-only|\+)$", "", s, flags=re.IGNORECASE).strip()
    core = re.sub(r"\s*\((or|or any) later.*?\)$", "", core, flags=re.IGNORECASE)
    core = re.sub(r"\s+(or|or any) later.*$", "", core, flags=re.IGNORECASE)
    core = re.sub(r"\s+only$", "", core, flags=re.IGNORECASE).strip()
    key = re.sub(r"\s+", " ", core.lower()).strip(" .")
    for cand in (key, key.replace(" license", ""), key.replace("licence", "license")):
        if cand in ALIASES:
            return ALIASES[cand], variant
    for canon in CATEGORY:
        if canon.lower() == key:
            return canon, variant
    return "UNKNOWN", variant


# ---------- SPDX expression evaluation ----------

_OPS = ("AND", "OR", "WITH")


def _tokenize(expr: str) -> list[str]:
    """Split on parens and operators; join consecutive plain words ("Apache License 2.0") into one id."""
    tokens: list[str] = []
    for raw in re.findall(r"\(|\)|[^\s()]+", expr):
        is_word = raw not in ("(", ")") and raw.upper() not in _OPS
        prev_is_word = bool(tokens) and tokens[-1] not in ("(", ")") and tokens[-1].upper() not in _OPS
        if is_word and prev_is_word:
            tokens[-1] += " " + raw
        else:
            tokens.append(raw)
    return tokens


class _Parser:
    def __init__(self, tokens: list[str]):
        self.toks, self.i = tokens, 0

    def peek(self):
        return self.toks[self.i] if self.i < len(self.toks) else None

    def take(self):
        tok = self.peek()
        self.i += 1
        return tok

    def expr(self):  # OR has lowest precedence
        node = self.term()
        while self.peek() and self.peek().upper() == "OR":
            self.take()
            node = ("OR", node, self.term())
        return node

    def term(self):
        node = self.factor()
        while self.peek() and self.peek().upper() == "AND":
            self.take()
            node = ("AND", node, self.factor())
        return node

    def factor(self):
        tok = self.take()
        if tok is None:
            return ("ID", "")
        if tok == "(":
            node = self.expr()
            if self.peek() == ")":
                self.take()
            return node
        node = ("ID", tok)
        if self.peek() and self.peek().upper() == "WITH":
            self.take()
            exc = self.take() or ""
            node = ("WITH", tok, exc)
        return node


def evaluate(expr: str) -> dict:
    """Evaluate a license string or SPDX expression.

    OR means the user may pick, so the least restrictive option wins.
    AND means all apply, so the most restrictive wins.
    """
    expr = (expr or "").strip()
    if not expr:
        return {"id": "UNKNOWN", "variant": "", "category": UNKNOWN, "note": "no license declared"}
    # Free-text values like "MIT/Apache-2.0" or "MIT or Apache 2.0" are common in the wild.
    if not re.search(r"\b(AND|OR|WITH)\b", expr) and "/" in expr and "(" not in expr:
        expr = " OR ".join(p.strip() for p in expr.split("/"))
    expr = re.sub(r"\s+\bor\b\s+(?!later|any later)", " OR ", expr)
    expr = re.sub(r"\s+\band\b\s+", " AND ", expr)

    def walk(node) -> dict:
        kind = node[0]
        if kind == "ID":
            canon, variant = normalize(node[1])
            return {"id": canon, "variant": variant, "category": CATEGORY.get(canon, UNKNOWN), "note": ""}
        if kind == "WITH":
            base = walk(("ID", node[1]))
            exc = node[2]
            if base["category"] == STRONG and re.search(r"classpath|gcc|linking|autoconf|bison", exc, re.I):
                base = dict(base, category=WEAK, note=f"{exc} relaxes linking terms")
            else:
                base = dict(base, note=f"with {exc}")
            return base
        left, right = walk(node[1]), walk(node[2])
        if kind == "OR":
            return left if RANK[left["category"]] <= RANK[right["category"]] else right
        return left if RANK[left["category"]] >= RANK[right["category"]] else right

    parser = _Parser(_tokenize(expr))
    result = walk(parser.expr())
    result["expression"] = expr
    return result


# ---------- compatibility table ----------

def check(project: dict, dep: dict, dev: bool = False) -> tuple[str, str]:
    """Return (verdict, reason). Verdicts: ok, review, conflict, unknown."""
    p_cat, d_cat = project["category"], dep["category"]
    p_id, d_id = project["id"], dep["id"]
    if d_cat == UNKNOWN:
        return "unknown", "license not found; look it up before shipping"
    if p_cat == UNKNOWN:
        return "review", "your project has no recognised license, so compatibility cannot be judged"

    verdict, reason = "ok", ""
    if d_cat == PERMISSIVE:
        if d_id == "Apache-2.0" and p_id == "GPL-2.0" and project.get("variant") != "or-later":
            verdict, reason = "conflict", "Apache-2.0 is generally considered incompatible with GPL-2.0-only"
        else:
            verdict, reason = "ok", "permissive; keep its copyright and license notice"
    elif d_cat == WEAK:
        verdict = "review"
        if d_id.startswith("LGPL"):
            reason = "LGPL: fine to link as a library; changes to the library itself must stay LGPL"
        elif d_id == "MPL-2.0":
            reason = "MPL-2.0: file-level copyleft; modified MPL files must stay MPL"
        else:
            reason = f"{d_id}: weak copyleft; modifications to that component must be shared"
        if p_cat == STRONG and d_id in ("EPL-1.0", "CDDL-1.0", "CDDL-1.1") and p_id.startswith("GPL"):
            verdict, reason = "conflict", f"{d_id} is generally considered incompatible with the GPL"
    elif d_cat == STRONG:
        if p_cat in (PERMISSIVE, WEAK):
            verdict = "conflict"
            reason = (f"{d_id} is strong copyleft; distributing it combined with your {p_id} project "
                      f"would require the combined work to be released under {d_id}")
        else:
            verdict, reason = _strong_vs_strong(project, dep)
        if d_id == "AGPL-3.0" and verdict != "conflict":
            reason += "; AGPL also applies to software offered over a network"
    elif d_cat == RESTRICTED:
        verdict = "conflict"
        reason = f"{d_id} is not an open source license; check its terms before depending on it"

    if dev and verdict == "conflict":
        verdict = "review"
        reason += " (dev-only dependency: usually not distributed, so lower risk)"
    return verdict, reason


def _strong_vs_strong(project: dict, dep: dict) -> tuple[str, str]:
    p_id, d_id = project["id"], dep["id"]
    if p_id == d_id:
        return "ok", f"same license family ({d_id})"
    if p_id == "GPL-2.0" and d_id in ("GPL-3.0", "AGPL-3.0"):
        if project.get("variant") == "or-later":
            return "review", f"your GPL-2.0-or-later code can be used under GPL-3.0; the combined work becomes {d_id}"
        return "conflict", f"GPL-2.0-only code cannot be combined with {d_id}"
    if p_id == "GPL-3.0" and d_id == "GPL-2.0":
        if dep.get("variant") == "or-later":
            return "ok", "GPL-2.0-or-later can be used under GPL-3.0"
        return "conflict", "GPL-2.0-only code cannot be combined with GPL-3.0"
    if p_id == "GPL-3.0" and d_id == "AGPL-3.0":
        return "review", "GPLv3 section 13 allows combining with AGPL-3.0; the AGPL part keeps its network clause"
    return "review", f"two different copyleft licenses ({p_id} and {d_id}); check they are compatible"


# ---------- minimal TOML reading (tomllib is 3.11+) ----------

def _parse_toml(text: str) -> dict:
    try:
        import tomllib  # type: ignore[import-not-found]
        return tomllib.loads(text)
    except ModuleNotFoundError:
        return mini_toml(text)
    except Exception:
        return mini_toml(text)


def _toml_value(raw: str):
    raw = raw.strip()
    if raw.startswith(("\"", "'")):
        q = raw[0]
        end = raw.find(q, 1)
        return raw[1:end] if end > 0 else raw[1:]
    if raw.startswith("["):
        return [a or b for a, b in re.findall(r"\"([^\"]*)\"|'([^']*)'", raw)]
    if raw.startswith("{"):
        table = {}
        for k, v in re.findall(r"([\w.-]+)\s*=\s*(\"[^\"]*\"|'[^']*'|[^,}]+)", raw):
            table[k] = _toml_value(v)
        return table
    return raw.split("#", 1)[0].strip()


def mini_toml(text: str) -> dict:
    """Very small TOML subset: [tables], key = "str" | [array of str] | {inline table}."""
    data: dict = {}
    current = data
    pending_key, buffer = None, ""
    for line in text.replace("\r\n", "\n").split("\n"):
        stripped = line.strip()
        if pending_key is not None:
            buffer += " " + stripped
            if stripped.startswith("]") or stripped.endswith("]"):
                current[pending_key] = _toml_value(buffer)
                pending_key, buffer = None, ""
            continue
        if not stripped or stripped.startswith("#"):
            continue
        m = re.match(r"^\[\[?([^\]]+)\]\]?$", stripped)
        if m:
            current = data
            for part in m.group(1).strip().split("."):
                current = current.setdefault(part.strip().strip('"'), {})
            continue
        m = re.match(r"^([\w.\"'-]+)\s*=\s*(.*)$", stripped)
        if not m:
            continue
        key, raw = m.group(1).strip("\"'"), m.group(2)
        if raw.startswith("[") and not raw.rstrip().split("#")[0].rstrip().endswith("]"):
            pending_key, buffer = key, raw
            continue
        current[key] = _toml_value(raw)
    return data


# ---------- manifest readers ----------

LICENSE_TEXT_HINTS = [
    ("GNU AFFERO GENERAL PUBLIC LICENSE", "AGPL-3.0"),
    ("GNU LESSER GENERAL PUBLIC LICENSE", "LGPL-3.0"),
    ("GNU GENERAL PUBLIC LICENSE", "GPL"),
    ("Mozilla Public License Version 2.0", "MPL-2.0"),
    ("Apache License", "Apache-2.0"),
    ("Permission is hereby granted, free of charge", "MIT"),
    ("Redistribution and use in source and binary forms", "BSD"),
    ("Permission to use, copy, modify, and/or distribute", "ISC"),
    ("This is free and unencumbered software", "Unlicense"),
]


def license_from_text(text: str) -> str:
    """Guess an SPDX id from the opening of a LICENSE file. Returns '' when unsure."""
    for needle, lic in LICENSE_TEXT_HINTS:
        if needle not in text:
            continue
        if lic == "GPL":
            return "GPL-2.0" if re.search(r"Version 2,", text) else "GPL-3.0"
        if lic == "BSD":
            return "BSD-3-Clause" if "Neither the name" in text else "BSD-2-Clause"
        return lic
    return ""


def _req_name(line: str) -> str:
    line = line.split("#", 1)[0].strip()
    if not line or line.startswith(("-", "git+", "http://", "https://")):
        return ""
    m = re.match(r"^([A-Za-z0-9][A-Za-z0-9._-]*)", line)
    return m.group(1).lower() if m else ""


def scan_repo(root: Path) -> dict:
    """Collect project license candidates and dependencies from manifests under root (top level)."""
    project: list[tuple[str, str]] = []  # (source, license)
    deps: dict[tuple[str, str], dict] = {}

    def add(eco: str, name: str, license_: str = "", dev: bool = False, source: str = ""):
        if not name:
            return
        key = (eco, name)
        entry = deps.setdefault(key, {"ecosystem": eco, "name": name, "license": "", "dev": dev, "source": source})
        if license_ and not entry["license"]:
            entry["license"] = license_
        entry["dev"] = entry["dev"] and dev

    pj = root / "package.json"
    if pj.is_file():
        data = json.loads(pj.read_text(encoding="utf-8"))
        lic = data.get("license")
        if isinstance(lic, dict):
            lic = lic.get("type", "")
        if lic:
            project.append(("package.json", str(lic)))
        for section, dev in (("dependencies", False), ("optionalDependencies", False),
                             ("peerDependencies", False), ("devDependencies", True)):
            for name in (data.get(section) or {}):
                add("npm", name, dev=dev, source="package.json")

    lock = root / "package-lock.json"
    if lock.is_file():
        data = json.loads(lock.read_text(encoding="utf-8"))
        for path, meta in (data.get("packages") or {}).items():
            if not path or "node_modules/" not in path:
                continue
            name = path.rsplit("node_modules/", 1)[1]
            lic = meta.get("license", "")
            if isinstance(lic, dict):
                lic = lic.get("type", "")
            add("npm", name, str(lic or ""), dev=bool(meta.get("dev")), source="package-lock.json")

    for req in sorted(root.glob("requirements*.txt")):
        dev = any(t in req.name for t in ("dev", "test", "lint", "doc"))
        for line in req.read_text(encoding="utf-8", errors="replace").splitlines():
            add("pypi", _req_name(line), dev=dev, source=req.name)

    pp = root / "pyproject.toml"
    if pp.is_file():
        data = _parse_toml(pp.read_text(encoding="utf-8"))
        proj = data.get("project") or {}
        lic = proj.get("license")
        if isinstance(lic, dict):
            lic = lic.get("text") or ""
        if lic:
            project.append(("pyproject.toml", str(lic)))
        for spec in proj.get("dependencies") or []:
            add("pypi", _req_name(spec), source="pyproject.toml")
        for group, specs in (proj.get("optional-dependencies") or {}).items():
            for spec in specs or []:
                add("pypi", _req_name(spec), dev=group in ("dev", "test", "tests", "docs", "lint"),
                    source="pyproject.toml")
        poetry = (data.get("tool") or {}).get("poetry") or {}
        if poetry.get("license"):
            project.append(("pyproject.toml [tool.poetry]", str(poetry["license"])))
        for name in (poetry.get("dependencies") or {}):
            if name.lower() != "python":
                add("pypi", name.lower(), source="pyproject.toml")
        for name in (poetry.get("dev-dependencies") or {}):
            add("pypi", name.lower(), dev=True, source="pyproject.toml")

    cargo = root / "Cargo.toml"
    if cargo.is_file():
        data = _parse_toml(cargo.read_text(encoding="utf-8"))
        lic = (data.get("package") or {}).get("license")
        if lic:
            project.append(("Cargo.toml", str(lic)))
        for section, dev in (("dependencies", False), ("build-dependencies", False), ("dev-dependencies", True)):
            for name in (data.get(section) or {}):
                add("cargo", name, dev=dev, source="Cargo.toml")

    gomod = root / "go.mod"
    if gomod.is_file():
        in_block = False
        for line in gomod.read_text(encoding="utf-8").splitlines():
            s = line.split("//", 1)[0].strip()
            if s.startswith("require ("):
                in_block = True
                continue
            if in_block and s == ")":
                in_block = False
                continue
            if s.startswith("require "):
                s = s[len("require "):].strip()
            elif not in_block:
                continue
            parts = s.split()
            if len(parts) >= 2:
                add("go", parts[0], source="go.mod")

    for name in ("LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING", "LICENCE"):
        f = root / name
        if f.is_file():
            guessed = license_from_text(f.read_text(encoding="utf-8", errors="replace"))
            if guessed:
                project.append((f"{name} (text match)", guessed))
            break

    return {"project_candidates": project, "dependencies": list(deps.values())}


def load_license_data(path: Path) -> dict[str, str]:
    """Read extra license info. Returns {lowercased name: license}."""
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    out: dict[str, str] = {}
    if path.suffix.lower() == ".csv":
        rows = [r for r in csv.reader(io.StringIO(text)) if len(r) >= 2 and r[0].strip()]
        name_idx, lic_idx = 0, None
        header_cell = re.compile(r"[a-z _-]*licen[cs]es?[a-z _-]*")
        if rows and any(header_cell.fullmatch(c.strip().lower()) for c in rows[0]):
            header = [c.strip().lower() for c in rows.pop(0)]
            lic_idx = next(i for i, c in enumerate(header) if header_cell.fullmatch(c))
            name_idx = next((i for i, c in enumerate(header) if c in ("name", "package", "module")), 0)
        for row in rows:
            idx = lic_idx if lic_idx is not None else (len(row) - 1 if len(row) >= 3 else 1)
            if idx < len(row):
                out[row[name_idx].strip().lower()] = row[idx].strip()
        return out
    data = json.loads(text)
    if isinstance(data, dict) and isinstance(data.get("packages"), list):  # cargo metadata
        data = data["packages"]
    if isinstance(data, list):  # pip-licenses / cargo metadata
        for item in data:
            if not isinstance(item, dict):
                continue
            name = item.get("Name") or item.get("name")
            lic = item.get("License") or item.get("license") or ""
            if name:
                out[str(name).lower()] = str(lic or "")
        return out
    for key, value in data.items():
        name = key
        if "@" in key[1:]:  # license-checker: "pkg@1.2.3" or "@scope/pkg@1.2.3"
            name = key[: key.rfind("@")]
        if isinstance(value, dict):
            lic = value.get("licenses") or value.get("license") or ""
            if isinstance(lic, list):
                lic = " OR ".join(str(x) for x in lic)
        else:
            lic = value
        out[name.lower()] = str(lic)
    return out


# ---------- report ----------

def analyze(project_license: str, deps: list[dict]) -> dict:
    project = evaluate(project_license or "")
    rows = []
    for d in deps:
        ev = evaluate(d.get("license", ""))
        verdict, reason = check(project, ev, dev=d.get("dev", False))
        if ev.get("note") and ev["note"] not in reason and ev["note"] != "no license declared":
            reason = f"{reason}; {ev['note']}"
        rows.append(dict(d, normalized=ev["id"] + ("-" + ev["variant"] if ev["variant"] else ""),
                         category=ev["category"], verdict=verdict, reason=reason))
    order = {"conflict": 0, "unknown": 1, "review": 2, "ok": 3}
    rows.sort(key=lambda r: (order[r["verdict"]], r["ecosystem"], r["name"]))
    counts = {k: sum(1 for r in rows if r["verdict"] == k) for k in order}
    return {"project": project, "project_license": project_license, "rows": rows, "counts": counts}


def render_markdown(result: dict, sources: list[tuple[str, str]] | None = None) -> str:
    p = result["project"]
    c = result["counts"]
    lines = ["# License compatibility report", "",
             f"> {DISCLAIMER}", "",
             f"**Project license:** {result['project_license'] or 'none found'} "
             f"(read as `{p['id']}{'-' + p['variant'] if p['variant'] else ''}`, {p['category']})", ""]
    if sources:
        lines.append("Declared in: " + "; ".join(f"{s}: `{lic}`" for s, lic in sources))
        lines.append("")
    lines += [f"**Dependencies checked:** {len(result['rows'])} | "
              f"conflict: {c['conflict']} | unknown: {c['unknown']} | review: {c['review']} | ok: {c['ok']}", ""]
    flagged = [r for r in result["rows"] if r["verdict"] != "ok"]
    if flagged:
        lines += ["## Needs attention", "",
                  "| Verdict | Package | Ecosystem | License | Category | Dev | Why |",
                  "|---|---|---|---|---|---|---|"]
        for r in flagged:
            lines.append(f"| {r['verdict']} | `{r['name']}` | {r['ecosystem']} | {r['license'] or '?'} | "
                         f"{r['category']} | {'yes' if r['dev'] else 'no'} | {r['reason']} |")
        lines.append("")
    else:
        lines += ["No conflicts or unknown licenses found.", ""]
    ok = [r for r in result["rows"] if r["verdict"] == "ok"]
    if ok:
        lines += ["## Compatible", "", "| Package | Ecosystem | License |", "|---|---|---|"]
        for r in ok:
            lines.append(f"| `{r['name']}` | {r['ecosystem']} | {r['license']} |")
        lines.append("")
    lines += ["## How to read this", "",
              "- **conflict**: the table says these licenses usually cannot be combined the way most projects ship. "
              "Replace the dependency, get an exception, or relicense (talk to a lawyer).",
              "- **unknown**: no license data. Fill it in with `--licenses` or check the package page.",
              "- **review**: allowed with conditions (weak copyleft, network clause, dev-only).",
              "- **ok**: permissive; keep the notices.", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Flag dependency licenses that may conflict with your project license. "
                                             "Not legal advice.")
    ap.add_argument("path", nargs="?", default=".", help="repository root to scan (default: .)")
    ap.add_argument("--project-license", help="override the project license (SPDX id or expression)")
    ap.add_argument("--licenses", action="append", default=[], metavar="FILE",
                    help="extra license data (license-checker/pip-licenses/cargo metadata JSON, map JSON, or CSV)")
    ap.add_argument("--no-scan", action="store_true", help="do not read manifests; use only --licenses data")
    ap.add_argument("--format", choices=["markdown", "json"], default="markdown")
    ap.add_argument("--fail-on", choices=["conflict", "unknown", "never"], default="never",
                    help="exit 1 when any dependency has this verdict (unknown also fails on conflict)")
    ap.add_argument("-o", "--output", help="write the report to this file")
    args = ap.parse_args(argv)

    root = Path(args.path)
    scanned = {"project_candidates": [], "dependencies": []} if args.no_scan else scan_repo(root)
    extra: dict[str, str] = {}
    for f in args.licenses:
        extra.update(load_license_data(Path(f)))
    deps = scanned["dependencies"]
    known = {d["name"].lower() for d in deps}
    for d in deps:
        if not d["license"] and d["name"].lower() in extra:
            d["license"] = extra[d["name"].lower()]
    for name, lic in sorted(extra.items()):
        if name not in known:
            deps.append({"ecosystem": "extra", "name": name, "license": lic, "dev": False, "source": "--licenses"})

    candidates = scanned["project_candidates"]
    project_license = args.project_license or (candidates[0][1] if candidates else "")
    result = analyze(project_license, deps)
    if args.format == "json":
        out = json.dumps({"disclaimer": DISCLAIMER, "project_license": project_license,
                          "project": result["project"], "declared": candidates,
                          "counts": result["counts"], "dependencies": result["rows"]}, indent=2) + "\n"
    else:
        out = render_markdown(result, candidates)
    if args.output:
        Path(args.output).write_bytes((out).encode("utf-8"))
    else:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        sys.stdout.write(out)
    c = result["counts"]
    if args.fail_on == "conflict" and c["conflict"]:
        return 1
    if args.fail_on == "unknown" and (c["conflict"] or c["unknown"]):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
