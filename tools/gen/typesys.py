"""Type handling of the generator.

Every C++ type in a CEF method signature is classified into a *kind*. A kind is a
small description (what the type is, how it looks in Python) that the emitters
turn into C++, Cython and .pyi code. Types the generator cannot handle yet are
reported with a reason instead of being skipped silently, so the coverage report
shows exactly what is left to do.

To support a new kind of type:
  1. add a `Kind` subclass here and recognise it in `classify()`;
  2. teach the emitters (emit_cpp.py, emit_cython.py, emit_pyi.py) how to convert it.
The method planning below does not need to change.
"""

import re
from dataclasses import dataclass, field

from model import py_method_name, py_param_name


class Unsupported(Exception):
    """A type or construct that is not handled yet; the message says why."""


# -- kinds -------------------------------------------------------------------------


@dataclass(frozen=True)
class Kind:
    pass


@dataclass(frozen=True)
class Void(Kind):
    pass


@dataclass(frozen=True)
class Prim(Kind):
    cpp: str  # the type as written in the header
    py: str  # annotation in Python: int, bool or float


@dataclass(frozen=True)
class Str(Kind):
    """CefString (UTF-16 inside CEF, str in Python)."""


@dataclass(frozen=True)
class Enum(Kind):
    spelled: str  # as written where it is used, e.g. TransitionType
    cname: str  # the C enumeration, e.g. cef_transition_type_t
    # The class in cefweaver.types ("" if the enumeration could not be read: then an int).
    py: str = field(default="", compare=False)


@dataclass(frozen=True)
class LibRef(Kind):
    """CefRefPtr<T> of an object implemented by CEF (wrapped for Python)."""

    cls: str


@dataclass(frozen=True)
class ClientRef(Kind):
    """CefRefPtr<T> of an object implemented by the application (proxied to Python)."""

    cls: str


@dataclass(frozen=True)
class Struct(Kind):
    """A plain data struct passed by value (CefRect, CefPoint, ...): a named tuple in Python."""

    cls: str  # the C++ class, e.g. CefRect
    fields: tuple  # of model.StructField


@dataclass(frozen=True)
class Vector(Kind):
    """`std::vector<T>` (a list in Python). The element is a string, a number (not bool), a
    value type struct or, from a library method, an object implemented by CEF."""

    element: Kind


@dataclass(frozen=True)
class Buffer(Kind):
    """`void* data, <integer> size`: a writable memoryview in Python."""

    size_cpp: str  # type of the size parameter


_PRIMITIVES = {
    "bool": "bool",
    "int": "int",
    "int16_t": "int",
    "uint16_t": "int",
    "int32_t": "int",
    "uint32_t": "int",
    "int64_t": "int",
    "uint64_t": "int",
    "size_t": "int",
    "long": "int",
    "unsigned long": "int",
    "long long": "int",
    "cef_color_t": "int",
    "double": "float",
    "float": "float",
}


def _vector_element(model, scope, analysis):
    """The kind of the elements of a `std::vector<T>`; the parser reports T."""
    element = analysis.result_value[0] if analysis.result_value else {}
    spelled = element.get("vector_type", "")
    kind = element.get("result_type")
    if kind == "string":
        return Str()
    if kind == "simple":
        if spelled in _PRIMITIVES and spelled != "bool":  # std::vector<bool> is not a container
            return Prim(spelled, _PRIMITIVES[spelled])
        if spelled in model.structs:
            return Struct(spelled, model.structs[spelled].fields)
        raise Unsupported("vector of values")
    if kind == "refptr":
        inner = re.match(r"^CefRefPtr<\s*(\w+)\s*>$", spelled)
        if inner and scope.is_library(inner.group(1)):
            return LibRef(inner.group(1))
        if inner and not scope.is_client(inner.group(1)):
            raise Unsupported("class %s is not generated yet" % inner.group(1))
    raise Unsupported("vector of values")


def classify(model, scope, analysis):
    """Return the Kind of one parsed type, or raise Unsupported(reason)."""
    spelled = analysis.get_type()
    result = analysis.result_type

    if result == "simple":
        if spelled == "void" and not analysis.is_byaddr():
            return Void()
        if analysis.is_byaddr():
            raise Unsupported("pointer to %s" % spelled)
        if spelled in _PRIMITIVES:
            return Prim(spelled, _PRIMITIVES[spelled])
        if spelled in model.structs:
            return Struct(spelled, model.structs[spelled].fields)
        raise Unsupported("struct-like value type %s" % spelled)

    if result == "string":
        if analysis.is_byaddr():
            raise Unsupported("pointer to CefString")
        return Str()

    if result == "structure":
        cname = analysis.result_value
        if cname in model.enums and not analysis.is_byaddr():
            info = model.enum_defs.get(cname)
            return Enum(spelled, cname, info.py_name if info else "")
        raise Unsupported("struct %s" % cname)

    if result == "refptr":
        if analysis.is_byref() and not analysis.is_const():
            raise Unsupported("reference to a CefRefPtr")
        # get_result_ptr_type_root() is the C API name (cef_request_t); we need CefRequest.
        inner = re.match(r"^CefRefPtr<\s*(\w+)\s*>$", spelled).group(1)
        if scope.is_library(inner):
            return LibRef(inner)
        if scope.is_client(inner):
            return ClientRef(inner)
        raise Unsupported("class %s is not generated yet" % inner)

    if result == "vector":
        return Vector(_vector_element(model, scope, analysis))
    if result in ("map", "multimap"):
        raise Unsupported(result + " of values")
    if result in ("ownptr", "rawptr"):
        raise Unsupported("%s pointer" % result)
    raise Unsupported("type %s" % spelled)


