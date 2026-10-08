"""Tests of the binding generator (tools/gen). They do not need CEF to run, only its headers.

The headers are read from build/native/cef (see `python tools/prepare.py`); the tests that
need them are skipped when they are missing.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CEF_ROOT = os.path.join(ROOT, "build", "native", "cef")
sys.path.insert(0, os.path.join(ROOT, "tools", "gen"))

import model  # noqa: E402
from typesys import ClientRef, Enum, LibRef, Prim, Str, Struct, Void  # noqa: E402

def generate_outputs():
    import generate
    return generate.OUTPUTS


HAS_HEADERS = os.path.isfile(os.path.join(CEF_ROOT, "include", "cef_version.h"))


class Naming(unittest.TestCase):
    def test_snake_case(self):
        cases = {
            "GetURL": "get_url",
            "OnLoadEnd": "on_load_end",
            "IsReadOnly": "is_read_only",
            "SetHeaderByName": "set_header_by_name",
            "GetResourceType": "get_resource_type",
            "HTTPStatus": "http_status",
            "Open": "open",
        }
        for cef_name, expected in cases.items():
            self.assertEqual(model.snake_case(cef_name), expected, cef_name)

    def test_python_keywords_get_an_underscore(self):
        self.assertEqual(model.py_method_name("Continue"), "continue_")
        self.assertEqual(model.py_param_name("from"), "from_")

    def test_class_names_lose_the_cef_prefix(self):
        self.assertEqual(model.py_class_name("CefResourceHandler"), "ResourceHandler")
        self.assertEqual(model.py_class_name("Other"), "Other")


@unittest.skipUnless(HAS_HEADERS, "needs the CEF headers (python tools/prepare.py)")
class WithHeaders(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from scope import Scope
        from typesys import plan_method
        cls.plan_method = staticmethod(plan_method)
        cls.model = model.Model(CEF_ROOT)
        cls.scope = Scope.current(cls.model)
        cls.everything = Scope.everything(cls.model)

    def plan(self, cls_name, method_name):
        cls = self.model.classes[cls_name]
        for method in list(cls.get_virtual_funcs()) + list(cls.get_static_funcs()):
            if method.get_name() == method_name:
                return self.plan_method(self.model, self.scope, cls_name, method,
                                        client_side=cls.is_client_side())
        raise KeyError(method_name)

    def test_the_class_name_comes_from_the_declaration(self):
        # The parser's own "pointer type root" is the C API name (cef_request_t).
        plan = self.plan("CefResourceHandler", "Open")
        self.assertTrue(plan.supported, plan.reason)
        self.assertIsInstance(plan.params[0].kind, LibRef)
        self.assertEqual(plan.params[0].kind.cls, "CefRequest")

    def test_output_parameters_are_returned(self):
        plan = self.plan("CefResourceHandler", "GetResponseHeaders")
        self.assertTrue(plan.supported, plan.reason)
        self.assertEqual([p.name for p in plan.outs], ["response_length", "redirect_url"])
        self.assertIsInstance(plan.ret, Void)
        self.assertEqual([name for name, _ in plan.results], ["response_length", "redirect_url"])

    def test_return_value_comes_before_the_output_parameters(self):
        plan = self.plan("CefResourceHandler", "Open")
        self.assertEqual([name for name, _ in plan.results], ["return", "handle_request"])

    def test_buffer_pair_becomes_one_parameter(self):
        plan = self.plan("CefResourceHandler", "Read")
        self.assertTrue(plan.supported, plan.reason)
        self.assertEqual([p.name for p in plan.ins], ["data_out", "callback"])
        self.assertEqual(plan.params[0].size_name, "bytes_to_read")

    def test_enumerations_are_told_apart_from_structs(self):
        plan = self.plan("CefRequest", "GetResourceType")
        self.assertTrue(plan.supported, plan.reason)
        self.assertEqual(plan.ret, Enum("ResourceType", "cef_resource_type_t"))

    def test_unsupported_types_are_reported_with_a_reason(self):
        plan = self.plan("CefRequest", "GetHeaderMap")
        self.assertFalse(plan.supported)
        self.assertIn("multimap", plan.reason)
        plan = self.plan("CefRequest", "GetPostData")
        self.assertFalse(plan.supported)
        self.assertIn("CefPostData is not generated yet", plan.reason)

    def test_pure_virtual_methods_are_detected(self):
        cls = self.model.classes["CefResourceHandler"]
        pure = {m.get_name(): self.model.is_pure_virtual(cls, m) for m in cls.get_virtual_funcs()}
        self.assertTrue(pure["Cancel"])
        self.assertTrue(pure["GetResponseHeaders"])
        self.assertFalse(pure["Open"])
        factory = self.model.classes["CefSchemeHandlerFactory"]
        self.assertTrue(self.model.is_pure_virtual(factory, factory.get_virtual_funcs()[0]))

    def test_primitives_and_strings(self):
        plan = self.plan("CefRequest", "SetURL")
        self.assertIsInstance(plan.params[0].kind, Str)
        plan = self.plan("CefResponse", "SetStatus")
        self.assertEqual(plan.params[0].kind, Prim("int", "int"))

    # -- CefClient and the handlers it hands out ---------------------------------

    def test_the_client_and_its_handlers_are_generated(self):
        for name in ("CefClient", "CefLoadHandler", "CefLifeSpanHandler", "CefDisplayHandler"):
            self.assertTrue(self.scope.is_client(name), name)

    def test_client_getters_return_handlers(self):
        plan = self.plan("CefClient", "GetLoadHandler")
        self.assertTrue(plan.supported, plan.reason)
        self.assertEqual(plan.ret, ClientRef("CefLoadHandler"))

    def test_handlers_that_are_not_generated_yet_are_reported(self):
        plan = self.plan("CefClient", "GetRequestHandler")
        self.assertFalse(plan.supported)
        self.assertIn("CefRequestHandler is not generated yet", plan.reason)

    def test_enumerations_reach_the_load_handler(self):
        plan = self.plan("CefLoadHandler", "OnLoadError")
        self.assertTrue(plan.supported, plan.reason)
        self.assertEqual([p.name for p in plan.ins],
                         ["browser", "frame", "error_code", "error_text", "failed_url"])

    # -- forwarding, which lets the wrapper observe an event and still call the user -----

    def generated(self, key):
        import generate
        return generate.build_all(CEF_ROOT)[key]

    def test_a_forwarder_is_generated_for_every_handler(self):
        header = self.generated("proxies")
        for name in ("LoadHandler", "LifeSpanHandler", "DisplayHandler", "ResourceHandler"):
            self.assertIn("class Cw%sForward : public Cef%s {" % (name, name), header)
        self.assertIn("forward_load_handler_->OnLoadEnd(", header)

    @unittest.skipUnless(shutil.which("c++"), "needs a C++ compiler")
    def test_forwarders_combine_in_one_reference_counted_class(self):
        # The wrapper implements the client and three handlers in one object, as the
        # hand-written handler always did. That works only if the forwarders carry no
        # reference counting of their own and leave no method abstract.
        source = (
            '#include "cefweaver_proxies.h"\n'
            "class Combined : public CefClient, public CwDisplayHandlerForward,\n"
            "                 public CwLifeSpanHandlerForward, public CwLoadHandlerForward {\n"
            "  IMPLEMENT_REFCOUNTING(Combined);\n"
            "};\n"
            "CefRefPtr<CefClient> make() { return new Combined; }\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "combined.cc")
            with open(path, "w", encoding="utf-8") as f:
                f.write(source)
            result = subprocess.run(
                ["c++", "-std=c++20", "-fsyntax-only", "-I" + CEF_ROOT,
                 "-I" + os.path.dirname(generate_outputs()["proxies"]), path],
                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr[-3000:])


    # -- value type structs (CefRect, CefPoint, ...) ------------------------------------

    def plan_in(self, scope, cls_name, method_name):
        cls = self.model.classes[cls_name]
        for method in list(cls.get_virtual_funcs()) + list(cls.get_static_funcs()):
            if method.get_name() == method_name:
                return self.plan_method(self.model, scope, cls_name, method,
                                        client_side=cls.is_client_side())
        raise KeyError(method_name)

    def test_struct_fields_are_read_from_the_c_headers(self):
        rect = self.model.structs["CefRect"]
        self.assertEqual(rect.cname, "cef_rect_t")
        self.assertEqual([(f.cname, f.cpp) for f in rect.fields],
                         [("x", "int"), ("y", "int"), ("width", "int"), ("height", "int")])
        mouse = self.model.structs["CefMouseEvent"]
        self.assertEqual([(f.cname, f.cpp) for f in mouse.fields],
                         [("x", "int"), ("y", "int"), ("modifiers", "uint32_t")])

    def test_field_names_avoid_python_keywords(self):
        range_ = self.model.structs["CefRange"]
        self.assertEqual([f.name for f in range_.fields], ["from_", "to"])
        self.assertEqual([f.cname for f in range_.fields], ["from", "to"])

    def test_structs_that_are_not_plain_data_stay_unsupported(self):
        # A `size` header, enumeration or character fields: not handled yet.
        for name in ("CefKeyEvent", "CefPopupFeatures", "CefTouchEvent"):
            self.assertNotIn(name, self.model.structs, name)

    def test_a_struct_input_of_a_handler(self):
        plan = self.plan("CefDisplayHandler", "OnContentsBoundsChange")
        self.assertTrue(plan.supported, plan.reason)
        kind = plan.params[1].kind
        self.assertIsInstance(kind, Struct)
        self.assertEqual(kind.cls, "CefRect")
        self.assertEqual([f.name for f in kind.fields], ["x", "y", "width", "height"])
        self.assertFalse(plan.params[1].out)

    def test_a_struct_output_of_a_handler_is_returned(self):
        plan = self.plan("CefDisplayHandler", "GetRootWindowScreenRect")
        self.assertTrue(plan.supported, plan.reason)
        self.assertEqual([p.name for p in plan.outs], ["rect"])
        self.assertEqual([name for name, _ in plan.results], ["return", "rect"])

    def test_library_methods_take_and_return_structs(self):
        everything = self.everything
        plan = self.plan_in(everything, "CefDisplay", "GetBounds")
        self.assertTrue(plan.supported, plan.reason)
        self.assertIsInstance(plan.ret, Struct)
        plan = self.plan_in(everything, "CefBrowserHost", "SetAutoResizeEnabled")
        self.assertTrue(plan.supported, plan.reason)
        self.assertEqual([type(p.kind).__name__ for p in plan.params], ["Prim", "Struct", "Struct"])

    def test_a_handler_returning_a_struct_is_reported(self):
        plan = self.plan_in(self.everything, "CefViewDelegate", "GetPreferredSize")
        self.assertFalse(plan.supported)
        self.assertIn("returning the value type CefSize", plan.reason)

    def test_struct_tables_use_pointers(self):
        header = self.generated("proxies")
        self.assertIn("bool (*fn_on_contents_bounds_change)(void*, CefBrowser*, const CefRect*)",
                      header)
        self.assertIn("bool (*fn_get_root_window_screen_rect)(void*, CefBrowser*, CefRect*)", header)

    def test_the_stub_declares_named_tuples(self):
        stub = self.generated("pyi")
        self.assertIn("class Rect(NamedTuple):", stub)
        self.assertIn("    width: int", stub)
        self.assertIn("class Range(NamedTuple):", stub)
        self.assertIn("    from_: int\n    to: int\n", stub)
        self.assertIn("def on_contents_bounds_change(self, browser: Browser, new_bounds: Rect) -> bool:",
                      stub)

    @unittest.skipUnless(shutil.which("c++") and os.path.isfile(
        os.path.join(CEF_ROOT, "Release", "libcef.so")), "needs a C++ compiler and libcef.so")
    def test_a_proxy_passes_structs_in_and_copies_them_out(self):
        # Runs the generated C++: input structs reach the table as pointers, and an output
        # struct filled by the table lands in the reference parameter of the CEF method.
        source = (
            '#include "cefweaver_proxies.h"\n'
            "#include <cstdio>\n"
            "struct Seen { int x, y, width, height; };\n"
            "static bool bounds(void* py, CefBrowser*, const CefRect* r) {\n"
            "  *static_cast<Seen*>(py) = Seen{r->x, r->y, r->width, r->height};\n"
            "  return true;\n"
            "}\n"
            "static bool screen(void*, CefBrowser*, CefRect* rect) {\n"
            "  rect->x = 10; rect->y = 20; rect->width = 30; rect->height = 40;\n"
            "  return true;\n"
            "}\n"
            "int main() {\n"
            "  Seen seen{};\n"
            "  CwDisplayHandlerCallbacks cb;\n"
            "  cb.py = &seen;\n"
            "  cb.fn_on_contents_bounds_change = bounds;\n"
            "  cb.fn_get_root_window_screen_rect = screen;\n"
            "  CefRefPtr<CefDisplayHandler> ref = new CwDisplayHandlerProxy(cb);\n"
            "  CefDisplayHandler* handler = ref.get();  // operator-> would need the wrapper library\n"
            "  bool a = handler->OnContentsBoundsChange(nullptr, CefRect(5, 6, 7, 8));\n"
            "  CefRect out(9, 9, 9, 9);\n"
            "  bool b = handler->GetRootWindowScreenRect(nullptr, out);\n"
            '  std::printf("%d %d,%d,%d,%d %d %d,%d,%d,%d\\n", a, seen.x, seen.y, seen.width,\n'
            "              seen.height, b, out.x, out.y, out.width, out.height);\n"
            "  return 0;\n"
            "}\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "structs.cc")
            exe = os.path.join(tmp, "structs")
            with open(path, "w", encoding="utf-8") as f:
                f.write(source)
            libdir = os.path.join(CEF_ROOT, "Release")  # CefString lives in libcef
            built = subprocess.run(
                ["c++", "-std=c++20", "-I" + CEF_ROOT,
                 "-I" + os.path.dirname(generate_outputs()["proxies"]), path, "-o", exe,
                 "-L" + libdir, "-l:libcef.so", "-Wl,-rpath," + libdir],
                capture_output=True, text=True)
            self.assertEqual(built.returncode, 0, built.stderr[-3000:])
            ran = subprocess.run([exe], capture_output=True, text=True)
        self.assertEqual(ran.stdout.strip(), "1 5,6,7,8 1 10,20,30,40", ran.stderr)


    def test_generated_files_are_up_to_date(self):
        import generate
        files = generate.build_all(CEF_ROOT)
        for key, text in files.items():
            path = generate.OUTPUTS[key]
            with open(path, encoding="utf-8", newline="") as f:
                self.assertEqual(f.read(), text,
                                 "%s is out of date: run python tools/gen/generate.py" % path)

    def test_generation_is_deterministic(self):
        import generate
        self.assertEqual(generate.build_all(CEF_ROOT), generate.build_all(CEF_ROOT))


if __name__ == "__main__":
    unittest.main()
