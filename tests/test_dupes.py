import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from _load import load

dupes = load("maintainer-triage", "dupes")

ISSUES = [
    {"number": 10, "title": "Crash when config file is empty", "state": "OPEN",
     "body": "Running `demo run` with an empty config.yml raises KeyError: 'name'."},
    {"number": 14, "title": "Add dark mode to the dashboard", "state": "OPEN", "body": "Would be nice."},
    {"number": 22, "title": "KeyError crash with empty config file", "state": "OPEN",
     "body": "If config.yml is empty I get KeyError: 'name' on startup."},
    {"number": 30, "title": "Dark mode for dashboard please", "state": "CLOSED", "body": ""},
    {"number": 31, "title": "Docs: typo in install section", "state": "OPEN", "body": "Small typo."},
]


class TokenTests(unittest.TestCase):
    def test_tokens_drop_noise(self):
        t = dupes.tokens("The app crashes with KeyError when I use https://x.y/z ```long trace```")
        self.assertIn("keyerror", t)
        self.assertIn("crashe", t)  # light plural stripping
        self.assertNotIn("the", t)
        self.assertNotIn("trace", t)
        self.assertFalse(any("http" in w for w in t))

    def test_jaccard(self):
        self.assertEqual(dupes.jaccard({"a", "b"}, {"a", "b"}), 1.0)
        self.assertEqual(dupes.jaccard(set(), {"a"}), 0.0)


class PairTests(unittest.TestCase):
    def test_finds_obvious_duplicates(self):
        pairs = dupes.find_pairs(ISSUES, threshold=0.3)
        found = {(p["keep"], p["duplicate"]) for p in pairs}
        self.assertIn((10, 22), found)
        self.assertIn((14, 30), found)
        self.assertNotIn((10, 31), found)
        top = pairs[0]
        self.assertEqual((top["keep"], top["duplicate"]), (10, 22))
        self.assertIn("keyerror", top["shared_words"])

    def test_only_one_issue(self):
        pairs = dupes.find_pairs(ISSUES, threshold=0.3, only=30)
        self.assertEqual([(p["keep"], p["duplicate"]) for p in pairs], [(14, 30)])

    def test_closed_pairs_skipped_by_default(self):
        issues = [{"number": 1, "title": "same title here", "state": "CLOSED"},
                  {"number": 2, "title": "same title here", "state": "CLOSED"}]
        self.assertEqual(dupes.find_pairs(issues), [])
        self.assertEqual(len(dupes.find_pairs(issues, include_closed_pairs=True)), 1)

    def test_high_threshold_filters(self):
        self.assertEqual(dupes.find_pairs(ISSUES, threshold=0.99), [])

    def test_deterministic(self):
        self.assertEqual(dupes.find_pairs(ISSUES, 0.2), dupes.find_pairs(list(reversed(ISSUES)), 0.2))

    def test_markdown(self):
        md = dupes.render_markdown(dupes.find_pairs(ISSUES, threshold=0.3), 0.3)
        self.assertIn("| Score | Keep (older) | Possible duplicate | Shared words |", md)
        self.assertIn("#30 Dark mode for dashboard please (closed)", md)
        self.assertIn("No likely duplicates found.", dupes.render_markdown([], 0.5))

    def test_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "issues.json"
            f.write_text(json.dumps(ISSUES), encoding="utf-8")
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = dupes.main([str(f), "--format", "json", "--threshold", "0.3"])
            self.assertEqual(rc, 0)
            self.assertEqual(json.loads(buf.getvalue())[0]["duplicate"], 22)


if __name__ == "__main__":
    unittest.main()
