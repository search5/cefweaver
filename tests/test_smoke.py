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
