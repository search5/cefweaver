"""Emit the C++ proxies for the classes implemented by the application.

For every client-side CEF class (a handler) the header declares

  * `Cw<Name>Callbacks`: a table of function pointers plus the owner (`py`);
  * `Cw<Name>Proxy`: a class that implements the CEF class and forwards each
    virtual method to the matching entry of the table;
  * `Cw<Name>Forward`: a base class for hand-written handlers that observe an event
    and still pass it on. It forwards each method to `forward_<name>_` (another
    object of the CEF class, usually a proxy) or, when that is empty, behaves like the
    CEF base class. It has no reference counting of its own, so one object can
    derive from the forwarders of several handlers and count references once.

The Cython module fills the table with functions that call the Python object. A
method the Python class does not override has no entry, and the proxy then
behaves exactly like the CEF base class (or returns the default for pure
virtual methods).
"""

from model import py_class_name, snake_case
from typesys import (Buffer, Planes, REMEMBER, ClientRef, Enum, Ignored, LibRef, Prim, Str, Struct, Time,
                     Vector, Void)


def field_name(plan):
    return "fn_" + snake_case(plan.cef_name)


def element_cpp(kind):
    """The C++ type of the elements of a vector."""
    if isinstance(kind, Str):
        return "CefString"
    if isinstance(kind, Prim):
        return kind.cpp
    if isinstance(kind, Struct):
        return kind.cls
    if isinstance(kind, LibRef):
        return "CefRefPtr<%s>" % kind.cls
    raise AssertionError(kind)


def table_in_types(param):
    """C types of an input parameter in the function pointer table."""
    kind = param.kind
    if isinstance(kind, Prim):
        return [kind.cpp]
    if isinstance(kind, Time):
        return ["int64_t"]
    if isinstance(kind, Enum):
        return ["int"]
    if isinstance(kind, Str):
        return ["const CefString*"]
    if isinstance(kind, Struct):
        return ["const %s*" % kind.cls]
    if isinstance(kind, Vector):
        return ["const std::vector<%s>*" % element_cpp(kind.element)]
    if isinstance(kind, LibRef):
        return [kind.cls + "*"]
    if isinstance(kind, Buffer):
        return ["void*", kind.size_cpp]
    if isinstance(kind, Planes):
        return ["const float**", "int", "int"]       # the data, the frames, the channels
    raise AssertionError(kind)


def table_out_type(param):
    kind = param.kind
    if isinstance(kind, Prim):
        return kind.cpp + "*"
    if isinstance(kind, Enum):
        return "int*"
    if isinstance(kind, Str):
        return "CefString*"
    if isinstance(kind, Struct):
        return kind.cls + "*"
    raise AssertionError(kind)


def table_ret_type(plan):
    kind = plan.ret
    if isinstance(kind, Void):
        return "void"
    if isinstance(kind, Prim):
        return kind.cpp
    if isinstance(kind, Enum):
        return "int"
    if isinstance(kind, ClientRef):
        return kind.cls + "*"  # one reference is passed to the proxy
    raise AssertionError(kind)


def table_param_types(plan):
    types = ["void*"]
    for param in plan.params:
        if isinstance(param.kind, Ignored):
            continue
        types += [table_out_type(param)] if param.out else table_in_types(param)
    return types


def declaration(param):
    """The parameter as it is declared in the CEF header."""
    if isinstance(param.kind, Planes):
        return "const float** %s, int %s" % (param.cef_name, param.size_name)
    if isinstance(param.kind, Buffer):
        if param.kind.size_expr:
            return "%svoid* %s" % ("const " if param.kind.readonly else "", param.cef_name)
        return "%svoid* %s, %s %s" % ("const " if param.kind.readonly else "", param.cef_name,
                                      param.kind.size_cpp, param.size_name)
    text = ("const " if param.const else "") + param.spelled + (
        "&" if param.byref else "*" if param.byaddr else "")
    return "%s %s" % (text, param.cef_name)


def call_arguments(plan):
    """Names of the arguments in the order of the CEF declaration."""
    names = []
    for param in plan.params:
        if param.is_return:
            continue
        names.append(param.cef_name)
        if isinstance(param.kind, Planes) or (isinstance(param.kind, Buffer) and not param.kind.size_expr):
            names.append(param.size_name)
    return names


