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
from dataclasses import dataclass

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


# -- value type structs -----------------------------------------------------------------

# The field types a struct may have to be handled as plain data: C type -> Python type.
_FIELD_TYPES = {
    "bool": "bool", "int": "int", "int16_t": "int", "uint16_t": "int", "int32_t": "int",
    "uint32_t": "int", "int64_t": "int", "uint64_t": "int", "float": "float", "double": "float",
    "cef_color_t": "int",
}


@dataclass(frozen=True)
class StructField:
    cname: str  # the member of the C struct (may be a Python keyword)
    name: str  # PEP 8 name in Python
    cpp: str  # the C type
    py: str  # annotation in Python: int, bool or float


@dataclass(frozen=True)
class StructInfo:
    cls: str  # the C++ class CEF uses in signatures, e.g. CefRect
    cname: str  # the C struct it derives from, e.g. cef_rect_t
    fields: tuple


def _strip_comments(text):
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"//[^\n]*", "", text)


def parse_struct_fields(body):
    """Fields of a C struct body, or None if any member is not plain data.

    Plain data means a primitive type per member: no pointers, arrays, enumerations,
    nested structs or `size` headers (CefKeyEvent and the like are not handled yet).
    """
    fields = []
    for statement in _strip_comments(body).split(";"):
        statement = " ".join(statement.split())
        if not statement:
            continue
        found = re.match(r"^([A-Za-z_][\w ]*?) (\w+)$", statement)
        if not found or found.group(1) not in _FIELD_TYPES or found.group(2) == "size":
            return None
        ctype, cname = found.groups()
        fields.append(StructField(cname, py_param_name(cname), ctype, _FIELD_TYPES[ctype]))
    return tuple(fields) or None


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
        self.structs = self._find_structs()

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

    def _find_structs(self):
        """The plain data structs CEF passes by value: `class CefRect : public cef_rect_t`."""
        internal = os.path.join(self.cef_root, "include", "internal")
        wrappers = os.path.join(internal, "cef_types_wrappers.h")
        if not os.path.isfile(wrappers):
            return {}
        bodies = {}
        for filename in sorted(os.listdir(internal)):
            if filename.endswith(".h"):
                text = self._read(os.path.join(internal, filename))
                for match in re.finditer(r"typedef\s+struct\s+_\w+\s*\{(.*?)\}\s*(\w+)\s*;", text, re.S):
                    bodies[match.group(2)] = match.group(1)
        structs = {}
        for match in re.finditer(r"\bclass\s+(Cef\w+)\s*:\s*public\s+(cef_\w+_t)\s*\{",
                                 self._read(wrappers)):
            cls, cname = match.groups()
            fields = parse_struct_fields(bodies[cname]) if cname in bodies else None
            if fields:
                structs[cls] = StructInfo(cls, cname, fields)
        return structs

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
