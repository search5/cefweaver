"""The wiki (docs/llm-wiki) must stay consistent: see docs/llm-wiki/SCHEMA.md, "lint"."""

import subprocess
import sys
import unittest
from pathlib import Path

LINT = Path(__file__).resolve().parent.parent / "docs" / "llm-wiki" / "lint.py"


class WikiLint(unittest.TestCase):
    @unittest.skipUnless(LINT.is_file(), "the wiki is not in this checkout")
    def test_wiki_passes_the_mechanical_checks(self):
        result = subprocess.run([sys.executable, "-I", str(LINT), "--quiet"],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