def _default_return(plan):
    kind = plan.ret
    if isinstance(kind, Void) and not plan.void_return:
        return "return %s();" % plan.ret_spelled
    if isinstance(kind, Void):
        return "return;"
    if isinstance(kind, ClientRef):
        return "return nullptr;"
    return "return %s();" % plan.ret_spelled


def _method(model, cls, plan):
    field = field_name(plan)
    params = ", ".join(declaration(p) for p in plan.params if not p.is_return)
    const = " const" if plan.const_method else ""
    out = []
    out.append("  %s %s(%s)%s override {" % (plan.ret_spelled, plan.cef_name, params, const))
    out.append("    if (!cb_.%s) {" % field)
    if model.is_pure_virtual(cls, plan.node):
        out.append("      %s" % _default_return(plan))
    else:
        call = "%s::%s(%s)" % (cls.get_name(), plan.cef_name, ", ".join(call_arguments(plan)))
        out.append("      %s%s;" % ("" if plan.void_return else "return ", call))
        if plan.void_return:
            out.append("      return;")
    out.append("    }")

    for remembered, member in [REMEMBER.get((cls.get_name(), plan.cef_name), (None, None))][:1]:
        if remembered:
            out.append("    %s = %s;" % (member, remembered))    # what a later call needs (the channels)
    args = ["cb_.py"]
    for param in plan.params:
        name = param.cef_name
        kind = param.kind
        if isinstance(kind, Ignored):
            continue
        if param.out:
            if isinstance(kind, Str):
                out.append("    CefString out_%s%s;" % (name, " = " + name if param.inout else ""))
            elif isinstance(kind, Enum):
                out.append("    int out_%s = 0;" % name)
            elif isinstance(kind, Struct):
                out.append("    %s out_%s;" % (kind.cls, name))
            else:
                out.append("    %s out_%s = %s();" % (kind.cpp, name, kind.cpp))
            args.append("&out_%s" % name)
        elif isinstance(kind, Prim):
            args.append(name)
        elif isinstance(kind, Time):
            args.append("%s.val" % name)
        elif isinstance(kind, Enum):
            args.append("static_cast<int>(%s)" % name)
        elif isinstance(kind, (Str, Struct, Vector)):
            args.append("&%s" % name)
        elif isinstance(kind, LibRef):
            args.append("%s.get()" % name)
        elif isinstance(kind, Buffer):
            # The function table takes void*; a read-only view never writes through it.
            args += ["const_cast<void*>(%s)" % name if param.kind.readonly else name,
                     param.kind.size_expr or param.size_name]
        elif isinstance(kind, Planes):
            args += [name, param.size_name, kind.count_member]
    call = "cb_.%s(%s)" % (field, ", ".join(args))

    ret = plan.ret
    if isinstance(ret, Void):
        out.append("    %s;" % call)
    elif isinstance(ret, ClientRef):
        out.append("    %s* raw = %s;" % (ret.cls, call))
        out.append("    CefRefPtr<%s> result;" % ret.cls)
        out.append("    if (raw) {")
        out.append("      result = raw;")
        out.append("      raw->Release();")
        out.append("    }")
    elif isinstance(ret, Enum):
        out.append("    %s result = static_cast<%s>(%s);" % (plan.ret_spelled, plan.ret_spelled, call))
    else:
        out.append("    %s result = %s;" % (plan.ret_spelled, call))

    if plan.clamp_return:  # a Python handler cannot claim more items than the buffer has
        out.append("    if (result > %s) result = %s;" % (plan.clamp_return, plan.clamp_return))
    for param in plan.outs:
        if param.is_return:
            out.append("    return out_%s;" % param.cef_name)
        elif param.byaddr:
            out.append("    if (%s) *%s = out_%s;" % (param.cef_name, param.cef_name, param.cef_name))
        elif isinstance(param.kind, Enum):
            out.append("    %s = static_cast<%s>(out_%s);" % (param.cef_name, param.spelled, param.cef_name))
        else:
            out.append("    %s = out_%s;" % (param.cef_name, param.cef_name))
    if not isinstance(ret, Void):
        out.append("    return result;")
    out.append("  }")
    return out


