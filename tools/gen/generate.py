"""Generate the Python binding of the CEF API.

    python tools/gen/generate.py            # write the generated files
    python tools/gen/generate.py --check    # fail if they are out of date
    python tools/gen/generate.py --report   # print the coverage report

The input is the header set of the CEF distribution in use (build/native/cef after
`python tools/prepare.py`). The generated files are committed, so building the
package does not need the generator.
"""

import argparse
import datetime
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import emit_cpp  # noqa: E402
import emit_cython  # noqa: E402
import emit_pyi  # noqa: E402
import emit_types  # noqa: E402
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
    "types": os.path.join(ROOT, "cefweaver", "types.py"),
    # A page of the wiki (docs/llm-wiki); the front matter field `generated: true` exempts it
    # from the page length check of the wiki lint.
    "coverage": os.path.join(ROOT, "docs", "llm-wiki", "pages", "reference", "coverage-report.md"),
}


def cef_version(cef_root):
    with open(os.path.join(cef_root, "include", "cef_version.h"), encoding="utf-8") as f:
        return re.search(r'#define CEF_VERSION "([^"]+)"', f.read()).group(1)


COVERAGE_FRONT_MATTER = """---
title: 커버리지 보고서 (생성됨)
type: reference
generated: true
sources:
  - tools/gen/scope.py
  - tools/gen/report.py
  - tools/gen/typesys.py
updated: {date}
---
"""


def coverage_page(report, version):
    """The coverage report as a wiki page.

    `updated` keeps its value while the content does not change, so that the page is
    stable (`--check`, the up-to-date test) and only moves when the report does.
    """
    content = (
        "# 커버리지 보고서 (생성됨)\n\n"
        "이 페이지는 `python tools/gen/generate.py`가 CEF %s 헤더로 생성합니다. "
        "직접 고치지 않습니다. 같은 내용을 `python tools/gen/generate.py --report`로 "
        "출력할 수 있고, 해석과 다음 단계는 [생성 범위와 커버리지](generated-api-coverage.md)에 "
        "있습니다.\n\n```\n%s```\n\n## 관련 페이지\n\n"
        "- [생성 범위와 커버리지](generated-api-coverage.md)\n"
        "- [바인딩 생성기의 설계](../concepts/binding-generator.md)\n"
        "- [새 타입 지원 추가하기](../procedures/add-type-to-generator.md)\n" % (version, report)
    )
    tail = "\n" + content  # what follows the closing `---` of the front matter
    path = OUTPUTS["coverage"]
    if os.path.exists(path):
        with open(path, encoding="utf-8", newline="") as f:
            existing = f.read()
        if existing.split("\n---\n", 1)[-1] == tail:
            return existing
    return COVERAGE_FRONT_MATTER.format(date=datetime.date.today().isoformat()) + tail


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
    names += [py_class_name(cls) for cls in emit_cython.all_structs(model)]
    assert len(names) == len(set(names)), "duplicate public names: %s" % names

    banner = "Generated from CEF " + cef_version(cef_root)
    with open(os.path.join(HERE, "handwritten.pyi"), encoding="utf-8") as f:
        handwritten = f.read()
    files = {
        "proxies": emit_cpp.emit(model, scope, plans_by_class, banner),
        "pxd": emit_cython.emit_pxd(model, scope, plans_by_class, function_plans, banner),
        "pxi": emit_cython.emit_pxi(model, scope, plans_by_class, function_plans, banner),
        "pyi": emit_pyi.emit(model, scope, plans_by_class, function_plans, handwritten, banner),
        "types": emit_types.emit(model, banner),
        "coverage": coverage_page(build_report(model, scope, Scope.everything(model)),
                                  cef_version(cef_root)),
    }
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--cef-root", default=os.path.join(ROOT, "build", "native", "cef"))
    parser.add_argument("--check", action="store_true", help="fail if the files are out of date")
    parser.add_argument("--report", action="store_true", help="print the coverage report")
    args = parser.parse_args()

    if args.report:
        model = Model(args.cef_root)
        print(build_report(model, Scope.current(model), Scope.everything(model)))
        return
    files = build_all(args.cef_root)
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
