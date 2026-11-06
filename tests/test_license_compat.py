import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from _load import load

lc = load("maintainer-license-check", "license_compat")


class NormalizeTests(unittest.TestCase):
    def test_aliases(self):
        cases = {
            "MIT": "MIT", "MIT License": "MIT", "Apache 2.0": "Apache-2.0",
            "Apache License, Version 2.0": "Apache-2.0", "Apache Software License": "Apache-2.0",
            "BSD License": "BSD", "BSD-3-Clause": "BSD-3-Clause", "ISC": "ISC",
            "GPLv3": "GPL-3.0", "LGPL-2.1": "LGPL-2.1", "MPL 2.0": "MPL-2.0",
            "UNLICENSED": "Proprietary", "Unlicense": "Unlicense",
            "Python Software Foundation License": "PSF-2.0",
        }
        for raw, want in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(lc.normalize(raw)[0], want)

    def test_variants(self):
        self.assertEqual(lc.normalize("GPL-2.0-or-later"), ("GPL-2.0", "or-later"))
        self.assertEqual(lc.normalize("GPL-3.0-only"), ("GPL-3.0", "only"))
        self.assertEqual(lc.normalize("GPL-2.0+"), ("GPL-2.0", "or-later"))
        self.assertEqual(lc.normalize("GPL v3 or later"), ("GPL-3.0", "or-later"))

    def test_unknown(self):
        self.assertEqual(lc.normalize("Some Custom Thing")[0], "UNKNOWN")
        self.assertEqual(lc.normalize("")[0], "UNKNOWN")


class EvaluateTests(unittest.TestCase):
    def test_tokenize_keeps_multiword_ids(self):
        self.assertEqual(lc._tokenize("(MIT OR Apache License 2.0) AND ISC"),
                         ["(", "MIT", "OR", "Apache License 2.0", ")", "AND", "ISC"])

    def test_or_picks_least_restrictive(self):
        self.assertEqual(lc.evaluate("GPL-3.0 OR MIT")["category"], lc.PERMISSIVE)
        self.assertEqual(lc.evaluate("MIT OR Apache-2.0")["category"], lc.PERMISSIVE)

    def test_and_picks_most_restrictive(self):
        r = lc.evaluate("MIT AND GPL-3.0")
        self.assertEqual((r["id"], r["category"]), ("GPL-3.0", lc.STRONG))

    def test_precedence_and_parens(self):
        self.assertEqual(lc.evaluate("(MIT OR Apache-2.0) AND Unicode-DFS-2016")["category"], lc.PERMISSIVE)
        self.assertEqual(lc.evaluate("MIT OR GPL-3.0 AND LGPL-2.1")["category"], lc.PERMISSIVE)
        self.assertEqual(lc.evaluate("(MIT OR GPL-3.0) AND AGPL-3.0")["id"], "AGPL-3.0")

    def test_slash_and_lowercase_or(self):
        self.assertEqual(lc.evaluate("MIT/Apache-2.0")["category"], lc.PERMISSIVE)
        self.assertEqual(lc.evaluate("GPL-3.0 or MIT")["category"], lc.PERMISSIVE)

    def test_with_exception(self):
        r = lc.evaluate("GPL-2.0 WITH Classpath-exception-2.0")
        self.assertEqual(r["category"], lc.WEAK)
        self.assertIn("Classpath", r["note"])

    def test_empty(self):
        self.assertEqual(lc.evaluate("")["category"], lc.UNKNOWN)


class CheckTests(unittest.TestCase):
    def verdict(self, project, dep, dev=False):
        return lc.check(lc.evaluate(project), lc.evaluate(dep), dev)[0]

    def test_matrix(self):
        cases = [
            ("MIT", "BSD-3-Clause", "ok"),
            ("MIT", "LGPL-3.0", "review"),
            ("MIT", "MPL-2.0", "review"),
            ("MIT", "GPL-3.0", "conflict"),
            ("Apache-2.0", "AGPL-3.0", "conflict"),
            ("MIT", "SSPL-1.0", "conflict"),
            ("MIT", "", "unknown"),
            ("GPL-3.0", "MIT", "ok"),
            ("GPL-3.0", "GPL-3.0", "ok"),
            ("GPL-3.0", "GPL-2.0-or-later", "ok"),
            ("GPL-3.0", "GPL-2.0-only", "conflict"),
            ("GPL-2.0-only", "Apache-2.0", "conflict"),
            ("GPL-2.0-or-later", "Apache-2.0", "ok"),
            ("GPL-2.0-only", "GPL-3.0", "conflict"),
            ("GPL-2.0-or-later", "GPL-3.0", "review"),
            ("GPL-3.0", "AGPL-3.0", "review"),
            ("GPL-3.0", "EPL-2.0", "review"),
            ("GPL-3.0", "CDDL-1.0", "conflict"),
            ("", "MIT", "review"),
        ]
        for project, dep, want in cases:
            with self.subTest(project=project, dep=dep):
                self.assertEqual(self.verdict(project, dep), want)

    def test_dev_dependency_softens_conflict(self):
        verdict, reason = lc.check(lc.evaluate("MIT"), lc.evaluate("GPL-3.0"), dev=True)
        self.assertEqual(verdict, "review")
        self.assertIn("dev-only", reason)

    def test_agpl_network_note(self):
        _, reason = lc.check(lc.evaluate("AGPL-3.0"), lc.evaluate("AGPL-3.0"))
        self.assertIn("network", reason)