def _forward_method(model, cls, plan, member):
    params = ", ".join(declaration(p) for p in plan.params if not p.is_return)
    const = " const" if plan.const_method else ""
    args = ", ".join(call_arguments(plan))
    out = []
    out.append("  %s %s(%s)%s override {" % (plan.ret_spelled, plan.cef_name, params, const))
    out.append("    if (!%s) {" % member)
    if model.is_pure_virtual(cls, plan.node):
        out.append("      %s" % _default_return(plan))
    else:
        call = "%s::%s(%s)" % (cls.get_name(), plan.cef_name, args)
        if plan.void_return:
            out.append("      %s;" % call)
            out.append("      return;")
        else:
            out.append("      return %s;" % call)
    out.append("    }")
    call = "%s->%s(%s)" % (member, plan.cef_name, args)
    out.append("    %s%s;" % ("" if plan.void_return else "return ", call))
    out.append("  }")
    return out


def _forwarder(model, cls, plans):
    name = py_class_name(cls.get_name())
    member = "forward_%s_" % snake_case(name)
    lines = ["class Cw%sForward : public %s {" % (name, cls.get_name()),
             " protected:",
             "  CefRefPtr<%s> %s;" % (cls.get_name(), member),
             "",
             " public:"]
    for plan in plans:
        lines += _forward_method(model, cls, plan, member)
        lines.append("")
    lines[-1:] = ["};", ""]
    return lines


def emit(model, scope, plans_by_class, banner):
    lines = [
        "// " + banner,
        "// GENERATED by tools/gen/generate.py. DO NOT EDIT.",
        "",
        "#ifndef CEFWEAVER_GENERATED_PROXIES_H_",
        "#define CEFWEAVER_GENERATED_PROXIES_H_",
        "",
    ]
    headers = sorted({model.header_path(c) for c in scope.client_classes} |
                     {model.header_path(c) for c in scope.library_classes})
    lines += ['#include "%s"' % h for h in headers]
    lines.append("#include <atomic>")
    lines.append("#include <vector>")
    lines.append("")

    for cls in scope.client_classes:
        name = py_class_name(cls.get_name())
        plans = [p for p in plans_by_class[cls.get_name()] if p.supported and not p.static]
        lines.append("// ---- %s ----" % cls.get_name())
        lines.append("")
        lines += _forwarder(model, cls, plans)
        lines.append("struct Cw%sCallbacks {" % name)
        lines.append("  void* py = nullptr;  // owner, released through |release|")
        lines.append("  void (*release)(void* py) = nullptr;")
        for plan in plans:
            lines.append("  %s (*%s)(%s) = nullptr;" % (
                table_ret_type(plan), field_name(plan), ", ".join(table_param_types(plan))))
        lines.append("};")
        lines.append("")
        lines.append("class Cw%sProxy : public %s {" % (name, cls.get_name()))
        lines.append(" public:")
        lines.append("  explicit Cw%sProxy(const Cw%sCallbacks& callbacks) : cb_(callbacks) {}" % (name, name))
        lines.append("  ~Cw%sProxy() override {" % name)
        lines.append("    if (cb_.release) {")
        lines.append("      cb_.release(cb_.py);")
        lines.append("    }")
        lines.append("  }")
        lines.append("")
        for plan in plans:
            lines += _method(model, cls, plan)
            lines.append("")
        lines.append(" private:")
        for member in sorted({m for (c, _), (_, m) in REMEMBER.items() if c == cls.get_name()}):
            lines.append("  std::atomic<int> %s{0};  // from an earlier call, for a later one" % member)
        lines.append("  Cw%sCallbacks cb_;" % name)
        lines.append("")
        lines.append("  IMPLEMENT_REFCOUNTING(Cw%sProxy);" % name)
        lines.append("  DISALLOW_COPY_AND_ASSIGN(Cw%sProxy);" % name)
        lines.append("};")
        lines.append("")

    lines.append("#endif  // CEFWEAVER_GENERATED_PROXIES_H_")
    return "\n".join(lines) + "\n"
