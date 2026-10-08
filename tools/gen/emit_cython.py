"""Emit the Cython declarations (.pxd) and the wrappers (.pxi).

Library classes (implemented by CEF, e.g. Request) become `cdef class` wrappers that
hold a CefRefPtr. Client classes (handlers, e.g. ResourceHandler) become plain Python
base classes; passing an instance to CEF builds a C++ proxy (see emit_cpp.py) whose
function pointer table points at the trampolines generated here.

GIL rules (see also _cefweaver.pyx):
  * calls into CEF release the GIL (`with nogil`);
  * trampolines called by CEF are `with gil`, never raise into C++, and report
    exceptions through sys.excepthook.
"""

import re

from emit_cpp import (element_cpp, field_name, table_in_types, table_out_type,
                      table_param_types, table_ret_type)
from model import py_class_name, py_method_name
from model import py_class_name as _py_class_name  # noqa: F401
from typesys import Buffer, ClientRef, Enum, LibRef, Prim, Str, Struct, Vector, Void

_BUILTIN_CY = {
    "int", "unsigned long", "long", "long long", "double", "float", "size_t",
    "int16_t", "uint16_t", "int32_t", "uint32_t", "int64_t", "uint64_t",
}


def cy_c(cpp):
    """A C++ type as Cython spells it in declarations (`bool*` -> `cpp_bool*`,
    `std::vector<CefString>` -> `vector[CefString]`)."""
    cpp = cpp.replace("std::vector<", "vector[").replace("CefRefPtr<", "CefRefPtr[").replace(">", "]")
    return re.sub(r"\bbool\b", "cpp_bool", cpp)


def vector_cy(kind):
    """The Cython type of a vector: vector[CefString], vector[CefRect], ..."""
    return "vector[%s]" % cy_c(element_cpp(kind.element))


def vector_tag(kind):
    """Names the conversion functions of a vector: `_g_list_<tag>` and `_g_vector_<tag>`."""
    element = kind.element
    if isinstance(element, Str):
        return "str"
    if isinstance(element, Prim):
        return element.cpp.replace(" ", "_")
    return py_class_name(element.cls)


def used_vectors(plans):
    """The vectors the generated methods use, as {tag: Vector}."""
    found = {}
    for plan in plans:
        for kind in [plan.ret] + [p.kind for p in plan.params]:
            if isinstance(kind, Vector):
                found[vector_tag(kind)] = kind
    return dict(sorted(found.items()))


def cy_arg(cpp):
    """The Cython type of a Python-facing argument."""
    return "bint" if cpp == "bool" else cpp


def public_function_name(cef_name):
    return py_method_name(cef_name[3:] if cef_name.startswith("Cef") else cef_name)


def _docstring(lines, indent):
    text = [re.sub(r"[\\\"]", lambda m: "\\" + m.group(0), line) for line in lines]
    while text and not text[0].strip():
        text.pop(0)
    text = [t[1:] if t.startswith(" ") else t for t in text]
    while text and not text[-1].strip():
        text.pop()
    if not text:
        return []
    pad = " " * indent
    if len(text) == 1:
        return ['%s"""%s"""' % (pad, text[0])]
    return ['%s"""%s' % (pad, text[0])] + [pad + t if t else "" for t in text[1:]] + [pad + '"""']


# ---------------------------------------------------------------------------------
# .pxd
# ---------------------------------------------------------------------------------


def _used_enums(plans):
    names = set()
    for plan in plans:
        kinds = [plan.ret] + [p.kind for p in plan.params]
        names |= {k.cname for k in kinds if isinstance(k, Enum)}
    return sorted(names)


def all_structs(model):
    """Every value type struct of the headers, as {class name: Struct}.

    They are generated whether or not a method in scope uses them: they are part of
    the public API (a caller builds a Rect to pass it to CEF) and cost nothing. A struct
    that contains another one comes after it.
    """
    ordered, pending = {}, dict(sorted(model.structs.items()))
    while pending:
        for cls, info in list(pending.items()):
            if all(f.struct == "" or f.struct in ordered for f in info.fields):
                ordered[cls] = Struct(cls, info.fields)
                del pending[cls]
    return ordered