class MiniTomlTests(unittest.TestCase):
    TOML = (
        "[project]\n"
        "name = \"demo\"\n"
        "license = {text = \"MIT\"}\n"
        "dependencies = [\n"
        "  \"requests>=2.0\",  # http\n"
        "  'click[extra]~=8.1',\n"
        "]\n"
        "\n"
        "[project.optional-dependencies]\n"
        "dev = [\"pytest\"]\n"
        "\n"
        "[tool.poetry.dependencies]\n"
        "python = \"^3.9\"\n"
        "rich = { version = \"13\" }\n"
    )

    def test_subset(self):
        data = lc.mini_toml(self.TOML)
        self.assertEqual(data["project"]["license"], {"text": "MIT"})
        self.assertEqual(data["project"]["dependencies"], ["requests>=2.0", "click[extra]~=8.1"])
        self.assertEqual(data["project"]["optional-dependencies"]["dev"], ["pytest"])
        self.assertEqual(set(data["tool"]["poetry"]["dependencies"]), {"python", "rich"})


def write(root: Path, rel: str, text: str):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


class ScanTests(unittest.TestCase):
    def test_scan_all_ecosystems(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "package.json", json.dumps({
                "name": "demo", "license": "MIT",
                "dependencies": {"left-pad": "^1.0.0", "gpl-lib": "1.0.0"},
                "devDependencies": {"jest": "^29"}}))
            write(root, "package-lock.json", json.dumps({"lockfileVersion": 3, "packages": {
                "": {"name": "demo"},
                "node_modules/left-pad": {"version": "1.3.0", "license": "WTFPL"},
                "node_modules/gpl-lib": {"version": "1.0.0", "license": "GPL-3.0"},
                "node_modules/jest": {"version": "29.0.0", "license": "MIT", "dev": True},
                "node_modules/@scope/pkg": {"version": "1.0.0", "license": "ISC"}}}))
            write(root, "requirements.txt", "requests==2.31.0\n# comment\n-r other.txt\nFlask>=2\n")
            write(root, "requirements-dev.txt", "pytest\n")
            write(root, "pyproject.toml", MiniTomlTests.TOML)
            write(root, "Cargo.toml", "[package]\nname = \"x\"\nlicense = \"MIT OR Apache-2.0\"\n\n"
                                      "[dependencies]\nserde = \"1\"\ntokio = { version = \"1\" }\n\n"
                                      "[dev-dependencies]\ncriterion = \"0.5\"\n")
            write(root, "go.mod", "module example.com/x\n\ngo 1.21\n\nrequire (\n\tgithub.com/pkg/errors v0.9.1\n"
                                  "\tgolang.org/x/text v0.14.0 // indirect\n)\n\nrequire github.com/spf13/cobra v1.8.0\n")
            write(root, "LICENSE", "MIT License\n\nPermission is hereby granted, free of charge, to any person\n")
            scan = lc.scan_repo(root)
        sources = [s for s, _ in scan["project_candidates"]]
        self.assertEqual(scan["project_candidates"][0], ("package.json", "MIT"))
        self.assertIn("Cargo.toml", sources)
        self.assertIn("LICENSE (text match)", sources)
        deps = {(d["ecosystem"], d["name"]): d for d in scan["dependencies"]}
        self.assertEqual(deps[("npm", "gpl-lib")]["license"], "GPL-3.0")
        self.assertFalse(deps[("npm", "gpl-lib")]["dev"])
        self.assertTrue(deps[("npm", "jest")]["dev"])
        self.assertIn(("npm", "@scope/pkg"), deps)
        for key in [("pypi", "requests"), ("pypi", "flask"), ("pypi", "click"), ("pypi", "rich"),
                    ("cargo", "serde"), ("cargo", "tokio"), ("go", "github.com/pkg/errors"),
                    ("go", "golang.org/x/text"), ("go", "github.com/spf13/cobra")]:
            self.assertIn(key, deps)
        self.assertTrue(deps[("pypi", "pytest")]["dev"])
        self.assertTrue(deps[("cargo", "criterion")]["dev"])
        self.assertNotIn(("pypi", "python"), deps)

    def test_license_from_text(self):
        self.assertEqual(lc.license_from_text("GNU GENERAL PUBLIC LICENSE\n Version 3, 29 June 2007"), "GPL-3.0")
        self.assertEqual(lc.license_from_text("GNU GENERAL PUBLIC LICENSE\n Version 2, June 1991"), "GPL-2.0")
        self.assertEqual(lc.license_from_text("Apache License\nVersion 2.0, January 2004"), "Apache-2.0")
        self.assertEqual(lc.license_from_text(
            "Redistribution and use in source and binary forms ... Neither the name"), "BSD-3-Clause")
        self.assertEqual(lc.license_from_text("All rights reserved."), "")


