"""Read the CEF headers into a model the generators work from.

The parsing itself is done by CEF's own header parser (vendor/cef_parser.py), the
same one CEF uses to generate its C API wrappers. This module adds what the
generators need on top of it: Python names (PEP 8), enumeration detection and
pure virtual detection.
"""

import keyword
import os
import re
import sys

VENDOR_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor")
if VENDOR_DIR not in sys.path:
    sys.path.insert(0, VENDOR_DIR)

import cef_parser  # noqa: E402  (vendored, see vendor/README.txt)


# -- names ------------------------------------------------------------------------


def snake_case(name):
    """GetURL -> get_url, OnLoadEnd -> on_load_end, HTTPStatus -> http_status."""
    name = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    name = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
    return name.lower()


def _safe(name):
    """Avoid Python keywords (PEP 8: append an underscore)."""
    return name + "_" if keyword.iskeyword(name) else name


def py_class_name(cef_name):
    """CefResourceHandler -> ResourceHandler."""
    return cef_name[3:] if cef_name.startswith("Cef") else cef_name


def py_method_name(cef_name):
    return _safe(snake_case(cef_name))


def py_param_name(cef_name):
    return _safe(snake_case(cef_name))


# -- the model -----------------------------------------------------------------------


class Model:
    """The parsed headers of one CEF distribution."""

    def __init__(self, cef_root):
        self.cef_root = os.path.abspath(cef_root)
        self._sources = {}
        header = cef_parser.obj_header()
        header.set_root_directory(self.cef_root)
        for sub in ("include", "include/test", "include/views"):
            path = os.path.join(self.cef_root, sub)
            if os.path.isdir(path):
                header.add_directory(path)
        self.header = header
        self.classes = {c.get_name(): c for c in header.get_classes()}
        self.functions = {f.get_name(): f for f in header.get_funcs()}
        self.enums = self._find_enums()

    def _read(self, path):
        if path not in self._sources:
            with open(path, encoding="utf-8") as f:
                self._sources[path] = f.read()
        return self._sources[path]

    def _find_enums(self):
        """Names of the C enumerations: `typedef enum { ... } cef_x_t;`."""
        names = set()
        include = os.path.join(self.cef_root, "include")
        for dirpath, _, files in os.walk(include):
            for filename in files:
                if not filename.endswith(".h"):
                    continue
                text = self._read(os.path.join(dirpath, filename))
                for match in re.finditer(r"typedef\s+enum\s*\w*\s*\{.*?\}\s*(\w+)\s*;", text, re.S):
                    names.add(match.group(1))
        return names

    def header_path(self, cls):
        """`include/cef_x.h` as it is written in an #include line."""
        return "include/" + cls.get_file_name().replace("\\", "/").split("include/")[-1]

    def is_pure_virtual(self, cls, method):
        """True for `virtual ... Name(...) = 0;` (the parser does not report it)."""
        path = os.path.join(self.cef_root, self.header_path(cls))
        text = self._read(path)
        # Library-side classes are declared `class CEF_EXPORT Name`, client-side ones `class Name`.
        found = re.search(r"\bclass\s+(?:CEF_EXPORT\s+)?%s\b[^;{]*\{" % re.escape(cls.get_name()), text)
        if not found:
            raise RuntimeError("class %s not found in %s" % (cls.get_name(), path))
        start = found.start()
        end = text.find("\n};", start)
        body = text[start:end if end > 0 else len(text)]
        pattern = r"virtual\s+[^;{}]*?\b%s\s*\([^;{}]*?\)\s*(?:const\s*)?=\s*0\s*;" % re.escape(
            method.get_name())
        return re.search(pattern, body, re.S) is not None

    def comment(self, node):
        """The doc comment of a class or method as plain text lines."""
        try:
            lines = node.get_comment()
        except Exception:
            return []
        return [re.sub(r"^\s*/+\s?", "", line).rstrip() for line in lines]
