"""Smoke tests for the installed cefweaver wheel (Linux).

Run against the *installed* wheel, on a virtual X server so that no window opens
on the desktop (Chromium prefers Wayland when WAYLAND_DISPLAY is set)::

    uv build --wheel && uv pip install dist/cefweaver-*.whl
    env -u WAYLAND_DISPLAY xvfb-run -a python -P -m unittest discover -s tests -v

`-P` keeps the current directory out of sys.path. Without it, run from the repository
root, the source tree `cefweaver/` shadows the installed wheel and the CEF tests are
skipped (the run still ends with OK).

CEF can be initialized only once per process, so each test that starts CEF runs
its script in a separate Python process.
"""

import os
import shutil
import subprocess
import sys
import textwrap
import unittest

try:
    import cefweaver
except ImportError:  # not installed, or run from the source tree
    cefweaver = None

RUNTIME_OK = (
    cefweaver is not None
    and sys.platform.startswith("linux")
    and os.path.exists(os.path.join(os.path.dirname(cefweaver.__file__), "libcef.so"))
)
HAS_X = bool(os.environ.get("DISPLAY")) and not os.environ.get("WAYLAND_DISPLAY")

PRELUDE = """
import base64, sys, tempfile, time
import cefweaver

def wait_until(app, condition, what, timeout=30):
    # CEF runs on this thread's message loop, so waiting means pumping it.
    # The timeout is only an upper bound: the loop ends as soon as `condition`
    # holds, and a timeout is reported as a failure naming what was awaited.
    end = time.time() + timeout
    while not condition():
        if time.time() > end:
            raise TimeoutError("timed out waiting for " + what)
        app.do_message_loop_work()
        time.sleep(0.005)

def send_until(app, send, delivered, what, timeout=30):
    # Input that reaches the browser before it takes input is dropped, not queued (and there
    # is no signal for "ready", not even the first frame), so send it again until it arrives.
    end = time.time() + timeout
    while not delivered():
        if time.time() > end:
            raise TimeoutError("timed out waiting for " + what)
        send()
        until = time.time() + 0.1
        while time.time() < until and not delivered():
            app.do_message_loop_work()
            time.sleep(0.005)

def page(body):
    html = '<html><head><meta charset="utf-8"></head><body>' + body + '</body></html>'
    return "data:text/html;base64," + base64.b64encode(html.encode()).decode()

app = cefweaver.CefApp()
app.set_cache_path(tempfile.mkdtemp(prefix="cefweaver-test-"))
app.add_command_line_switch("ozone-platform", "x11")
"""


def run_cef(script, timeout=90, ozone="x11"):
    """Run `script` (after PRELUDE) in a new process; return CompletedProcess."""
    # ozone=None leaves the platform to the wrapper (its default).
    line = '"ozone-platform", "x11"'
    prelude = PRELUDE.replace('app.add_command_line_switch(%s)' % line, "pass") if ozone is None \
        else PRELUDE.replace(line, '"ozone-platform", "%s"' % ozone)
    code = prelude + textwrap.dedent(script)
    return subprocess.run([sys.executable, "-I", "-c", code], capture_output=True,
                          text=True, timeout=timeout)


