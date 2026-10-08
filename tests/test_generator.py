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
from typesys import Buffer, Bytes, ClientRef, Ignored, ItemBytes, StrMap, Time, Enum, LibRef, Prim, Str, Struct, Vector, Void  # noqa: E402

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

    def test_a_read_only_buffer_whose_size_is_a_rule_of_the_method(self):
        # OnPaint(browser, type, dirty_rects, const void* buffer, width, height): the header
        # says the buffer holds width * height 32-bit pixels, and no size is passed.
        plan = self.plan("CefRenderHandler", "OnPaint")
        self.assertTrue(plan.supported, plan.reason)
        self.assertEqual([p.name for p in plan.ins],
                         ["browser", "type", "dirty_rects", "buffer", "width", "height"])
        buffer = plan.params[3]
        self.assertIsInstance(buffer.kind, Buffer)
        self.assertTrue(buffer.kind.readonly)
        self.assertIn("width", buffer.kind.size_expr)
        self.assertIn("height", buffer.kind.size_expr)
        self.assertEqual(buffer.size_name, "")

    def test_a_library_method_takes_bytes_for_a_pointer_and_size_pair(self):
        plan = self.plan("CefBinaryValue", "Create")
        self.assertTrue(plan.supported, plan.reason)
        self.assertIsInstance(plan.params[0].kind, Bytes)
        self.assertFalse(plan.params[0].out)
        self.assertEqual(plan.params[0].size_name, "data_size")
        self.assertEqual([p.name for p in plan.ins], ["data"])
        plan = self.plan("CefBrowserHost", "SendDevToolsMessage")
        self.assertTrue(plan.supported, plan.reason)

    def test_get_data_returns_bytes_and_takes_the_size_to_read(self):
        plan = self.plan("CefBinaryValue", "GetData")
        self.assertTrue(plan.supported, plan.reason)
        self.assertIsInstance(plan.params[0].kind, Bytes)
        self.assertTrue(plan.params[0].out)
        self.assertEqual(plan.params[0].size_name, "buffer_size")
        self.assertEqual([p.name for p in plan.params], ["buffer", "data_offset"])

    def test_a_pointer_whose_size_is_not_known_stays_unsupported(self):
        # Only the pointers of the tables (SIZED_BUFFERS, BYTES_OUT, ITEM_BYTES, ...) are given a
        # size; any other `void*` says why it is not generated.
        plan = self.plan_in(self.everything, "CefV8Value", "CreateArrayBuffer")
        self.assertFalse(plan.supported)
        self.assertIn("V8", plan.reason)  # a reason in words, not "untyped pointer"

    def test_the_stub_shows_bytes(self):
        stub = self.generated("pyi")
        # CEF returns nothing for empty data, so it may be None (unlike other Create()).
        self.assertIn("def create(data: bytes | bytearray | memoryview) -> BinaryValue | None:",
                      stub)
        self.assertIn("def get_data(self, buffer_size: int, data_offset: int) -> bytes:", stub)

    def test_the_dialog_focus_and_download_handlers_are_generated(self):
        for name in ("CefFocusHandler", "CefJSDialogHandler", "CefDialogHandler",
                     "CefDownloadHandler"):
            self.assertTrue(self.scope.is_client(name), name)
        for name in ("CefJSDialogCallback", "CefFileDialogCallback", "CefBeforeDownloadCallback",
                     "CefDownloadItemCallback", "CefDownloadItem"):
            self.assertTrue(self.scope.is_library(name), name)
        plan = self.plan("CefJSDialogHandler", "OnJSDialog")
        self.assertTrue(plan.supported, plan.reason)
        self.assertEqual([name for name, _ in plan.results], ["return", "suppress_message"])
        plan = self.plan("CefDialogHandler", "OnFileDialog")
        self.assertTrue(plan.supported, plan.reason)
        stub = self.generated("pyi")
        for text in ("class FocusHandler:", "class JSDialogHandler:", "class DialogHandler:",
                     "class DownloadHandler:", "class JSDialogCallback:",
                     "class FileDialogCallback:", "class BeforeDownloadCallback:",
                     "def get_focus_handler(self)", "def get_js_dialog_handler(self)",
                     "def get_dialog_handler(self)", "def get_download_handler(self)"):
            self.assertIn(text, stub)

    def test_the_keyboard_handler_hides_the_platform_event_and_returns_the_out_pointer(self):
        # `CefEventHandle os_event` (XEvent* on Linux) is not given to Python, as in java-cef;
        # `bool* is_keyboard_shortcut` is an output like a reference.
        self.assertTrue(self.scope.is_client("CefKeyboardHandler"))
        plan = self.plan("CefKeyboardHandler", "OnPreKeyEvent")
        self.assertTrue(plan.supported, plan.reason)
        self.assertEqual([p.name for p in plan.ins], ["browser", "event"])
        self.assertEqual([name for name, _ in plan.results], ["return", "is_keyboard_shortcut"])
        self.assertIsInstance(plan.params[2].kind, Ignored)
        plan = self.plan("CefKeyboardHandler", "OnKeyEvent")
        self.assertTrue(plan.supported, plan.reason)
        self.assertEqual([p.name for p in plan.ins], ["browser", "event"])
        stub = self.generated("pyi")
        self.assertIn("def on_pre_key_event(self, browser: Browser, event: KeyEvent) -> tuple[bool, bool]:",
                      stub)
        self.assertIn("def on_key_event(self, browser: Browser, event: KeyEvent) -> bool:", stub)
        self.assertIn("def get_keyboard_handler(self) -> KeyboardHandler | None:", stub)

    def test_a_handler_method_may_return_a_struct(self):
        # GetPdfPaperSize() returns a CefSize: the Python method returns a Size.
        self.assertTrue(self.scope.is_client("CefPrintHandler"))
        plan = self.plan("CefPrintHandler", "GetPdfPaperSize")
        self.assertTrue(plan.supported, plan.reason)
        self.assertEqual([name for name, _ in plan.results], ["result"])
        self.assertIsInstance(plan.results[0][1], Struct)
        for name in ("OnPrintStart", "OnPrintSettings", "OnPrintDialog", "OnPrintJob",
                     "OnPrintReset"):
            plan = self.plan("CefPrintHandler", name)
            self.assertTrue(plan.supported, "%s: %s" % (name, plan.reason))
        stub = self.generated("pyi")
        self.assertIn("def get_pdf_paper_size(self, browser: Browser, device_units_per_inch: int)"
                      " -> Size | tuple[int, int]:", stub)
        with open(generate_outputs()["proxies"], encoding="utf-8") as f:
            header = f.read()
        self.assertIn("CefSize GetPdfPaperSize(", header)

    def test_the_request_handlers_are_generated(self):
        for name in ("CefRequestHandler", "CefResourceRequestHandler"):
            self.assertTrue(self.scope.is_client(name), name)
        for name in ("CefAuthCallback", "CefSSLInfo", "CefUnresponsiveProcessCallback"):
            self.assertTrue(self.scope.is_library(name), name)
        plan = self.plan("CefRequestHandler", "GetResourceRequestHandler")
        self.assertTrue(plan.supported, plan.reason)
        self.assertEqual([name for name, _ in plan.results], ["return", "disable_default_handling"])
        for name in ("OnBeforeBrowse", "GetAuthCredentials", "OnCertificateError",
                     "OnRenderProcessTerminated"):
            plan = self.plan("CefRequestHandler", name)
            self.assertTrue(plan.supported, "%s: %s" % (name, plan.reason))
        plan = self.plan("CefResourceRequestHandler", "OnBeforeResourceLoad")
        self.assertTrue(plan.supported, plan.reason)
        stub = self.generated("pyi")
        for text in ("class RequestHandler:", "class ResourceRequestHandler:",
                     "class AuthCallback:", "def get_request_handler(self) -> RequestHandler | None:"):
            self.assertIn(text, stub)

    def test_a_pointer_with_size_and_count_is_read_and_written_in_items(self):
        # Write(const void* ptr, size_t size, size_t n) is fwrite: n items of size bytes. The
        # Python method takes the bytes and the item size and returns the items written.
        for name in ("CefStreamReader", "CefStreamWriter", "CefZipReader"):
            self.assertTrue(self.scope.is_library(name), name)
        plan = self.plan("CefStreamWriter", "Write")
        self.assertTrue(plan.supported, plan.reason)
        self.assertIsInstance(plan.params[0].kind, ItemBytes)
        self.assertFalse(plan.params[0].out)
        plan = self.plan("CefStreamReader", "Read")
        self.assertTrue(plan.supported, plan.reason)
        self.assertIsInstance(plan.params[0].kind, ItemBytes)
        self.assertTrue(plan.params[0].out)
        stub = self.generated("pyi")
        for text in ("def write(self, data: bytes | bytearray | memoryview, size: int = 1) -> int:",
                     "def read(self, n: int, size: int = 1) -> bytes:",
                     "def read_file(self, buffer_size: int) -> bytes:",
                     "def create_for_data(data: bytes | bytearray | memoryview) -> StreamReader | None:"):
            self.assertIn(text, stub)

    def test_the_stream_handlers_get_a_buffer_of_size_times_count(self):
        for name in ("CefReadHandler", "CefWriteHandler"):
            self.assertTrue(self.scope.is_client(name), name)
        plan = self.plan("CefReadHandler", "Read")
        self.assertTrue(plan.supported, plan.reason)
        self.assertEqual([p.name for p in plan.ins], ["ptr", "size"])  # n is the buffer's length
        self.assertFalse(plan.params[0].kind.readonly)
        plan = self.plan("CefWriteHandler", "Write")
        self.assertTrue(plan.supported, plan.reason)
        self.assertTrue(plan.params[0].kind.readonly)
        stub = self.generated("pyi")
        self.assertIn("def read(self, ptr: memoryview, size: int) -> int:", stub)
        self.assertIn("def write(self, ptr: memoryview, size: int) -> int:", stub)

    def test_a_time_is_a_datetime(self):
        # CefBaseTime is microseconds since 1601 in UTC (cef_time.h): a timezone-aware datetime.
        plan = self.plan("CefZipReader", "GetFileLastModified")
        self.assertTrue(plan.supported, plan.reason)
        self.assertIsInstance(plan.ret, Time)
        for name in ("GetStartTime", "GetEndTime"):
            plan = self.plan("CefDownloadItem", name)
            self.assertTrue(plan.supported, "%s: %s" % (name, plan.reason))
        plan = self.plan_in(self.everything, "CefV8Value", "CreateDate")  # a time given to CEF
        self.assertTrue(plan.supported, plan.reason)
        self.assertIsInstance(plan.params[0].kind, Time)
        stub = self.generated("pyi")
        self.assertIn("def get_file_last_modified(self) -> datetime.datetime | None:", stub)
        self.assertIn("import datetime", stub)

    def test_the_post_data_bytes_have_their_own_order_of_size_and_pointer(self):
        # SetToBytes(size_t size, const void* bytes) and GetBytes(size_t size, void* bytes).
        for name in ("CefPostData", "CefPostDataElement"):
            self.assertTrue(self.scope.is_library(name), name)
        plan = self.plan("CefPostDataElement", "SetToBytes")
        self.assertTrue(plan.supported, plan.reason)
        self.assertIsInstance(plan.params[0].kind, Bytes)
        self.assertEqual([p.name for p in plan.ins], ["bytes"])
        plan = self.plan("CefPostDataElement", "GetBytes")
        self.assertTrue(plan.supported, plan.reason)
        self.assertTrue(plan.params[0].out or plan.params[1].out)
        for name in ("GetPostData", "SetPostData"):
            plan = self.plan("CefRequest", name)
            self.assertTrue(plan.supported, "%s: %s" % (name, plan.reason))
        stub = self.generated("pyi")
        self.assertIn("def set_to_bytes(self, bytes: bytes | bytearray | memoryview) -> None:", stub)
        self.assertIn("def get_bytes(self, size: int) -> bytes:", stub)

    def test_the_array_buffer_with_a_copy_takes_bytes(self):
        plan = self.plan_in(self.everything, "CefV8Value", "CreateArrayBufferWithCopy")
        self.assertTrue(plan.supported, plan.reason)
        self.assertIsInstance(plan.params[0].kind, Bytes)

    def test_every_pointer_to_void_is_generated_or_says_why(self):
        # A `void*` the tables do not know is not left as "untyped pointer": the ones that stay
        # out are pointers into memory that CEF or V8 owns (or that CEF keeps), each with its
        # reason. Methods out for another type (a multimap) are not about the pointer.
        deliberate = {
            "CefBinaryValue::GetRawData", "CefSharedMemoryRegion::Memory",
            "CefSharedProcessMessageBuilder::Memory", "CefV8BackingStore::Data",
            "CefV8Value::GetArrayBufferData", "CefV8Value::CreateArrayBuffer",
            "CefV8ArrayBufferReleaseCallback::ReleaseBuffer",
            "CefResourceBundleHandler::GetDataResource",
            "CefResourceBundleHandler::GetDataResourceForScale",
        }
        out = {}
        for name, cls in sorted(self.model.classes.items()):
            for method in list(cls.get_virtual_funcs()) + list(cls.get_static_funcs()):
                plan = self.plan_method(self.model, self.everything, name, method,
                                        client_side=cls.is_client_side())
                types = [method.get_retval().get_type()] + [x.get_type() for x in method.get_arguments()]
                if (any(t.get_type() == "void" and t.is_byaddr() for t in types)
                        or "%s::%s" % (name, plan.cef_name) in deliberate) and not plan.supported:
                    out["%s::%s" % (name, plan.cef_name)] = plan.reason
        self.assertTrue(deliberate <= set(out), deliberate - set(out))
        for name, reason in out.items():
            for generic in ("untyped pointer", "pointer to void", "struct-like value type void"):
                self.assertNotIn(generic, reason, name)
            if name in deliberate:
                self.assertGreater(len(reason), 40, name)  # a sentence, not a type name

    def test_the_proxies_of_the_handlers_with_buffers_compile_in_a_wide_scope(self):
        # Handlers outside the scope that take a `const void*` (DevTools messages, WebSocket
        # data, downloaded data, response filters): a const pointer is declared const and read
        # only, which a header check of the current scope alone would not show.
        import emit_cpp
        import scope as scope_module
        wide = scope_module.Scope(
            self.model, scope_module.LIBRARY_CLASSES,
            scope_module.CLIENT_CLASSES + ["CefDevToolsMessageObserver", "CefMediaObserver",
                                           "CefServerHandler", "CefURLRequestClient",
                                           "CefResponseFilter"], [])
        plans = {}
        for cls in wide.library_classes + wide.client_classes:
            side = cls.is_client_side()
            plans[cls.get_name()] = (
                [self.plan_method(self.model, wide, cls.get_name(), m, client_side=side)
                 for m in cls.get_virtual_funcs()])
        text = emit_cpp.emit(self.model, wide, plans, "test")
        self.assertIn("const void* message", text)  # OnDevToolsMessage keeps its const
        with tempfile.TemporaryDirectory() as tmp:
            header = os.path.join(tmp, "wide_proxies.h")
            with open(header, "w", encoding="utf-8") as f:
                f.write(text)
            path = os.path.join(tmp, "wide.cc")
            with open(path, "w", encoding="utf-8") as f:
                f.write('#include "wide_proxies.h"\n')
            result = subprocess.run(
                ["c++", "-std=c++20", "-fsyntax-only", "-I" + CEF_ROOT, "-I" + tmp, path],
                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr[-3000:])

    # What java-cef opens and cefweaver has not generated yet. java-cef is the floor of the API
    # (tools/gen/surface.py): this list only shrinks, and a method that is added or removed
    # without changing it fails here. When a gap is closed, delete it from this table.
    EXPECTED_GAPS = {
        "CefBrowserHost": ["DragTargetDragEnter"],
        "CefCommandLine": None, "CefCookieAccessFilter": None, "CefCookieManager": None,
        "CefDragData": None, "CefRequestContext": None,
        "CefRequestContextHandler": None, "CefSchemeRegistrar": None, "CefURLRequest": None,
        "CefURLRequestClient": None,
        "CefDragHandler": ["OnDragEnter"],
        "CefRenderHandler": ["StartDragging"],
        "CefResourceRequestHandler": ["GetCookieAccessFilter"],
    }

    def test_the_gaps_to_the_java_cef_floor_are_the_listed_ones(self):
        import report
        gaps = report.java_cef_gaps(self.model, self.scope)
        found = {name: (methods if name in self.scope._library | self.scope._client else None)
                 for name, (methods, _) in gaps.items()}
        self.assertEqual(found, self.EXPECTED_GAPS)

    def test_the_java_cef_list_names_only_cef_methods_of_known_classes(self):
        # surface.py is derived from java-cef's code; a name that is no CEF method is java-cef's own
        # (a Java-side helper) and is ignored, but every class of CEF in it must exist.
        from surface import SURFACE
        own = {"CefMessageRouter", "CefQueryCallback", "CefRegistration"}
        for name, methods in SURFACE.items():
            if name in own:
                continue
            self.assertIn(name, self.model.classes, name)
            header = {m.get_name() for m in list(self.model.classes[name].get_virtual_funcs())
                      + list(self.model.classes[name].get_static_funcs())}
            if name not in ("CefBrowser", "CefBrowserHost", "CefFrame", "CefClient"):
                self.assertTrue(methods & header, name)  # it opens something that exists

    def test_arguments_java_cef_does_not_pass_are_left_out(self):
        # java-cef gives Java the URL and the frame name of a popup, the cursor type, and the
        # certificate error without its ssl_info: the rest is not given to Python.
        plan = self.plan("CefLifeSpanHandler", "OnBeforePopup")
        self.assertTrue(plan.supported, plan.reason)
        self.assertEqual([p.name for p in plan.ins], ["browser", "frame", "target_url",
                                                      "target_frame_name"])
        plan = self.plan("CefDisplayHandler", "OnCursorChange")
        self.assertTrue(plan.supported, plan.reason)
        self.assertEqual([p.name for p in plan.ins], ["browser", "type"])
        plan = self.plan("CefRequestHandler", "OnCertificateError")
        self.assertTrue(plan.supported, plan.reason)
        self.assertNotIn("ssl_info", [p.name for p in plan.ins])
        stub = self.generated("pyi")
        self.assertIn("def on_before_popup(self, browser: Browser, frame: Frame, target_url: str, "
                      "target_frame_name: str) -> bool:", stub)
        self.assertIn("def on_cursor_change(self, browser: Browser, type: CursorType) -> bool:", stub)
        with open(generate_outputs()["proxies"], encoding="utf-8") as f:
            header = f.read()
        # the C++ side still declares every parameter of the CEF method
        self.assertIn("CefWindowInfo& windowInfo", header)
        self.assertIn("bool* no_javascript_access", header)

    def test_header_maps_are_dicts_as_in_java_cef(self):
        # std::multimap<CefString, CefString> is a Java Map in java-cef, a dict here.
        for cls, name in (("CefRequest", "GetHeaderMap"), ("CefRequest", "SetHeaderMap"),
                          ("CefRequest", "Set"), ("CefResponse", "GetHeaderMap"),
                          ("CefResponse", "SetHeaderMap")):
            plan = self.plan(cls, name)
            self.assertTrue(plan.supported, "%s::%s: %s" % (cls, name, plan.reason))
        plan = self.plan("CefRequest", "GetHeaderMap")
        self.assertIsInstance(plan.params[0].kind, StrMap)
        self.assertTrue(plan.params[0].out)
        stub = self.generated("pyi")
        for text in ("def get_header_map(self) -> dict[str, str]:",
                     "def set_header_map(self, header_map: dict[str, str]) -> None:",
                     "def set(self, url: str, method: str, post_data: PostData | None, "
                     "header_map: dict[str, str]) -> None:"):
            self.assertIn(text, stub)

    def test_a_window_handle_is_an_integer(self):
        plan = self.plan("CefBrowserHost", "GetWindowHandle")
        self.assertTrue(plan.supported, plan.reason)
        self.assertIsInstance(plan.ret, Prim)
        self.assertEqual(plan.ret.py, "int")
        self.assertIn("def get_window_handle(self) -> int:", self.generated("pyi"))

    def test_the_visitor_the_file_dialog_callback_and_the_devtools_observer_are_generated(self):
        for name in ("CefStringVisitor", "CefRunFileDialogCallback", "CefDevToolsMessageObserver"):
            self.assertTrue(self.scope.is_client(name), name)
        self.assertTrue(self.scope.is_library("CefRegistration"))
        for cls, name in (("CefFrame", "GetSource"), ("CefFrame", "GetText"),
                          ("CefBrowserHost", "RunFileDialog"),
                          ("CefBrowserHost", "AddDevToolsMessageObserver")):
            plan = self.plan(cls, name)
            self.assertTrue(plan.supported, "%s::%s: %s" % (cls, name, plan.reason))
        stub = self.generated("pyi")
        for text in ("class StringVisitor:", "def visit(self, string: str) -> None:",
                     "class RunFileDialogCallback:",
                     "def on_file_dialog_dismissed(self, file_paths: list[str]) -> None:",
                     "class DevToolsMessageObserver:", "class Registration:",
                     "def add_dev_tools_message_observer(self, observer: DevToolsMessageObserver) "
                     "-> Registration | None:"):
            self.assertIn(text, stub)

    def test_structs_with_strings_and_times_are_read_from_the_traits_classes(self):
        # CefPdfPrintSettings, CefCookie: `using CefX = CefStructBase<CefXTraits>`, with
        # cef_string_t members (str), cef_basetime_t members (datetime) and a `size` header.
        pdf = self.model.structs["CefPdfPrintSettings"]
        fields = {f.name: f for f in pdf.fields}
        self.assertEqual(fields["page_ranges"].py, "str")
        self.assertTrue(fields["page_ranges"].string)
        self.assertEqual(fields["margin_type"].py, "PdfPrintMarginType")
        self.assertEqual(fields["scale"].py, "float")
        self.assertNotIn("size", fields)
        cookie = {f.name: f for f in self.model.structs["CefCookie"].fields}
        self.assertTrue(cookie["creation"].time)
        self.assertEqual(cookie["same_site"].py, "CookieSameSite")
        self.assertTrue(cookie["name"].string)
        self.assertIn("CefRequestContextSettings", self.model.structs)

    def test_print_to_pdf_takes_the_settings_and_a_callback(self):
        self.assertTrue(self.scope.is_client("CefPdfPrintCallback"))
        plan = self.plan("CefBrowserHost", "PrintToPDF")
        self.assertTrue(plan.supported, plan.reason)
        stub = self.generated("pyi")
        self.assertIn("class PdfPrintCallback:", stub)
        self.assertIn("def on_pdf_print_finished(self, path: str, ok: bool) -> None:", stub)
        self.assertIn("def print_to_pdf(self, path: str, settings: PdfPrintSettings | tuple[", stub)
        with open(generate_outputs()["types"], encoding="utf-8") as f:
            types_text = f.read()
        self.assertIn("class PdfPrintSettings(NamedTuple):", types_text)
        self.assertIn("    page_ranges: str = \"\"\n", types_text)
        self.assertIn("    scale: float = 0.0\n", types_text)
        self.assertIn("    x: int = 0\n", types_text)             # every struct has defaults
        self.assertIn("    bounds: Rect = Rect()\n", types_text)    # a nested struct too

    def test_the_render_handler_is_generated_and_gives_a_read_only_view(self):
        self.assertTrue(self.scope.is_client("CefRenderHandler"))
        files = generate_outputs()
        with open(files["pxi"], encoding="utf-8") as f:
            self.assertIn("PyBUF_READ", f.read())
        with open(files["pyi"], encoding="utf-8") as f:
            stub = f.read()
        self.assertIn("class RenderHandler:", stub)
        self.assertIn("def on_paint(self, browser: Browser, type: PaintElementType, "
                      "dirty_rects: list[Rect], buffer: memoryview, width: int, height: int)",
                      stub)

    def test_enumerations_are_told_apart_from_structs(self):
        plan = self.plan("CefRequest", "GetResourceType")
        self.assertTrue(plan.supported, plan.reason)
        self.assertEqual(plan.ret, Enum("ResourceType", "cef_resource_type_t"))

    def test_unsupported_types_are_reported_with_a_reason(self):
        plan = self.plan("CefDownloadItem", "GetSuggestedFileName")
        self.assertTrue(plan.supported, plan.reason)
        plan = self.plan("CefBrowserHost", "GetNavigationEntries")
        self.assertFalse(plan.supported)
        self.assertIn("CefNavigationEntryVisitor is not generated yet", plan.reason)

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
        plan = self.plan("CefClient", "GetAudioHandler")
        self.assertFalse(plan.supported)
        self.assertIn("CefAudioHandler is not generated yet", plan.reason)

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

    def test_structs_with_a_size_header_and_enumeration_members_are_read(self):
        # `size` is the C API's version header (the C++ class sets it); an enumeration
        # member is a Python enumeration.
        key = self.model.structs["CefKeyEvent"]
        self.assertEqual([(f.name, f.py) for f in key.fields],
                         [("type", "KeyEventType"), ("modifiers", "int"),
                          ("windows_key_code", "int"), ("native_key_code", "int"),
                          ("is_system_key", "int"), ("character", "int"),
                          ("unmodified_character", "int"), ("focus_on_editable_field", "int")])
        self.assertEqual(key.fields[0].cpp, "cef_key_event_type_t")
        screen = self.model.structs["CefScreenInfo"]
        self.assertEqual([(f.name, f.py) for f in screen.fields],
                         [("device_scale_factor", "float"), ("depth", "int"),
                          ("depth_per_component", "int"), ("is_monochrome", "int"),
                          ("rect", "Rect"), ("available_rect", "Rect")])
        popup = self.model.structs["CefPopupFeatures"]
        self.assertEqual([f.cname for f in popup.fields][:3], ["x", "xSet", "y"])
        self.assertEqual([f.name for f in popup.fields][:3], ["x", "x_set", "y"])
        for name in ("CefTouchEvent", "CefTouchHandleState", "CefCompositionUnderline"):
            self.assertIn(name, self.model.structs)
        # What has pointers or strings stays out.
        for name in ("CefCursorInfo", "CefAcceleratedPaintInfo", "CefSettings"):
            self.assertNotIn(name, self.model.structs, name)

    def test_methods_that_take_the_new_structs_are_generated(self):
        for cls, method in (("CefBrowserHost", "SendKeyEvent"),
                            ("CefBrowserHost", "SendTouchEvent"),
                            ("CefRenderHandler", "GetScreenInfo"),
                            ("CefRenderHandler", "OnTouchHandleStateChanged")):
            plan = self.plan(cls, method)
            self.assertTrue(plan.supported, "%s::%s: %s" % (cls, method, plan.reason))
        plan = self.plan("CefRenderHandler", "GetScreenInfo")
        self.assertEqual([name for name, _ in plan.results], ["return", "screen_info"])

    def test_a_vector_of_structs_with_a_size_header_goes_to_a_library_method(self):
        plan = self.plan("CefBrowserHost", "ImeSetComposition")
        self.assertTrue(plan.supported, plan.reason)
        self.assertIsInstance(plan.params[1].kind, Vector)
        self.assertEqual(plan.params[1].kind.element.cls, "CefCompositionUnderline")

    def test_the_new_structs_are_in_the_types_module_and_the_stub(self):
        files = generate_outputs()
        with open(files["types"], encoding="utf-8") as f:
            types_text = f.read()
        self.assertIn("class KeyEvent(NamedTuple):", types_text)
        self.assertIn("    type: KeyEventType = 0\n", types_text)
        self.assertIn("    x_set: int = 0\n", types_text)
        with open(files["pyi"], encoding="utf-8") as f:
            stub = f.read()
        self.assertIn("def send_key_event(self, event: KeyEvent | tuple[", stub)
        self.assertIn("def get_screen_info(self, browser: Browser) -> tuple[bool, ScreenInfo", stub)

    def test_field_names_avoid_python_keywords(self):
        range_ = self.model.structs["CefRange"]
        self.assertEqual([f.name for f in range_.fields], ["from_", "to"])
        self.assertEqual([f.cname for f in range_.fields], ["from", "to"])

    def test_structs_that_are_not_plain_data_stay_unsupported(self):
        # Pointers, arrays, strings: not plain data.
        for name in ("CefCursorInfo", "CefAcceleratedPaintInfo", "CefSettings"):
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

    def test_a_handler_returning_a_struct_is_supported_through_a_hidden_output(self):
        plan = self.plan_in(self.everything, "CefViewDelegate", "GetPreferredSize")
        self.assertTrue(plan.supported, plan.reason)
        self.assertIsInstance(plan.ret, Void)
        self.assertTrue(plan.params[-1].is_return)
        self.assertFalse(plan.void_return)

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
        self.assertIn("    from_: int = 0\n    to: int = 0", types_source)

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
        for cls, name in (("CefTranslatorTest", "SetRefPtrClientList"),):
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


    # -- the context menu ----------------------------------------------------------------

    def test_the_context_menu_classes_are_generated(self):
        self.assertTrue(self.scope.is_client("CefContextMenuHandler"))
        for name in ("CefContextMenuParams", "CefRunContextMenuCallback", "CefRunQuickMenuCallback"):
            self.assertTrue(self.scope.is_library(name), name)
        plan = self.plan("CefClient", "GetContextMenuHandler")
        self.assertTrue(plan.supported, plan.reason)
        self.assertEqual(plan.ret, ClientRef("CefContextMenuHandler"))

    def test_every_context_menu_handler_method_is_generated(self):
        cls = self.model.classes["CefContextMenuHandler"]
        for method in cls.get_virtual_funcs():
            plan = self.plan("CefContextMenuHandler", method.get_name())
            self.assertTrue(plan.supported, "%s: %s" % (method.get_name(), plan.reason))

    def test_a_menu_handler_can_replace_the_menu_and_choose_an_item(self):
        # RunContextMenu gets the callback that picks an item: this is how a program opens a
        # menu and chooses from it without any user interface.
        plan = self.plan("CefContextMenuHandler", "RunContextMenu")
        self.assertEqual([k.cls for k in (p.kind for p in plan.params)],
                         ["CefBrowser", "CefFrame", "CefContextMenuParams", "CefMenuModel",
                          "CefRunContextMenuCallback"])
        self.assertEqual(plan.ret, Prim("bool", "bool"))
        plan = self.plan_in(self.scope, "CefRunContextMenuCallback", "Continue")
        self.assertTrue(plan.supported, plan.reason)
        self.assertEqual(plan.name, "continue_")

    def test_the_menu_parameters_include_a_list_of_suggestions(self):
        plan = self.plan_in(self.scope, "CefContextMenuParams", "GetDictionarySuggestions")
        self.assertTrue(plan.supported, plan.reason)
        self.assertEqual(plan.outs[0].kind, Vector(Str()))

    def test_the_context_menu_handler_can_be_forwarded_by_the_wrapper(self):
        self.assertIn("class CwContextMenuHandlerForward : public CefContextMenuHandler {",
                      self.generated("proxies"))

    def test_the_stub_declares_the_context_menu_handler(self):
        stub = self.generated("pyi")
        self.assertIn("def on_before_context_menu(self, browser: Browser, frame: Frame, "
                      "params: ContextMenuParams, model: MenuModel) -> None:", stub)
        self.assertIn("def get_context_menu_handler(self) -> ContextMenuHandler | None:", stub)


    # -- process messages and the value containers --------------------------------------

    def test_the_value_containers_and_the_process_message_are_generated(self):
        for name in ("CefProcessMessage", "CefListValue", "CefDictionaryValue", "CefValue",
                     "CefBinaryValue"):
            self.assertTrue(self.scope.is_library(name), name)

    def test_a_frame_can_send_a_process_message(self):
        plan = self.plan("CefFrame", "SendProcessMessage")
        self.assertTrue(plan.supported, plan.reason)
        self.assertEqual([type(p.kind).__name__ for p in plan.params], ["Enum", "LibRef"])
        self.assertEqual(plan.params[0].kind.py, "ProcessId")

    def test_the_client_receives_process_messages(self):
        plan = self.plan("CefClient", "OnProcessMessageReceived")
        self.assertTrue(plan.supported, plan.reason)
        self.assertEqual([type(p.kind).__name__ for p in plan.params],
                         ["LibRef", "LibRef", "Enum", "LibRef"])
        self.assertEqual(plan.ret, Prim("bool", "bool"))

    def test_the_binary_value_opens_bytes_but_not_the_pointer_to_its_memory(self):
        for name in ("Create", "GetData"):
            plan = self.plan("CefBinaryValue", name)
            self.assertTrue(plan.supported, "%s: %s" % (name, plan.reason))
        # The memory belongs to CEF and can end with the object: get_data() copies instead.
        plan = self.plan("CefBinaryValue", "GetRawData")
        self.assertFalse(plan.supported)
        self.assertIn("pointer", plan.reason)

    def test_the_value_types_have_a_type_enumeration(self):
        plan = self.plan("CefListValue", "GetType")
        self.assertTrue(plan.supported, plan.reason)
        self.assertEqual(plan.ret.py, "ValueType")

    def test_the_stub_declares_the_process_message_api(self):
        stub = self.generated("pyi")
        self.assertIn("def send_process_message(self, target_process: ProcessId | int, "
                      "message: ProcessMessage) -> None:", stub)
        self.assertIn("def on_process_message_received(self, browser: Browser, frame: Frame, "
                      "source_process: ProcessId, message: ProcessMessage) -> bool:", stub)


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