# -- method plans --------------------------------------------------------------------


@dataclass
class ParamPlan:
    cef_name: str
    name: str  # PEP 8 name in Python
    spelled: str  # the C++ type as written
    kind: Kind
    out: bool = False  # filled by the callee and returned from the Python method
    # A library method that takes a struct by non-const reference reads and changes it
    # (CefDisplay::ConvertPointToPixels): the Python method takes it and returns it.
    inout: bool = False
    const: bool = False
    byref: bool = False
    optional: bool = False  # the header marks it optional_param: None is allowed
    size_name: str = ""  # Buffer only: the C++ name of the size parameter


@dataclass
class MethodPlan:
    owner: str  # CEF class name, or "" for a global function
    cef_name: str
    name: str
    static: bool
    ret: Kind = None
    ret_spelled: str = ""
    params: list = field(default_factory=list)
    reason: str = ""  # why it is not generated; empty when it is
    pure: bool = False
    node: object = None
    const_method: bool = False

    @property
    def supported(self):
        return not self.reason

    @property
    def outs(self):
        return [p for p in self.params if p.out]

    @property
    def ins(self):
        return [p for p in self.params if not p.out or p.inout]

    @property
    def results(self):
        """What the Python side of a client method returns, in order."""
        found = [] if isinstance(self.ret, Void) else [("return", self.ret)]
        return found + [(p.name, p.kind) for p in self.outs]


def plan_method(model, scope, owner, method, *, client_side, static=False):
    """Decide how one method or function is generated (or why it is not)."""
    plan = MethodPlan(
        owner=owner,
        cef_name=method.get_name(),
        name=py_method_name(method.get_name()),
        static=static,
        node=method,
        const_method=method.is_const() if hasattr(method, "is_const") else False,
    )
    try:
        retval = method.get_retval().get_type()
        plan.ret = classify(model, scope, retval)
        plan.ret_spelled = retval.get_type()
        _check_return(plan.ret, client_side)

        arguments = list(method.get_arguments())
        optional_names = set(method.get_attrib_list("optional_param") or [])
        i = 0
        while i < len(arguments):
            argument = arguments[i]
            analysis = argument.get_type()
            name = argument.get_name()
            if analysis.get_type() == "void" and analysis.is_byaddr():
                # `void* data, <integer> size` -> Buffer
                if not client_side or i + 1 >= len(arguments):
                    raise Unsupported("untyped pointer parameter %s" % name)
                size = classify(model, scope, arguments[i + 1].get_type())
                if not isinstance(size, Prim) or size.py != "int":
                    raise Unsupported("untyped pointer parameter %s" % name)
                plan.params.append(
                    ParamPlan(name, py_param_name(name), "void*", Buffer(size.cpp)))
                plan.params[-1].size_name = arguments[i + 1].get_name()
                i += 2
                continue
            kind = classify(model, scope, analysis)
            out = analysis.is_byref() and not analysis.is_const() and not isinstance(kind, LibRef)
            if out:
                if not client_side and not isinstance(kind, (Vector, Prim, Str, Enum, Struct)):
                    raise Unsupported("output parameter %s of a library method" % name)
                if client_side and isinstance(kind, Vector):
                    raise Unsupported("output vector %s of a handler method" % name)
                if isinstance(kind, (LibRef, ClientRef)):
                    raise Unsupported("output parameter %s of object type" % name)
            elif isinstance(kind, Vector) and not client_side and isinstance(kind.element, LibRef):
                raise Unsupported("vector of objects passed to a library method")
            if isinstance(kind, Void):
                raise Unsupported("void parameter")
            if isinstance(kind, ClientRef) and client_side:
                raise Unsupported("client object parameter %s passed to the application" % name)
            plan.params.append(ParamPlan(name, py_param_name(name), analysis.get_type(), kind,
                                         out=out, const=analysis.is_const(),
                                         byref=analysis.is_byref(),
                                         optional=name in optional_names,
                                         inout=out and not client_side and isinstance(kind, Struct)))
            i += 1
    except Unsupported as reason:
        plan.reason = str(reason)
    return plan


def _check_return(kind, client_side):
    if client_side:
        if isinstance(kind, LibRef):
            raise Unsupported("a client method returning a library object")
        if isinstance(kind, Struct):
            raise Unsupported("a client method returning the value type %s" % kind.cls)
    else:
        if isinstance(kind, ClientRef):
            raise Unsupported("a library method returning a client object")
