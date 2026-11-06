"""Structural checks for the whole pack: frontmatter, manifests, README coverage, license."""
import json
import re
import unittest

from _load import REPO

REPO_NAME = "maintainer-skill"


def frontmatter(path):
    """Parse a simple YAML frontmatter block by hand. Supports `key: value` and `key: >-` folded blocks."""
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---", 4)
    if end == -1:
        return None
    data, key = {}, None
    for line in text[4:end].split("\n"):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        m = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if m and not line.startswith((" ", "\t")):
            key, value = m.group(1), m.group(2).strip()
            if value in (">", ">-", "|", "|-"):
                data[key] = ""
            else:
                data[key] = value.strip("\"'")
        elif key is not None:
            data[key] = (data[key] + " " + line.strip()).strip()
    return data


class SkillTests(unittest.TestCase):
    def skill_dirs(self):
        return sorted(p for p in (REPO / "skills").iterdir() if p.is_dir())

    def test_has_skills(self):
        self.assertGreaterEqual(len(self.skill_dirs()), 7)

    def test_skill_frontmatter(self):
        for d in self.skill_dirs():
            with self.subTest(skill=d.name):
                skill_md = d / "SKILL.md"
                self.assertTrue(skill_md.is_file(), f"{d.name} has no SKILL.md")
                fm = frontmatter(skill_md)
                self.assertIsNotNone(fm, "missing frontmatter")
                self.assertEqual(fm.get("name"), d.name)
                self.assertRegex(d.name, r"^maintainer-[a-z0-9-]+$")
                desc = fm.get("description", "")
                self.assertTrue(desc, "missing description")
                self.assertIn("Use when", desc)
                self.assertLess(len(desc), 1024)

    def test_skill_length(self):
        for d in self.skill_dirs():
            with self.subTest(skill=d.name):
                n = len((d / "SKILL.md").read_text(encoding="utf-8").splitlines())
                self.assertTrue(60 <= n <= 200, f"{d.name}/SKILL.md has {n} lines")

    def test_referenced_scripts_exist(self):
        for d in self.skill_dirs():
            text = (d / "SKILL.md").read_text(encoding="utf-8")
            for script in re.findall(r"\$\{CLAUDE_SKILL_DIR\}/([\w.-]+\.py)", text):
                with self.subTest(skill=d.name, script=script):
                    self.assertTrue((d / script).is_file())

    def test_every_script_has_tests(self):
        for script in (REPO / "skills").glob("*/*.py"):
            with self.subTest(script=script.name):
                self.assertTrue((REPO / "tests" / f"test_{script.stem}.py").is_file())


class AgentTests(unittest.TestCase):
    def test_agent_frontmatter(self):
        agents = sorted((REPO / "agents").glob("*.md"))
        self.assertGreaterEqual(len(agents), 3)
        for a in agents:
            with self.subTest(agent=a.name):
                fm = frontmatter(a)
                self.assertIsNotNone(fm)
                self.assertEqual(fm.get("name"), a.stem)
                self.assertTrue(fm.get("description"))
                self.assertTrue(fm.get("tools"))


class ManifestTests(unittest.TestCase):
    def load(self, name):
        return json.loads((REPO / ".claude-plugin" / name).read_text(encoding="utf-8"))

    def test_marketplace(self):
        m = self.load("marketplace.json")
        self.assertEqual(m["name"], REPO_NAME)
        self.assertEqual(m["owner"]["name"], "Vivek Bhange")
        self.assertEqual(len(m["plugins"]), 1)
        plugin = m["plugins"][0]
        self.assertEqual(plugin["name"], REPO_NAME)
        self.assertEqual(plugin["source"], "./")
        self.assertEqual(plugin["category"], "development")

    def test_plugin(self):
        p = self.load("plugin.json")
        self.assertEqual(p["name"], REPO_NAME)
        self.assertEqual(p["version"], "1.0.0")
        self.assertEqual(p["license"], "MIT")
        self.assertIn("claude-code", p["keywords"])
        self.assertIn("claude-skills", p["keywords"])
        self.assertTrue(6 <= len(p["keywords"]) <= 10)
        self.assertTrue(p["repository"].endswith("/" + REPO_NAME))


class DocsTests(unittest.TestCase):
    def test_readme_mentions_every_skill_and_agent(self):
        readme = (REPO / "README.md").read_text(encoding="utf-8")
        for d in (REPO / "skills").iterdir():
            if d.is_dir():
                with self.subTest(skill=d.name):
                    self.assertIn(d.name, readme)
        for a in (REPO / "agents").glob("*.md"):
            with self.subTest(agent=a.stem):
                self.assertIn(a.stem, readme)

    def test_license(self):
        text = (REPO / "LICENSE").read_text(encoding="utf-8")
        self.assertIn("MIT", text)
        self.assertIn("Copyright (c) 2026 Vivek Bhange", text)

    def test_required_files(self):
        for name in ("README.md", "LICENSE", "CONTRIBUTING.md", "CHANGELOG.md", ".gitignore"):
            with self.subTest(file=name):
                self.assertTrue((REPO / name).is_file())
        self.assertIn("## [1.0.0] - 2026-11-07", (REPO / "CHANGELOG.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