def _used_typedefs(plans):
    names = set()
    for plan in plans:
        kinds = [plan.ret] + [p.kind for p in plan.params]
        for kind in kinds:
            if isinstance(kind, Prim) and kind.cpp == "cef_color_t":
                names.add("cef_color_t")
            if isinstance(kind, Struct) and any(f.cpp == "cef_color_t" for f in kind.fields):
                names.add("cef_color_t")
    return sorted(names)


def _cy_method_signature(plan):
    args = []
    for param in plan.params:
        kind = param.kind
        ref = "&" if param.out else ""  # an output parameter of a library method
        if isinstance(kind, Prim):
            args.append(cy_c(kind.cpp) + ref)
        elif isinstance(kind, Enum):
            args.append(kind.cname + ref)
        elif isinstance(kind, Str):
            args.append("CefString&" if param.out else "const CefString&")
        elif isinstance(kind, Struct):
            args.append("%s&" % kind.cls if param.out else "const %s&" % kind.cls)
        elif isinstance(kind, Vector):
            args.append(vector_cy(kind) + "&" if param.out else "const %s&" % vector_cy(kind))
        elif isinstance(kind, LibRef):
            args.append("CefRefPtr[%s]" % kind.cls)
        elif isinstance(kind, ClientRef):
            args.append("CefRefPtr[%s]" % kind.cls)
        else:
            raise AssertionError(kind)
    ret = plan.ret
    if isinstance(ret, Void):
        rtype = "void"
    elif isinstance(ret, Prim):
        rtype = cy_c(ret.cpp)
    elif isinstance(ret, Enum):
        rtype = ret.cname
    elif isinstance(ret, Str):
        rtype = "CefString"
    elif isinstance(ret, Struct):
        rtype = ret.cls
    elif isinstance(ret, (LibRef, ClientRef)):
        rtype = "CefRefPtr[%s]" % ret.cls
    else:
        raise AssertionError(ret)
    return rtype, args


