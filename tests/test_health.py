import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from _load import load

health = load("maintainer-health", "health")

GOOD_README = "\n".join([
    "# demo", "", "Demo does one thing well.", "", "## Install", "", "pip install demo", "",
    "## Usage", "", "demo run", "", "## Contributing", "", "See CONTRIBUTING.md.", "",
    "## License", "", "MIT", "", "More words.", "Even more words.",
])


def write(root: Path, rel: str, text: str = "x\n"):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def full_repo(root: Path):
    write(root, "README.md", GOOD_README)
    write(root, "LICENSE", "MIT License\n")
    write(root, "CONTRIBUTING.md")
    write(root, ".github/SECURITY.md")
    write(root, "CODE_OF_CONDUCT.md")
    write(root, ".github/workflows/ci.yml", "on: push\n")
    write(root, "tests/test_x.py")
    write(root, ".github/ISSUE_TEMPLATE/bug.yml")
    write(root, ".github/pull_request_template.md")
    write(root, "CHANGELOG.md")
    write(root, ".gitignore")
    write(root, ".github/CODEOWNERS", "* @me\n")


def by_id(results):
    return {r["id"]: r for r in results}


class HealthTests(unittest.TestCase):
    def test_weights_sum_to_100(self):
        with tempfile.TemporaryDirectory() as tmp:
            results = health.check_repo(Path(tmp))
        self.assertEqual(sum(r["max"] for r in results), 100)

    def test_empty_repo_scores_zero_with_fixes(self):
        with tempfile.TemporaryDirectory() as tmp:
            results = health.check_repo(Path(tmp))
        s = health.summarize(results)
        self.assertEqual((s["score"], s["grade"]), (0, "F"))
        self.assertTrue(all(r["fix"] for r in results))

    def test_full_repo_scores_100(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            full_repo(root)
            results = health.check_repo(root)
        failed = [r["id"] for r in results if not r["passed"]]
        self.assertEqual(failed, [])
        self.assertEqual(health.summarize(results), {"score": 100, "points": 100, "max": 100, "grade": "A"})

    def test_case_insensitive_and_variants(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "readme.rst", GOOD_README)
            write(root, "LICENSE-MIT")
            write(root, "docs/contributing.md")
            write(root, "History.md")
            write(root, ".gitlab-ci.yml")
            write(root, "src/pkg/parser_test.go")
            results = by_id(health.check_repo(root))
        for cid in ("readme", "license", "contributing", "changelog", "ci", "tests"):
            self.assertTrue(results[cid]["passed"], cid)
        self.assertEqual(results["contributing"]["evidence"], "docs/contributing.md")
        self.assertEqual(results["tests"]["evidence"], "src/pkg/parser_test.go")

    def test_short_readme_gets_partial_credit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "README.md", "# x\n\nTiny.\n")
            r = by_id(health.check_repo(root))["readme"]
        self.assertFalse(r["passed"])
        self.assertEqual(r["points"], 5)

    def test_tests_inside_node_modules_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "node_modules/lib/tests/a.test.js")
            self.assertIsNone(health.find_tests(root))
            write(root, "src/app.spec.ts")
            self.assertEqual(health.find_tests(root), "src/app.spec.ts")

    def test_grade_cutoffs(self):
        self.assertEqual([health.grade(x) for x in (95, 90, 80, 61, 45, 10)], ["A", "A", "B", "C", "D", "F"])

    def test_markdown_orders_fixes_by_gain(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "README.md", GOOD_README)
            md = health.render_markdown(root, health.check_repo(root), name="demo")
        self.assertIn("# Repo health: demo", md)
        self.assertIn("## Fixes, biggest gain first", md)
        self.assertLess(md.index("**LICENSE file** (+15)"), md.index("**.gitignore** (+2)"))
        self.assertIn("| [x] | README exists and has substance | 10/10 |", md)

    def test_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            full_repo(root)
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = health.main([str(root), "--format", "json", "--min-score", "90"])
            self.assertEqual(rc, 0)
            self.assertEqual(json.loads(buf.getvalue())["summary"]["score"], 100)
            empty = root / "empty"
            empty.mkdir()
            out = root / "health.md"
            rc = health.main([str(empty), "--min-score", "50", "-o", str(out)])
            self.assertEqual(rc, 1)
            self.assertIn("Score: 0/100", out.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
