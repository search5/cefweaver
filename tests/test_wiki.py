"""The wiki (llm-wiki/, at the root of the repository) must stay consistent: see llm-wiki/SCHEMA.md, "lint"."""

import subprocess
import sys
import unittest
from pathlib import Path

LINT = Path(__file__).resolve().parent.parent / "llm-wiki" / "lint.py"


ROOT = Path(__file__).resolve().parent.parent


class WikiPlace(unittest.TestCase):
    def test_in_a_checkout_the_wiki_is_at_the_root_not_under_docs(self):
        # the lint test below skips where there is no wiki (a source distribution): it must not skip by a wrong path
        if not (ROOT / ".git").exists():
            self.skipTest("not a checkout of the repository")
        self.assertTrue(LINT.is_file(), "the wiki is expected at llm-wiki/ (docs/ is the site for people)")
        self.assertFalse((ROOT / "docs" / "llm-wiki").exists(), "the wiki moved out of docs/, which is published")


class WikiLint(unittest.TestCase):
    @unittest.skipUnless(LINT.is_file(), "the wiki is not in this checkout")
    def test_wiki_passes_the_mechanical_checks(self):
        result = subprocess.run([sys.executable, "-I", str(LINT), "--quiet"],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