@unittest.skipIf(cefweaver is None, "cefweaver is not installed")
class ApiWithoutCef(unittest.TestCase):
    def test_calls_before_initialize_raise(self):
        app = cefweaver.CefApp()
        for call in (lambda: app.do_message_loop_work(),
                     lambda: app.load_url("about:blank"),
                     lambda: app.execute_javascript("1")):
            with self.assertRaises(RuntimeError):
                call()
        self.assertFalse(app.is_running)
        app.shutdown()  # harmless when never initialized

    def test_binding_must_be_callable(self):
        with self.assertRaises(TypeError):
            cefweaver.CefApp().add_javascript_binding("x", 3)

    def test_generated_names_are_public_and_pep8(self):
        for name in ("Request", "Response", "Callback", "ResourceHandler", "SchemeHandlerFactory",
                     "register_scheme_handler_factory", "get_mime_type"):
            self.assertIn(name, cefweaver.__all__)
        self.assertTrue(hasattr(cefweaver.Callback, "continue_"))  # Continue() is a keyword
        self.assertTrue(hasattr(cefweaver.Request, "get_url"))  # GetURL()
        self.assertEqual(cefweaver.get_mime_type("html"), "text/html")

    def test_library_objects_cannot_be_created_directly(self):
        with self.assertRaises(TypeError):
            cefweaver.Request()
        request = cefweaver.Request.create()
        request.set_url("http://example.test/a?b=1")
        self.assertEqual(request.get_url(), "http://example.test/a?b=1")

    def test_the_client_and_its_handlers_are_public(self):
        for name in ("Client", "LoadHandler", "LifeSpanHandler", "DisplayHandler"):
            self.assertIn(name, cefweaver.__all__)
        self.assertTrue(hasattr(cefweaver.Client, "get_load_handler"))
        self.assertTrue(hasattr(cefweaver.LoadHandler, "on_load_end"))

    def test_set_client_checks_its_argument(self):
        app = cefweaver.CefApp()
        with self.assertRaises(TypeError):
            app.set_client(object())
        with self.assertRaises(TypeError):
            app.set_client(cefweaver.LoadHandler())  # a handler, not a client
        app.set_client(cefweaver.Client())
        app.set_client(None)  # removes it again

    def test_value_types_are_named_tuples(self):
        for name in ("Point", "Rect", "Size", "Insets", "Range", "MouseEvent"):
            self.assertIn(name, cefweaver.__all__)
        rect = cefweaver.Rect(1, 2, 3, 4)
        self.assertEqual(rect, (1, 2, 3, 4))  # a tuple, so it also unpacks and compares
        self.assertEqual((rect.x, rect.y, rect.width, rect.height), (1, 2, 3, 4))
        self.assertEqual(cefweaver.Size._fields, ("width", "height"))
        self.assertEqual(cefweaver.Range._fields, ("from_", "to"))  # `from` is a keyword
        self.assertEqual(cefweaver.MouseEvent._fields, ("x", "y", "modifiers"))

    def test_the_browser_host_is_public(self):
        self.assertIn("BrowserHost", cefweaver.__all__)
        for name in ("close_browser", "try_close_browser", "send_mouse_click_event",
                     "send_mouse_move_event", "set_zoom_level", "get_zoom_level",
                     "set_auto_resize_enabled", "get_browser"):
            self.assertTrue(hasattr(cefweaver.BrowserHost, name), name)
        self.assertTrue(hasattr(cefweaver.Browser, "get_host"))

    def test_browser_lists_its_frames_as_lists_of_strings(self):
        self.assertTrue(hasattr(cefweaver.Browser, "get_frame_names"))
        self.assertTrue(hasattr(cefweaver.Browser, "get_frame_identifiers"))

    def test_the_types_module_has_the_enumerations_and_value_types(self):
        import enum
        from cefweaver import types
        self.assertIs(cefweaver.types, types)
        self.assertTrue(issubclass(types.MouseButtonType, enum.IntEnum))
        self.assertEqual(types.MouseButtonType.LEFT, 0)
        self.assertEqual(types.ErrorCode.CONNECTION_REFUSED, -102)
        self.assertTrue(issubclass(types.EventFlags, enum.IntFlag))
        self.assertIs(types.Rect, cefweaver.Rect)  # the same value types as in cefweaver
        self.assertEqual(types.Rect(1, 2, 3, 4), (1, 2, 3, 4))

    def test_library_methods_return_enumeration_members(self):
        from cefweaver import types
        request = cefweaver.Request.create()
        resource_type = request.get_resource_type()
        self.assertIsInstance(resource_type, types.ResourceType)
        self.assertEqual(resource_type, types.ResourceType.SUB_RESOURCE)  # the default
        self.assertEqual(resource_type, int(resource_type))  # and still an int
        request.set_url("http://example.test/")
        self.assertIsInstance(request.get_transition_type(), types.TransitionType)

    def test_the_menu_model_and_the_display_are_public(self):
        for name in ("MenuModel", "MenuModelDelegate", "Display"):
            self.assertIn(name, cefweaver.__all__)
        self.assertTrue(hasattr(cefweaver.MenuModel, "get_accelerator"))
        self.assertTrue(hasattr(cefweaver.Display, "convert_point_to_pixels"))

    def test_print_settings_and_the_drag_handler_are_public(self):
        for name in ("PrintSettings", "DragHandler"):
            self.assertIn(name, cefweaver.__all__)
        self.assertTrue(hasattr(cefweaver.PrintSettings, "get_page_ranges"))
        self.assertTrue(hasattr(cefweaver.Display, "get_all_displays"))

    def test_the_task_manager_is_public(self):
        self.assertIn("TaskManager", cefweaver.__all__)
        self.assertTrue(hasattr(cefweaver.TaskManager, "get_task_ids_list"))

    def test_the_context_menu_classes_and_the_devtools_switch_are_public(self):
        for name in ("ContextMenuHandler", "ContextMenuParams", "RunContextMenuCallback",
                     "RunQuickMenuCallback"):
            self.assertIn(name, cefweaver.__all__)
        app = cefweaver.CefApp()
        self.assertIs(app.devtools_menu, False)  # off by default
        app.devtools_menu = 1
        self.assertIs(app.devtools_menu, True)
        app.devtools_menu = False
        self.assertIs(app.devtools_menu, False)

    def test_the_process_message_and_the_value_containers_are_public(self):
        for name in ("ProcessMessage", "Value", "ListValue", "DictionaryValue", "BinaryValue"):
            self.assertIn(name, cefweaver.__all__)
        self.assertTrue(hasattr(cefweaver.Frame, "send_process_message"))

    def test_values_can_be_built_and_read_without_cef(self):
        from cefweaver import types
        values = cefweaver.ListValue.create()
        self.assertEqual(values.get_size(), 0)
        self.assertTrue(values.set_size(4))
        self.assertTrue(values.set_int(0, 7))
        self.assertTrue(values.set_string(1, "é한글"))
        self.assertTrue(values.set_bool(2, True))
        self.assertTrue(values.set_double(3, 2.5))
        self.assertEqual((values.get_int(0), values.get_string(1), values.get_bool(2),
                          values.get_double(3)), (7, "é한글", True, 2.5))
        self.assertIs(values.get_type(1), types.ValueType.STRING)  # a member, not a number
        self.assertIs(values.get_type(0), types.ValueType.INT)
        record = cefweaver.DictionaryValue.create()
        self.assertTrue(record.set_string("name", "x"))
        self.assertTrue(record.set_int("count", 5))
        self.assertEqual(sorted(record.get_keys()[1]), ["count", "name"])  # (ok, keys)
        self.assertTrue(record.has_key("name") and not record.has_key("other"))
        values.set_size(5)
        self.assertTrue(values.set_dictionary(4, record))  # the dictionary is copied in
        self.assertEqual(values.get_dictionary(4).get_string("name"), "x")
        message = cefweaver.ProcessMessage.create("my-message")
        self.assertEqual(message.get_name(), "my-message")
        self.assertTrue(message.is_valid())
        self.assertEqual(message.get_argument_list().get_size(), 0)

    def test_the_message_router_api_is_public_and_checks_its_arguments(self):
        for name in ("QueryHandler", "QueryCallback"):
            self.assertIn(name, cefweaver.__all__)
        app = cefweaver.CefApp()
        with self.assertRaises(TypeError):
            app.add_query_handler(object())
        with self.assertRaises(TypeError):
            app.set_query_functions(1, "cancel")
        with self.assertRaises(ValueError):
            app.set_query_functions("", "cancel")
        handler = cefweaver.QueryHandler()
        app.add_query_handler(handler)
        self.assertFalse(app.remove_query_handler(cefweaver.QueryHandler()))  # never added
        self.assertTrue(app.remove_query_handler(handler))
        self.assertFalse(app.remove_query_handler(handler))  # already removed

    def test_the_offscreen_api_is_public_and_checks_its_arguments(self):
        self.assertIn("RenderHandler", cefweaver.__all__)
        self.assertTrue(hasattr(cefweaver.Client, "get_render_handler"))
        app = cefweaver.CefApp()
        self.assertIs(app.offscreen, False)
        app.offscreen = True
        self.assertIs(app.offscreen, True)
        self.assertEqual(app.windowless_frame_rate, 30)
        app.windowless_frame_rate = 60
        self.assertEqual(app.windowless_frame_rate, 60)
        for bad in (0, -1, 1000):
            with self.assertRaises(ValueError):
                app.windowless_frame_rate = bad

    def test_the_structs_with_a_size_header_are_public_values(self):
        for name in ("KeyEvent", "ScreenInfo", "PopupFeatures", "TouchEvent", "TouchHandleState",
                     "CompositionUnderline"):
            self.assertIn(name, cefweaver.__all__)
            self.assertTrue(issubclass(getattr(cefweaver, name), tuple), name)
        event = cefweaver.KeyEvent(cefweaver.types.KeyEventType.CHAR, 0, 97, 0, 0, 97, 97, 0)
        self.assertEqual(event.type, cefweaver.types.KeyEventType.CHAR)
        self.assertEqual(event._fields, (
            "type", "modifiers", "windows_key_code", "native_key_code", "is_system_key",
            "character", "unmodified_character", "focus_on_editable_field"))
        self.assertEqual(cefweaver.PopupFeatures._fields[:4], ("x", "x_set", "y", "y_set"))
        self.assertEqual(cefweaver.ScreenInfo._fields[-2:], ("rect", "available_rect"))

    def test_binary_values_take_and_give_bytes(self):
        data = b"\x00\x01\xfe\xff abc"
        value = cefweaver.BinaryValue.create(data)
        self.assertEqual(value.get_size(), 8)
        self.assertEqual(value.get_data(8, 0), data)
        self.assertEqual(value.get_data(3, 5), b"abc")       # from an offset
        self.assertEqual(value.get_data(100, 6), b"bc")      # less is left than asked for
        self.assertEqual(value.get_data(4, 8), b"")          # nothing is left
        for other in (bytearray(b"xy"), memoryview(b"xy")):
            self.assertEqual(cefweaver.BinaryValue.create(other).get_data(2, 0), b"xy")
        # CEF has no empty binary value: create() gives None for no bytes (values_impl.cc).
        self.assertIsNone(cefweaver.BinaryValue.create(b""))
        for bad in ("text", 5, None, [1, 2]):
            with self.assertRaises(TypeError):
                cefweaver.BinaryValue.create(bad)
        with self.assertRaises(OverflowError):
            value.get_data(-1, 0)
        # As a copy, and in a list. The list takes the value over (it is not valid afterwards,
        # as CEF documents), so the copy is made first.
        duplicate = value.copy()
        self.assertEqual(duplicate.get_data(8, 0), data)
        items = cefweaver.ListValue.create()
        items.set_size(1)
        items.set_binary(0, value)
        self.assertEqual(items.get_binary(0).get_data(8, 0), data)
        self.assertIsNone(value.copy())

    def test_streams_read_and_write_bytes_in_items(self):
        import tempfile, os
        folder = tempfile.mkdtemp()
        path = os.path.join(folder, "data.bin")
        writer = cefweaver.StreamWriter.create_for_file(path)
        self.assertEqual(writer.write(b"hello"), 5)              # items of one byte
        self.assertEqual(writer.write(b"abcdef", 2), 3)          # three items of two bytes
        self.assertEqual(writer.write(b""), 0)
        with self.assertRaises(ValueError):
            writer.write(b"abc", 2)                              # not a whole number of items
        with self.assertRaises(ValueError):
            writer.write(b"abc", 0)
        with self.assertRaises(TypeError):
            writer.write("text")
        self.assertEqual(writer.tell(), 11)
        self.assertEqual(writer.flush(), 0)
        reader = cefweaver.StreamReader.create_for_file(path)
        self.assertEqual(reader.read(5), b"hello")
        self.assertEqual(reader.read(2, 2), b"abcd")             # two items of two bytes
        self.assertEqual(reader.tell(), 9)
        self.assertEqual(reader.read(100), b"ef")                # less is left than asked for
        self.assertTrue(reader.eof())
        self.assertEqual(reader.read(4), b"")
        self.assertEqual(reader.seek(1, os.SEEK_SET), 0)
        self.assertEqual(reader.read(3), b"ell")
        with self.assertRaises(OverflowError):
            reader.read(-1)
        data = cefweaver.StreamReader.create_for_data(b"0123456789")
        self.assertEqual(data.read(4), b"0123")
        self.assertIsNone(cefweaver.StreamReader.create_for_data(b""))   # CEF has no empty one

    def test_python_objects_can_be_the_source_and_the_sink_of_a_stream(self):
        class Source(cefweaver.ReadHandler):
            def __init__(self):
                self.data, self.offset = b"abcdefghij", 0
            def read(self, ptr, size):
                count = min(len(ptr) // size, (len(self.data) - self.offset) // size)
                ptr[:count * size] = self.data[self.offset:self.offset + count * size]
                self.offset += count * size
                return count
            def seek(self, offset, whence):
                self.offset = offset
                return 0
            def tell(self):
                return self.offset
            def eof(self):
                return int(self.offset >= len(self.data))
            def may_block(self):
                return False
        class Sink(cefweaver.WriteHandler):
            def __init__(self):
                self.parts = []
            def write(self, ptr, size):
                self.parts.append((bytes(ptr), size))
                return len(ptr) // size
            def seek(self, offset, whence):
                return 0
            def tell(self):
                return sum(len(p) for p, _ in self.parts)
            def flush(self):
                return 0
            def may_block(self):
                return False
        reader = cefweaver.StreamReader.create_for_handler(Source())
        self.assertEqual(reader.read(4), b"abcd")
        self.assertEqual(reader.read(3, 2), b"efghij")           # three items of two bytes
        self.assertTrue(reader.eof())
        sink = Sink()
        writer = cefweaver.StreamWriter.create_for_handler(sink)
        self.assertEqual(writer.write(b"xyz"), 3)
        self.assertEqual(writer.write(b"1234", 2), 2)
        self.assertEqual(sink.parts, [(b"xyz", 1), (b"1234", 2)])

    def test_a_zip_reader_reads_a_file_of_the_archive(self):
        import datetime, tempfile, os, zipfile
        path = os.path.join(tempfile.mkdtemp(), "a.zip")
        with zipfile.ZipFile(path, "w") as archive:
            first = zipfile.ZipInfo("first.txt", date_time=(2020, 1, 2, 12, 0, 0))
            archive.writestr(first, "one" * 100)
            archive.writestr("second.txt", "two")
        zip_reader = cefweaver.ZipReader.create(cefweaver.StreamReader.create_for_file(path))
        self.assertTrue(zip_reader.move_to_first_file())
        self.assertEqual(zip_reader.get_file_name(), "first.txt")
        self.assertEqual(zip_reader.get_file_size(), 300)
        modified = zip_reader.get_file_last_modified()     # a datetime in UTC (the zip has no zone)
        self.assertIsNotNone(modified.tzinfo)
        self.assertLess(abs((modified - datetime.datetime(2020, 1, 2, 12, tzinfo=datetime.timezone.utc))
                            .total_seconds()), 24 * 3600)
        self.assertTrue(zip_reader.open_file(""))
        self.assertEqual(zip_reader.read_file(100), b"one" * 33 + b"o")  # a part of the file
        self.assertEqual(zip_reader.read_file(1000), b"ne" + b"one" * 66)  # the rest
        self.assertEqual(zip_reader.read_file(10), b"")                    # the end of the file
        self.assertTrue(zip_reader.close_file())
        self.assertTrue(zip_reader.move_to_next_file())
        self.assertEqual(zip_reader.get_file_name(), "second.txt")
        self.assertFalse(zip_reader.move_to_next_file())
        with self.assertRaises(RuntimeError):
            zip_reader.read_file(10)                              # no file is open: CEF reports -1

    def test_a_request_carries_post_data_made_of_bytes(self):
        element = cefweaver.PostDataElement.create()
        element.set_to_bytes(b"name=value&n=\x00\xff")
        self.assertEqual(element.get_bytes_count(), 15)
        self.assertEqual(element.get_bytes(15), b"name=value&n=\x00\xff")
        self.assertEqual(element.get_bytes(4), b"name")             # a part
        self.assertEqual(element.get_bytes(100), b"name=value&n=\x00\xff")  # no more than it has
        for bad in ("text", None, 5):
            with self.assertRaises(TypeError):
                element.set_to_bytes(bad)
        data = cefweaver.PostData.create()
        self.assertTrue(data.add_element(element))
        request = cefweaver.Request.create()
        request.set_url("http://example.test/")
        request.set_post_data(data)
        elements = request.get_post_data().get_elements()
        self.assertEqual(len(elements), 1)
        self.assertEqual(elements[0].get_bytes(15), b"name=value&n=\x00\xff")

    def test_add_resource_needs_a_running_cef(self):
        with self.assertRaises(RuntimeError):
            cefweaver.CefApp().add_resource("http://a.test/", "x")


@unittest.skipUnless(RUNTIME_OK and HAS_X, "needs the Linux wheel with the CEF runtime "
                     "and a virtual X server (see the module docstring)")
class WithCef(unittest.TestCase):
    def assertClean(self, result):
        # A TimeoutError in the script names the awaited event in its traceback.
        self.assertEqual(result.returncode, 0, (result.stdout + result.stderr)[-3000:])
        self.assertNotIn("stack smashing", result.stderr)

    def test_javascript_to_python_binding_and_shutdown(self):
        result = run_cef("""
            got = []
            app.add_javascript_binding("report", lambda *a: got.append(a))
            app.initialize(page('<script>window.addEventListener("load",'
                                '()=>report(1, "é한글", true, 2.5, "x"))</script>'))
            wait_until(app, lambda: got, "the JavaScript call")
            assert got == [(1, "é한글", True, 2.5, "x")], got
            app.shutdown()
            assert not app.is_running
            print("OK")
        """)
        self.assertClean(result)
        self.assertIn("OK", result.stdout)

    def test_zero_argument_call_and_exceptions_do_not_crash(self):
        result = run_cef("""
            got = []
            def boom(*a): raise ValueError("expected in test")
            app.add_javascript_binding("noargs", lambda *a: got.append(a))
            app.add_javascript_binding("boom", boom)
            app.initialize(page('<script>addEventListener("load",()=>{noargs();boom();noargs(7)})</script>'))
            wait_until(app, lambda: len(got) == 2, "both noargs() calls")
            assert got == [(), (7,)], got
            app.shutdown()
            print("OK")
        """)
        self.assertClean(result)
        self.assertIn("OK", result.stdout)
        self.assertIn("ValueError: expected in test", result.stderr)  # via sys.excepthook

    def test_load_url_and_execute_javascript(self):
        result = run_cef("""
            got = []
            app.add_javascript_binding("report", lambda *a: got.append(a))
            app.initialize("about:blank")
            assert app.execute_javascript("1") is False          # page still loading
            wait_until(app, lambda: app.is_ready_to_execute_javascript, "the first page")
            assert app.load_url(page('<script>report("second")</script>')) is True
            wait_until(app, lambda: got, "the script of the loaded page")
            wait_until(app, lambda: app.is_ready_to_execute_javascript, "the page load to end")
            assert app.execute_javascript('report("exec")') is True
            wait_until(app, lambda: len(got) == 2, "the execute_javascript() call")
            assert got == [("second",), ("exec",)], got
            app.shutdown()
            print("OK")
        """)
        self.assertClean(result)
        self.assertIn("OK", result.stdout)

    def test_add_resource_serves_pages_without_a_network(self):
        result = run_cef("""
            got = {}
            app.add_javascript_binding("report", lambda key, *v: got.setdefault(key, v))
            big = bytes((i * 7 + 3) % 251 for i in range(300000))  # read in several chunks
            app.initialize("about:blank")
            app.add_resource("http://res.test/index.html",
                             '<meta charset="utf-8"><title>가짜 페이지</title>'
                             '<script src="/app.js"></script>', headers={"X-Test": "yes"})
            app.add_resource("http://res.test/app.js", '''
                report('page', document.title, location.href);
                fetch('/big.bin').then(r => r.arrayBuffer()).then(b => {
                  const a = new Uint8Array(b); let h = 0;
                  for (let i = 0; i < a.length; i++) h = (h * 31 + a[i]) % 1000000007;
                  report('big', a.length, h);
                });
                fetch('/index.html').then(r => report('headers', r.status,
                    r.headers.get('content-type'), r.headers.get('x-test')));
                fetch('/gone.html?x=1').then(r => report('gone', r.status));
            ''', mime_type="text/javascript")
            app.add_resource("http://res.test/big.bin", big, mime_type="application/octet-stream")
            app.add_resource("http://res.test/gone.html", "gone", status=404)
            assert app.load_url("http://res.test/index.html") is True
            wait_until(app, lambda: {"page", "big", "headers", "gone"} <= set(got), "the resources")
            h = 0
            for byte in big:
                h = (h * 31 + byte) % 1000000007
            assert got["page"] == ("가짜 페이지", "http://res.test/index.html"), got
            assert got["big"] == (len(big), h), got["big"]
            assert got["headers"] == (200, "text/html", "yes"), got["headers"]
            assert got["gone"] == (404,), got["gone"]
            app.shutdown()
            print("OK")
        """)
        self.assertClean(result)
        self.assertIn("OK", result.stdout)

    def test_resource_handler_can_answer_later_from_another_thread(self):
        # The generated low-level API: a handler that continues asynchronously.
        result = run_cef("""
            import threading
            got = []
            app.add_javascript_binding("report", lambda *a: got.append(a))
            body = b"<script>report('late answer')</script>"

            class LateHandler(cefweaver.ResourceHandler):
                sent = False

                def open(self, request, callback):
                    threading.Timer(0.3, callback.continue_).start()
                    return True, False  # handled, but not yet: continue_() will tell
                def get_response_headers(self, response):
                    response.set_mime_type("text/html")
                    response.set_status(200)
                    return len(body), ""
                def read(self, data_out, callback):
                    if self.sent:
                        return False, 0  # the end of the response
                    self.sent = True
                    data_out[:len(body)] = body
                    return True, len(body)
                def cancel(self):
                    pass

            class Factory(cefweaver.SchemeHandlerFactory):
                def create(self, browser, frame, scheme_name, request):
                    assert isinstance(request, cefweaver.Request)
                    assert scheme_name == "http"
                    return LateHandler()

            app.initialize("about:blank")
            assert cefweaver.register_scheme_handler_factory("http", "late.test", Factory())
            app.load_url("http://late.test/")
            wait_until(app, lambda: got, "the delayed answer")
            assert got == [("late answer",)], got
            app.shutdown()
            print("OK")
        """)
        self.assertClean(result)
        self.assertIn("OK", result.stdout)

    def test_exceptions_in_a_resource_handler_do_not_crash(self):
        result = run_cef("""
            got = []
            app.add_javascript_binding("report", lambda *a: got.append(a))

            class Broken(cefweaver.ResourceHandler):
                def open(self, request, callback):
                    raise RuntimeError("broken on purpose")

            class Factory(cefweaver.SchemeHandlerFactory):
                def create(self, browser, frame, scheme_name, request):
                    if request.get_url().endswith("/broken"):
                        return Broken()
                    raise ValueError("factory failed on purpose")

            app.initialize("about:blank")
            cefweaver.register_scheme_handler_factory("http", "err.test", Factory())
            app.add_resource("http://ok.test/", "<script>report('still alive')</script>")
            app.load_url("http://err.test/broken")
            wait_until(app, lambda: app.is_ready_to_execute_javascript, "the failed load")
            app.load_url("http://ok.test/")
            wait_until(app, lambda: got, "a page after the failures")
            assert got == [("still alive",)], got
            app.shutdown()
            print("OK")
        """)
        self.assertClean(result)
        self.assertIn("OK", result.stdout)
        self.assertIn("broken on purpose", result.stderr)  # reported through sys.excepthook


    def test_client_handlers_receive_events_and_the_wrapper_keeps_working(self):
        result = run_cef("""
            import threading
            events, titles = [], []
            got = []
            main_thread = threading.get_ident()
            threads = set()  # the threads the handlers ran on

            class Load(cefweaver.LoadHandler):
                def on_loading_state_change(self, browser, is_loading, can_go_back, can_go_forward):
                    threads.add(threading.get_ident())
                    events.append(("state", is_loading))
                def on_load_start(self, browser, frame, transition_type):
                    threads.add(threading.get_ident())
                    events.append(("start", frame.is_main()))
                def on_load_end(self, browser, frame, http_status_code):
                    threads.add(threading.get_ident())
                    events.append(("end", frame.is_main(), isinstance(http_status_code, int)))

            class Display(cefweaver.DisplayHandler):
                def on_title_change(self, browser, title):
                    threads.add(threading.get_ident())
                    titles.append(title)

            class Life(cefweaver.LifeSpanHandler):
                def on_after_created(self, browser):
                    threads.add(threading.get_ident())
                    events.append(("created", browser.get_identifier() > 0))
                def on_before_close(self, browser):
                    threads.add(threading.get_ident())
                    events.append(("closing",))

            class MyClient(cefweaver.Client):
                def __init__(self):
                    self.load, self.display, self.life = Load(), Display(), Life()
                def get_load_handler(self):
                    return self.load
                def get_display_handler(self):
                    return self.display
                def get_life_span_handler(self):
                    return self.life

            app.add_javascript_binding("report", lambda *a: got.append(a))
            app.set_client(MyClient())
            app.initialize(page("<title>제목</title><script>report('js')</script>"))
            wait_until(app, lambda: ("end", True, True) in events and titles, "the load events")

            # What the wrapper does for itself still happens.
            wait_until(app, lambda: app.is_ready_to_execute_javascript, "the ready flag")
            wait_until(app, lambda: got, "the JavaScript binding")
            assert got == [("js",)], got
            assert titles[-1] == "제목", titles
            assert ("created", True) in events, events
            assert events.index(("created", True)) < events.index(("start", True)), events
            assert events.index(("start", True)) < events.index(("end", True, True)), events
            assert ("state", True) in events and ("state", False) in events, events
            # The UI thread is the thread that called initialize().
            assert threads == {main_thread}, (threads, main_thread)

            app.shutdown()
            assert ("closing",) in events, events  # forwarded while shutting down
            print("OK")
        """)
        self.assertClean(result)
        self.assertIn("OK", result.stdout)

    def test_on_load_error_reports_the_failure_and_the_wrapper_still_shows_its_page(self):
        result = run_cef("""
            import socket
            sock = socket.socket()
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
            sock.close()  # nothing listens here any more

            errors, ends = [], []
            class Load(cefweaver.LoadHandler):
                def on_load_error(self, browser, frame, error_code, error_text, failed_url):
                    errors.append((error_code, error_text, failed_url))
                def on_load_end(self, browser, frame, http_status_code):
                    ends.append(frame.get_url())

            class MyClient(cefweaver.Client):
                def __init__(self):
                    self.load = Load()
                def get_load_handler(self):
                    return self.load

            app.set_client(MyClient())
            app.initialize("about:blank")
            app.load_url("http://127.0.0.1:%d/" % port)
            wait_until(app, lambda: errors, "the load error")
            code, text, url = errors[0]
            assert code == -102, errors  # ERR_CONNECTION_REFUSED
            assert url == "http://127.0.0.1:%d/" % port, errors
            # The wrapper replaces a failed page with an error page (a data: URL).
            wait_until(app, lambda: any(u.startswith("data:") for u in ends), "the error page")
            app.shutdown()
            print("OK")
        """)
        self.assertClean(result)
        self.assertIn("OK", result.stdout)

    def test_a_client_without_handlers_and_broken_handlers_do_not_disturb_the_wrapper(self):
        result = run_cef("""
            got = []
            class Load(cefweaver.LoadHandler):
                def on_load_end(self, browser, frame, http_status_code):
                    raise RuntimeError("load handler broken on purpose")

            class Broken(cefweaver.Client):
                def get_load_handler(self):
                    return Load()
                def get_display_handler(self):
                    raise ValueError("client broken on purpose")

            app.add_javascript_binding("report", lambda *a: got.append(a))
            app.set_client(Broken())
            app.initialize(page("<title>t</title><script>report('alive')</script>"))
            wait_until(app, lambda: got, "the JavaScript binding")
            wait_until(app, lambda: app.is_ready_to_execute_javascript, "the ready flag")
            app.shutdown()
            print("OK")
        """)
        self.assertClean(result)
        self.assertIn("OK", result.stdout)
        self.assertIn("load handler broken on purpose", result.stderr)
        self.assertIn("client broken on purpose", result.stderr)

    def test_set_client_must_come_before_initialize(self):
        result = run_cef("""
            app.initialize("about:blank")
            try:
                app.set_client(cefweaver.Client())
            except RuntimeError:
                print("OK")
            app.shutdown()
        """)
        self.assertClean(result)
        self.assertIn("OK", result.stdout)


    def test_browser_host_gives_back_its_browser_and_sets_the_zoom(self):
        result = run_cef("""
            boxes = []
            class Life(cefweaver.LifeSpanHandler):
                def on_after_created(self, browser):
                    boxes.append(browser)
            class MyClient(cefweaver.Client):
                def __init__(self):
                    self.life = Life()
                def get_life_span_handler(self):
                    return self.life
            app.set_client(MyClient())
            app.initialize(page("zoom"))
            wait_until(app, lambda: boxes and app.is_ready_to_execute_javascript, "the browser")
            browser = boxes[0]
            host = browser.get_host()
            assert isinstance(host, cefweaver.BrowserHost), host
            assert host.get_browser().get_identifier() == browser.get_identifier()
            assert cefweaver.BrowserHost.get_browser_by_identifier(
                browser.get_identifier()).get_identifier() == browser.get_identifier()
            host.set_zoom_level(1.0)
            wait_until(app, lambda: host.get_zoom_level() == 1.0, "the zoom level")
            app.shutdown()
            print("OK")
        """)
        self.assertClean(result)
        self.assertIn("OK", result.stdout)

    def test_mouse_events_reach_the_page_at_their_coordinates(self):
        result = run_cef("""
            got, boxes = [], []
            class Life(cefweaver.LifeSpanHandler):
                def on_after_created(self, browser):
                    boxes.append(browser)
            class MyClient(cefweaver.Client):
                def __init__(self):
                    self.life = Life()
                def get_life_span_handler(self):
                    return self.life
            app.add_javascript_binding("report", lambda *a: got.append(a))
            app.set_client(MyClient())
            app.initialize(page("<script>requestAnimationFrame(() => report('frame'));"
                                "document.addEventListener('mousedown',"
                                "e => report(e.clientX, e.clientY, e.button));</script>"))
            wait_until(app, lambda: boxes and app.is_ready_to_execute_javascript, "the page")
            host = boxes[0].get_host()
            from cefweaver import types
            # Input sent before the first frame is rendered is dropped, not queued.
            wait_until(app, lambda: ("frame",) in got, "the first frame")
            got.clear()
            # A MouseEvent and a plain tuple of the same fields are both accepted.
            send_until(app, lambda: host.send_mouse_click_event(
                types.MouseEvent(50, 60, 0), types.MouseButtonType.LEFT, False, 1),
                lambda: got, "the first mouse down")
            send_until(app, lambda: host.send_mouse_click_event(
                (150, 100, 0), types.MouseButtonType.LEFT, False, 1),
                lambda: (150, 100, 0) in got, "the second mouse down")
            # No offset, and x and y are not swapped (a repeated send may add a duplicate).
            assert set(got) == {(50, 60, 0), (150, 100, 0)}, got
            assert got[0] == (50, 60, 0), got
            for bad in ((1, 2), "xyz", None):
                try:
                    host.send_mouse_move_event(bad, False)
                except TypeError:
                    continue
                raise AssertionError("expected a TypeError for %r" % (bad,))
            app.shutdown()
            print("OK")
        """)
        self.assertClean(result)
        self.assertIn("OK", result.stdout)

    def test_auto_resize_reports_the_content_size_to_the_display_handler(self):
        result = run_cef("""
            sizes, boxes = [], []
            class Life(cefweaver.LifeSpanHandler):
                def on_after_created(self, browser):
                    boxes.append(browser)
            class Display(cefweaver.DisplayHandler):
                def on_auto_resize(self, browser, new_size):
                    sizes.append(new_size)
                    return True
            class MyClient(cefweaver.Client):
                def __init__(self):
                    self.life, self.display = Life(), Display()
                def get_life_span_handler(self):
                    return self.life
                def get_display_handler(self):
                    return self.display
            app.set_client(MyClient())
            app.initialize(page("<div style='width:300px;height:200px'>content</div>"))
            wait_until(app, lambda: boxes and app.is_ready_to_execute_javascript, "the page")
            boxes[0].get_host().set_auto_resize_enabled(
                True, cefweaver.Size(100, 100), (900, 700))  # a Size and a plain tuple
            wait_until(app, lambda: sizes, "the auto resize notification")
            size = sizes[-1]
            assert isinstance(size, cefweaver.Size), size
            assert 100 <= size.width <= 900 and 100 <= size.height <= 700, size
            app.shutdown()
            print("OK")
        """)
        self.assertClean(result)
        self.assertIn("OK", result.stdout)

    def test_the_browsers_are_alloy_style(self):
        # The wrapper creates Alloy style browsers, as java-cef does: the style that adds
        # the client callbacks (do_close, ...), supports a client-provided parent window and
        # windowless rendering. If this fails the wrapper changed its style, and the
        # documentation of do_close and of the window title has to change with it.
        result = run_cef("""
            boxes = []
            class Life(cefweaver.LifeSpanHandler):
                def on_after_created(self, browser):
                    boxes.append(browser)
            class MyClient(cefweaver.Client):
                def __init__(self):
                    self.life = Life()
                def get_life_span_handler(self):
                    return self.life
            app.set_client(MyClient())
            app.initialize(page("style"))
            wait_until(app, lambda: boxes, "the browser")
            assert boxes[0].get_host().get_runtime_style() == 2  # CEF_RUNTIME_STYLE_ALLOY
            app.shutdown()
            print("OK")
        """)
        self.assertClean(result)
        self.assertIn("OK", result.stdout)

    def test_do_close_can_keep_the_browser_open(self):
        result = run_cef("""
            events, boxes = [], []
            allow = [False]
            class Life(cefweaver.LifeSpanHandler):
                def on_after_created(self, browser):
                    boxes.append(browser)
                def do_close(self, browser):
                    events.append(("do_close", allow[0]))
                    return not allow[0]  # True keeps the browser open
                def on_before_close(self, browser):
                    events.append(("before_close",))
            class MyClient(cefweaver.Client):
                def __init__(self):
                    self.life = Life()
                def get_life_span_handler(self):
                    return self.life
            app.set_client(MyClient())
            app.initialize(page("closing"))
            wait_until(app, lambda: boxes and app.is_ready_to_execute_javascript, "the page")
            host = boxes[0].get_host()

            host.close_browser(False)
            wait_until(app, lambda: events, "do_close")
            # Nothing happens after a veto, so this waits a bounded time for nothing to happen.
            for _ in range(100):
                app.do_message_loop_work()
                time.sleep(0.005)
            assert events == [("do_close", False)], events
            assert app.is_running

            allow[0] = True
            host.close_browser(False)
            wait_until(app, lambda: ("before_close",) in events, "the browser to close")
            wait_until(app, lambda: not app.is_running, "the application to stop")
            assert events == [("do_close", False), ("do_close", True), ("before_close",)], events
            app.shutdown()
            print("OK")
        """)
        self.assertClean(result)
        self.assertIn("OK", result.stdout)

    @unittest.skipUnless(shutil.which("xwininfo"), "needs xwininfo to read the window names")
    def test_the_window_title_follows_the_page_title(self):
        result = run_cef("""
            import subprocess
            titles = []
            class Display(cefweaver.DisplayHandler):
                def on_title_change(self, browser, title):
                    titles.append(title)
            class MyClient(cefweaver.Client):
                def __init__(self):
                    self.display = Display()
                def get_display_handler(self):
                    return self.display
            import re
            def has_title():
                # A top-level window is a direct child of the root: five spaces of indent.
                tree = subprocess.run(["xwininfo", "-root", "-tree"], capture_output=True,
                                      text=True).stdout
                return re.search(r'^ {5}0x[0-9a-f]+ "Window Title Test"', tree, re.M) is not None
            app.set_client(MyClient())
            app.initialize(page("<title>Window Title Test</title>x"))
            wait_until(app, lambda: "Window Title Test" in titles, "the page title")
            wait_until(app, has_title, "the title of the top-level window")
            app.shutdown()
            print("OK")
        """)
        self.assertClean(result)
        self.assertIn("OK", result.stdout)


    def test_initialize_after_shutdown_raises_instead_of_crashing(self):
        # CEF can be initialized once per process: a second initialize() after shutdown()
        # used to crash the process (segmentation fault).
        result = run_cef("""
            app.initialize("about:blank")
            wait_until(app, lambda: app.is_ready_to_execute_javascript, "the page")
            app.shutdown()
            again = cefweaver.CefApp()
            try:
                again.initialize("about:blank")
            except RuntimeError as error:
                assert "once" in str(error), error
                print("OK")
        """)
        self.assertClean(result)
        self.assertIn("OK", result.stdout)

    def test_the_process_can_end_without_shutdown(self):
        # Handlers and a request in flight are still alive when the interpreter exits.
        result = run_cef("""
            class Handler(cefweaver.ResourceHandler):
                def open(self, request, callback):
                    return True, True
                def get_response_headers(self, response):
                    response.set_status(200)
                    return -1, ""
                def read(self, data_out, callback):
                    return False, 0
            class Factory(cefweaver.SchemeHandlerFactory):
                def create(self, browser, frame, scheme_name, request):
                    return Handler()
            class Load(cefweaver.LoadHandler):
                pass
            class MyClient(cefweaver.Client):
                def __init__(self):
                    self.load = Load()
                def get_load_handler(self):
                    return self.load
            app.set_client(MyClient())
            app.initialize("about:blank")
            cefweaver.register_scheme_handler_factory("http", "exit.test", Factory())
            app.load_url("http://exit.test/a")
            wait_until(app, lambda: app.is_ready_to_execute_javascript, "the page")
            app.load_url("http://exit.test/b")
            print("OK")
        """)
        self.assertClean(result)
        self.assertIn("OK", result.stdout)

    def test_a_path_the_factory_declines_goes_on_to_the_default_handling(self):
        # create() returning None leaves the request to CEF, which here means the network:
        # the made-up host cannot be resolved, so the load fails (ERR_NAME_NOT_RESOLVED, -105).
        result = run_cef("""
            asked, errors, ends = [], [], []
            class Handler(cefweaver.ResourceHandler):
                def open(self, request, callback):
                    return True, True
                def get_response_headers(self, response):
                    response.set_status(200)
                    response.set_mime_type("text/html")
                    return 3, ""
                def read(self, data_out, callback):
                    if asked.count("served"):
                        return False, 0
                    asked.append("served")
                    data_out[:3] = b"ok\\n"
                    return True, 3
            class Factory(cefweaver.SchemeHandlerFactory):
                def create(self, browser, frame, scheme_name, request):
                    url = request.get_url()
                    asked.append(url)
                    return Handler() if url.endswith("/served") else None
            class Load(cefweaver.LoadHandler):
                def on_load_end(self, browser, frame, http_status_code):
                    ends.append(frame.get_url())
                def on_load_error(self, browser, frame, error_code, error_text, failed_url):
                    errors.append((error_code, failed_url))
            class MyClient(cefweaver.Client):
                def __init__(self):
                    self.load = Load()
                def get_load_handler(self):
                    return self.load
            app.set_client(MyClient())
            app.initialize("about:blank")
            cefweaver.register_scheme_handler_factory("http", "partial.test", Factory())
            app.load_url("http://partial.test/served")
            wait_until(app, lambda: "http://partial.test/served" in ends, "the served page")
            assert not errors, errors
            app.load_url("http://partial.test/declined")
            wait_until(app, lambda: errors, "the load error", timeout=30)
            assert "http://partial.test/declined" in asked, asked  # the factory was asked
            assert errors[0][1] == "http://partial.test/declined", errors
            app.shutdown()
            print("OK")
        """)
        self.assertClean(result)
        self.assertIn("OK", result.stdout)

    def test_resource_handler_callbacks_run_on_threads_other_than_the_ui_thread(self):
        result = run_cef("""
            import threading
            main = threading.get_ident()
            threads = {}
            class Handler(cefweaver.ResourceHandler):
                def open(self, request, callback):
                    threads["open"] = threading.get_ident()
                    return True, True
                def get_response_headers(self, response):
                    threads["get_response_headers"] = threading.get_ident()
                    response.set_status(200)
                    return 1, ""
                def read(self, data_out, callback):
                    threads["read"] = threading.get_ident()
                    if "done" in threads:
                        return False, 0
                    threads["done"] = 1
                    data_out[:1] = b"x"
                    return True, 1
            class Factory(cefweaver.SchemeHandlerFactory):
                def create(self, browser, frame, scheme_name, request):
                    threads["create"] = threading.get_ident()
                    return Handler()
            app.initialize("about:blank")
            cefweaver.register_scheme_handler_factory("http", "thread.test", Factory())
            app.load_url("http://thread.test/")
            wait_until(app, lambda: "read" in threads, "the resource to be read")
            for name in ("create", "open", "get_response_headers", "read"):
                assert threads[name] != main, (name, threads)
            app.shutdown()
            print("OK")
        """)
        self.assertClean(result)
        self.assertIn("OK", result.stdout)


    def test_a_browser_lists_the_names_and_identifiers_of_its_frames(self):
        result = run_cef("""
            boxes = []
            class Life(cefweaver.LifeSpanHandler):
                def on_after_created(self, browser):
                    boxes.append(browser)
            class MyClient(cefweaver.Client):
                def __init__(self):
                    self.life = Life()
                def get_life_span_handler(self):
                    return self.life
            app.set_client(MyClient())
            # (An srcdoc iframe in a data: page never finishes loading, so use about:blank.)
            app.initialize(page("<iframe name='inner' src='about:blank'></iframe>"))
            wait_until(app, lambda: boxes and app.is_ready_to_execute_javascript, "the page")
            browser = boxes[0]
            wait_until(app, lambda: "inner" in browser.get_frame_names(), "the child frame")
            names = browser.get_frame_names()
            identifiers = browser.get_frame_identifiers()
            assert isinstance(names, list) and all(isinstance(n, str) for n in names), names
            assert isinstance(identifiers, list) and all(isinstance(i, str) for i in identifiers)
            assert len(identifiers) == len(names) >= 2, (names, identifiers)
            app.shutdown()
            print("OK")
        """)
        self.assertClean(result)
        self.assertIn("OK", result.stdout)

    def test_favicon_urls_reach_the_display_handler_as_a_list_of_strings(self):
        result = run_cef("""
            icons = []
            class Display(cefweaver.DisplayHandler):
                def on_favicon_url_change(self, browser, icon_urls):
                    icons.append(icon_urls)
            class MyClient(cefweaver.Client):
                def __init__(self):
                    self.display = Display()
                def get_display_handler(self):
                    return self.display
            app.set_client(MyClient())
            app.initialize("about:blank")
            app.add_resource("http://fav.test/icon.png", b"\\x89PNG", mime_type="image/png")
            app.add_resource("http://fav.test/",
                             "<html><head><link rel='icon' href='/icon.png'></head><body>x</body></html>")
            app.load_url("http://fav.test/")
            wait_until(app, lambda: icons, "the favicon notification")
            assert isinstance(icons[-1], list) and icons[-1], icons
            assert icons[-1] == ["http://fav.test/icon.png"], icons
            app.shutdown()
            print("OK")
        """)
        self.assertClean(result)
        self.assertIn("OK", result.stdout)


    @unittest.expectedFailure
    def test_known_cef_issue_a_srcdoc_iframe_in_a_data_page_never_finishes_loading(self):
        # CEF 154.0.34 stops the renderer of a page that has an <iframe srcdoc> when the
        # page's own URL is data: or about:blank (the child load is reported as ERR_ABORTED).
        # CEF's own cefsimple sample does the same, a plain Chrome 155 does not, and it is
        # not the GPU, the sandbox, the runtime style or a feature flag. If this test starts
        # to pass, CEF fixed it: remove expectedFailure and the entry in known-constraints.
        result = run_cef("""
            app.initialize(page("<iframe name='inner' srcdoc='child'></iframe>"))
            wait_until(app, lambda: app.is_ready_to_execute_javascript, "the page", timeout=4)
            print("OK")
        """)
        self.assertClean(result)
        self.assertIn("OK", result.stdout)

    def test_a_srcdoc_iframe_loads_in_a_page_served_over_http(self):
        # The workaround for the issue above: serve the page with add_resource().
        result = run_cef("""
            boxes = []
            class Life(cefweaver.LifeSpanHandler):
                def on_after_created(self, browser):
                    boxes.append(browser)
            class MyClient(cefweaver.Client):
                def __init__(self):
                    self.life = Life()
                def get_life_span_handler(self):
                    return self.life
            app.set_client(MyClient())
            app.initialize("about:blank")
            app.add_resource("http://srcdoc.test/",
                             "<html><body><iframe name='inner' srcdoc='child'></iframe></body></html>")
            app.load_url("http://srcdoc.test/")
            wait_until(app, lambda: app.is_ready_to_execute_javascript and
                       "inner" in boxes[0].get_frame_names(), "the page with its srcdoc frame")
            app.shutdown()
            print("OK")
        """)
        self.assertClean(result)
        self.assertIn("OK", result.stdout)


    def test_handlers_receive_enumeration_members_and_modifiers_are_flags(self):
        result = run_cef("""
            import socket
            from cefweaver import types
            errors, got, boxes = [], [], []
            sock = socket.socket()
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
            sock.close()
            class Load(cefweaver.LoadHandler):
                def on_load_error(self, browser, frame, error_code, error_text, failed_url):
                    errors.append(error_code)
            class Life(cefweaver.LifeSpanHandler):
                def on_after_created(self, browser):
                    boxes.append(browser)
            class MyClient(cefweaver.Client):
                def __init__(self):
                    self.load, self.life = Load(), Life()
                def get_load_handler(self):
                    return self.load
                def get_life_span_handler(self):
                    return self.life
            app.add_javascript_binding("report", lambda *a: got.append(a))
            app.set_client(MyClient())
            app.initialize(page("<script>requestAnimationFrame(() => report('frame'));"
                                "document.addEventListener('mousedown',"
                                "e => report(e.shiftKey, e.ctrlKey, e.altKey));</script>"))
            wait_until(app, lambda: ("frame",) in got, "the first frame")
            got.clear()
            # Modifiers are bit flags: they combine with | and reach the page.
            modifiers = types.EventFlags.SHIFT_DOWN | types.EventFlags.CONTROL_DOWN
            host = boxes[0].get_host()
            send_until(app, lambda: host.send_mouse_click_event(
                types.MouseEvent(5, 5, modifiers), types.MouseButtonType.LEFT, False, 1),
                lambda: got, "the mouse down")
            assert set(got) == {(True, True, False)}, got  # shift and control, not alt

            app.load_url("http://127.0.0.1:%d/" % port)
            wait_until(app, lambda: errors, "the load error", timeout=30)
            error = errors[0]
            assert isinstance(error, types.ErrorCode), type(error)
            assert error is types.ErrorCode.CONNECTION_REFUSED, error
            app.shutdown()
            print("OK")
        """)
        self.assertClean(result)
        self.assertIn("OK", result.stdout)


    def test_output_parameters_of_a_library_method_come_back_with_its_result(self):
        result = run_cef("""
            from cefweaver import types
            app.initialize("about:blank")
            wait_until(app, lambda: app.is_ready_to_execute_javascript, "the page")
            menu = cefweaver.MenuModel.create_menu_model(cefweaver.MenuModelDelegate())
            menu.add_item(1, "First")

            # Several outputs: the result first, then each output parameter.
            assert menu.get_accelerator(1) == (False, 0, False, False, False)
            assert menu.set_accelerator(1, 65, True, False, True) is True
            assert menu.get_accelerator(1) == (True, 65, True, False, True)

            # One output (a typedef of an integer) after the result.
            assert menu.set_color(1, types.MenuColorType.TEXT, 0xFF112233) is True
            assert menu.get_color(1, types.MenuColorType.TEXT) == (True, 0xFF112233)
            app.shutdown()
            print("OK")
        """)
        self.assertClean(result)
        self.assertIn("OK", result.stdout)

    def test_a_struct_given_to_a_library_method_is_changed_and_returned(self):
        # CefDisplay::ConvertPointToPixels changes the point it is given. At scale 1 it would
        # not show whether the point went in, so the device scale factor is forced to 2.
        result = run_cef("""
            from cefweaver import types
            app.add_command_line_switch("force-device-scale-factor", "2")
            app.initialize("about:blank")
            wait_until(app, lambda: app.is_ready_to_execute_javascript, "the page")
            display = cefweaver.Display.get_primary_display()
            assert display.get_device_scale_factor() == 2.0
            to_pixels = display.convert_point_to_pixels(types.Point(10, 20))
            assert isinstance(to_pixels, types.Point) and to_pixels == (20, 40), to_pixels
            assert display.convert_point_from_pixels((40, 80)) == (20, 40)  # a plain tuple goes in
            bounds = display.get_bounds()
            assert isinstance(bounds, types.Rect) and bounds.width > 0, bounds
            app.shutdown()
            print("OK")
        """)
        self.assertClean(result)
        self.assertIn("OK", result.stdout)


    def test_lists_of_structs_go_into_and_come_out_of_a_library_object(self):
        result = run_cef("""
            from cefweaver import types
            app.initialize("about:blank")
            wait_until(app, lambda: app.is_ready_to_execute_javascript, "the page")
            settings = cefweaver.PrintSettings.create()
            assert settings.get_page_ranges() == []
            # Range objects and plain tuples both go in; Range objects come out.
            settings.set_page_ranges([types.Range(1, 3), (5, 5), types.Range(9, 12)])
            ranges = settings.get_page_ranges()
            assert ranges == [(1, 3), (5, 5), (9, 12)], ranges
            assert all(isinstance(r, types.Range) for r in ranges), ranges
            assert settings.get_page_ranges_count() == 3
            try:
                settings.set_page_ranges([(1, 2, 3)])
            except TypeError:
                pass
            else:
                raise AssertionError("expected a TypeError for a range with three values")
            app.shutdown()
            print("OK")
        """)
        self.assertClean(result)
        self.assertIn("OK", result.stdout)

    def test_a_list_of_objects_comes_out_of_a_library_method(self):
        result = run_cef("""
            app.initialize("about:blank")
            wait_until(app, lambda: app.is_ready_to_execute_javascript, "the page")
            displays = cefweaver.Display.get_all_displays()
            assert isinstance(displays, list) and displays, displays
            assert all(isinstance(d, cefweaver.Display) for d in displays), displays
            primary = cefweaver.Display.get_primary_display()
            assert primary.get_id() in [d.get_id() for d in displays]
            app.shutdown()
            print("OK")
        """)
        self.assertClean(result)
        self.assertIn("OK", result.stdout)

    def test_the_drag_handler_receives_the_draggable_regions_as_value_types(self):
        result = run_cef("""
            from cefweaver import types
            regions = []
            class Drag(cefweaver.DragHandler):
                def on_draggable_regions_changed(self, browser, frame, regions_):
                    regions.append(list(regions_))
            class MyClient(cefweaver.Client):
                def __init__(self):
                    self.drag = Drag()
                def get_drag_handler(self):
                    return self.drag
            app.set_client(MyClient())
            app.initialize(page("<div style='-webkit-app-region: drag; position: absolute; "
                                "left: 10px; top: 20px; width: 300px; height: 40px'>title bar</div>"))
            wait_until(app, lambda: any(r for r in regions), "the draggable regions")
            region = next(r for r in regions if r)[0]
            assert isinstance(region, types.DraggableRegion), region
            assert isinstance(region.bounds, types.Rect), region
            assert region.bounds == (10, 20, 300, 40), region
            assert region.draggable, region
            app.shutdown()
            print("OK")
        """)
        self.assertClean(result)
        self.assertIn("OK", result.stdout)


    def test_a_list_of_integers_comes_out_of_a_library_method(self):
        result = run_cef("""
            app.initialize(page("<title>tasks</title>x"))
            wait_until(app, lambda: app.is_ready_to_execute_javascript, "the page")
            manager = cefweaver.TaskManager.get_task_manager()
            ok, ids = manager.get_task_ids_list()
            assert ok is True, ok
            assert isinstance(ids, list) and ids, ids
            assert all(type(i) is int for i in ids), ids
            assert len(ids) == manager.get_tasks_count(), (ids, manager.get_tasks_count())
            app.shutdown()
            print("OK")  # `manager` is still alive here, and is released after CEF has shut down
        """)
        self.assertClean(result)
        self.assertIn("OK", result.stdout)

    def test_a_library_object_that_outlives_shutdown_does_not_crash_the_process(self):
        # Releasing a CefTaskManager after CefShutdown() ended the process with SIGTRAP when
        # the interpreter exited (every time, even if no method was called). Library objects
        # that are freed after shutdown() are dropped without a Release().
        result = run_cef("""
            app.initialize("about:blank")
            wait_until(app, lambda: app.is_ready_to_execute_javascript, "the page")
            manager = cefweaver.TaskManager.get_task_manager()
            app.shutdown()
            print("OK")
        """)
        self.assertClean(result)
        self.assertIn("OK", result.stdout)


    # A script that right-clicks a page and answers the context menu like a program would:
    # run_context_menu() takes the place of the menu that CEF would show and picks an item.
    MENU_SCRIPT = """
        import json
        from cefweaver import types
        devtools = %(devtools)s
        pick = %(pick)r              # a label ("Show DevTools"), or a command id
        handled_by_user = %(handled)s   # does the user's handler claim the commands it gets?
        app.devtools_menu = devtools
        rec = {"labels": [], "ids": [], "commands": [], "before_count": None}
        boxes, got = [], []
        class Menu(cefweaver.ContextMenuHandler):
            def on_before_context_menu(self, browser, frame, params, model):
                rec["before_count"] = model.get_count()
                rec["position"] = [params.get_x_coord(), params.get_y_coord()]
                model.add_item(types.MenuId.USER_FIRST, "My item")
            def run_context_menu(self, browser, frame, params, model, callback):
                rec["labels"] = [model.get_label_at(i) for i in range(model.get_count())]
                rec["ids"] = [model.get_command_id_at(i) for i in range(model.get_count())]
                chosen = pick
                if isinstance(pick, str):
                    chosen = next(model.get_command_id_at(i) for i in range(model.get_count())
                                  if model.get_label_at(i).replace("&", "") == pick)
                callback.continue_(chosen, 0)
                return True
            def on_context_menu_command(self, browser, frame, params, command_id, event_flags):
                rec["commands"].append(command_id)
                return handled_by_user
        class Life(cefweaver.LifeSpanHandler):
            def on_after_created(self, browser):
                boxes.append(browser)
        class MyClient(cefweaver.Client):
            def __init__(self):
                self.menu, self.life = Menu(), Life()
            def get_context_menu_handler(self):
                return self.menu
            def get_life_span_handler(self):
                return self.life
        app.add_javascript_binding("report", lambda *a: got.append(a))
        app.set_client(MyClient())
        app.initialize(page("<script>requestAnimationFrame(() => report('frame'));</script>"
                            "<p>hello</p>"))
        wait_until(app, lambda: ("frame",) in got, "the first frame")
        host = boxes[0].get_host()
        def right_click():
            event = types.MouseEvent(30, 30, 0)
            host.send_mouse_click_event(event, types.MouseButtonType.RIGHT, False, 1)
            host.send_mouse_click_event(event, types.MouseButtonType.RIGHT, True, 1)
        send_until(app, right_click, lambda: rec["labels"], "the context menu")
        wait_until(app, lambda: rec["commands"] or %(command_is_ours)s, "the command")
        %(after)s
        print("RESULT " + json.dumps(rec))
        app.shutdown()
    """

    def run_menu(self, devtools=False, pick="My item", handled=True, after="", ours=False):
        import json
        result = run_cef(self.MENU_SCRIPT % {
            "devtools": devtools, "pick": pick, "handled": handled, "after": after,
            "command_is_ours": ours})
        self.assertClean(result)
        line = next(l for l in result.stdout.splitlines() if l.startswith("RESULT "))
        return json.loads(line[len("RESULT "):])

    def test_a_program_can_open_the_context_menu_and_pick_an_item(self):
        rec = self.run_menu()
        self.assertEqual(rec["position"], [30, 30])
        self.assertIn("My item", rec["labels"])  # the user's item is in the menu
        self.assertEqual(rec["ids"][rec["labels"].index("My item")], 26500)  # USER_FIRST
        self.assertEqual(rec["commands"], [26500])  # and the pick reaches the user's handler
        self.assertFalse([l for l in rec["labels"] if "DevTools" in l])  # off by default

    def test_the_devtools_items_come_after_the_users_and_change_nothing_else(self):
        off, on = self.run_menu(devtools=False), self.run_menu(devtools=True)
        extra = ["", "&Show DevTools", "Close DevTools", "", "Inspect Element"]
        self.assertEqual(on["labels"], off["labels"] + extra)
        self.assertEqual(on["ids"][:len(off["ids"])], off["ids"])
        self.assertEqual(on["before_count"], off["before_count"])  # what the user's handler saw
        self.assertEqual(on["commands"], off["commands"])
        # The wrapper's ids are the last ones of the range CEF leaves to applications.
        added = [i for i in on["ids"][len(off["ids"]):] if i != -1]  # without the separators
        self.assertEqual(added, [28498, 28499, 28500])

    def test_choosing_show_devtools_opens_devtools_without_asking_the_users_handler(self):
        rec = self.run_menu(devtools=True, pick="Show DevTools", ours=True, after=(
            "wait_until(app, host.has_dev_tools, 'the DevTools window')"))
        self.assertEqual(rec["commands"], [])  # the command was the wrapper's own

    def test_a_standard_command_the_user_does_not_handle_runs_as_usual(self):
        # The wrapper used to claim every command it did not know, so CEF skipped its own
        # handling (Select All, Copy, ...). The user's handler answers False here.
        for devtools in (False, True):
            rec = self.run_menu(devtools=devtools, pick=117, handled=False, after=(
                "app.execute_javascript(\"report('selection', window.getSelection().toString())\")\n"
                "        wait_until(app, lambda: any(g[0] == 'selection' for g in got), 'the selection')\n"
                "        assert ('selection', 'hello') in got, got"))
            self.assertEqual(rec["commands"], [117])  # 117 is MENU_ID_SELECT_ALL


    def test_a_process_message_makes_a_round_trip_through_the_renderer(self):
        result = run_cef("""
            from cefweaver import types
            received, boxes, js = [], [], []
            class Life(cefweaver.LifeSpanHandler):
                def on_after_created(self, browser):
                    boxes.append(browser)
            class MyClient(cefweaver.Client):
                def __init__(self):
                    self.life = Life()
                def get_life_span_handler(self):
                    return self.life
                def on_process_message_received(self, browser, frame, source_process, message):
                    arguments = message.get_argument_list()
                    received.append((message.get_name(), source_process, arguments.get_size(),
                                     arguments.get_int(0), arguments.get_string(1),
                                     arguments.get_dictionary(2).get_string("k")))
                    return True
            app.add_javascript_binding("report", lambda *a: js.append(a))
            app.set_client(MyClient())
            app.initialize(page("<script>requestAnimationFrame(() => report('frame'));</script>"))
            wait_until(app, lambda: ("frame",) in js, "the first frame")

            # The renderer answers cefweaver-ping with cefweaver-pong and the same arguments.
            message = cefweaver.ProcessMessage.create("cefweaver-ping")
            arguments = message.get_argument_list()
            arguments.set_size(3)
            arguments.set_int(0, 42)
            arguments.set_string(1, "안녕")
            record = cefweaver.DictionaryValue.create()
            record.set_string("k", "v")
            arguments.set_dictionary(2, record)
            boxes[0].get_main_frame().send_process_message(types.ProcessId.RENDERER, message)
            wait_until(app, lambda: received, "the pong")
            assert received == [("cefweaver-pong", types.ProcessId.RENDERER, 3, 42, "안녕", "v")], received
            assert received[0][1] is types.ProcessId.RENDERER
            assert not message.is_valid()  # the message was handed over

            # The wrapper's own messages (JavaScript bindings) still work, and never reach the user.
            app.execute_javascript("report('after')")
            wait_until(app, lambda: ("after",) in js, "a JavaScript binding after the message")
            assert [r[0] for r in received] == ["cefweaver-pong"], received
            app.shutdown()
            print("OK")
        """)
        self.assertClean(result)
        self.assertIn("OK", result.stdout)


    # -- the message router: window.cefQuery(...) in a page reaches a QueryHandler ---------

    QUERY_PAGE = """<script>
        function ask(request, persistent) {
          return window.cefQuery({request: request, persistent: !!persistent,
                           onSuccess: function (r) { report('ok', String(request), r); },
                           onFailure: function (c, m) { report('fail', String(request), c, m); }});
        }
        requestAnimationFrame(() => report('frame'));
    </script>"""

    def run_query_script(self, body, prelude=""):
        """Runs `body` in a CEF process whose page has ask(request, persistent)."""
        import textwrap
        script = ("QUERY_PAGE = %r\n" % self.QUERY_PAGE) + textwrap.dedent("""
            import threading
            from cefweaver import types
            js, boxes = [], []
            app.add_javascript_binding("report", lambda *a: js.append(a))
            class Life(cefweaver.LifeSpanHandler):
                def on_after_created(self, browser):
                    boxes.append(browser)
            class MyClient(cefweaver.Client):
                def __init__(self):
                    self.life = Life()
                def get_life_span_handler(self):
                    return self.life
            def start(page_html=QUERY_PAGE):
                app.set_client(MyClient())
                app.initialize(page(page_html))
                wait_until(app, lambda: ("frame",) in js, "the first frame")
            def answers():
                return {r[1]: (r[0],) + r[2:] for r in js if r[0] in ("ok", "fail")}
        """) + textwrap.dedent(prelude) + textwrap.dedent(body)
        result = run_cef(script)
        self.assertClean(result)
        self.assertIn("OK", result.stdout)

    def test_a_page_asks_and_the_handler_answers_with_success_or_failure(self):
        self.run_query_script("""
            seen, late = [], []
            class Handler(cefweaver.QueryHandler):
                def on_query(self, browser, frame, query_id, request, persistent, callback):
                    seen.append((isinstance(browser, cefweaver.Browser), frame.is_main(),
                                 type(query_id) is int, persistent))
                    if request == "ok":
                        assert callback.success("pong:" + request) is True
                        assert callback.success("again") is False  # a query is answered once
                        return True
                    if request == "bad":
                        callback.failure(7, "nope")
                        return True
                    if request == "late":  # answered later, from another thread
                        threading.Timer(0.1, lambda: late.append(callback.success("later"))).start()
                        return True
                    return False  # not handled
            app.add_query_handler(Handler())
            start()
            for request in ("ok", "bad", "late", "unknown"):
                app.execute_javascript("ask(%r)" % request)
            wait_until(app, lambda: len(answers()) == 4, "four answers")
            found = answers()
            assert found["ok"] == ("ok", "pong:ok"), found
            assert found["bad"] == ("fail", 7, "nope"), found
            assert found["late"] == ("ok", "later"), found
            assert found["unknown"][:2] == ("fail", -1), found  # no handler took it
            wait_until(app, lambda: late, "the late answer to be sent")
            assert late == [True], late
            assert len(seen) == 4 and all(s == (True, True, True, False) for s in seen), seen
            app.shutdown()
            print("OK")
        """)

    def test_a_persistent_query_can_answer_many_times_and_the_page_can_cancel_it(self):
        self.run_query_script("""
            pending, canceled = {}, []
            class Handler(cefweaver.QueryHandler):
                def on_query(self, browser, frame, query_id, request, persistent, callback):
                    assert persistent is True
                    pending[query_id] = callback
                    return True
                def on_query_canceled(self, browser, frame, query_id):
                    canceled.append(query_id)
            app.add_query_handler(Handler())
            start()
            app.execute_javascript("window.queryId = ask('subscribe', true)")
            wait_until(app, lambda: pending, "the query")
            (query_id, callback), = pending.items()
            for n in range(3):
                assert callback.success("event %d" % n) is True  # a persistent query stays open
            wait_until(app, lambda: len([r for r in js if r[0] == "ok"]) == 3, "three answers")
            assert [r[2] for r in js if r[0] == "ok"] == ["event 0", "event 1", "event 2"], js
            app.execute_javascript("cefQueryCancel(window.queryId)")  # the page cancels it
            wait_until(app, lambda: canceled, "the cancellation")
            assert canceled == [query_id], canceled
            assert callback.success("too late") is False  # nothing can be sent any more
            app.shutdown()
            print("OK")
        """)

    def test_leaving_the_page_cancels_its_pending_queries(self):
        self.run_query_script("""
            pending, canceled = {}, []
            class Handler(cefweaver.QueryHandler):
                def on_query(self, browser, frame, query_id, request, persistent, callback):
                    pending[query_id] = callback
                    return True
                def on_query_canceled(self, browser, frame, query_id):
                    canceled.append(query_id)
            app.add_query_handler(Handler())
            start()
            app.execute_javascript("ask('stay', true)")
            wait_until(app, lambda: pending, "the query")
            (query_id, callback), = pending.items()
            app.load_url(page("<p>another page</p>"))
            wait_until(app, lambda: canceled, "the cancellation by the navigation")
            assert canceled == [query_id], canceled
            assert callback.failure(1, "late") is False
            app.shutdown()
            print("OK")
        """)

    def test_binary_requests_and_responses(self):
        self.run_query_script("""
            seen = []
            class Handler(cefweaver.QueryHandler):
                def on_query(self, browser, frame, query_id, request, persistent, callback):
                    seen.append(request)
                    callback.success(bytes(reversed(request)) if isinstance(request, bytes) else "text")
                    return True
            app.add_query_handler(Handler())
            start()
            app.execute_javascript(
                "window.cefQuery({request: new Uint8Array([1, 2, 3]).buffer, persistent: false,"
                " onSuccess: function (r) { report('binary', r instanceof ArrayBuffer,"
                " Array.from(new Uint8Array(r)).join(',')); },"
                " onFailure: function (c, m) { report('binary', false, m); }})")
            wait_until(app, lambda: any(r[0] == "binary" for r in js), "the binary answer")
            assert seen == [b"\\x01\\x02\\x03"], seen
            assert [r for r in js if r[0] == "binary"] == [("binary", True, "3,2,1")], js
            app.shutdown()
            print("OK")
        """)

    def test_handlers_are_asked_in_order_and_can_be_removed(self):
        self.run_query_script("""
            order = []
            def make(name, takes):
                class Handler(cefweaver.QueryHandler):
                    def on_query(self, browser, frame, query_id, request, persistent, callback):
                        order.append(name)
                        if request in takes:
                            callback.success(name)
                            return True
                        return False
                return Handler()
            a, b, c = make("a", ["x"]), make("b", ["x", "y"]), make("c", ["x", "y", "z"])
            app.add_query_handler(a)
            app.add_query_handler(b)
            app.add_query_handler(c, first=True)   # c is asked first
            start()
            for request in ("x", "y", "z"):
                app.execute_javascript("ask(%r)" % request)
            wait_until(app, lambda: len(answers()) == 3, "three answers")
            assert {k: v[1] for k, v in answers().items()} == {"x": "c", "y": "c", "z": "c"}, answers()
            assert app.remove_query_handler(c) is True       # now a, then b
            del order[:]
            js[:] = [r for r in js if r[0] == "frame"]
            for request in ("x", "y"):
                app.execute_javascript("ask(%r)" % request)
            wait_until(app, lambda: len(answers()) == 2, "answers without c")
            assert {k: v[1] for k, v in answers().items()} == {"x": "a", "y": "b"}, answers()
            assert order[:1] == ["a"], order
            app.shutdown()
            print("OK")
        """)

    def test_the_names_of_the_query_functions_can_be_changed(self):
        self.run_query_script("""
            class Handler(cefweaver.QueryHandler):
                def on_query(self, browser, frame, query_id, request, persistent, callback):
                    callback.success("named")
                    return True
            app.set_query_functions("myQuery", "myCancel")
            app.add_query_handler(Handler())
            start('<script>requestAnimationFrame(() => report("frame"));</script>')
            app.execute_javascript(
                "report('names', typeof window.myQuery, typeof window.myCancel, typeof window.cefQuery);"
                "window.myQuery({request: 'r', onSuccess: function (r) { report('named', r); }})")
            wait_until(app, lambda: any(r[0] == "named" for r in js), "the answer")
            assert ("names", "function", "function", "undefined") in js, js
            assert ("named", "named") in js, js
            app.shutdown()
            print("OK")
        """)

    def test_without_a_query_handler_the_page_has_no_query_function(self):
        self.run_query_script("""
            start('<script>requestAnimationFrame(() => report("frame"));</script>')
            app.execute_javascript("report('type', typeof window.cefQuery)")
            wait_until(app, lambda: any(r[0] == "type" for r in js), "the report")
            assert ("type", "undefined") in js, js
            app.shutdown()
            print("OK")
        """)

    def test_a_callback_that_is_dropped_without_an_answer_fails_the_query(self):
        # It is an error for CEF to destroy a callback of an open query, so dropping it
        # answers the page with a failure.
        self.run_query_script("""
            class Handler(cefweaver.QueryHandler):
                def on_query(self, browser, frame, query_id, request, persistent, callback):
                    return True  # takes the query and forgets the callback
            app.add_query_handler(Handler())
            start()
            app.execute_javascript("ask('forgotten')")
            wait_until(app, lambda: "forgotten" in answers(), "the failure")
            assert answers()["forgotten"][:2] == ("fail", -1), answers()
            app.shutdown()
            print("OK")
        """)

    def test_the_router_works_with_bindings_and_the_users_process_messages(self):
        self.run_query_script("""
            received = []
            class Handler(cefweaver.QueryHandler):
                def on_query(self, browser, frame, query_id, request, persistent, callback):
                    callback.success("router")
                    return True
            class Client2(MyClient):
                def on_process_message_received(self, browser, frame, source_process, message):
                    received.append(message.get_name())
                    return True
            MyClient = Client2
            app.add_query_handler(Handler())
            start()
            app.execute_javascript("ask('q'); report('binding', 1)")
            wait_until(app, lambda: ("binding", 1) in js and "q" in answers(), "both answers")
            message = cefweaver.ProcessMessage.create("cefweaver-ping")
            boxes[0].get_main_frame().send_process_message(types.ProcessId.RENDERER, message)
            wait_until(app, lambda: "cefweaver-pong" in received, "the user's message")
            # The router's own messages and the wrapper's never reach the user.
            assert received == ["cefweaver-pong"], received
            app.shutdown()
            print("OK")
        """)


    # -- the message router with several frames and several browsers ----------------------

    SITE_SCRIPT = """
        SITE = "http://router.test"
        CHILD = ('<script>function ask(r, p) { window.cefQuery({request: r, persistent: !!p,'
                 'onSuccess: function (x) { report("ok", r, x); },'
                 'onFailure: function (c, m) { report("fail", r, c); }}); }'
                 'requestAnimationFrame(() => report("child-frame"));</script>')
        MAIN = ('<script>function ask(r, p) { window.cefQuery({request: r, persistent: !!p,'
                'onSuccess: function (x) { report("ok", r, x); },'
                'onFailure: function (c, m) { report("fail", r, c); }}); }'
                'requestAnimationFrame(() => report("main-frame"));</script>'
                '<iframe id="f" src="%s/child.html"></iframe>' % SITE)
        def start_site():
            app.add_command_line_switch("disable-popup-blocking")  # window.open without a click
            app.set_client(MyClient())
            app.initialize("about:blank")
            app.add_resource(SITE + "/main.html", MAIN)
            app.add_resource(SITE + "/child.html", CHILD)
            app.add_resource(SITE + "/other.html", CHILD.replace("child-frame", "other-frame"))
            wait_until(app, lambda: app.is_ready_to_execute_javascript, "about:blank")
            app.load_url(SITE + "/main.html")
            wait_until(app, lambda: ("main-frame",) in js and ("child-frame",) in js, "both frames")
    """

    def test_queries_from_a_frame_know_their_frame_and_only_that_frame_is_canceled(self):
        self.run_query_script(prelude=self.SITE_SCRIPT, body="""
            seen, canceled, pending = [], [], {}
            class Handler(cefweaver.QueryHandler):
                def on_query(self, browser, frame, query_id, request, persistent, callback):
                    seen.append((request, frame.is_main(), frame.get_url()))
                    pending[request] = (query_id, callback)
                    if not persistent:
                        callback.success("to " + request)
                    return True
                def on_query_canceled(self, browser, frame, query_id):
                    canceled.append(query_id)
            app.add_query_handler(Handler())
            start_site()
            # Both frames ask (the iframe's own window is reached through the frame element).
            app.execute_javascript("ask('from-main'); ask('keep', true)")
            app.execute_javascript("var w = document.getElementById('f').contentWindow;"
                                   "w.ask('from-child'); w.ask('leave', true)")
            wait_until(app, lambda: len(pending) == 4, "four queries")
            found = {r: (m, u) for r, m, u in seen}
            assert found["from-main"] == (True, SITE + "/main.html"), found
            assert found["from-child"] == (False, SITE + "/child.html"), found
            wait_until(app, lambda: ("ok", "from-child", "to from-child") in js
                       and ("ok", "from-main", "to from-main") in js, "the two answers")
            # The iframe goes to another page: only its query is canceled.
            app.execute_javascript("document.getElementById('f').src = '%s/other.html'" % SITE)
            wait_until(app, lambda: canceled, "the cancellation")
            assert canceled == [pending["leave"][0]], (canceled, pending)
            assert pending["keep"][1].success("still open") is True
            wait_until(app, lambda: ("ok", "keep", "still open") in js, "the open query")
            assert pending["leave"][1].success("late") is False
            app.shutdown()
            print("OK")
        """)

    def test_queries_from_a_popup_browser_and_its_close(self):
        self.run_query_script(prelude=self.SITE_SCRIPT, body="""
            seen, canceled, pending = [], [], {}
            class Handler(cefweaver.QueryHandler):
                def on_query(self, browser, frame, query_id, request, persistent, callback):
                    seen.append((request, browser.get_identifier()))
                    pending[request] = (query_id, callback)
                    if not persistent:
                        callback.success("to " + request)
                    return True
                def on_query_canceled(self, browser, frame, query_id):
                    canceled.append((query_id, browser.get_identifier()))
            app.add_query_handler(Handler())
            start_site()
            app.execute_javascript("ask('first')")
            wait_until(app, lambda: ("ok", "first", "to first") in js, "the first browser")
            app.execute_javascript("window.popup = window.open('%s/other.html')" % SITE)
            wait_until(app, lambda: ("other-frame",) in js, "the popup page")
            app.execute_javascript("popup.ask('second'); popup.ask('open', true)")
            wait_until(app, lambda: ("ok", "second", "to second") in js and "open" in pending,
                       "the popup's queries")
            ids = dict(seen)
            assert ids["first"] != ids["second"], ids       # two browsers
            assert ids["open"] == ids["second"], ids
            app.execute_javascript("popup.close()")        # closing it cancels its open query
            wait_until(app, lambda: canceled, "the cancellation by the close")
            assert canceled == [(pending["open"][0], ids["open"])], canceled
            app.execute_javascript("ask('after')")          # the first browser still works
            wait_until(app, lambda: ("ok", "after", "to after") in js, "the first browser again")
            app.shutdown()
            print("OK")
        """)


    # -- offscreen rendering: CEF draws into a buffer that on_paint receives ---------------

    OSR_SCRIPT = """
        from cefweaver import types
        paints, boxes, js = [], [], []
        size = [200, 100]
        screen = [None]  # a ScreenInfo to give, or None to leave the screen to CEF
        app.add_javascript_binding("report", lambda *a: js.append(a))
        class Render(cefweaver.RenderHandler):
            def get_view_rect(self, browser):
                return cefweaver.Rect(0, 0, size[0], size[1])
            def get_screen_info(self, browser):
                if screen[0] is None:
                    return False, cefweaver.ScreenInfo(1.0, 24, 8, 0, cefweaver.Rect(0, 0, 0, 0),
                                                       cefweaver.Rect(0, 0, 0, 0))
                return True, screen[0]
            def on_paint(self, browser, type, dirty_rects, buffer, width, height):
                try:
                    buffer[0] = 1
                    writable = True
                except TypeError:
                    writable = False
                paints.append(dict(type=type, rects=list(dirty_rects), writable=writable,
                                   nbytes=len(buffer), width=width, height=height,
                                   first=bytes(buffer[:4]), view=buffer))
        class Life(cefweaver.LifeSpanHandler):
            def on_after_created(self, browser):
                boxes.append(browser)
        handlers = {}  # more handlers of the client: "focus", "js_dialog", "dialog", "download"
        class MyClient(cefweaver.Client):
            def __init__(self):
                self.render, self.life = Render(), Life()
            def get_render_handler(self):
                return self.render
            def get_life_span_handler(self):
                return self.life
            def get_focus_handler(self):
                return handlers.get("focus")
            def get_js_dialog_handler(self):
                return handlers.get("js_dialog")
            def get_dialog_handler(self):
                return handlers.get("dialog")
            def get_download_handler(self):
                return handlers.get("download")
            def get_keyboard_handler(self):
                return handlers.get("keyboard")
            def get_print_handler(self):
                return handlers.get("print")
            def get_request_handler(self):
                return handlers.get("request")
        def start(body):
            app.offscreen = True
            app.set_client(MyClient())
            app.initialize(page(body))
            wait_until(app, lambda: paints, "the first paint")
        RED = "<style>html, body { margin: 0; background: rgb(255, 0, 0); }</style>"
    """

    def run_osr_script(self, body):
        import textwrap
        result = run_cef(textwrap.dedent(self.OSR_SCRIPT) + textwrap.dedent(body))
        self.assertClean(result)
        self.assertIn("OK", result.stdout)

    def test_on_paint_gives_a_read_only_view_of_the_pixels(self):
        self.run_osr_script("""
            start(RED)
            wait_until(app, lambda: any(p["first"] == b"\\x00\\x00\\xff\\xff" for p in paints),
                       "a red frame")  # BGRA
            frame = [p for p in paints if p["first"] == b"\\x00\\x00\\xff\\xff"][-1]
            assert frame["type"] == types.PaintElementType.VIEW, frame["type"]
            assert (frame["width"], frame["height"], frame["nbytes"]) == (200, 100, 200 * 100 * 4), frame
            assert frame["writable"] is False
            assert frame["rects"] and all(isinstance(r, cefweaver.Rect) for r in frame["rects"])
            r = frame["rects"][0]
            assert 0 <= r.x and 0 <= r.y and r.x + r.width <= 200 and r.y + r.height <= 100, r
            try:                       # the buffer belongs to CEF: the view ends with the call
                len(frame["view"])
                raise AssertionError("the view is still valid")
            except ValueError:
                pass
            assert boxes[0].get_host().is_window_rendering_disabled() is True
            try:
                app.offscreen = False  # only before initialize()
                raise AssertionError("accepted")
            except RuntimeError:
                pass
            app.shutdown()
            print("OK")
        """)

    def test_the_view_size_follows_get_view_rect_after_was_resized(self):
        self.run_osr_script("""
            start(RED)
            size[:] = [320, 240]
            send_until(app, lambda: boxes[0].get_host().was_resized(),
                       lambda: any(p["width"] == 320 for p in paints), "a 320x240 frame")
            frame = [p for p in paints if p["width"] == 320][-1]
            assert (frame["height"], frame["nbytes"]) == (240, 320 * 240 * 4), frame
            app.shutdown()
            print("OK")
        """)

    def test_mouse_events_reach_an_offscreen_page(self):
        self.run_osr_script("""
            start('<button style="position:fixed;left:0;top:0;width:200px;height:100px" '
                  'onclick="report(\\'clicked\\')">go</button>')
            host = boxes[0].get_host()
            def click():
                host.send_mouse_click_event((50, 50, 0), types.MouseButtonType.LEFT, False, 1)
                host.send_mouse_click_event((50, 50, 0), types.MouseButtonType.LEFT, True, 1)
            send_until(app, click, lambda: ("clicked",) in js, "the click")
            app.shutdown()
            print("OK")
        """)

    def test_an_offscreen_browser_blocks_popups_as_java_cef_does(self):
        self.run_osr_script("""
            app.add_command_line_switch("disable-popup-blocking")
            start(RED)
            app.execute_javascript("report('popup', window.open('about:blank') === null)")
            wait_until(app, lambda: any(r[0] == "popup" for r in js), "the answer")
            assert ("popup", True) in js, js
            assert len(boxes) == 1, boxes
            app.shutdown()
            print("OK")
        """)


    def test_keyboard_events_type_into_an_offscreen_page(self):
        self.run_osr_script("""
            start('<input id="i" autofocus style="width:150px">'
                  '<script>document.getElementById("i").addEventListener("keydown",'
                  'e => report("keydown", e.key));</script>')
            host = boxes[0].get_host()
            host.set_focus(True)
            KT = types.KeyEventType
            def key(kind, code):
                return cefweaver.KeyEvent(kind, 0, 65, 0, 0, code, code, 0)
            def type_a():
                host.send_key_event(key(KT.RAWKEYDOWN, 97))
                host.send_key_event(key(KT.CHAR, 97))
                host.send_key_event(key(KT.KEYUP, 97))
            send_until(app, type_a, lambda: ("keydown", "a") in js, "the key")
            app.execute_javascript("report('value', document.getElementById('i').value)")
            wait_until(app, lambda: any(r[0] == "value" for r in js), "the value")
            value = [r[1] for r in js if r[0] == "value"][0]
            assert value and set(value) == {"a"}, value      # one or more 'a' (the keys are resent)
            try:
                host.send_key_event("a")
                raise AssertionError("accepted")
            except TypeError:
                pass
            app.shutdown()
            print("OK")
        """)

    def test_the_handler_gives_the_screen_info_and_the_page_sees_the_scale(self):
        self.run_osr_script("""
            screen[0] = cefweaver.ScreenInfo(2.0, 24, 8, 0, cefweaver.Rect(0, 0, 200, 100),
                                             cefweaver.Rect(0, 0, 200, 100))
            start(RED)
            app.execute_javascript("report('dpr', window.devicePixelRatio)")
            wait_until(app, lambda: any(r[0] == "dpr" for r in js), "the scale")
            assert ("dpr", 2) in js or ("dpr", 2.0) in js, js
            wait_until(app, lambda: any(p["width"] == 400 for p in paints), "a scaled frame")
            frame = [p for p in paints if p["width"] == 400][-1]
            assert (frame["height"], frame["nbytes"]) == (200, 400 * 200 * 4), frame
            app.shutdown()
            print("OK")
        """)

    def test_touch_events_and_ime_compositions_are_accepted(self):
        self.run_osr_script("""
            start(RED)
            host = boxes[0].get_host()
            touch = cefweaver.TouchEvent(1, 10.0, 10.0, 1.0, 1.0, 0.0, 1.0,
                                         types.TouchEventType.PRESSED, 0, types.PointerType.TOUCH)
            host.send_touch_event(touch)
            host.send_touch_event(touch._replace(type=types.TouchEventType.RELEASED))
            underline = cefweaver.CompositionUnderline(cefweaver.Range(0, 1), 0xFF000000, 0, 0,
                                                       types.CompositionUnderlineStyle.SOLID)
            host.ime_set_composition("\\uac00", [underline], cefweaver.Range(0xFFFFFFFF, 0xFFFFFFFF),
                                     cefweaver.Range(1, 1))
            host.ime_cancel_composition()
            try:
                host.send_touch_event(5)
                raise AssertionError("accepted")
            except TypeError:
                pass
            app.shutdown()
            print("OK")
        """)


    def test_binary_values_travel_in_process_messages(self):
        self.run_query_script("""
            received = []
            class Client2(MyClient):
                def on_process_message_received(self, browser, frame, source_process, message):
                    received.append((message.get_name(),
                                     message.get_argument_list().get_binary(0).get_data(256, 0)))
                    return True
            MyClient = Client2
            start()
            payload = bytes(range(256))                    # every byte value
            message = cefweaver.ProcessMessage.create("cefweaver-ping")
            arguments = message.get_argument_list()
            arguments.set_size(1)
            arguments.set_binary(0, cefweaver.BinaryValue.create(payload))
            boxes[0].get_main_frame().send_process_message(types.ProcessId.RENDERER, message)
            wait_until(app, lambda: received, "the answer of the renderer")
            assert received == [("cefweaver-pong", payload)], received
            app.shutdown()
            print("OK")
        """)


    # -- more handlers of the client: focus, JavaScript dialogs, file dialog, downloads ----

    def test_the_focus_handler_sees_the_focus_of_the_browser(self):
        self.run_osr_script("""
            events = []
            class Focus(cefweaver.FocusHandler):
                def on_set_focus(self, browser, source):
                    events.append(("set", source))
                    return False                  # let CEF set the focus
                def on_got_focus(self, browser):
                    events.append(("got",))
            handlers["focus"] = Focus()
            start(RED)
            host = boxes[0].get_host()
            send_until(app, lambda: host.set_focus(True),
                       lambda: ("got",) in events, "the focus")
            sources = [e[1] for e in events if e[0] == "set"]
            assert all(isinstance(x, types.FocusSource) for x in sources), events
            app.shutdown()
            print("OK")
        """)

    def test_javascript_dialogs_are_answered_by_the_handler(self):
        self.run_osr_script("""
            seen = []
            class Dialogs(cefweaver.JSDialogHandler):
                def on_js_dialog(self, browser, origin_url, dialog_type, message_text,
                                 default_prompt_text, callback):
                    seen.append((dialog_type, message_text, default_prompt_text))
                    if dialog_type == types.JSDialogType.PROMPT:
                        callback.continue_(True, "typed")
                    else:
                        callback.continue_(dialog_type == types.JSDialogType.CONFIRM, "")
                    return True, False             # handled, do not suppress
            handlers["js_dialog"] = Dialogs()
            start(RED)
            app.execute_javascript("alert('a'); report('confirm', confirm('c?'));"
                                   "report('prompt', prompt('p?', 'dflt'))")
            wait_until(app, lambda: any(r[0] == "prompt" for r in js), "the dialogs")
            T = types.JSDialogType
            assert seen == [(T.ALERT, "a", ""), (T.CONFIRM, "c?", ""), (T.PROMPT, "p?", "dflt")], seen
            assert ("confirm", True) in js and ("prompt", "typed") in js, js
            app.shutdown()
            print("OK")
        """)

    def test_the_file_dialog_gets_the_files_from_the_handler(self):
        self.run_osr_script("""
            import os, tempfile
            folder = tempfile.mkdtemp()
            path = os.path.join(folder, "chosen.txt")
            open(path, "w").write("hello")
            asked = []
            class Files(cefweaver.DialogHandler):
                def on_file_dialog(self, browser, mode, title, default_file_path, accept_filters,
                                   accept_extensions, accept_descriptions, callback):
                    asked.append((mode, list(accept_filters), list(accept_extensions)))
                    callback.continue_([path])
                    return True
            handlers["dialog"] = Files()
            start('<input type="file" accept=".txt" style="position:fixed;left:0;top:0;'
                  'width:200px;height:100px" onchange="report(\\'file\\', this.files[0].name)">')
            host = boxes[0].get_host()
            def click():
                host.send_mouse_click_event((50, 50, 0), types.MouseButtonType.LEFT, False, 1)
                host.send_mouse_click_event((50, 50, 0), types.MouseButtonType.LEFT, True, 1)
            send_until(app, click, lambda: any(r[0] == "file" for r in js), "the chosen file")
            assert ("file", "chosen.txt") in js, js
            assert asked and asked[0][0] == types.FileDialogMode.OPEN, asked
            app.shutdown()
            print("OK")
        """)

    def test_a_download_is_saved_where_the_handler_says(self):
        self.run_osr_script("""
            import os, tempfile
            folder = tempfile.mkdtemp()
            target = os.path.join(folder, "saved.txt")
            began, updates, times = [], [], []
            class Downloads(cefweaver.DownloadHandler):
                def on_before_download(self, browser, download_item, suggested_name, callback):
                    began.append((suggested_name, download_item.get_url()))
                    callback.continue_(target, False)    # no dialog
                    return True
                def on_download_updated(self, browser, download_item, callback):
                    updates.append((download_item.is_complete(), download_item.get_received_bytes()))
                    times.append((download_item.get_start_time(), download_item.get_end_time()))
            handlers["download"] = Downloads()
            start(RED)
            app.add_resource("http://files.test/a.bin", b"0123456789", mime_type="application/octet-stream",
                             headers={"Content-Disposition": 'attachment; filename="named.txt"'})
            app.load_url("http://files.test/a.bin")
            wait_until(app, lambda: updates and updates[-1][0], "the download")
            assert began == [("named.txt", "http://files.test/a.bin")], began
            assert updates[-1] == (True, 10), updates
            assert open(target, "rb").read() == b"0123456789"
            import datetime
            start, end = times[-1]                    # UTC datetimes with a time zone
            now = datetime.datetime.now(datetime.timezone.utc)
            assert start.tzinfo is not None and abs((now - start).total_seconds()) < 120, start
            assert end >= start, (start, end)
            app.shutdown()
            print("OK")
        """)


    def test_the_keyboard_handler_sees_key_events_before_the_page(self):
        self.run_osr_script("""
            seen, pre = [], []
            class Keys(cefweaver.KeyboardHandler):
                def on_pre_key_event(self, browser, event):
                    pre.append(event)
                    return False, False            # not handled, not a keyboard shortcut
                def on_key_event(self, browser, event):
                    seen.append(event)
                    return False
            handlers["keyboard"] = Keys()
            start('<input id="i" autofocus>')
            host = boxes[0].get_host()
            host.set_focus(True)
            KT = types.KeyEventType
            def key(kind):
                return cefweaver.KeyEvent(kind, 0, 65, 0, 0, 97, 97, 0)
            def type_a():
                host.send_key_event(key(KT.RAWKEYDOWN))
                host.send_key_event(key(KT.CHAR))
                host.send_key_event(key(KT.KEYUP))
            send_until(app, type_a, lambda: pre, "the key event")
            assert all(isinstance(e, cefweaver.KeyEvent) for e in pre), pre
            assert pre[0].type == KT.RAWKEYDOWN and pre[0].windows_key_code == 65, pre[0]
            app.shutdown()
            print("OK")
        """)


    def test_the_print_handler_sees_the_start_the_settings_and_the_reset(self):
        self.run_osr_script("""
            order = []
            class Printing(cefweaver.PrintHandler):
                def on_print_start(self, browser):
                    order.append("start")
                def on_print_settings(self, browser, settings, get_defaults):
                    order.append(("settings", isinstance(settings, cefweaver.PrintSettings)))
                def on_print_dialog(self, browser, has_selection, callback):
                    order.append("dialog")
                    callback.continue_(cefweaver.PrintSettings.create())  # the user presses "Print"
                    return True
                def on_print_job(self, browser, document_name, pdf_job_name, callback):
                    order.append("job")
                    callback.continue_()
                    return True
                def on_print_reset(self, browser):
                    order.append("reset")
                def get_pdf_paper_size(self, browser, device_units_per_inch):
                    return cefweaver.Size(595, 842)
            handlers["print"] = Printing()
            start('<p>print me</p>')
            boxes[0].get_host().print()
            wait_until(app, lambda: "reset" in order, "the end of the print")
            assert cefweaver.PrintHandler.get_pdf_paper_size is not None
            # With no printer (this environment) CEF reports an error instead of asking for
            # the dialog and the job: only the start, the settings and the reset arrive.
            assert order == ["start", ("settings", True), "reset"], order
            app.shutdown()
            print("OK")
        """)


    def test_the_request_handler_can_cancel_a_navigation(self):
        self.run_osr_script("""
            asked = []
            class Requests(cefweaver.RequestHandler):
                def on_before_browse(self, browser, frame, request, user_gesture, is_redirect):
                    asked.append((frame.is_main(), request.get_url(), user_gesture, is_redirect))
                    return request.get_url().endswith("/blocked")     # True cancels it
            handlers["request"] = Requests()
            start(RED)
            for name in ("blocked", "allowed"):
                app.add_resource("http://nav.test/" + name,
                                 "<script>report('loaded', '%s')</script>" % name)
            app.load_url("http://nav.test/blocked")
            wait_until(app, lambda: any(a[1].endswith("/blocked") for a in asked),
                       "the first navigation")
            app.load_url("http://nav.test/allowed")
            wait_until(app, lambda: ("loaded", "allowed") in js, "the allowed page")
            site = [a for a in asked if a[1].startswith("http://nav.test")]  # not the start page
            assert [a[1] for a in site] == ["http://nav.test/blocked", "http://nav.test/allowed"], asked
            assert all(a[0] is True for a in site), asked
            assert ("loaded", "blocked") not in js, js              # it never loaded
            app.shutdown()
            print("OK")
        """)

    def test_the_resource_request_handler_sees_and_can_cancel_resources(self):
        self.run_osr_script("""
            events, seen = [], []
            class Resources(cefweaver.ResourceRequestHandler):
                def on_before_resource_load(self, browser, frame, request, callback):
                    seen.append(request.get_url())
                    if request.get_url().endswith("/image.png"):
                        return types.ReturnValue.CANCEL
                    return types.ReturnValue.CONTINUE
                def on_resource_load_complete(self, browser, frame, request, response, status,
                                              received_content_length):
                    events.append((request.get_url(), status, received_content_length))
            class Requests(cefweaver.RequestHandler):
                def get_resource_request_handler(self, browser, frame, request, is_navigation,
                                                 is_download, request_initiator):
                    return Resources(), False                      # (the handler, disable defaults)
            handlers["request"] = Requests()
            start(RED)
            app.add_resource("http://res.test/page", "<img src='/image.png' "
                             "onerror=\\"report('image', 'blocked')\\" onload=\\"report('image', 'ok')\\">")
            app.add_resource("http://res.test/image.png", b"x", mime_type="image/png")
            app.load_url("http://res.test/page")
            wait_until(app, lambda: ("image", "blocked") in js, "the canceled image")
            assert "http://res.test/page" in seen and "http://res.test/image.png" in seen, seen
            wait_until(app, lambda: any(e[0].endswith("/page") for e in events), "the page complete")
            page = [e for e in events if e[0].endswith("/page")][0]
            assert page[1] == types.URLRequestStatus.SUCCESS and page[2] > 0, page
            app.shutdown()
            print("OK")
        """)

    def test_the_router_and_the_users_request_handler_both_get_the_navigation(self):
        self.run_query_script("""
            asked, canceled, pending = [], [], {}
            class Requests(cefweaver.RequestHandler):
                def on_before_browse(self, browser, frame, request, user_gesture, is_redirect):
                    asked.append(request.get_url())
                    return request.get_url().endswith("/stay")        # the user cancels this one
            class Handler(cefweaver.QueryHandler):
                def on_query(self, browser, frame, query_id, request, persistent, callback):
                    pending[query_id] = callback
                    return True
                def on_query_canceled(self, browser, frame, query_id):
                    canceled.append(query_id)
            class Client2(MyClient):
                def get_request_handler(self):
                    return Requests()
            MyClient = Client2
            app.add_query_handler(Handler())
            start()
            app.execute_javascript("ask('open', true)")
            wait_until(app, lambda: pending, "the query")
            app.add_resource("http://nav.test/stay", "<p>stay</p>")
            app.add_resource("http://nav.test/go", "<p>go</p>")
            app.load_url("http://nav.test/stay")                       # canceled by the user
            wait_until(app, lambda: any(u.endswith("/stay") for u in asked), "the first navigation")
            for _ in range(100):
                app.do_message_loop_work(); time.sleep(0.005)
            assert canceled == [], canceled                             # the page was not left
            app.load_url("http://nav.test/go")                         # allowed: the query ends
            wait_until(app, lambda: canceled, "the cancellation by the navigation")
            site = [u for u in asked if u.startswith("http://nav.test")]  # not the start page
            assert site == ["http://nav.test/stay", "http://nav.test/go"], asked
            app.shutdown()
            print("OK")
        """)


    def test_the_life_span_handler_decides_about_a_popup_from_its_url_and_name(self):
        self.run_query_script(prelude=self.SITE_SCRIPT, body="""
            asked = []
            class Life2(Life):
                def on_before_popup(self, browser, frame, target_url, target_frame_name):
                    asked.append((frame.is_main(), target_url, target_frame_name))
                    return target_url.endswith("/denied")           # True cancels the popup
            class Client2(MyClient):
                def __init__(self):
                    self.life = Life2()
            MyClient = Client2
            start_site()
            app.add_resource(SITE + "/denied", "<p>no</p>")
            app.add_resource(SITE + "/granted", "<p>yes</p>")
            app.execute_javascript("report('denied', window.open('%s/denied', 'one') === null)" % SITE)
            wait_until(app, lambda: any(r[0] == "denied" for r in js), "the first popup")
            assert ("denied", True) in js, js                      # the popup was canceled
            app.execute_javascript("report('granted', window.open('%s/granted', 'two') === null)" % SITE)
            wait_until(app, lambda: len(boxes) == 2 and ("granted", False) in js,
                       "the second browser")
            assert asked == [(True, SITE + "/denied", "one"), (True, SITE + "/granted", "two")], asked
            app.shutdown()
            print("OK")
        """)

    def test_the_display_handler_gets_the_cursor_type(self):
        self.run_osr_script("""
            kinds = []
            class Display(cefweaver.DisplayHandler):
                def on_cursor_change(self, browser, type):
                    kinds.append(type)
                    return False                      # CEF changes the cursor
            class Client2(MyClient):
                def get_display_handler(self):
                    return self.display
                def __init__(self):
                    super().__init__()
                    self.display = Display()
            MyClient = Client2
            start('<div style="position:fixed;left:0;top:0;width:200px;height:100px;'
                  'cursor:pointer"></div>')
            host = boxes[0].get_host()
            def move():
                host.send_mouse_move_event((50, 50, 0), False)
            send_until(app, move, lambda: types.CursorType.HAND in kinds, "the hand cursor")
            assert all(isinstance(k, types.CursorType) for k in kinds), kinds
            app.shutdown()
            print("OK")
        """)


WAYLAND_OK = (RUNTIME_OK and bool(os.environ.get("WAYLAND_DISPLAY"))
              and os.environ.get("CEFWEAVER_TEST_WAYLAND") == "1")


@unittest.skipUnless(WAYLAND_OK, "opens a window on the Wayland desktop; run it with "
                     "CEFWEAVER_TEST_WAYLAND=1 in a Wayland session")
class WithCefOnWayland(unittest.TestCase):
    """Native Wayland needs a real compositor, so these tests are opt-in (the other tests
    use a virtual X server and never open a window on the desktop)."""

    assertClean = WithCef.assertClean

    def test_the_default_on_a_wayland_session_is_x11_and_the_window_gets_its_title(self):
        # Alloy style crashes libcef on native Wayland (see below), so without an explicit
        # ozone-platform the wrapper uses X11 (XWayland) when there is an X display.
        result = run_cef("""
            import re, subprocess
            got, titles = {}, []
            app.add_javascript_binding("report", lambda k, v: got.__setitem__(k, v))
            class Display(cefweaver.DisplayHandler):
                def on_title_change(self, browser, title):
                    titles.append(title)
            class MyClient(cefweaver.Client):
                def __init__(self):
                    self.display = Display()
                def get_display_handler(self):
                    return self.display
            def x11_window():
                tree = subprocess.run(["xwininfo", "-root", "-tree"], capture_output=True,
                                      text=True).stdout
                return re.search(r'"Default Platform Title"', tree) is not None
            app.set_client(MyClient())
            app.initialize(page("<title>Default Platform Title</title><script>"
                                "let n = 0, t0 = performance.now();"
                                "function f() { n++; if (performance.now() - t0 < 700) "
                                "requestAnimationFrame(f); else report('frames', n); }"
                                "requestAnimationFrame(f);</script>"))
            wait_until(app, lambda: "frames" in got and titles, "the frames and the title")
            assert got["frames"] > 10, got
            wait_until(app, x11_window, "an X11 window with the page title")
            app.shutdown()
            print("OK")
        """, ozone=None)
        self.assertClean(result)
        self.assertIn("OK", result.stdout)

    @unittest.expectedFailure
    def test_known_cef_issue_alloy_style_crashes_on_native_wayland(self):
        # With ozone-platform=wayland the browser process of an Alloy style browser ends with
        # SIGTRAP inside libcef, whatever the page is and with or without the window title
        # code. Chrome style worked on native Wayland. If this starts to pass, CEF fixed it:
        # remove expectedFailure and reconsider the X11 default.
        result = run_cef("""
            got = {}
            app.add_javascript_binding("report", lambda k, v: got.__setitem__(k, v))
            app.initialize(page("<script>setTimeout(() => report('done', 1), 1500)</script>"))
            wait_until(app, lambda: "done" in got, "the page", timeout=20)
            app.shutdown()
            print("OK")
        """, ozone="wayland")
        self.assertClean(result)
        self.assertIn("OK", result.stdout)


if __name__ == "__main__":
    unittest.main()