def emit_pxd(model, scope, plans_by_class, function_plans, banner):
    classes = scope.library_classes + scope.client_classes
    all_plans = [p for plans in plans_by_class.values() for p in plans if p.supported]
    all_plans += [p for p in function_plans if p.supported]

    out = [
        "# " + banner,
        "# GENERATED by tools/gen/generate.py. DO NOT EDIT.",
        "",
        "from libc.stdint cimport int16_t, uint16_t, int32_t, uint32_t, int64_t, uint64_t",
        "from libcpp cimport bool as cpp_bool",
        "from libcpp.string cimport string",
        "from libcpp.vector cimport vector",
        "",
        'cdef extern from "include/cef_base.h":',
        "    cdef cppclass CefBaseRefCounted:",
        "        void AddRef() nogil",
        "        cpp_bool Release() nogil",
        "",
        'cdef extern from "include/cef_api_hash.h":',
        "    enum: CEF_API_VERSION",
        "    const char* CEF_API_HASH_PLATFORM",
        "    const char* cef_api_hash(int version, int entry)",
        "",
        'cdef extern from "include/internal/cef_ptr.h":',
        "    cdef cppclass CefRefPtr[T]:",
        "        CefRefPtr()",
        "        CefRefPtr(T*)",
        "        T* get() nogil",
        "",
        'cdef extern from "include/internal/cef_string.h":',
        "    cdef cppclass CefString:",
        "        CefString()",
        "        CefString(const string&)",
        "        string ToString() nogil",
        "",
    ]
    for name in _used_typedefs(all_plans):
        out.append("ctypedef uint32_t %s" % name)
    enums = _used_enums(all_plans)
    if enums:
        out.append('cdef extern from "include/internal/cef_types.h":')
        out += ["    ctypedef enum %s:" % e + "\n        pass" for e in enums]
        out.append("")

    structs = all_structs(model)
    if structs:
        out.append("# Value type structs (plain data, copied to and from Python named tuples)")
        out.append('cdef extern from "include/internal/cef_types_wrappers.h":')
        for ctype in sorted({f.cpp for s in structs.values() for f in s.fields if f.struct}):
            out.append("    ctypedef struct %s:  # a field that is another struct" % ctype)
            out.append("        pass")
        for struct in structs.values():
            out.append("    cdef cppclass %s:" % struct.cls)
            out.append("        %s()" % struct.cls)
            for f in struct.fields:
                cname = "" if f.name == f.cname else ' "%s"' % f.cname
                out.append("        %s %s%s" % (cy_c(f.cpp), f.name, cname))
        out.append("")

    # Forward declarations first: classes refer to each other.
    out.append("# Forward declarations")
    for cls in classes:
        out.append('cdef extern from "%s":' % model.header_path(cls))
        out.append("    cdef cppclass %s(CefBaseRefCounted)" % cls.get_name())
    out.append("")

    out.append("# Library classes (implemented by CEF)")
    for cls in scope.library_classes:
        out.append('cdef extern from "%s":' % model.header_path(cls))
        out.append("    cdef cppclass %s(CefBaseRefCounted):" % cls.get_name())
        plans = [p for p in plans_by_class[cls.get_name()] if p.supported]
        if not plans:
            out.append("        pass")
        for plan in plans:
            rtype, args = _cy_method_signature(plan)
            if plan.static:
                out.append("        @staticmethod")
            out.append("        %s %s(%s) nogil" % (rtype, plan.cef_name, ", ".join(args)))
        out.append("")

    out.append("# Client classes (implemented by the application; Cython only needs the type)")
    for cls in scope.client_classes:
        out.append('cdef extern from "%s":' % model.header_path(cls))
        out.append("    cdef cppclass %s(CefBaseRefCounted):" % cls.get_name())
        out.append("        pass")
    out.append("")

    out.append("# Global functions")
    for plan in function_plans:
        if not plan.supported:
            continue
        function = plan.node
        rtype, args = _cy_method_signature(plan)
        out.append('cdef extern from "include/%s":' %
                   function.get_file_name().replace("\\", "/").split("include/")[-1])
        out.append("    %s %s(%s) nogil" % (rtype, plan.cef_name, ", ".join(args)))
    out.append("")

    out.append("# Proxies for the client classes (native/cefwrapper/generated/cefweaver_proxies.h)")
    out.append('cdef extern from "generated/cefweaver_proxies.h":')
    for cls in scope.client_classes:
        name = py_class_name(cls.get_name())
        out.append("    cdef cppclass Cw%sCallbacks:" % name)
        out.append("        void* py")
        out.append("        void (*release)(void*) noexcept")
        for plan in plans_by_class[cls.get_name()]:
            if not plan.supported or plan.static:
                continue
            types = [cy_c(t) for t in table_param_types(plan)]
            ret = cy_c(table_ret_type(plan))
            out.append("        %s (*%s)(%s) noexcept" % (ret, field_name(plan), ", ".join(types)))
        out.append("    cdef cppclass Cw%sProxy(%s):" % (name, cls.get_name()))
        out.append("        Cw%sProxy(const Cw%sCallbacks&)" % (name, name))
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------------------------
# .pxi
# ---------------------------------------------------------------------------------

PRELUDE = '''
from cpython.buffer cimport PyBUF_WRITE
from cpython.memoryview cimport PyMemoryView_FromMemory
from cpython.ref cimport Py_DECREF, Py_INCREF

import sys as _sys
from cefweaver import types as _types
from libc.string cimport strcmp as _strcmp


# CEF needs the API version to be configured before any other call; CefInitialize()
# does it too, but the objects below can be used before that (Request.create(), ...).
cdef const char* _api_hash = cef_api_hash(CEF_API_VERSION, 0)
if _api_hash == NULL or _strcmp(_api_hash, CEF_API_HASH_PLATFORM) != 0:
    raise ImportError("the API hash of libcef does not match the headers cefweaver was built with")


cdef string _g_std(object value) except *:
    if isinstance(value, bytes):
        return <bytes>value
    if not isinstance(value, str):
        raise TypeError("expected str, not %s" % type(value).__name__)
    return (<str>value).encode("utf-8")


cdef CefString _g_cef(object value) except *:
    cdef string s = _g_std(value)
    return CefString(s)


cdef object _g_str(const CefString& value):
    return value.ToString().decode("utf-8", "replace")


cdef inline object _g_enum(object cls, long long value):
    """The member of the enumeration, or the plain int when CEF reports a value without one."""
    try:
        return cls(value)
    except ValueError:
        return value


cdef inline list _g_str_list(const vector[CefString]* values):
    cdef list result = []
    cdef size_t i
    for i in range(values.size()):
        result.append(_g_str(values[0][i]))
    return result


# Set by CefApp.shutdown(). Releasing a CEF object after CefShutdown() can end the process
# (CefTaskManager does, when the interpreter frees it on exit), so a library object that is
# freed afterwards is dropped without a Release(): nothing can use it any more.
cdef bint _cef_was_shut_down = False


cdef inline void _g_forget(void* ref) noexcept:
    (<void**>ref)[0] = NULL  # a CefRefPtr holds exactly one pointer


cdef void _g_report() noexcept:
    """Report the exception being handled (inside a callback called by CEF)."""
    try:
        _sys.excepthook(*_sys.exc_info())
    except BaseException:
        pass


cdef void _g_release(void* py) noexcept with gil:
    Py_DECREF(<object>py)
'''


