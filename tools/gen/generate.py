"""Generate the Python binding of the CEF API.

    python tools/gen/generate.py            # write the generated files
    python tools/gen/generate.py --check    # fail if they are out of date
    python tools/gen/generate.py --report   # print the coverage report

The input is the header set of the CEF distribution in use (build/native/cef after
`python tools/prepare.py`). The generated files are committed, so building the
package does not need the generator.
"""

import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import emit_cpp  # noqa: E402
import emit_cython  # noqa: E402
import emit_pyi  # noqa: E402
from model import Model, py_class_name  # noqa: E402
from report import build_report  # noqa: E402
from scope import Scope  # noqa: E402
from typesys import plan_method  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(HERE))
OUTPUTS = {
    "proxies": os.path.join(ROOT, "native", "cefwrapper", "generated", "cefweaver_proxies.h"),
    "pxd": os.path.join(ROOT, "cefweaver", "cef_api.pxd"),
    "pxi": os.path.join(ROOT, "cefweaver", "cef_api.pxi"),
    "pyi": os.path.join(ROOT, "cefweaver", "_cefweaver.pyi"),
    "coverage": os.path.join(HERE, "COVERAGE.txt"),
}


def cef_version(cef_root):
    with open(os.path.join(cef_root, "include", "cef_version.h"), encoding="utf-8") as f:
        return re.search(r'#define CEF_VERSION "([^"]+)"', f.read()).group(1)


def build_all(cef_root):
    model = Model(cef_root)
    scope = Scope.current(model)
    plans_by_class = {}
    for cls in scope.library_classes + scope.client_classes:
        client = cls.is_client_side()
        plans = [plan_method(model, scope, cls.get_name(), m, client_side=client)
                 for m in cls.get_virtual_funcs()]
        plans += [plan_method(model, scope, cls.get_name(), m, client_side=client, static=True)
                  for m in cls.get_static_funcs()]
        plans_by_class[cls.get_name()] = plans
    function_plans = [plan_method(model, scope, "", model.functions[n], client_side=False,
                                  static=True) for n in scope.functions]

    names = [py_class_name(c.get_name()) for c in scope.library_classes + scope.client_classes]
    names += [emit_cython.public_function_name(p.cef_name) for p in function_plans if p.supported]
    assert len(names) == len(set(names)), "duplicate public names: %s" % names

    banner = "Generated from CEF " + cef_version(cef_root)
    with open(os.path.join(HERE, "handwritten.pyi"), encoding="utf-8") as f:
        handwritten = f.read()
    files = {
        "proxies": emit_cpp.emit(model, scope, plans_by_class, banner),
        "pxd": emit_cython.emit_pxd(model, scope, plans_by_class, function_plans, banner),
        "pxi": emit_cython.emit_pxi(model, scope, plans_by_class, function_plans, banner),
        "pyi": emit_pyi.emit(model, scope, plans_by_class, function_plans, handwritten, banner),
        "coverage": build_report(model, scope, Scope.everything(model)),
    }
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--cef-root", default=os.path.join(ROOT, "build", "native", "cef"))
    parser.add_argument("--check", action="store_true", help="fail if the files are out of date")
    parser.add_argument("--report", action="store_true", help="print the coverage report")
    args = parser.parse_args()

    files = build_all(args.cef_root)
    if args.report:
        print(files["coverage"])
        return
    stale = []
    for key, text in files.items():
        path = OUTPUTS[key]
        current = None
        if os.path.exists(path):
            with open(path, encoding="utf-8", newline="") as f:
                current = f.read()
        if current != text:
            stale.append(os.path.relpath(path, ROOT))
            if not args.check:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w", encoding="utf-8", newline="\n") as f:
                    f.write(text)
    if args.check:
        if stale:
            sys.exit("out of date (run python tools/gen/generate.py): " + ", ".join(stale))
        print("generated files are up to date")
    else:
        print("updated: " + (", ".join(stale) if stale else "nothing"))


if __name__ == "__main__":
    main()
