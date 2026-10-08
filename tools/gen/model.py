"""Read the CEF headers into a model the generators work from.

The parsing itself is done by CEF's own header parser (vendor/cef_parser.py), the
same one CEF uses to generate its C API wrappers. This module adds what the
generators need on top of it: Python names (PEP 8), enumeration detection and
pure virtual detection.
"""

import ast
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
    "cef_color_t": "int", "char16_t": "int",
}


@dataclass(frozen=True)
class StructField:
    cname: str  # the member of the C struct (may be a Python keyword)
    name: str  # PEP 8 name in Python
    cpp: str  # the C type
    py: str  # annotation in Python: int, bool or float, or the class of a nested struct
    struct: str = ""  # the C++ class of a nested struct (CefRect in CefDraggableRegion), else ""
    enum: bool = False  # `py` is the Python enumeration of the member (`cpp` is its C name)
    string: bool = False  # a cef_string_t member (str)
    time: bool = False  # a cef_basetime_t member (a datetime)


@dataclass(frozen=True)
class StructInfo:
    cls: str  # the C++ class CEF uses in signatures, e.g. CefRect
    cname: str  # the C struct it derives from, e.g. cef_rect_t
    fields: tuple


def _strip_comments(text):
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"//[^\n]*", "", text)


def parse_struct_fields(body, nested=None, enums=None):
    """Fields of a C struct body, or None if any member is not plain data.

    Plain data means a primitive type per member, an enumeration (`enums` maps the C name to
    the Python class), or another plain struct (`nested` maps the C name `cef_rect_t` to its
    C++ class `CefRect`): no pointers or arrays. A leading `size_t size` is the version
    header of the C API; the C++ class sets it, so it is not a field.
    """
    nested = nested or {}
    enums = enums or {}
    fields = []
    for index, statement in enumerate(s for s in _strip_comments(body).split(";") if s.strip()):
        statement = " ".join(statement.split())
        found = re.match(r"^([A-Za-z_][\w ]*?) (\w+)$", statement)
        if not found:
            return None
        if found.group(2) == "size":
            if index == 0 and found.group(1) == "size_t":
                continue
            return None
        ctype, cname = found.groups()
        if ctype == "cef_string_t":
            fields.append(StructField(cname, py_param_name(cname), ctype, "str", "", False, True))
        elif ctype == "cef_basetime_t":
            fields.append(StructField(cname, py_param_name(cname), ctype,
                                      "datetime.datetime | None", "", False, False, True))
        elif ctype in enums:
            fields.append(StructField(cname, py_param_name(cname), ctype, enums[ctype], "", True))
        elif ctype in _FIELD_TYPES:
            fields.append(StructField(cname, py_param_name(cname), ctype, _FIELD_TYPES[ctype]))
        elif ctype in nested:
            fields.append(StructField(cname, py_param_name(cname), ctype,
                                      py_class_name(nested[ctype]), nested[ctype]))
        else:
            return None
    return tuple(fields) or None


# -- enumerations ---------------------------------------------------------------------


@dataclass(frozen=True)
class EnumInfo:
    cname: str  # the C enumeration, e.g. cef_mouse_button_type_t
    py_name: str  # the Python class, e.g. MouseButtonType
    members: tuple  # of (Python name, value)
    flag: bool  # bit flags (an IntFlag in Python)
    doc: str = ""


class EnumUnsupported(Exception):
    """An enumeration the generator cannot read; the message says why."""


_C_CONSTANTS = {"UINT_MAX": 0xFFFFFFFF, "INT_MAX": 0x7FFFFFFF}


def _strip_c_comments(text):
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"//[^\n]*", "", text)


def _condition(expression):
    """Whether an `#if` holds when the latest API is selected."""
    expression = expression.strip()
    if re.fullmatch(r"CEF_API_ADDED\([^)]*\)", expression):
        return True
    if expression == "!defined(GENERATING_CEF_API_HASH)":
        return True
    raise EnumUnsupported("preprocessor condition %s" % expression)