def _struct_pxi(struct):
    """The conversions of a value type struct; the named tuple itself is in cefweaver.types."""
    py = py_class_name(struct.cls)
    names = [f.name for f in struct.fields]
    temps = ["_f%d" % i for i in range(len(names))]

    def from_c(f):
        if f.struct:  # a nested struct: the C struct and its C++ class have the same layout
            return "_g_from_%s(<const %s*>&value.%s)" % (py_class_name(f.struct), f.struct, f.name)
        return "value.%s" % f.name

    out = ["cdef inline object _g_from_%s(const %s* value):" % (py, struct.cls),
           "    return %s(%s)" % (py, ", ".join(from_c(f) for f in struct.fields)),
           "",
           "",
           "cdef inline int _g_to_%s(object obj, %s* out) except -1:" % (py, struct.cls),
           "    try:",
           "        %s = obj" % ("%s," % temps[0] if len(temps) == 1 else ", ".join(temps)),
           "    except (TypeError, ValueError):",
           '        raise TypeError("expected a %s (or a sequence of %d values), not %%r" %% (obj,)) from None'
           % (py, len(names))]
    for f, t in zip(struct.fields, temps):
        if f.struct:
            out.append("    _g_to_%s(%s, <%s*>&out.%s)" % (py_class_name(f.struct), t, f.struct, f.name))
        else:
            out.append("    out.%s = %s" % (f.name, t))
    out.append("    return 0")
    return out


def _vector_helpers(vectors):
    """Conversions between std::vector and list for every vector a method uses."""
    out = []
    for tag, kind in vectors.items():
        element, cy = kind.element, vector_cy(kind)
        if isinstance(element, Str):
            out += ["cdef inline int _g_str_vector(object seq, vector[CefString]& out) except -1:",
                    "    out.clear()",
                    "    for item in seq:",
                    "        out.push_back(_g_cef(item))",
                    "    return 0", "", ""]
            continue  # _g_str_list is in the prelude
        convert = {Prim: "values[0][i]",
                   Struct: "_g_from_%s(&values[0][i])" % (py_class_name(element.cls)
                                                          if isinstance(element, Struct) else ""),
                   LibRef: "_wrap_%s(values[0][i])" % (py_class_name(element.cls)
                                                       if isinstance(element, LibRef) else "")}[type(element)]
        out += ["cdef inline list _g_list_%s(const %s* values):" % (tag, cy),
                "    cdef list result = []",
                "    cdef size_t i",
                "    for i in range(values.size()):",
                "        result.append(%s)" % convert,
                "    return result", "", ""]
        if isinstance(element, LibRef):
            continue  # a list of objects is only returned (never given to a library method)
        out += ["cdef inline int _g_vector_%s(object seq, %s& out) except -1:" % (tag, cy)]
        if isinstance(element, Struct):
            out += ["    cdef %s item" % element.cls,
                    "    out.clear()",
                    "    for obj in seq:",
                    "        _g_to_%s(obj, &item)" % py_class_name(element.cls),
                    "        out.push_back(item)"]
        else:
            out += ["    out.clear()", "    for item in seq:", "        out.push_back(item)"]
        out += ["    return 0", "", ""]
    return out


def _py_default(kind):
    if isinstance(kind, Struct):
        return "%s(%s)" % (py_class_name(kind.cls), ", ".join(
            {"bool": "False", "float": "0.0"}.get(f.py, "0") for f in kind.fields))
    if isinstance(kind, Prim):
        return {"bool": "False", "float": "0.0"}.get(kind.py, "0")
    if isinstance(kind, Enum):
        return "0"
    if isinstance(kind, Str):
        return '""'
    return "None"


