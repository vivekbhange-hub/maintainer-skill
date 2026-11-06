import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from _load import load

cl = load("maintainer-release-notes", "changelog")

US, RS = "\x1f", "\x1e"


def record(h, author, subject, body=""):
    return f"{h}{US}{author}{US}{subject}{US}{body}{RS}\n"


SAMPLE = (
    record("a1b2c3d", "Ana Ruiz", "feat(cli): add --json output (#41)")
    + record("b2c3d4e", "Ben Ode", "fix: handle empty config file (#42)")
    + record("c3d4e5f", "Ana Ruiz", "docs: fix typo in README")
    + record("d4e5f6a", "dependabot[bot]", "chore(deps): bump lodash from 4.17.20 to 4.17.21")
    + record("e5f6a7b", "Chen Li", "refactor!: drop Python 3.8 support")
    + record("f6a7b8c", "Dee Park", "fix(auth): patch token leak CVE-2026-1234")
    + record("0a1b2c3", "Ben Ode", "Merge pull request #43 from ben/feature")
)


class ParseLogTests(unittest.TestCase):
    def test_record_format(self):
        commits = cl.parse_log(SAMPLE)
        self.assertEqual(len(commits), 7)
        self.assertEqual(commits[0]["author"], "Ana Ruiz")
        self.assertEqual(commits[0]["subject"], "feat(cli): add --json output (#41)")

    def test_oneline_format(self):
        commits = cl.parse_log("abc1234 fix: crash on start\ndef5678 Add dark mode\n")
        self.assertEqual([c["hash"] for c in commits], ["abc1234", "def5678"])
        self.assertEqual(commits[1]["subject"], "Add dark mode")

    def test_tab_format_and_crlf(self):
        commits = cl.parse_log("abc1234\tAna\tfeat: x\r\ndef5678\tBen\tfix: y\r\n")
        self.assertEqual([c["author"] for c in commits], ["Ana", "Ben"])
        self.assertEqual(commits[1]["subject"], "fix: y")

    def test_bare_subjects(self):
        commits = cl.parse_log("Fix the thing\n")
        self.assertEqual(commits[0]["subject"], "Fix the thing")
        self.assertEqual(commits[0]["hash"], "")


class ClassifyTests(unittest.TestCase):
    def c(self, subject, body=""):
        return cl.classify({"hash": "abc1234", "author": "x", "subject": subject, "body": body})

    def test_conventional_types(self):
        self.assertEqual(self.c("feat: new thing")["section"], "Added")
        self.assertEqual(self.c("fix(parser): off by one")["section"], "Fixed")
        self.assertEqual(self.c("perf: faster")["section"], "Changed")
        self.assertIsNone(self.c("docs: readme")["section"])
        self.assertIsNone(self.c("chore: tidy")["section"])

    def test_scope_and_pr(self):
        e = self.c("feat(cli): add flag (#12)")
        self.assertEqual(e["scope"], "cli")
        self.assertEqual(e["prs"], [12])
        self.assertEqual(e["description"], "Add flag")

    def test_breaking_bang(self):
        self.assertTrue(self.c("feat(api)!: rename endpoint")["breaking"])

    def test_breaking_footer(self):
        e = self.c("feat: new config loader", "Details.\n\nBREAKING CHANGE: config.yml is now required")
        self.assertTrue(e["breaking"])
        self.assertEqual(e["breaking_note"], "config.yml is now required")

    def test_breaking_internal_type_becomes_visible(self):
        e = self.c("chore!: drop node 16")
        self.assertTrue(e["breaking"])
        self.assertEqual(e["section"], "Changed")

    def test_security_fix(self):
        self.assertEqual(self.c("fix: sanitize input to prevent XSS")["section"], "Security")

    def test_non_conventional_heuristics(self):
        self.assertEqual(self.c("Fixed crash when list is empty")["section"], "Fixed")
        self.assertEqual(self.c("Add Windows support")["section"], "Added")
        self.assertEqual(self.c("Remove deprecated flag")["section"], "Removed")
        self.assertEqual(self.c("Deprecate old API")["section"], "Deprecated")
        self.assertEqual(self.c("Improve error messages")["section"], "Changed")
        self.assertIsNone(self.c("Typo in docs")["section"])
        self.assertTrue(self.c("Improve error messages")["guessed"])

    def test_unknown_conventional_type_falls_back(self):
        e = self.c("update: tweak colours")
        self.assertFalse(e["conventional"])
        self.assertEqual(e["section"], "Changed")

    def test_merge_and_release_skipped(self):
        self.assertTrue(self.c("Merge pull request #5 from x/y")["skip"])
        self.assertTrue(self.c("chore(release): 1.2.0")["skip"])
        self.assertTrue(self.c("v1.2.0")["skip"])
        self.assertFalse(self.c("Releases page now loads faster")["skip"])


