"""The documentation (docs/, Sphinx with the Read the Docs theme) must stay true to the repository.

The text is the docstrings of the source code; docs/ holds the configuration, the pages that list the modules and the
translation catalogs. The wiki (llm-wiki/) is the notes of the work and is not published. These tests keep the
configuration, the page list and the catalogs from drifting; a full build runs only where Sphinx and the installed
package are available (docs/Makefile).
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
LANGUAGES = ("ko",)


def read(path):
    return path.read_text(encoding="utf-8")


@unittest.skipUnless((ROOT / ".git").exists(), "not a checkout of the repository")
class Site(unittest.TestCase):
    def test_the_configuration_uses_the_rtd_theme_and_napoleon(self):
        config = read(DOCS / "conf.py")
        for key in ('html_theme = "sphinx_rtd_theme"', "sphinx.ext.autodoc", "sphinx.ext.napoleon",
                    "napoleon_google_docstring = True", 'locale_dirs = ["locale/"]', "gettext_compact = False"):
            self.assertIn(key, config, key)

    def test_the_requirements_name_the_tools(self):
        text = read(DOCS / "requirements.txt")
        for name in ("sphinx", "sphinx-rtd-theme", "sphinx-intl"):
            self.assertRegex(text, r"(?m)^%s\b" % name)

    def test_nothing_is_left_over_from_jekyll(self):
        for name in ("_config.yml", "_layouts", "_data", "assets", "Gemfile"):
            self.assertFalse((DOCS / name).exists(), name)
        self.assertEqual(list(DOCS.glob("*.md")), [])

    def test_every_page_of_the_toctree_exists(self):
        index = read(DOCS / "index.rst")
        entries = re.findall(r"(?m)^   ((?:api|guide)/[\w-]+)$", index)
        self.assertTrue(entries)
        for entry in entries:
            self.assertTrue((DOCS / (entry + ".rst")).is_file(), entry)

    def test_every_page_is_in_the_toctree(self):
        index = read(DOCS / "index.rst")
        for folder in ("api", "guide"):
            for page in (DOCS / folder).glob("*.rst"):
                self.assertIn("%s/%s" % (folder, page.stem), index, page.name)

    def test_the_toolkit_page_has_every_toolkit_module(self):
        modules = [p.stem for p in (ROOT / "cefweaver" / "ui" / "toolkits").glob("*.py") if p.stem != "__init__"]
        self.assertGreaterEqual(len(modules), 6, modules)
        page = read(DOCS / "api" / "toolkits.rst")
        for module in modules:
            self.assertIn("cefweaver.ui.toolkits.%s" % module, page, module)

    def test_the_ui_page_has_every_ui_module(self):
        # the package documents what it exports (cefweaver.ui.__all__), the other modules are listed
        page = read(DOCS / "api" / "ui.rst")
        init = read(ROOT / "cefweaver" / "ui" / "__init__.py")
        for module in (ROOT / "cefweaver" / "ui").glob("*.py"):
            if module.stem == "__init__":
                continue
            exported = re.search(r"from \.%s import|from \. import [^\n]*\b%s\b" % (module.stem, module.stem), init)
            self.assertTrue(exported or "cefweaver.ui.%s" % module.stem in page, module.name)

    def test_the_build_checks_references_and_warnings(self):
        self.assertIn("nitpicky = True", read(DOCS / "conf.py"))
        self.assertIn("-W", read(DOCS / "Makefile"))

    def test_every_language_has_a_catalog_of_the_pages(self):
        for language in LANGUAGES:
            catalog = DOCS / "locale" / language / "LC_MESSAGES"
            for page in ["index"] + ["%s/%s" % (d, p.stem) for d in ("api", "guide") for p in (DOCS / d).glob("*.rst")]:
                self.assertTrue((catalog / (page + ".po")).is_file(), "%s: %s" % (language, page))

    def test_the_recipes_script_is_the_one_the_cookbook_shows(self):
        cookbook = read(DOCS / "guide" / "cookbook.rst")
        self.assertIn("literalinclude:: recipes/headless.py", cookbook)
        self.assertTrue((DOCS / "guide" / "recipes" / "headless.py").is_file())

    def test_the_page_titles_are_translated(self):
        for language in LANGUAGES:
            text = read(DOCS / "locale" / language / "LC_MESSAGES" / "index.po")
            self.assertRegex(text, r'msgid "Reference"\nmsgstr "[^"]+"')

    def test_the_built_files_are_not_tracked(self):
        ignore = read(ROOT / ".gitignore")
        self.assertIn("docs/_build/", ignore)
        self.assertIn("*.mo", ignore)


if __name__ == "__main__":
    unittest.main()