def _annotation(kind):
    if isinstance(kind, Prim):
        return kind.py
    if isinstance(kind, Enum):
        return kind.py or "int"
    if isinstance(kind, Str):
        return "str"
    if isinstance(kind, (LibRef, ClientRef, Struct)):
        return py_class_name(kind.cls)
    if isinstance(kind, Vector):
        return "list[%s]" % _annotation(kind.element)
    if isinstance(kind, Void):
        return "None"
    raise AssertionError(kind)


def struct_tuple_annotation(kind):
    """`tuple[int, int, int, int]`: what is accepted in place of the named tuple."""
    return "tuple[%s]" % ", ".join(f.py for f in kind.fields)


def _library_method(plan, owner_py):
    """Python-callable wrapper of a library method or function."""
    name = plan.name if plan.owner else public_function_name(plan.cef_name)
    sig = [] if plan.static else ["self"]
    decls, pre, call_args = [], [], []
    for i, param in enumerate(plan.params):
        kind, n = param.kind, param.name
        if param.out:
            # An output parameter of a library method: a local that is returned to Python
            # (a struct is also an argument: it is read, changed by CEF and returned).
            if isinstance(kind, Vector):
                decls.append("cdef %s _a%d" % (vector_cy(kind), i))
            elif isinstance(kind, Str):
                decls.append("cdef CefString _a%d" % i)
            elif isinstance(kind, Enum):
                decls.append("cdef %s _a%d" % (kind.cname, i))
                pre.append("_a%d = <%s>0" % (i, kind.cname))
            elif isinstance(kind, Prim):
                decls.append("cdef %s _a%d" % (cy_c(kind.cpp), i))
                pre.append("_a%d = %s" % (i, "False" if kind.py == "bool" else "0"))
            elif isinstance(kind, Struct):
                sig.append(n)
                decls.append("cdef %s _a%d" % (kind.cls, i))
                pre.append("_g_to_%s(%s, &_a%d)" % (py_class_name(kind.cls), n, i))
            call_args.append("_a%d" % i)
            continue
        if isinstance(kind, Vector):
            sig.append(n)
            decls.append("cdef %s _a%d" % (vector_cy(kind), i))
            pre.append("_g_%s(%s, _a%d)" % ("str_vector" if isinstance(kind.element, Str)
                                            else "vector_" + vector_tag(kind), n, i))
            call_args.append("_a%d" % i)
        elif isinstance(kind, Prim):
            sig.append("%s %s" % (cy_arg(kind.cpp), n))
            call_args.append(n)
        elif isinstance(kind, Enum):
            sig.append("int %s" % n)
            call_args.append("<%s>%s" % (kind.cname, n))
        elif isinstance(kind, Str):
            sig.append(n)
            decls.append("cdef CefString _a%d" % i)
            if param.optional:
                pre += ["if %s is not None:" % n, "    _a%d = _g_cef(%s)" % (i, n)]
            else:
                pre.append("_a%d = _g_cef(%s)" % (i, n))
            call_args.append("_a%d" % i)
        elif isinstance(kind, Struct):
            sig.append(n)
            decls.append("cdef %s _a%d" % (kind.cls, i))
            pre.append("_g_to_%s(%s, &_a%d)" % (py_class_name(kind.cls), n, i))
            call_args.append("_a%d" % i)
        elif isinstance(kind, LibRef):
            sig.append("%s %s%s" % (py_class_name(kind.cls), n, "" if param.optional else " not None"))
            decls.append("cdef CefRefPtr[%s] _a%d" % (kind.cls, i))
            if param.optional:
                pre += ["if %s is not None:" % n, "    _a%d = %s._ref" % (i, n)]
            else:
                pre.append("_a%d = %s._ref" % (i, n))
            call_args.append("_a%d" % i)
        elif isinstance(kind, ClientRef):
            sig.append(n)
            decls.append("cdef CefRefPtr[%s] _a%d" % (kind.cls, i))
            if not param.optional:
                pre += ["if %s is None:" % n,
                        '    raise TypeError("%s must not be None")' % n]
            pre.append("_a%d = _g_make_%s(%s)" % (i, py_class_name(kind.cls), n))
            call_args.append("_a%d" % i)
        else:
            raise AssertionError(kind)

    ret = plan.ret
    lines = []
    if plan.static and plan.owner:
        lines.append("    @staticmethod")
    lines.append("    def %s(%s):" % (name, ", ".join(sig)) if plan.owner else
                 "def %s(%s):" % (name, ", ".join(sig)))
    base = "        " if plan.owner else "    "
    body = []
    body += _docstring(plan.comment, len(base)) if getattr(plan, "comment", None) else []
    for d in decls:
        body.append(base + d)
    if not plan.static:
        body.append(base + "cdef %s* _p = self._ptr()" % plan.owner)
    if isinstance(ret, Prim):
        body.append(base + "cdef %s _r" % cy_c(ret.cpp))
    elif isinstance(ret, Enum):
        body.append(base + "cdef %s _r" % ret.cname)
    elif isinstance(ret, Str):
        body.append(base + "cdef CefString _r")
    elif isinstance(ret, LibRef):
        body.append(base + "cdef CefRefPtr[%s] _r" % ret.cls)
    elif isinstance(ret, Struct):
        body.append(base + "cdef %s _r" % ret.cls)
    for p in pre:
        body.append(base + p)
    receiver = ("%s." % plan.owner) if plan.static and plan.owner else ("_p." if not plan.static else "")
    call = "%s%s(%s)" % (receiver, plan.cef_name, ", ".join(call_args))
    body.append(base + "with nogil:")
    body.append(base + "    %s%s" % ("" if isinstance(ret, Void) else "_r = ", call))
    values = []  # what the Python method returns: the return value, then the output parameters
    if isinstance(ret, Prim):
        values.append("_r")
    elif isinstance(ret, Enum):
        values.append("_g_enum(_types.%s, <int>_r)" % ret.py if ret.py else "<int>_r")
    elif isinstance(ret, Str):
        values.append("_g_str(_r)")
    elif isinstance(ret, LibRef):
        values.append("_wrap_%s(_r)" % py_class_name(ret.cls))
    elif isinstance(ret, Struct):
        values.append("_g_from_%s(&_r)" % py_class_name(ret.cls))
    for i, param in enumerate(plan.params):
        if not param.out:
            continue
        kind = param.kind
        if isinstance(kind, Vector):
            values.append("_g_%s(&_a%d)" % ("str_list" if isinstance(kind.element, Str)
                                            else "list_" + vector_tag(kind), i))
        elif isinstance(kind, Str):
            values.append("_g_str(_a%d)" % i)
        elif isinstance(kind, Enum):
            values.append("_g_enum(_types.%s, <int>_a%d)" % (kind.py, i) if kind.py else "<int>_a%d" % i)
        elif isinstance(kind, Struct):
            values.append("_g_from_%s(&_a%d)" % (py_class_name(kind.cls), i))
        else:
            values.append("_a%d" % i)
    if not values:
        body.append(base + "return None")
    elif len(values) == 1:
        body.append(base + "return " + values[0])
    else:
        body.append(base + "return (" + ", ".join(values) + ")")
    return lines + body


