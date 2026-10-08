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
from typesys import ClientRef, Enum, LibRef, Prim, Str, Struct, Vector, Void  # noqa: E402

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

    def test_the_stub_reexports_the_value_types_of_the_types_module(self):
        stub = self.generated("pyi")
        self.assertIn("    Rect as Rect,", stub)
        self.assertIn("    Range as Range,", stub)
        self.assertNotIn("class Rect", stub)  # defined once, in types.py
        self.assertIn("def on_contents_bounds_change(self, browser: Browser, new_bounds: Rect) -> bool:",
                      stub)
        types_source = self.generated("types")
        self.assertIn("class Rect(NamedTuple):", types_source)
        self.assertIn("    from_: int\n    to: int", types_source)

    @unittest.skipUnless(shutil.which("c++") and os.path.isfile(
        os.path.join(CEF_ROOT, "Release", "libcef.so")), "needs a C++ compiler and libcef.so")
    def test_a_proxy_passes_structs_in_and_copies_them_out(self):
        # Runs the generated C++: input structs reach the table as pointers, and an output
        # struct filled by the table lands in the reference parameter of the CEF method.
        source = (
            '#include "cefweaver_proxies.h"\n'
            "#include <cstdio>\n#include <string>\n#include <vector>\n"
            "struct Seen { int x, y, width, height; };\n"
            "static bool bounds(void* py, CefBrowser*, const CefRect* r) {\n"
            "  *static_cast<Seen*>(py) = Seen{r->x, r->y, r->width, r->height};\n"
            "  return true;\n"
            "}\n"
            "static int icons = 0; static std::string first;\n"
            "static void favicons(void*, CefBrowser*, const std::vector<CefString>* urls) {\n"
            "  icons = static_cast<int>(urls->size());\n"
            "  first = (*urls)[0].ToString();\n"
            "}\n"
            "static int regions = 0; static int region_w = 0; static int region_flag = 0;\n"
            "static void dragged(void*, CefBrowser*, CefFrame*,\n"
            "                    const std::vector<CefDraggableRegion>* list) {\n"
            "  regions = static_cast<int>(list->size());\n"
            "  region_w = (*list)[0].bounds.width;\n"
            "  region_flag = (*list)[0].draggable;\n"
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
            "  cb.fn_on_favicon_url_change = favicons;\n"
            "  CwDragHandlerCallbacks drag_cb;\n"
            "  drag_cb.fn_on_draggable_regions_changed = dragged;\n"
            "  CefRefPtr<CefDragHandler> drag_ref = new CwDragHandlerProxy(drag_cb);\n"
            "  std::vector<CefDraggableRegion> list;\n"
            "  list.push_back(CefDraggableRegion(CefRect(1, 2, 300, 40), true));\n"
            "  drag_ref.get()->OnDraggableRegionsChanged(nullptr, nullptr, list);\n"
            "  CefRefPtr<CefDisplayHandler> ref = new CwDisplayHandlerProxy(cb);\n"
            "  CefDisplayHandler* handler = ref.get();  // operator-> would need the wrapper library\n"
            "  bool a = handler->OnContentsBoundsChange(nullptr, CefRect(5, 6, 7, 8));\n"
            "  CefRect out(9, 9, 9, 9);\n"
            "  bool b = handler->GetRootWindowScreenRect(nullptr, out);\n"
            "  std::vector<CefString> urls;\n"
            '  urls.push_back(CefString("http://a/1.png")); urls.push_back(CefString("http://a/2.png"));\n'
            "  handler->OnFaviconURLChange(nullptr, urls);\n"
            '  std::printf("%d %d,%d,%d,%d %d %d,%d,%d,%d %d %s %d %d %d\\n", a, seen.x, seen.y, seen.width,\n'
            "              seen.height, b, out.x, out.y, out.width, out.height, icons, first.c_str(),\n"
            "              regions, region_w, region_flag);\n"
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
        self.assertEqual(ran.stdout.strip(), "1 5,6,7,8 1 10,20,30,40 2 http://a/1.png 1 300 1", ran.stderr)


    # -- CefBrowserHost -----------------------------------------------------------------

    def test_the_browser_host_is_generated_and_reachable_from_the_browser(self):
        self.assertTrue(self.scope.is_library("CefBrowserHost"))
        plan = self.plan("CefBrowser", "GetHost")
        self.assertTrue(plan.supported, plan.reason)
        self.assertEqual(plan.ret, LibRef("CefBrowserHost"))

    def test_browser_host_methods_take_structs_and_enumerations(self):
        plan = self.plan("CefBrowserHost", "SendMouseClickEvent")
        self.assertTrue(plan.supported, plan.reason)
        self.assertEqual([type(p.kind).__name__ for p in plan.params],
                         ["Struct", "Enum", "Prim", "Prim"])
        self.assertEqual(plan.params[0].kind.cls, "CefMouseEvent")

    def test_browser_host_methods_that_cannot_be_generated_say_why(self):
        reasons = {
            "ShowDevTools": "cef_window_info_t",
            "SendKeyEvent": "CefKeyEvent",
            "GetWindowHandle": "CefWindowHandle",
            "PrintToPDF": "cef_pdf_print_settings_t",
        }
        for name, expected in reasons.items():
            plan = self.plan("CefBrowserHost", name)
            self.assertFalse(plan.supported, name)
            self.assertIn(expected, plan.reason, name)


    # -- vectors of strings --------------------------------------------------------------

    def test_a_library_method_returns_a_vector_of_strings_through_an_output_parameter(self):
        plan = self.plan("CefBrowser", "GetFrameNames")
        self.assertTrue(plan.supported, plan.reason)
        self.assertEqual([p.name for p in plan.outs], ["names"])
        self.assertEqual(plan.outs[0].kind, Vector(Str()))
        self.assertEqual([name for name, _ in plan.results], ["names"])

    def test_a_handler_receives_a_vector_of_strings(self):
        plan = self.plan("CefDisplayHandler", "OnFaviconURLChange")
        self.assertTrue(plan.supported, plan.reason)
        self.assertEqual([p.name for p in plan.ins], ["browser", "icon_urls"])
        self.assertEqual(plan.ins[1].kind, Vector(Str()))

    def test_other_vectors_say_what_is_missing(self):
        # Elements other than strings, and vectors given to a library method.
        for cls, name in (("CefBrowserHost", "ImeSetComposition"),
                          ("CefTranslatorTest", "SetRefPtrClientList")):
            plan = self.plan_in(self.everything, cls, name)
            self.assertFalse(plan.supported, name)
            self.assertIn("vector", plan.reason, name)

    def test_a_vector_table_entry_is_a_pointer_to_the_vector(self):
        header = self.generated("proxies")
        self.assertIn("(*fn_on_favicon_url_change)(void*, CefBrowser*, const std::vector<CefString>*)",
                      header)

    def test_the_stub_declares_lists_of_strings(self):
        stub = self.generated("pyi")
        self.assertIn("def get_frame_names(self) -> list[str]:", stub)
        self.assertIn("def on_favicon_url_change(self, browser: Browser, icon_urls: list[str]) -> None:",
                      stub)


    # -- the types module: enumerations and value types ---------------------------------

    def test_enumerations_are_read_from_the_c_headers(self):
        info = self.model.enum_defs["cef_mouse_button_type_t"]
        self.assertEqual(info.py_name, "MouseButtonType")  # the C++ alias, not a guess
        self.assertEqual(info.members, (("LEFT", 0), ("MIDDLE", 1), ("RIGHT", 2)))
        self.assertFalse(info.flag)

    def test_enumerator_values_are_evaluated(self):
        flags = dict(self.model.enum_defs["cef_event_flags_t"].members)
        self.assertEqual(flags["SHIFT_DOWN"], 2)  # 1 << 1
        self.assertEqual(flags["NONE"], 0)
        transition = dict(self.model.enum_defs["cef_transition_type_t"].members)
        self.assertEqual(transition["LINK"], 0)
        self.assertEqual(transition["SOURCE_MASK"], 0xFF)
        self.assertEqual(transition["BLOCKED_FLAG"], 0x00800000)

    def test_bit_flags_become_flag_enumerations(self):
        self.assertTrue(self.model.enum_defs["cef_event_flags_t"].flag)
        self.assertFalse(self.model.enum_defs["cef_transition_type_t"].flag)  # mixes both

    def test_the_net_error_list_gives_the_error_codes(self):
        errors = dict(self.model.enum_defs["cef_errorcode_t"].members)
        self.assertEqual(self.model.enum_defs["cef_errorcode_t"].py_name, "ErrorCode")
        self.assertEqual(errors["ABORTED"], -3)
        self.assertEqual(errors["CONNECTION_REFUSED"], -102)
        self.assertEqual(errors["NAME_NOT_RESOLVED"], -105)

    def test_conditions_on_the_api_version_select_the_latest_api(self):
        # Members added by CEF_API_ADDED(...) are there, the ones of the #else branches are not.
        self.assertGreater(len(self.model.enum_defs["cef_resultcode_t"].members), 20)

    def test_only_the_selected_branch_of_a_condition_is_read(self):
        body = '''
            A = 0,
        #if CEF_API_ADDED(100)
          #if CEF_API_ADDED(200)
            B = 2,
          #else
            B = 1,
          #endif
        #else  // !CEF_API_ADDED(100)
            C = 5,
        #endif
            D,
        '''
        self.assertEqual(model.parse_enum(body, CEF_ROOT), [("A", 0), ("B", 2), ("D", 3)])

    def test_every_enumerator_is_defined_once(self):
        for cname, info in self.model.enum_defs.items():
            names = [name for name, _ in info.members]
            self.assertEqual(len(names), len(set(names)), cname)

    def test_enumerations_that_cannot_be_read_say_why(self):
        for cname, reason in self.model.enum_skipped.items():
            self.assertTrue(reason, cname)

    def generated_types(self):
        namespace = {}
        exec(compile(self.generated("types"), "types.py", "exec"), namespace)
        return namespace

    def test_the_types_module_defines_enumerations_and_value_types(self):
        import enum
        types = self.generated_types()
        self.assertTrue(issubclass(types["MouseButtonType"], enum.IntEnum))
        self.assertEqual(types["MouseButtonType"].RIGHT, 2)
        self.assertTrue(issubclass(types["EventFlags"], enum.IntFlag))
        both = types["EventFlags"].SHIFT_DOWN | types["EventFlags"].CONTROL_DOWN
        self.assertEqual(int(both), 2 | 4)
        self.assertEqual(types["ErrorCode"](-102).name, "CONNECTION_REFUSED")
        rect = types["Rect"](1, 2, 3, 4)
        self.assertEqual((rect.x, rect.width), (1, 3))
        self.assertEqual(types["Range"]._fields, ("from_", "to"))

    def test_the_types_module_lists_what_it_exports(self):
        types = self.generated_types()
        for name in ("MouseButtonType", "EventFlags", "ErrorCode", "Rect", "Point", "MouseEvent"):
            self.assertIn(name, types["__all__"])

    def test_the_stub_uses_the_enumerations_and_imports_the_types(self):
        stub = self.generated("pyi")
        self.assertIn("from .types import", stub)
        self.assertIn("error_code: ErrorCode", stub)
        self.assertIn("MouseButtonType | int", stub)  # a library method also takes a plain int


    # -- output parameters of library methods ---------------------------------------------

    def test_output_only_parameters_of_a_library_method_are_returned(self):
        plan = self.plan_in(self.everything, "CefMenuModel", "GetAccelerator")
        self.assertTrue(plan.supported, plan.reason)
        self.assertEqual([p.name for p in plan.outs],
                         ["key_code", "shift_pressed", "ctrl_pressed", "alt_pressed"])
        self.assertEqual([p.name for p in plan.ins], ["command_id"])
        self.assertEqual([name for name, _ in plan.results],
                         ["return", "key_code", "shift_pressed", "ctrl_pressed", "alt_pressed"])
        self.assertFalse(any(p.inout for p in plan.outs))

    def test_a_typedef_output_parameter_keeps_its_type(self):
        plan = self.plan_in(self.everything, "CefMenuModel", "GetColor")
        self.assertTrue(plan.supported, plan.reason)
        self.assertEqual(plan.outs[0].kind, Prim("cef_color_t", "int"))
        self.assertIsInstance(plan.ins[1].kind, Enum)  # the color type goes in

    def test_a_string_output_parameter(self):
        plan = self.plan_in(self.everything, "CefTranslatorTest", "GetStringByRef")
        self.assertTrue(plan.supported, plan.reason)
        self.assertEqual(plan.outs[0].kind, Str())

    def test_a_struct_given_by_reference_goes_in_and_comes_back(self):
        # CefDisplay::ConvertPointToPixels(CefPoint& point) reads the point and changes it.
        plan = self.plan_in(self.everything, "CefDisplay", "ConvertPointToPixels")
        self.assertTrue(plan.supported, plan.reason)
        self.assertTrue(plan.params[0].out and plan.params[0].inout)
        self.assertEqual([p.name for p in plan.ins], ["point"])
        self.assertEqual([name for name, _ in plan.results], ["point"])

    def test_handler_output_parameters_stay_output_only(self):
        plan = self.plan("CefDisplayHandler", "GetRootWindowScreenRect")
        self.assertFalse(any(p.inout for p in plan.outs))

    def test_the_menu_model_and_the_display_are_generated(self):
        for name in ("CefMenuModel", "CefDisplay"):
            self.assertTrue(self.scope.is_library(name), name)
        self.assertTrue(self.scope.is_client("CefMenuModelDelegate"))

    def test_the_stub_returns_the_output_parameters(self):
        stub = self.generated("pyi")
        self.assertIn("def get_accelerator(self, command_id: int) -> tuple[bool, int, bool, bool, bool]:",
                      stub)
        self.assertIn("def convert_point_to_pixels(self, point: Point | tuple[int, int]) -> Point:", stub)


    # -- vectors of structs, objects and integers ------------------------------------------

    def test_a_struct_may_contain_another_struct(self):
        region = self.model.structs["CefDraggableRegion"]
        self.assertEqual([(f.name, f.py) for f in region.fields],
                         [("bounds", "Rect"), ("draggable", "int")])
        self.assertEqual(region.fields[0].struct, "CefRect")
        self.assertEqual(region.fields[1].struct, "")

    def test_a_library_method_takes_and_returns_a_vector_of_structs(self):
        plan = self.plan_in(self.everything, "CefPrintSettings", "GetPageRanges")
        self.assertTrue(plan.supported, plan.reason)
        self.assertEqual(plan.outs[0].kind, Vector(Struct("CefRange", self.model.structs["CefRange"].fields)))
        plan = self.plan_in(self.everything, "CefPrintSettings", "SetPageRanges")
        self.assertTrue(plan.supported, plan.reason)
        self.assertIsInstance(plan.ins[0].kind, Vector)
        self.assertIsInstance(plan.ins[0].kind.element, Struct)

    def test_a_library_method_returns_a_vector_of_objects(self):
        plan = self.plan_in(self.everything, "CefDisplay", "GetAllDisplays")
        self.assertTrue(plan.supported, plan.reason)
        self.assertEqual(plan.outs[0].kind, Vector(LibRef("CefDisplay")))

    def test_a_library_method_returns_a_vector_of_integers(self):
        plan = self.plan_in(self.everything, "CefTaskManager", "GetTaskIdsList")
        self.assertTrue(plan.supported, plan.reason)
        self.assertEqual(plan.outs[0].kind, Vector(Prim("int64_t", "int")))

    def test_a_handler_receives_a_vector_of_nested_structs(self):
        plan = self.plan_in(self.scope, "CefDragHandler", "OnDraggableRegionsChanged")
        self.assertTrue(plan.supported, plan.reason)
        self.assertEqual(plan.ins[-1].kind.element.cls, "CefDraggableRegion")

    def test_vectors_of_things_that_are_not_ready_say_what_is_missing(self):
        # A list of client objects given to a library method, and lists of classes that
        # are not generated.
        plan = self.plan_in(self.everything, "CefTranslatorTest", "SetRefPtrClientList")
        self.assertFalse(plan.supported)
        self.assertIn("vector", plan.reason)

    def test_vector_tables_use_the_element_type(self):
        header = self.generated("proxies")
        self.assertIn("(*fn_on_draggable_regions_changed)(void*, CefBrowser*, CefFrame*, "
                      "const std::vector<CefDraggableRegion>*)", header)

    def test_the_stub_declares_lists_of_the_element_types(self):
        stub = self.generated("pyi")
        self.assertIn("def get_page_ranges(self) -> list[Range]:", stub)
        self.assertIn("def set_page_ranges(self, ranges: Sequence[Range | tuple[int, int]]) -> None:", stub)
        self.assertIn("    @staticmethod\n    def get_all_displays() -> list[Display]:", stub)  # a static method
        self.assertIn("regions: list[DraggableRegion]", stub)
        self.assertIn("def get_task_ids_list(self) -> tuple[bool, list[int]]:", stub)

    def test_the_draggable_region_is_a_value_type_with_a_nested_rect(self):
        types = self.generated_types()
        region = types["DraggableRegion"](types["Rect"](0, 0, 100, 50), 1)
        self.assertEqual(region.bounds.width, 100)
        self.assertEqual(types["DraggableRegion"]._fields, ("bounds", "draggable"))


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