def _active_lines(body, cef_root):
    """The lines of an enum body that are in effect: `#if` branches selected, the net error
    list (`#define NET_ERROR(label, value) ERR_##label = value,` + `#include`) expanded."""
    out, stack, macro = [], [], None
    for raw in _strip_c_comments(body).splitlines():
        line = raw.strip()
        if not line:
            continue
        if not line.startswith("#"):
            if all(active for active, _ in stack):
                out.append(line)
            continue
        directive, _, rest = line[1:].strip().partition(" ")
        if directive == "if":
            parent = all(active for active, _ in stack)
            value = parent and _condition(rest)
            stack.append((value, value))
        elif directive == "elif":
            was_taken = stack[-1][1]
            parent = all(active for active, _ in stack[:-1])
            value = (not was_taken) and parent and _condition(rest)
            stack[-1] = (value, was_taken or value)
        elif directive == "else":
            was_taken = stack[-1][1]
            parent = all(active for active, _ in stack[:-1])
            stack[-1] = ((not was_taken) and parent, True)
        elif directive == "endif":
            stack.pop()
        elif directive == "define":
            found = re.match(r"(\w+)\(label, value\)\s+(\w+)##label\s*=\s*value,", rest)
            if found:
                macro = (found.group(1), found.group(2))
        elif directive == "include" and macro and all(active for active, _ in stack):
            path = os.path.join(cef_root, re.search(r'"([^"]+)"', rest).group(1))
            with open(path, encoding="utf-8") as f:
                for entry in re.finditer(r"^%s\((\w+),\s*(-?\w+)\)" % macro[0], f.read(), re.M):
                    out.append("%s%s = %s," % (macro[1], entry.group(1), entry.group(2)))
        elif directive in ("undef",):
            macro = None
        else:
            raise EnumUnsupported("preprocessor directive #%s" % directive)
    return out


def _evaluate(expression, known):
    """The value of an enumerator expression: integers, names of earlier enumerators and
    the operators C programs use for flags."""
    expression = re.sub(r"\b(0[xX][0-9a-fA-F]+|\d+)[uUlL]+\b", r"\1", expression)

    def walk(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, int):
            return node.value
        if isinstance(node, ast.Name):
            if node.id in known:
                return known[node.id]
            if node.id in _C_CONSTANTS:
                return _C_CONSTANTS[node.id]
            raise EnumUnsupported("unknown name %s" % node.id)
        if isinstance(node, ast.UnaryOp):
            value = walk(node.operand)
            if isinstance(node.op, ast.USub):
                return -value
            if isinstance(node.op, ast.Invert):
                return ~value
            if isinstance(node.op, ast.UAdd):
                return value
        if isinstance(node, ast.BinOp):
            left, right = walk(node.left), walk(node.right)
            operations = {ast.LShift: lambda a, b: a << b, ast.RShift: lambda a, b: a >> b,
                          ast.BitOr: lambda a, b: a | b, ast.BitAnd: lambda a, b: a & b,
                          ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b}
            if type(node.op) in operations:
                return operations[type(node.op)](left, right)
        raise EnumUnsupported("expression %s" % expression)

    try:
        return walk(ast.parse(expression, mode="eval").body)
    except SyntaxError:
        raise EnumUnsupported("expression %s" % expression) from None


def parse_enum(body, cef_root):
    """[(C name, value)] of an enum body."""
    members, known, value = [], {}, -1
    text = " ".join(_active_lines(body, cef_root))
    for item in (i.strip() for i in text.split(",")):
        if not item:
            continue
        name, equals, expression = (p.strip() for p in item.partition("="))
        if not re.fullmatch(r"[A-Za-z_]\w*", name):
            raise EnumUnsupported("enumerator %r" % item)
        value = _evaluate(expression, known) if equals else value + 1
        known[name] = value
        members.append((name, value))
    if not members:
        raise EnumUnsupported("no enumerators")
    return members


def _python_member_names(cnames):
    """Strip the prefix all the enumerators share (`MBT_LEFT` -> `LEFT`)."""
    tokens = [name.split("_") for name in cnames]
    shared = 0
    while all(len(t) > shared + 1 and t[shared] == tokens[0][shared] for t in tokens):
        shared += 1
    names = ["_".join(t[shared:]) for t in tokens]
    names = [n if not n[0].isdigit() else "_" + n for n in names]
    if len(set(names)) != len(names):
        return list(cnames)  # stripping would merge two enumerators
    return names


def _camel_case(cname):
    core = re.sub(r"^cef_|_t$", "", cname)
    return "".join(part.capitalize() for part in core.split("_"))