def _results_unpack(plan, indent):
    n = len(plan.results)
    pad = " " * indent
    if n == 0:
        return []
    if n == 1:
        return [pad + "_r0 = _r"]
    return [pad + "%s = _r" % ", ".join("_r%d" % i for i in range(n))]


def _trampoline(plan, cls_py):
    """The function CEF calls (through the proxy) for one client method."""
    args = ["void* py"]
    for param in plan.params:
        if param.out:
            args.append("%s %s" % (cy_c(table_out_type(param)), param.name))
        else:
            kinds = table_in_types(param)
            if isinstance(param.kind, Buffer):
                args += ["void* %s" % param.name, "%s %s_size" % (cy_c(kinds[1]), param.name)]
            else:
                args.append("%s %s" % (cy_c(kinds[0]), param.name))
    ret_c = cy_c(table_ret_type(plan))
    out = ["cdef %s _%s_%s(%s) noexcept with gil:" % (ret_c, cls_py, plan.name, ", ".join(args))]
    out.append("    try:")

    py_args = []
    for param in plan.ins:
        kind, n = param.kind, param.name
        if isinstance(kind, Prim):
            py_args.append(n)
        elif isinstance(kind, Enum):
            py_args.append("_g_enum(_types.%s, %s)" % (kind.py, n) if kind.py else n)
        elif isinstance(kind, Str):
            py_args.append("_g_str(%s[0])" % n)
        elif isinstance(kind, Struct):
            py_args.append("_g_from_%s(%s)" % (py_class_name(kind.cls), n))
        elif isinstance(kind, Vector):
            py_args.append("_g_%s(%s)" % ("str_list" if isinstance(kind.element, Str)
                                          else "list_" + vector_tag(kind), n))
        elif isinstance(kind, LibRef):
            py_args.append("_wrap_%s(CefRefPtr[%s](%s))" % (py_class_name(kind.cls), kind.cls, n))
        elif isinstance(kind, Buffer):
            py_args.append("PyMemoryView_FromMemory(<char*>%s, %s_size, PyBUF_WRITE)" % (n, n))
        else:
            raise AssertionError(kind)

    views = [p for p in plan.ins if isinstance(p.kind, Buffer)]
    if views:
        # The buffer belongs to CEF: invalidate the view when the call is over.
        for p in plan.ins:
            if isinstance(p.kind, Buffer):
                out.append("        _view_%s = PyMemoryView_FromMemory(<char*>%s, %s_size, PyBUF_WRITE)"
                           % (p.name, p.name, p.name))
        py_args = ["_view_%s" % p.name if isinstance(p.kind, Buffer) else a
                   for p, a in zip(plan.ins, py_args)]
        out.append("        try:")
        out.append("            _r = (<object>py).%s(%s)" % (plan.name, ", ".join(py_args)))
        out.append("        finally:")
        for p in views:
            out.append("            try:")
            out.append("                _view_%s.release()" % p.name)
            out.append("            except BaseException:")
            out.append("                pass")
    else:
        out.append("        _r = (<object>py).%s(%s)" % (plan.name, ", ".join(py_args)))

    out += _results_unpack(plan, 8)
    index = 0 if isinstance(plan.ret, Void) else 1
    for k, param in enumerate(plan.outs):
        var = "_r%d" % (index + k)
        kind = param.kind
        if isinstance(kind, Str):
            out.append("        %s[0] = _g_cef(%s)" % (param.name, var))
        elif isinstance(kind, Enum):
            out.append("        %s[0] = <int>%s" % (param.name, var))
        elif isinstance(kind, Struct):
            out.append("        _g_to_%s(%s, %s)" % (py_class_name(kind.cls), var, param.name))
        else:
            out.append("        %s[0] = %s" % (param.name, var))
    ret = plan.ret
    if isinstance(ret, Prim):
        out.append("        return _r0")
    elif isinstance(ret, Enum):
        out.append("        return <int>_r0")
    elif isinstance(ret, ClientRef):
        out.append("        return _g_export_%s(_r0)" % py_class_name(ret.cls))
    out.append("    except BaseException:")
    out.append("        _g_report()")
    if isinstance(ret, ClientRef):
        out.append("        return NULL")
    elif not isinstance(ret, Void):
        out.append("        return 0")
    return out