class BumpTests(unittest.TestCase):
    def entries(self, *subjects):
        return [cl.classify({"hash": "", "author": "", "subject": s, "body": ""}) for s in subjects]

    def test_major(self):
        b = cl.suggest_bump(self.entries("feat!: x", "fix: y"), "1.4.2")
        self.assertEqual((b["bump"], b["next"]), ("major", "2.0.0"))

    def test_minor_keeps_v_prefix(self):
        b = cl.suggest_bump(self.entries("feat: x", "fix: y"), "v1.4.2")
        self.assertEqual((b["bump"], b["next"]), ("minor", "v1.5.0"))

    def test_patch(self):
        b = cl.suggest_bump(self.entries("fix: y"), "1.4.2")
        self.assertEqual((b["bump"], b["next"]), ("patch", "1.4.3"))

    def test_none(self):
        b = cl.suggest_bump(self.entries("docs: y", "chore: z"), "1.4.2")
        self.assertEqual((b["bump"], b["next"]), ("none", None))

    def test_pre_one_zero_breaking_is_minor(self):
        b = cl.suggest_bump(self.entries("feat!: x"), "0.3.1")
        self.assertEqual((b["bump"], b["next"]), ("minor", "0.4.0"))

    def test_bad_version(self):
        with self.assertRaises(ValueError):
            cl.suggest_bump(self.entries("fix: y"), "banana")


class BuildAndRenderTests(unittest.TestCase):
    def setUp(self):
        self.result = cl.build(SAMPLE, current="1.4.2")

    def test_groups(self):
        g = self.result["groups"]
        self.assertEqual(len(g["Added"]), 1)
        self.assertEqual(len(g["Fixed"]), 1)
        self.assertEqual(len(g["Security"]), 1)
        self.assertEqual(len(g["Changed"]), 1)
        self.assertEqual(len(self.result["internal"]), 2)

    def test_contributors_exclude_bots(self):
        self.assertEqual(self.result["contributors"], ["Ana Ruiz", "Ben Ode", "Chen Li", "Dee Park"])
        self.assertIn("dependabot[bot]", cl.build(SAMPLE, include_bots=True)["contributors"])

    def test_co_authors_credited(self):
        log = record("1234abc", "Ana Ruiz", "feat: pair work",
                     "Body.\n\nCo-authored-by: Sam Ito <sam@example.com>\n"
                     "Co-authored-by: github-actions[bot] <x@y>")
        self.assertEqual(cl.build(log)["contributors"], ["Ana Ruiz", "Sam Ito"])

    def test_markdown(self):
        md = cl.render_markdown(self.result, date="2026-11-07", repo_url="https://github.com/o/r")
        self.assertTrue(md.startswith("## [2.0.0] - 2026-11-07"))
        self.assertIn("- **cli:** Add --json output ([#41](https://github.com/o/r/pull/41))", md)
        self.assertIn("**BREAKING:** Drop Python 3.8 support", md)
        self.assertIn("> Breaking changes in this release:", md)
        self.assertNotIn("Merge pull request", md)
        self.assertNotIn("typo", md)
        self.assertLess(md.index("### Added"), md.index("### Changed"))
        self.assertLess(md.index("### Fixed"), md.index("### Security"))

    def test_markdown_unreleased_and_internal(self):
        md = cl.render_markdown(cl.build("abc1234 docs: readme\n", include_internal=True))
        self.assertTrue(md.startswith("## [Unreleased]"))
        self.assertIn("### Internal", md)

    def test_no_changes(self):
        self.assertIn("_No user-facing changes._", cl.render_markdown(cl.build("abc1234 chore: tidy\n")))

    def test_json(self):
        data = json.loads(cl.render_json(self.result))
        self.assertEqual(data["bump"]["next"], "2.0.0")
        self.assertEqual(len(data["breaking"]), 1)
        self.assertIn("Merge pull request #43 from ben/feature", data["skipped"])

    def test_deterministic(self):
        a = cl.render_markdown(cl.build(SAMPLE, "1.0.0"), date="2026-01-01")
        b = cl.render_markdown(cl.build(SAMPLE, "1.0.0"), date="2026-01-01")
        self.assertEqual(a, b)


class CliTests(unittest.TestCase):
    def test_cli_file_and_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "log.txt"
            log.write_text(SAMPLE, encoding="utf-8")
            out = Path(tmp) / "entry.md"
            rc = cl.main([str(log), "--current", "1.4.2", "--date", "2026-11-07", "-o", str(out)])
            self.assertEqual(rc, 0)
            self.assertIn("## [2.0.0] - 2026-11-07", out.read_text(encoding="utf-8"))

    def test_cli_json_stdout(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "log.txt"
            log.write_text("abc1234 feat: x\n", encoding="utf-8")
            buf = io.StringIO()
            with redirect_stdout(buf):
                cl.main([str(log), "--format", "json", "--current", "2.0.0"])
            self.assertEqual(json.loads(buf.getvalue())["bump"]["next"], "2.1.0")


if __name__ == "__main__":
    unittest.main()