def _is_flag(cname, values):
    single = [v for v in values if v > 0 and v & (v - 1) == 0]
    if cname.endswith(("_flags_t", "_mask_t")):
        return len(single) >= 2
    nonzero = [v for v in values if v != 0]
    return len(single) >= 3 and len(single) == len(nonzero)


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
        self.enum_defs, self.enum_skipped = self._read_enums()
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

    def _read_enums(self):
        """EnumInfo of every enumeration that can be read, and why the others cannot."""
        include = os.path.join(self.cef_root, "include")
        aliases = {}  # C name -> the name the C++ headers give it (`ErrorCode`)
        found = {}
        for dirpath, _, files in sorted(os.walk(include)):
            for filename in sorted(files):
                if not filename.endswith(".h"):
                    continue
                text = self._read(os.path.join(dirpath, filename))
                for match in re.finditer(r"^\s*typedef\s+(cef_\w+_t)\s+(\w+)\s*;", text, re.M):
                    aliases.setdefault(match.group(1), match.group(2))
                for match in re.finditer(r"((?:^[ \t]*///[^\n]*\n)*)[ \t]*typedef\s+enum\s*\w*\s*\{(.*?)\}\s*(\w+)\s*;",
                                         text, re.S | re.M):
                    found[match.group(3)] = (match.group(2), match.group(1))
        defs, skipped, used_names = {}, {}, set()
        for cname, (body, comment) in sorted(found.items()):
            try:
                members = parse_enum(body, self.cef_root)
            except EnumUnsupported as reason:
                skipped[cname] = str(reason)
                continue
            # The C++ spelling (`ErrorCode`) is used where it only differs from the one made of
            # the C name (`Errorcode`) in capitals. An alias that is declared inside a class
            # (`TypeFlags` of CefContextMenuParams) means little without the class.
            py_name = _camel_case(cname)
            alias = py_class_name(aliases.get(cname, ""))
            if alias and alias.lower() == py_name.lower() and alias not in used_names:
                py_name = alias
            used_names.add(py_name)
            names = _python_member_names([n for n, _ in members])
            values = [v for _, v in members]
            doc = " ".join(l.strip().lstrip("/").strip() for l in comment.splitlines()).strip()
            defs[cname] = EnumInfo(cname, py_name, tuple(zip(names, values)),
                                   _is_flag(cname, values), doc)
        return defs, skipped

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
        # `class CefRect : public cef_rect_t {`, and the ones with a size header:
        # `class CefScreenInfo : public CefStructBaseSimple<cef_screen_info_t> {` and
        # `using CefKeyEvent = CefStructBaseSimple<cef_key_event_t>;`
        text = self._read(wrappers)
        classes = dict((c, cn) for c, cn in re.findall(
            r"\bclass\s+(Cef\w+)\s*:\s*public\s+(?:CefStructBaseSimple<\s*)?(cef_\w+_t)\s*>?\s*\{", text))
        classes.update((c, cn) for c, cn in re.findall(
            r"\busing\s+(Cef\w+)\s*=\s*CefStructBaseSimple<\s*(cef_\w+_t)\s*>\s*;", text))
        # The ones with strings: `using CefCookie = CefStructBase<CefCookieTraits>;` and
        # `struct CefCookieTraits { using struct_type = cef_cookie_t; ...`
        traits = dict(re.findall(r"\bstruct\s+(Cef\w+Traits)\s*\{\s*using\s+struct_type\s*=\s*(cef_\w+_t)\s*;", text))
        for c, tr in re.findall(r"\busing\s+(Cef\w+)\s*=\s*CefStructBase<\s*(Cef\w+Traits)\s*>\s*;", text):
            if tr in traits:
                classes[c] = traits[tr]
        enum_names = {cname: info.py_name for cname, info in self.enum_defs.items()}
        by_cname = {cn: c for c, cn in classes.items()}
        structs = {}
        # A struct may contain another one (CefDraggableRegion has a CefRect), which has to be
        # read first: repeat until nothing more is added.
        progress = True
        while progress:
            progress = False
            for cls, cname in classes.items():
                if cls in structs or cname not in bodies:
                    continue
                known = {cn: c for cn, c in by_cname.items() if c in structs}
                fields = parse_struct_fields(bodies[cname], known, enum_names)
                if fields:
                    structs[cls] = StructInfo(cls, cname, fields)
                    progress = True
        return dict(sorted(structs.items()))

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