def emit_pxi(model, scope, plans_by_class, function_plans, banner):
    lib = scope.library_classes
    cli = scope.client_classes
    out = ["# " + banner, "# GENERATED by tools/gen/generate.py. DO NOT EDIT.", ""]
    out += PRELUDE.strip("\n").split("\n")
    out.append("")

    vectors = used_vectors([p for plans in plans_by_class.values() for p in plans if p.supported] +
                           [p for p in function_plans if p.supported])
    structs = all_structs(model)
    if structs:
        out.append("")
        out.append("# Value type structs: the named tuples are defined in cefweaver/types.py")
        out.append("from cefweaver.types import %s" % ", ".join(py_class_name(c) for c in structs))
        out.append("")
        for struct in structs.values():
            out += _struct_pxi(struct)
            out.append("")
            out.append("")

    if vectors:
        out.append("# Lists")
        out += _vector_helpers(vectors)

    out.append("# Forward declarations (the classes refer to each other)")
    for cls in lib:
        out.append("cdef class %s" % py_class_name(cls.get_name()))
    out.append("")

    # Library classes.
    for cls in lib:
        py = py_class_name(cls.get_name())
        cn = cls.get_name()
        out.append("cdef class %s:" % py)
        out += _docstring(model.comment(cls), 4)
        out.append("    cdef CefRefPtr[%s] _ref" % cn)
        out.append("")
        out.append("    def __dealloc__(self):")
        out.append("        if _cef_was_shut_down:")
        out.append("            _g_forget(<void*>&self._ref)")
        out.append("")
        out.append("    def __init__(self):")
        out.append('        raise TypeError("%s objects are created by CEF or by a create() function")' % py)
        out.append("")
        out.append("    cdef %s* _ptr(self) except NULL:" % cn)
        out.append("        cdef %s* p = self._ref.get()" % cn)
        out.append("        if p == NULL:")
        out.append('            raise RuntimeError("%s has no CEF object")' % py)
        out.append("        return p")
        out.append("")
        for plan in plans_by_class[cn]:
            if not plan.supported:
                continue
            plan.comment = model.comment(plan.node)
            out += _library_method(plan, cn)
            out.append("")
        out.append("")
        out.append("cdef object _wrap_%s(CefRefPtr[%s] ref):" % (py, cn))
        out.append("    cdef %s obj" % py)
        out.append("    if ref.get() == NULL:")
        out.append("        return None")
        out.append("    obj = %s.__new__(%s)" % (py, py))
        out.append("    obj._ref = ref")
        out.append("    return obj")
        out.append("")
        out.append("")

    # Client classes.
    for cls in cli:
        py = py_class_name(cls.get_name())
        cn = cls.get_name()
        plans = [p for p in plans_by_class[cn] if p.supported and not p.static]
        out.append("class %s:" % py)
        out += _docstring(model.comment(cls), 4)
        out.append("")
        for plan in plans:
            sig = ["self"] + [p.name for p in plan.ins]
            out.append("    def %s(%s):" % (plan.name, ", ".join(sig)))
            out += _docstring(model.comment(plan.node), 8)
            results = [_py_default(k) for _, k in plan.results]
            out.append("        return %s" % (", ".join(results) if results else "None"))
            out.append("")
        out.append("")
        for plan in plans:
            out += _trampoline(plan, py)
            out.append("")
        out.append("")
        out.append("cdef CefRefPtr[%s] _g_make_%s(object obj) except *:" % (cn, py))
        out.append("    cdef CefRefPtr[%s] ref" % cn)
        out.append("    cdef Cw%sCallbacks cb" % py)
        out.append("    cdef type cls")
        out.append("    if obj is None:")
        out.append("        return ref")
        out.append("    if not isinstance(obj, %s):" % py)
        out.append('        raise TypeError("expected a %s or None, not %%s" %% type(obj).__name__)' % py)
        out.append("    cls = type(obj)")
        out.append("    Py_INCREF(obj)")
        out.append("    cb.py = <void*>obj")
        out.append("    cb.release = _g_release")
        for plan in plans:
            out.append('    if getattr(cls, "%s", None) is not %s.%s:' % (plan.name, py, plan.name))
            out.append("        cb.%s = _%s_%s" % (field_name(plan), py, plan.name))
        out.append("    ref = CefRefPtr[%s](<%s*>new Cw%sProxy(cb))" % (cn, cn, py))
        out.append("    return ref")
        out.append("")
        out.append("")
        out.append("cdef inline %s* _g_export_%s(object obj) except? NULL:" % (cn, py))
        out.append("    \"\"\"A reference for CEF to keep (the proxy calls Release() on it).\"\"\"")
        out.append("    cdef CefRefPtr[%s] ref = _g_make_%s(obj)" % (cn, py))
        out.append("    cdef %s* raw = ref.get()" % cn)
        out.append("    if raw != NULL:")
        out.append("        raw.AddRef()")
        out.append("    return raw")
        out.append("")
        out.append("")

    # Global functions.
    for plan in function_plans:
        if not plan.supported:
            continue
        plan.comment = model.comment(plan.node)
        out += _library_method(plan, "")
        out.append("")
        out.append("")

    names = ([py_class_name(s.cls) for s in structs.values()] +
             [py_class_name(c.get_name()) for c in lib + cli] +
             [public_function_name(p.cef_name) for p in function_plans if p.supported])
    out.append("__generated_all__ = [%s]" % ", ".join('"%s"' % n for n in names))
    return "\n".join(out) + "\n"
