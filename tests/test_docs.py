"""The site for people (docs/, Jekyll, published by GitHub Pages) must stay true to the repository.

The wiki (llm-wiki/) is the notes of the work and is not published; the pages here are written for people who use
cefweaver. These tests keep them from drifting: every page has a title and is reachable from the index, the links
resolve, the code of the quick start is the code of the example, and the installation and toolkit pages speak of every
extra of pyproject.toml and every toolkit module.
"""

import ast
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
PAGES = sorted(DOCS.glob("*.md"))
LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)\)")


def read(path):
    return path.read_text(encoding="utf-8")


def front_matter(text):
    match = re.match(r"---\n(.*?)\n---\n", text, re.S)
    return dict(line.split(":", 1) for line in match.group(1).splitlines() if ":" in line) if match else None


def code_after_the_docstring(path):
    text = read(path)
    first = ast.parse(text).body[0]
    return "\n".join(text.split("\n")[first.end_lineno:]).strip("\n") + "\n"


@unittest.skipUnless((ROOT / ".git").exists(), "not a checkout of the repository")
class Site(unittest.TestCase):
    def test_the_site_is_configured_for_jekyll_on_github_pages(self):
        config = read(DOCS / "_config.yml")
        for key in ("title:", "description:", "lang: ko", "theme: jekyll-theme-minimal", "jekyll-relative-links"):
            self.assertIn(key, config, key)

    def test_the_config_and_the_front_matter_are_valid_yaml(self):
        # Jekyll reads them as YAML: a colon in a title or a bad indent breaks the page or the whole build
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML is not installed")
        config = yaml.safe_load(read(DOCS / "_config.yml"))
        self.assertEqual(config["theme"], "jekyll-theme-minimal")
        # the theme draws the pages only with a layout: GitHub Pages fills it in by default, a plain Jekyll does not
        self.assertEqual(config["defaults"], [{"scope": {"path": ""}, "values": {"layout": "default"}}])
        self.assertEqual(sorted(config["plugins"]), ["jekyll-relative-links", "jekyll-seo-tag"])
        self.assertTrue(config["relative_links"]["enabled"])
        for page in PAGES:
            block = re.match(r"---\n(.*?)\n---\n", read(page), re.S).group(1)
            data = yaml.safe_load(block)
            self.assertIsInstance(data.get("title"), str, page.name)

    def test_the_style_sheet_has_the_front_matter_that_makes_jekyll_process_it(self):
        text = read(DOCS / "assets" / "css" / "style.scss")
        self.assertTrue(text.startswith("---\n---\n"), "without front matter Jekyll copies the file instead of building it")
        self.assertIn('@import "{{ site.theme }}";', text)

    def test_the_menu_lists_every_page_with_its_own_title(self):
        # java-cef has no menu: the pages are reached from the list in README.md. Here the sidebar of every page has one
        entries = re.findall(r"- title: (.+)\n  url: (\S+)", read(DOCS / "_data" / "navigation.yml"))
        by_url = {url: title.strip() for title, url in entries}
        self.assertEqual(len(entries), len(by_url), "a page is listed twice")
        expected = {}
        for page in PAGES:
            url = "/" if page.name == "index.md" else "/%s.html" % page.stem
            expected[url] = front_matter(read(page))["title"].strip()
        self.assertEqual(by_url, expected)

    def test_the_layout_shows_the_menu_and_the_page(self):
        layout = read(DOCS / "_layouts" / "default.html")
        self.assertIn("site.data.navigation", layout)
        self.assertIn("{{ content }}", layout)
        self.assertIn("{% seo %}", layout)                     # what the theme's own layout has in its head

    def test_the_style_sheet_keeps_the_tables_whole_and_has_dark_mode_and_a_phone_layout(self):
        text = read(DOCS / "assets" / "css" / "style.scss")
        self.assertIn("overflow-x: auto", text)
        self.assertIn("prefers-color-scheme: dark", text)
        self.assertIn("max-width: 720px", text)

    def test_there_are_pages(self):
        self.assertGreaterEqual(len(PAGES), 8, [p.name for p in PAGES])
        self.assertTrue((DOCS / "index.md").is_file())

    def test_every_page_has_a_title_in_its_front_matter(self):
        for page in PAGES:
            data = front_matter(read(page))
            self.assertIsNotNone(data, page.name)
            self.assertTrue(data.get("title", "").strip(), page.name)

    def test_the_links_between_pages_resolve(self):
        for page in PAGES:
            for target in LINK.findall(read(page)):
                if re.match(r"[a-z]+:", target) or target.startswith("#"):
                    continue                                         # another site, or a place in this page
                path = target.split("#")[0]
                self.assertTrue((page.parent / path).resolve().is_file(), "%s links to %s" % (page.name, target))

    def test_the_index_leads_to_every_page(self):
        linked = {target.split("#")[0] for target in LINK.findall(read(DOCS / "index.md"))}
        for page in PAGES:
            if page.name != "index.md":
                self.assertIn(page.name, linked, "index.md does not link %s" % page.name)

    def test_the_wiki_is_not_published_and_not_pointed_at_by_a_path_under_docs(self):
        self.assertFalse((DOCS / "llm-wiki").exists())
        for page in PAGES:
            self.assertNotIn("docs/llm-wiki", read(page), page.name)

    def test_the_quick_start_shows_the_code_of_the_example(self):
        code = code_after_the_docstring(ROOT / "examples" / "tk" / "quickstart.py")
        self.assertIn(code, read(DOCS / "quickstart.md"))

    def test_the_installation_page_speaks_of_every_extra_of_pyproject(self):
        text = read(ROOT / "pyproject.toml")
        block = text.split("[project.optional-dependencies]")[1].split("[project.urls]")[0]
        extras = re.findall(r"^(\w+) = \[", block, re.M)
        self.assertTrue(extras)
        page = read(DOCS / "installation.md")
        for extra in extras:
            self.assertIn("cefweaver[%s]" % extra, page, extra)

    def test_the_toolkit_page_speaks_of_every_toolkit_module(self):
        modules = [p.stem for p in (ROOT / "cefweaver" / "ui" / "toolkits").glob("*.py") if p.stem != "__init__"]
        self.assertGreaterEqual(len(modules), 6, modules)
        page = read(DOCS / "toolkits.md")
        for module in modules:
            self.assertIn("cefweaver.ui.toolkits.%s" % module, page, module)

    def test_no_page_is_left_over_from_sphinx(self):
        for name in ("conf.py", "index.rst", "Makefile", "make.bat"):
            self.assertFalse((DOCS / name).exists(), name)


if __name__ == "__main__":
    unittest.main()
