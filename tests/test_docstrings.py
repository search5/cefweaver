"""Every public module, class, function and method has a docstring (llm-wiki/pages/procedures/write-docstrings.md).

The modules in PENDING are not documented yet; remove a module from it when its docstrings are written.
"""

import ast
import re
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent.parent / "cefweaver"

# Modules that wait for their docstrings (paths relative to cefweaver/).
PENDING = set()


def missing(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = [] if ast.get_docstring(tree) else ["<module>"]

    def visit(node, prefix):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if child.name.startswith("_"):
                    continue
                if not ast.get_docstring(child):
                    found.append(prefix + child.name)
                if isinstance(child, ast.ClassDef):
                    visit(child, prefix + child.name + ".")
            elif isinstance(child, (ast.If, ast.Try, ast.With)):
                visit(child, prefix)

    visit(tree, "")
    return found


def missing_in_stub(path):
    """Public classes, methods and functions of the type stub (the generated API) without a docstring."""
    found = []
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
            if not ast.get_docstring(node):
                found.append(node.name)
            for method in node.body:
                if (isinstance(method, ast.FunctionDef) and not method.name.startswith("_")
                        and not ast.get_docstring(method)
                        and not any(isinstance(d, ast.Attribute) and d.attr == "setter"
                                    for d in method.decorator_list)):
                    found.append(node.name + "." + method.name)
        elif isinstance(node, ast.FunctionDef) and not node.name.startswith("_") and not ast.get_docstring(node):
            found.append(node.name)
    return found


@unittest.skipUnless(PACKAGE.is_dir(), "the source tree is not here")
class Docstrings(unittest.TestCase):
    def test_the_generated_api_has_a_docstring_everywhere(self):
        stub = PACKAGE / "_cefweaver.pyi"
        self.assertEqual(missing_in_stub(stub), [], "the generator writes them (tools/gen/docs.py)")

    def test_the_generated_docstrings_say_parameters_the_python_way(self):
        text = (PACKAGE / "_cefweaver.pyi").read_text(encoding="utf-8")
        self.assertEqual(re.findall(r"(?<![<\w])\|[a-z_]+\|(?![>\w])", text), [], "`|name|` of a header should be ``name``")

    def test_every_public_name_has_a_docstring(self):
        problems = {}
        for path in sorted(PACKAGE.rglob("*.py")):
            relative = path.relative_to(PACKAGE).as_posix()
            if relative in PENDING:
                continue
            names = missing(path)
            if names:
                problems[relative] = names
        self.assertEqual(problems, {}, "write the docstrings (llm-wiki/pages/procedures/write-docstrings.md)")

    def test_pending_lists_only_modules_that_still_miss_something(self):
        stale = [r for r in sorted(PENDING) if not missing(PACKAGE / r)]
        self.assertEqual(stale, [], "remove these from PENDING: they are documented")


if __name__ == "__main__":
    unittest.main()