class LicenseDataTests(unittest.TestCase):
    def test_formats(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "checker.json", json.dumps({
                "react@18.2.0": {"licenses": "MIT"}, "@babel/core@7.0.0": {"licenses": ["MIT", "Apache-2.0"]}}))
            write(root, "pip.json", json.dumps([{"Name": "Requests", "Version": "2", "License": "Apache 2.0"}]))
            write(root, "cargo.json", json.dumps({"packages": [{"name": "serde", "license": "MIT OR Apache-2.0"}]}))
            write(root, "map.json", json.dumps({"foo": "GPL-3.0"}))
            write(root, "deps.csv", "name,license\nbar,BSD-2-Clause\n")
            self.assertEqual(lc.load_license_data(root / "checker.json"),
                             {"react": "MIT", "@babel/core": "MIT OR Apache-2.0"})
            self.assertEqual(lc.load_license_data(root / "pip.json"), {"requests": "Apache 2.0"})
            self.assertEqual(lc.load_license_data(root / "cargo.json"), {"serde": "MIT OR Apache-2.0"})
            self.assertEqual(lc.load_license_data(root / "map.json"), {"foo": "GPL-3.0"})
            self.assertEqual(lc.load_license_data(root / "deps.csv"), {"bar": "BSD-2-Clause"})
            write(root, "go.csv", "github.com/pkg/errors,https://github.com/pkg/errors/LICENSE,BSD-2-Clause\n")
            self.assertEqual(lc.load_license_data(root / "go.csv"), {"github.com/pkg/errors": "BSD-2-Clause"})
            write(root, "hdr.csv", "version,license,name\n1.0,MIT,baz\n")
            self.assertEqual(lc.load_license_data(root / "hdr.csv"), {"baz": "MIT"})


class ReportTests(unittest.TestCase):
    def deps(self):
        return [
            {"ecosystem": "npm", "name": "a", "license": "MIT", "dev": False},
            {"ecosystem": "npm", "name": "b", "license": "GPL-3.0", "dev": False},
            {"ecosystem": "pypi", "name": "c", "license": "", "dev": False},
            {"ecosystem": "pypi", "name": "d", "license": "LGPL-3.0", "dev": False},
        ]

    def test_analyze_sorts_worst_first(self):
        r = lc.analyze("MIT", self.deps())
        self.assertEqual([row["verdict"] for row in r["rows"]], ["conflict", "unknown", "review", "ok"])
        self.assertEqual(r["counts"], {"conflict": 1, "unknown": 1, "review": 1, "ok": 1})

    def test_markdown_has_disclaimer_and_tables(self):
        md = lc.render_markdown(lc.analyze("MIT", self.deps()), [("package.json", "MIT")])
        self.assertIn("not legal advice", md)
        self.assertIn("## Needs attention", md)
        self.assertIn("| conflict | `b` |", md)
        self.assertIn("## Compatible", md)

    def test_cli_fail_on_and_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "deps.json", json.dumps({"gpl-thing": "GPL-3.0", "fine": "MIT"}))
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = lc.main([str(root), "--no-scan", "--project-license", "MIT",
                              "--licenses", str(root / "deps.json"), "--format", "json",
                              "--fail-on", "conflict"])
            self.assertEqual(rc, 1)
            data = json.loads(buf.getvalue())
            self.assertEqual(data["counts"]["conflict"], 1)
            self.assertIn("legal advice", data["disclaimer"])
            out = root / "report.md"
            rc = lc.main([str(root), "--no-scan", "--project-license", "GPL-3.0",
                          "--licenses", str(root / "deps.json"), "-o", str(out), "--fail-on", "conflict"])
            self.assertEqual(rc, 0)
            self.assertIn("# License compatibility report", out.read_text(encoding="utf-8"))

    def test_cli_fills_scanned_deps_from_extra_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "requirements.txt", "requests\n")
            write(root, "pip.json", json.dumps([{"Name": "requests", "License": "Apache Software License"}]))
            buf = io.StringIO()
            with redirect_stdout(buf):
                lc.main([str(root), "--project-license", "MIT", "--licenses", str(root / "pip.json"),
                         "--format", "json"])
            rows = json.loads(buf.getvalue())["dependencies"]
            self.assertEqual(len(rows), 1)
            self.assertEqual((rows[0]["name"], rows[0]["verdict"]), ("requests", "ok"))


if __name__ == "__main__":
    unittest.main()
