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
import re
import shutil
import subprocess
import sys
import tempfile
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


def run_cef(script, timeout=90, ozone="x11", without=()):
    """Run `script` (after PRELUDE) in a new process; return CompletedProcess."""
    # ozone=None leaves the platform to the wrapper (its default).
    line = '"ozone-platform", "x11"'
    prelude = PRELUDE.replace('app.add_command_line_switch(%s)' % line, "pass") if ozone is None \
        else PRELUDE.replace(line, '"ozone-platform", "%s"' % ozone)
    code = prelude + textwrap.dedent(script)
    # Everything the run makes (the CEF cache, files of the script) goes into one directory
    # that is removed afterwards: hundreds of runs would fill /tmp otherwise.
    with tempfile.TemporaryDirectory(prefix="cefweaver-run-") as scratch:
        env = {k: v for k, v in os.environ.items() if k not in without}
        env["TMPDIR"] = scratch
        return subprocess.run([sys.executable, "-I", "-c", code], capture_output=True,
                              text=True, timeout=timeout, env=env)


@unittest.skipIf(cefweaver is None, "cefweaver is not installed")
class ApiWithoutCef(unittest.TestCase):
    def test_shared_textures_are_a_flag_and_the_info_is_a_value_type(self):
        app = cefweaver.CefApp()
        self.assertIs(app.shared_texture, False)
        app.shared_texture = True
        self.assertIs(app.shared_texture, True)
        with self.assertRaises(TypeError):
            app.shared_texture = "yes"
        info = cefweaver.types.AcceleratedPaintInfo()
        self.assertEqual((info.planes, info.modifier), ((), 0))
        plane = cefweaver.types.AcceleratedPaintNativePixmapPlane(stride=4, offset=0, size=8, fd=3)
        self.assertEqual((plane.stride, plane.fd), (4, 3))
        self.assertIsNone(cefweaver.RenderHandler().on_accelerated_paint(None, 0, [], info))
        app.shutdown()

    def test_read_plane_copies_the_bytes_of_a_descriptor_from_its_offset(self):
        # a temporary file stands in for a dmabuf: the mapping is the same
        data = bytes(range(256)) * 16
        with tempfile.TemporaryFile() as handle:
            fd = handle.fileno()
            handle.write(data)
            handle.flush()
            plane = cefweaver.types.AcceleratedPaintNativePixmapPlane(stride=64, offset=128, size=1024, fd=fd)
            self.assertEqual(cefweaver.read_plane(plane), data[128:128 + 1024])
            self.assertEqual(cefweaver.read_plane(plane, 10), data[128:138])
            with self.assertRaises(OSError):
                cefweaver.read_plane(plane._replace(fd=-1))

    def test_a_javascript_bridge_checks_what_it_exposes(self):
        app = cefweaver.CefApp()
        bridge = cefweaver.JavascriptBridge(app)
        bridge.expose("add", lambda a, b: a + b)
        with self.assertRaises(TypeError):
            bridge.expose("x", 3)                                  # not callable
        for bad in ("bad name", "1x", "", "a.b", "class"):
            with self.assertRaises(ValueError, msg=bad):
                bridge.expose(bad, print)
        with self.assertRaises(ValueError):
            bridge.expose("add", print)                            # twice
        with self.assertRaises(TypeError):
            cefweaver.JavascriptBridge(cefweaver.CefApp(), origins="http://a.test/")   # a list
        self.assertTrue(callable(cefweaver.JsCallback.call) and callable(cefweaver.JsCallback.release))
        app.shutdown()

    def test_browser_settings_default_to_cefs_choices_and_cannot_change_after_initialize(self):
        types = cefweaver.types
        defaults = types.BrowserSettings()
        self.assertEqual(defaults.javascript, types.State.DEFAULT)
        self.assertEqual(defaults.default_encoding, "")
        self.assertEqual((defaults.default_font_size, defaults.windowless_frame_rate), (0, 0))
        app = cefweaver.CefApp()
        self.assertEqual(app.browser_settings, defaults)
        mine = defaults._replace(javascript=types.State.DISABLED, default_font_size=30)
        app.browser_settings = mine
        self.assertEqual(app.browser_settings, mine)
        with self.assertRaises(TypeError):
            app.browser_settings = {"javascript": 2}
        with self.assertRaises(TypeError):
            app.browser_settings = None
        app.shutdown()

    def test_tasks_and_threads_are_in_the_module(self):
        task = cefweaver.Task()
        self.assertTrue(callable(cefweaver.post_task))
        self.assertTrue(callable(cefweaver.post_delayed_task))
        self.assertTrue(callable(cefweaver.currently_on))
        self.assertIsNone(task.execute())                          # the default does nothing

    def test_a_message_pump_keeps_the_latest_request_and_a_fall_back_timer(self):
        import threading

        class Settings:
            external_message_pump = False

        class FakeApp:
            def __init__(self):
                self.settings = Settings()
                self.handler = None
                self.pumped = 0
                self.during = None

            def set_app_handler(self, handler):
                self.handler = handler

            def do_message_loop_work(self):
                self.pumped += 1
                if self.during is not None:
                    self.handler.on_schedule_message_pump_work(self.during)   # CEF asks while it works

        app = FakeApp()
        woken = []
        pump = cefweaver.MessagePump(app, wake=woken.append)
        self.assertIsInstance(pump, cefweaver.AppHandler)
        self.assertIs(app.handler, pump)
        self.assertTrue(app.settings.external_message_pump)        # the setting CEF needs
        self.assertEqual(pump.timeout(), 0.0)                      # the first pump is due at once
        self.assertTrue(pump.run())
        self.assertEqual(app.pumped, 1)
        self.assertTrue(0 < pump.timeout() <= 1 / 30)              # then the fall-back timer
        self.assertFalse(pump.run())                               # not due: nothing runs
        self.assertEqual(app.pumped, 1)
        pump.on_schedule_message_pump_work(5000)                   # a far request: still within 1/30 s
        self.assertTrue(pump.timeout() <= 1 / 30)
        self.assertTrue(woken[-1] <= 1 / 30)
        pump.on_schedule_message_pump_work(0)                      # a later request replaces it
        self.assertEqual(pump.timeout(), 0.0)
        thread = threading.Thread(target=pump.on_schedule_message_pump_work, args=(-3,))
        thread.start()
        thread.join()                                              # any thread, a negative delay is now
        self.assertEqual(pump.timeout(), 0.0)
        app.during = 0                                             # CEF asks for more work while it runs
        self.assertTrue(pump.run())
        self.assertEqual(pump.timeout(), 0.0)                      # and that request is not lost
        app.during = None
        self.assertTrue(pump.run())
        self.assertFalse(pump.run())

    def test_a_message_pump_needs_an_app_that_is_not_started_yet(self):
        app = cefweaver.CefApp()
        app.shutdown()
        pump = cefweaver.MessagePump(app)
        self.assertTrue(app.settings.external_message_pump)
        started = cefweaver.CefApp()
        started.settings._freeze()
        with self.assertRaises(RuntimeError):
            cefweaver.MessagePump(started)

    def test_the_app_handler_has_the_message_pump_hook_and_does_nothing_by_default(self):
        handler = cefweaver.AppHandler()
        self.assertIsNone(handler.on_schedule_message_pump_work(10))

    def test_a_browser_cannot_be_created_before_cef_runs(self):
        app = cefweaver.CefApp()
        with self.assertRaises(RuntimeError):
            app.create_browser("about:blank")
        app.shutdown()

    def test_the_version_is_known_before_cef_starts_and_matches_the_cef_headers(self):
        version = cefweaver.get_version()                          # java-cef: CefApp.getVersion()
        self.assertIsInstance(version, cefweaver.Version)
        self.assertEqual(cefweaver.CefApp.get_version(), version)
        self.assertEqual(cefweaver.CefApp().get_version(), version)
        self.assertRegex(version.cefweaver, r"^\d+\.\d+")
        self.assertEqual(version.cef, "%d.%d.%d" % (version.cef_major, version.cef_minor, version.cef_patch))
        self.assertEqual(version.chrome, "%d.%d.%d.%d" % (version.chrome_major, version.chrome_minor,
                                                          version.chrome_build, version.chrome_patch))
        header = os.path.join(os.path.dirname(__file__), "..", "build", "native", "cef", "include",
                              "cef_version.h")
        if not os.path.exists(header):
            self.skipTest("the CEF headers are not here")
        text = open(header, encoding="utf-8").read()
        def number(name):
            return int(re.search(r"#define %s (\d+)" % name, text).group(1))
        self.assertEqual((version.cef_major, version.cef_minor, version.cef_patch, version.cef_commit),
                         (number("CEF_VERSION_MAJOR"), number("CEF_VERSION_MINOR"), number("CEF_VERSION_PATCH"),
                          number("CEF_COMMIT_NUMBER")))
        self.assertEqual((version.chrome_major, version.chrome_minor, version.chrome_build, version.chrome_patch),
                         tuple(number("CHROME_VERSION_" + n) for n in ("MAJOR", "MINOR", "BUILD", "PATCH")))

    def test_settings_hold_the_fields_of_the_java_cef_settings_and_check_them(self):
        app = cefweaver.CefApp()
        settings = app.settings
        self.assertIsInstance(settings, cefweaver.Settings)
        names = ("root_cache_path", "external_message_pump", "user_agent", "user_agent_product", "locale", "log_file", "log_severity",
                 "javascript_flags", "remote_debugging_port", "persist_session_cookies",
                 "command_line_args_disabled", "chrome_policy_id", "uncaught_exception_stack_size",
                 "background_color", "cookieable_schemes_list", "cookieable_schemes_exclude_defaults")
        for name in names:
            self.assertIsNone(getattr(settings, name), name)       # unset: CEF decides
        settings.user_agent = "Agent/1"
        settings.root_cache_path = "/tmp/root"
        settings.external_message_pump = True
        settings.log_severity = cefweaver.types.LogSeverity.WARNING
        settings.remote_debugging_port = 9222
        settings.persist_session_cookies = True
        settings.background_color = 0xFF00FF00
        self.assertEqual(settings.user_agent, "Agent/1")
        settings.user_agent = None                                 # back to unset
        self.assertIsNone(settings.user_agent)
        with self.assertRaises(AttributeError):
            settings.no_such_setting = 1                           # a typo does not pass silently
        with self.assertRaises(TypeError):
            settings.user_agent = 3
        with self.assertRaises(TypeError):
            settings.persist_session_cookies = "yes"
        with self.assertRaises(TypeError):
            settings.remote_debugging_port = True                  # a bool is not a port
        with self.assertRaises(ValueError):
            settings.remote_debugging_port = 70000
        with self.assertRaises(ValueError):
            settings.background_color = -1
        fresh = cefweaver.Settings(locale="ko", remote_debugging_port=9333)
        self.assertEqual((fresh.locale, fresh.remote_debugging_port), ("ko", 9333))
        with self.assertRaises(TypeError):
            cefweaver.Settings(unknown=1)
        app.shutdown()

    def test_transparent_is_a_flag_for_the_offscreen_browser(self):
        app = cefweaver.CefApp()
        self.assertIs(app.transparent, True)
        app.transparent = False
        self.assertIs(app.transparent, False)
        app.shutdown()

    def test_settings_are_given_to_the_app_and_cannot_change_after_initialize(self):
        app = cefweaver.CefApp()
        mine = cefweaver.Settings(locale="ko")
        app.settings = mine
        self.assertIs(app.settings, mine)
        with self.assertRaises(TypeError):
            app.settings = {"locale": "ko"}
        app.shutdown()

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

    def test_header_maps_are_dicts(self):
        request = cefweaver.Request.create()
        request.set_url("http://example.test/")
        request.set_header_map({"X-Token": "abc", "Accept": "text/html"})
        self.assertEqual(request.get_header_map(), {"X-Token": "abc", "Accept": "text/html"})
        self.assertEqual(request.get_header_by_name("x-token"), "abc")   # CEF is case-insensitive
        request.set_header_map({})
        self.assertEqual(request.get_header_map(), {})
        request.set("http://example.test/a", "POST", None, {"Content-Type": "text/plain"})
        self.assertEqual((request.get_url(), request.get_method()), ("http://example.test/a", "POST"))
        self.assertEqual(request.get_header_map(), {"Content-Type": "text/plain"})
        response = cefweaver.Response.create()
        response.set_header_map({"Set-Cookie": "a=1", "Server": "x"})
        self.assertEqual(response.get_header_map(), {"Set-Cookie": "a=1", "Server": "x"})
        for bad in (None, [("a", "b")], {"a": 1}, {1: "b"}):
            with self.assertRaises((TypeError, AttributeError)):
                request.set_header_map(bad)

    def test_structs_with_strings_and_times_have_defaults(self):
        settings = cefweaver.types.PdfPrintSettings()
        self.assertEqual((settings.landscape, settings.scale, settings.page_ranges), (0, 0.0, ""))
        landscape = settings._replace(landscape=1, page_ranges="1-2", header_template="<b>x</b>")
        self.assertEqual((landscape.landscape, landscape.page_ranges), (1, "1-2"))
        cookie = cefweaver.types.Cookie()
        self.assertEqual((cookie.name, cookie.expires), ("", None))
        self.assertEqual(cefweaver.Rect(), (0, 0, 0, 0))           # every struct has defaults
        self.assertEqual(cefweaver.types.DraggableRegion().bounds, cefweaver.Rect())

    def test_a_command_line_is_built_and_read(self):
        self.assertIn("AppHandler", cefweaver.__all__)
        self.assertIn("SchemeRegistrar", cefweaver.__all__)
        line = cefweaver.CommandLine.create_command_line()
        # (init_from_string() parses a Windows command line; on Linux CEF has init_from_argv())
        line.set_program("prog")
        line.append_switch_with_value("alpha", "1")
        line.append_switch("beta")
        line.append_argument("file1")
        line.append_argument("file2")
        self.assertEqual(line.get_program(), "prog")
        self.assertEqual(line.get_switches(), {"alpha": "1", "beta": ""})
        self.assertEqual(line.get_arguments(), ["file1", "file2"])
        self.assertTrue(line.has_switches() and line.has_arguments())
        line.append_switch("gamma")
        line.append_switch_with_value("delta", "x y")
        line.append_argument("tail")
        self.assertTrue(line.has_switch("gamma"))
        self.assertEqual(line.get_switch_value("delta"), "x y")
        self.assertEqual(line.get_switch_value("missing"), "")
        self.assertEqual(line.get_arguments()[-1], "tail")
        line.set_program("other")
        self.assertEqual(line.get_program(), "other")
        line.reset()
        self.assertEqual((line.get_switches(), line.get_arguments()), ({}, []))
        self.assertFalse(line.has_switches() or line.has_arguments())

    def test_drag_data_holds_a_link_text_and_files(self):
        data = cefweaver.DragData.create()
        # CEF's kinds: a drag is a link, a file or else a fragment (so a new one is a fragment)
        self.assertEqual((data.is_link(), data.is_fragment(), data.is_file()), (False, True, False))
        data.set_fragment_text("some text")
        data.set_fragment_html("<b>some</b> text")
        data.set_fragment_base_url("http://example.test/")
        self.assertEqual((data.get_fragment_text(), data.get_fragment_html()),
                         ("some text", "<b>some</b> text"))
        self.assertEqual(data.get_fragment_base_url(), "http://example.test/")
        data.set_link_url("http://example.test/a")
        data.set_link_title("A link")
        data.set_link_metadata("text/plain:name.txt:http://example.test/file.txt")  # mime:name:url
        self.assertEqual((data.is_link(), data.is_fragment()), (True, False))
        self.assertEqual((data.get_link_url(), data.get_link_title(), data.get_link_metadata()),
                         ("http://example.test/a", "A link",
                          "text/plain:name.txt:http://example.test/file.txt"))
        data.add_file("/tmp/one.txt", "one.txt")
        self.assertTrue(data.is_file())
        # (get_file_name() is for the image of a drag with file contents: CEF ends the process
        # with a failed CHECK when there is none, so it is not called here)
        self.assertEqual(data.get_file_paths(), (True, ["/tmp/one.txt"]))
        self.assertEqual(data.get_file_names(), (True, ["one.txt"]))
        self.assertEqual(cefweaver.DragData.create().get_file_paths(), (False, []))
        copy = data.clone()
        copy.set_link_url("http://example.test/b")
        self.assertEqual(data.get_link_url(), "http://example.test/a")       # a copy of its own
        self.assertFalse(data.is_read_only())
        # the contents of a file go to a stream writer (java-cef's OutputStream); this one has none
        class Sink(cefweaver.WriteHandler):
            def write(self, ptr, size):
                return len(ptr) // size
            def seek(self, offset, whence):
                return 0
            def tell(self):
                return 0
            def flush(self):
                return 0
            def may_block(self):
                return False
        self.assertEqual(data.get_file_contents(cefweaver.StreamWriter.create_for_handler(Sink())), 0)

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
        dragged, drag_return = [], [False]  # what start_dragging() got, and what it answers
        popups = []  # on_popup_show() and on_popup_size() calls
        closed = []  # the identifiers of the browsers that were closed
        ranges = []  # on_ime_composition_range_changed(): (selected range, [bounds of the characters])
        probe = [None]  # a function (blue, green, red) -> bool: paints count the pixels it accepts
        app.add_javascript_binding("report", lambda *a: js.append(a))
        class Render(cefweaver.RenderHandler):
            def get_view_rect(self, browser):
                return cefweaver.Rect(0, 0, size[0], size[1])
            def on_ime_composition_range_changed(self, browser, selected_range, character_bounds):
                ranges.append((tuple(selected_range), [tuple(r) for r in character_bounds]))
            def on_popup_show(self, browser, show):
                popups.append(("show", show))
            def on_popup_size(self, browser, rect):
                popups.append(("size", tuple(rect)))
            def start_dragging(self, browser, drag_data, allowed_ops, x, y):
                dragged.append((drag_data.get_fragment_text(), drag_data.is_fragment(),
                                allowed_ops, x, y))
                return drag_return[0]
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
                found = 0
                if probe[0] is not None and type == types.PaintElementType.VIEW:
                    pixels = bytes(buffer)
                    found = sum(1 for i in range(0, len(pixels), 4) if probe[0](*pixels[i:i + 3]))
                paints.append(dict(type=type, rects=list(dirty_rects), writable=writable, found=found,
                                   browser=browser.get_identifier(),
                                   nbytes=len(buffer), width=width, height=height,
                                   first=bytes(buffer[:4]), view=buffer))
        class Life(cefweaver.LifeSpanHandler):
            def on_after_created(self, browser):
                boxes.append(browser)
            def on_before_close(self, browser):
                closed.append(browser.get_identifier())
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
            def get_drag_handler(self):
                return handlers.get("drag")
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

    LOCAL_SERVER = """
        import base64, http.server, threading
        class LocalHandler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_GET(self):
                if self.path == "/hello":
                    self.reply(200, b"hello world")
                elif self.path == "/auth":
                    expected = "Basic " + base64.b64encode(b"user:pass").decode()
                    if self.headers.get("Authorization") == expected:
                        self.reply(200, b"welcome user")
                    else:
                        self.reply(401, b"denied", {"WWW-Authenticate": 'Basic realm="test"'})
                elif self.path == "/redirect":
                    self.reply(302, b"", {"Location": "/hello"})
                else:
                    self.reply(404, b"not found")
            def reply(self, status, body, headers=None):
                self.send_response(status)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(body)))
                for name, value in (headers or {}).items():
                    self.send_header(name, value)
                self.end_headers()
                self.wfile.write(body)
        local_server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), LocalHandler)
        threading.Thread(target=local_server.serve_forever, daemon=True).start()
        BASE = "http://127.0.0.1:%d" % local_server.server_address[1]
    """

    LOCAL_TLS_SERVER = """
        import http.server, os, ssl, subprocess, tempfile, threading
        _folder = tempfile.mkdtemp()
        _key, _crt = os.path.join(_folder, "key.pem"), os.path.join(_folder, "crt.pem")
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", _key,
                        "-out", _crt, "-days", "1", "-subj", "/CN=127.0.0.1",
                        "-addext", "subjectAltName=IP:127.0.0.1"], check=True, capture_output=True)
        class SecureHandler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_GET(self):
                body = b"secure hello"
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
        _context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        _context.load_cert_chain(_crt, _key)
        secure_server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), SecureHandler)
        secure_server.socket = _context.wrap_socket(secure_server.socket, server_side=True)
        threading.Thread(target=secure_server.serve_forever, daemon=True).start()
        SECURE = "https://127.0.0.1:%d" % secure_server.server_address[1]
    """

    def run_osr_script(self, body, prelude=""):
        import textwrap
        result = run_cef(textwrap.dedent(self.OSR_SCRIPT) + textwrap.dedent(prelude)
                         + textwrap.dedent(body))
        self.assertClean(result)
        self.assertIn("OK", result.stdout)
        return result.stdout

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


    def test_the_window_handle_is_the_native_window_of_a_windowed_browser(self):
        self.run_query_script("""
            start()
            handle = boxes[0].get_host().get_window_handle()
            assert isinstance(handle, int) and handle > 0, handle      # an X11 window
            app.shutdown()
            print("OK")
        """)

    def test_an_offscreen_browser_has_no_window_handle(self):
        self.run_osr_script("""
            start(RED)
            assert boxes[0].get_host().get_window_handle() == 0
            app.shutdown()
            print("OK")
        """)


    def test_a_string_visitor_gets_the_source_and_the_text_of_a_frame(self):
        self.run_osr_script("""
            got = {}
            class Source(cefweaver.StringVisitor):
                def visit(self, string):
                    got["source"] = string
            class Text(cefweaver.StringVisitor):
                def visit(self, string):
                    got["text"] = string
            start('<p id="x">hello <b>there</b></p>')
            wait_until(app, lambda: app.is_ready_to_execute_javascript, "the page")
            frame = boxes[0].get_main_frame()
            frame.get_source(Source())
            frame.get_text(Text())
            wait_until(app, lambda: len(got) == 2, "both visitors")
            assert '<p id="x">hello <b>there</b></p>' in got["source"], got
            assert got["text"].strip() == "hello there", got
            app.shutdown()
            print("OK")
        """)

    def test_run_file_dialog_reports_the_files_the_dialog_handler_chose(self):
        self.run_osr_script("""
            import os, tempfile
            path = os.path.join(tempfile.mkdtemp(), "picked.txt")
            open(path, "w").write("x")
            asked, dismissed = [], []
            class Files(cefweaver.DialogHandler):
                def on_file_dialog(self, browser, mode, title, default_file_path, accept_filters,
                                   accept_extensions, accept_descriptions, callback):
                    asked.append((mode, title, default_file_path))
                    callback.continue_([path])
                    return True
            class Done(cefweaver.RunFileDialogCallback):
                def on_file_dialog_dismissed(self, file_paths):
                    dismissed.append(file_paths)
            handlers["dialog"] = Files()
            start(RED)
            boxes[0].get_host().run_file_dialog(types.FileDialogMode.OPEN, "Pick", "/tmp", [".txt"], Done())
            wait_until(app, lambda: dismissed, "the dismissed dialog")
            assert dismissed == [[path]], dismissed
            assert asked and asked[0][0] == types.FileDialogMode.OPEN, asked
            app.shutdown()
            print("OK")
        """)

    def test_a_devtools_message_observer_gets_the_result_of_a_method(self):
        self.run_osr_script("""
            results, events = [], []
            class Observer(cefweaver.DevToolsMessageObserver):
                def on_dev_tools_method_result(self, browser, message_id, success, result):
                    results.append((message_id, success, bytes(result)))
                def on_dev_tools_event(self, browser, method, params):
                    events.append((method, bytes(params)))
            start(RED)
            host = boxes[0].get_host()
            observer = Observer()
            registration = host.add_dev_tools_message_observer(observer)
            assert registration is not None
            params = cefweaver.DictionaryValue.create()
            params.set_string("expression", "1 + 2")
            message_id = host.execute_dev_tools_method(0, "Runtime.evaluate", params)
            assert message_id > 0, message_id
            wait_until(app, lambda: results, "the method result")
            assert results[0][0] == message_id and results[0][1] is True, results
            assert b'"value":3' in results[0][2], results[0]
            app.shutdown()
            print("OK")
        """)


    def test_print_to_pdf_writes_a_pdf_and_tells_the_callback(self):
        self.run_osr_script("""
            import os, tempfile
            path = os.path.join(tempfile.mkdtemp(), "page.pdf")
            done = []
            class Finished(cefweaver.PdfPrintCallback):
                def on_pdf_print_finished(self, path, ok):
                    done.append((path, ok))
            start('<h1>to pdf</h1>')
            wait_until(app, lambda: app.is_ready_to_execute_javascript, "the page")
            settings = types.PdfPrintSettings(scale=1.0, paper_width=8.27, paper_height=11.69,
                                              print_background=1, page_ranges="1",
                                              margin_type=types.PdfPrintMarginType.DEFAULT)
            boxes[0].get_host().print_to_pdf(path, settings, Finished())
            wait_until(app, lambda: done, "the end of the print")
            assert done == [(path, True)], done
            data = open(path, "rb").read()
            assert data.startswith(b"%PDF") and len(data) > 500, data[:20]
            app.shutdown()
            print("OK")
        """)


    def test_the_cookie_manager_sets_visits_and_deletes_cookies(self):
        self.run_osr_script("""
            T = types
            flushed, set_results, deleted, seen = [], [], [], []
            class Done(cefweaver.CompletionCallback):
                def on_complete(self):
                    flushed.append(True)
            class SetDone(cefweaver.SetCookieCallback):
                def on_complete(self, success):
                    set_results.append(success)
            class DeleteDone(cefweaver.DeleteCookiesCallback):
                def on_complete(self, num_deleted):
                    deleted.append(num_deleted)
            class Visitor(cefweaver.CookieVisitor):
                def visit(self, cookie, count, total):
                    seen.append((cookie.name, cookie.value, cookie.domain, count, total))
                    return True, False                 # go on, do not delete
            start(RED)
            manager = cefweaver.CookieManager.get_global_manager(None)
            assert manager is not None
            import datetime
            now = datetime.datetime.now(datetime.timezone.utc)
            expires = now + datetime.timedelta(days=1)
            cookie = T.Cookie(name="session", value="abc", domain="cookie.test", path="/",
                              secure=0, httponly=1, has_expires=1, expires=expires,
                              creation=now, last_access=now,
                              same_site=T.CookieSameSite.UNSPECIFIED, priority=T.CookiePriority.MEDIUM)
            assert manager.set_cookie("http://cookie.test/", cookie, SetDone()) is True
            wait_until(app, lambda: set_results, "the cookie to be set")
            assert set_results == [True], set_results
            assert manager.visit_all_cookies(Visitor()) is True
            wait_until(app, lambda: seen, "the visit")
            assert ("session", "abc", ".cookie.test", 0, 1) in seen, seen   # a domain cookie
            del seen[:]
            assert manager.visit_url_cookies("http://cookie.test/", True, Visitor()) is True
            wait_until(app, lambda: seen, "the visit of the URL")
            assert seen[0][:2] == ("session", "abc"), seen
            assert manager.delete_cookies("http://cookie.test/", "session", DeleteDone()) is True
            wait_until(app, lambda: deleted, "the deletion")
            assert deleted == [1], deleted
            assert manager.flush_store(Done()) is True
            wait_until(app, lambda: flushed, "the flush")
            del seen[:]
            manager.visit_all_cookies(Visitor())
            for _ in range(100):
                app.do_message_loop_work(); time.sleep(0.005)
            assert not [c for c in seen if c[0] == "session"], seen   # it is gone
            app.shutdown()
            print("OK")
        """)

    def test_the_cookie_access_filter_sees_the_cookies_of_a_resource(self):
        self.run_osr_script("""
            saved, sent = [], []
            class Filter(cefweaver.CookieAccessFilter):
                def can_save_cookie(self, browser, frame, request, response, cookie):
                    saved.append((request.get_url(), cookie.name, cookie.value))
                    return True
                def can_send_cookie(self, browser, frame, request, cookie):
                    sent.append((request.get_url(), cookie.name))
                    return True
            class Resources(cefweaver.ResourceRequestHandler):
                def get_cookie_access_filter(self, browser, frame, request):
                    return Filter()
            class Requests(cefweaver.RequestHandler):
                def get_resource_request_handler(self, browser, frame, request, is_navigation,
                                                 is_download, request_initiator):
                    return Resources(), False
            handlers["request"] = Requests()
            start(RED)
            app.add_resource("http://cookie.test/set", "<p>set</p>",
                             headers={"Set-Cookie": "token=xyz; Path=/"})
            app.add_resource("http://cookie.test/next", "<p>next</p>")
            app.load_url("http://cookie.test/set")
            wait_until(app, lambda: saved, "the cookie to be saved")
            assert saved[0] == ("http://cookie.test/set", "token", "xyz"), saved
            app.load_url("http://cookie.test/next")
            wait_until(app, lambda: sent, "the cookie to be sent")
            assert ("http://cookie.test/next", "token") in sent, sent
            app.shutdown()
            print("OK")
        """)


    def test_a_request_context_has_preferences_and_can_be_created(self):
        self.run_osr_script("""
            start(RED)
            context = cefweaver.RequestContext.get_global_context()
            assert context is not None and context.is_global() is True
            assert context.is_same(cefweaver.RequestContext.get_global_context()) is True
            # preferences (the methods of CefPreferenceManager, which the context inherits)
            assert context.has_preference("intl.accept_languages") is True
            value = context.get_preference("intl.accept_languages")
            assert value.get_type() == types.ValueType.STRING, value.get_type()
            assert context.can_set_preference("intl.accept_languages") is True
            new = cefweaver.Value.create()
            new.set_string("ko,en")
            ok, error = context.set_preference("intl.accept_languages", new)
            assert ok is True and error == "", (ok, error)
            assert context.get_preference("intl.accept_languages").get_string() == "ko,en"
            everything = context.get_all_preferences(False)         # a dictionary of the set ones
            assert everything.get_size() > 0 and everything.has_key("intl"), everything.get_size()
            ok, error = context.set_preference("no.such.preference", new)
            assert ok is False and error, (ok, error)
            # a new context of its own, with a handler
            class Handler(cefweaver.RequestContextHandler):
                def get_resource_request_handler(self, browser, frame, request, is_navigation,
                                                is_download, request_initiator):
                    return None, False
            own = cefweaver.RequestContext.create_context(
                types.RequestContextSettings(persist_session_cookies=1), Handler())
            assert own is not None and own.is_global() is False
            assert own.is_same(context) is False
            app.shutdown()
            print("OK")
        """)


    def test_a_url_request_downloads_with_progress_and_credentials(self):
        self.run_osr_script(prelude=self.LOCAL_SERVER, body="""
            start(RED)
            def fetch(path, client):
                request = cefweaver.Request.create()
                request.set_url(BASE + path)
                request.set_method("GET")
                # without this flag a 401 is passed on as it is and the client is not asked
                request.set_flags(types.UrlrequestFlags.ALLOW_STORED_CREDENTIALS)
                return cefweaver.URLRequest.create(request, client, None)
            class Plain(cefweaver.URLRequestClient):
                def __init__(self):
                    self.data, self.done, self.progress = b"", [], []
                def on_request_complete(self, request):
                    self.done.append((request.get_request_status(), request.get_response().get_status()))
                def on_download_progress(self, request, current, total):
                    self.progress.append((current, total))
                def on_upload_progress(self, request, current, total):
                    pass
                def on_download_data(self, request, data):
                    self.data += bytes(data)
                def get_auth_credentials(self, is_proxy, host, port, realm, scheme, callback):
                    return False
            plain = Plain()
            handle = fetch("/hello", plain)
            assert handle is not None
            wait_until(app, lambda: plain.done, "the request")
            assert plain.data == b"hello world", plain.data
            assert plain.done == [(types.URLRequestStatus.SUCCESS, 200)], plain.done
            assert plain.progress and plain.progress[-1][0] == 11, plain.progress
            assert handle.get_request_status() == types.URLRequestStatus.SUCCESS
            assert handle.get_request_error() == types.ErrorCode.NONE
            # credentials: the client is asked and answers
            asked = []
            class Auth(Plain):
                def get_auth_credentials(self, is_proxy, host, port, realm, scheme, callback):
                    asked.append((is_proxy, host, realm, scheme))
                    callback.continue_("user", "pass")
                    return True
            auth = Auth()
            fetch("/auth", auth)
            wait_until(app, lambda: auth.done, "the request with credentials")
            assert auth.data == b"welcome user" and auth.done[0][1] == 200, (auth.data, auth.done)
            assert asked and asked[0][0] is False and asked[0][2] == "test", asked
            # a request can be canceled
            late = Plain()
            fetch("/hello", late).cancel()
            wait_until(app, lambda: late.done, "the canceled request")
            assert late.done[0][0] in (types.URLRequestStatus.CANCELED, types.URLRequestStatus.SUCCESS)
            app.shutdown()
            print("OK")
        """)

    def test_a_browser_asks_for_credentials_and_reports_redirects_and_responses(self):
        self.run_osr_script(prelude=self.LOCAL_SERVER, body="""
            texts, redirects, responses, asked = [], [], [], []
            class Text(cefweaver.StringVisitor):
                def visit(self, string):
                    texts.append(string)
            class Resources(cefweaver.ResourceRequestHandler):
                def on_resource_redirect(self, browser, frame, request, response, new_url):
                    redirects.append((response.get_status(), new_url))
                    return new_url                                # unchanged
                def on_resource_response(self, browser, frame, request, response):
                    responses.append((request.get_url().rsplit("/", 1)[1], response.get_status()))
                    return False
            class Requests(cefweaver.RequestHandler):
                def get_resource_request_handler(self, browser, frame, request, is_navigation,
                                                 is_download, request_initiator):
                    return Resources(), False
                def get_auth_credentials(self, browser, origin_url, is_proxy, host, port, realm,
                                         scheme, callback):
                    asked.append((origin_url, is_proxy, realm, scheme))
                    callback.continue_("user", "pass")
                    return True
            handlers["request"] = Requests()
            start(RED)
            app.load_url(BASE + "/auth")
            wait_until(app, lambda: ("auth", 200) in responses, "the authenticated page")
            # the main frame can be a new object after a navigation: ask for it each time
            send_until(app, lambda: boxes[0].get_main_frame().get_text(Text()),
                       lambda: any(t.strip() == "welcome user" for t in texts), "the text")
            assert asked and asked[0][2] == "test" and asked[0][1] is False, asked
            assert ("auth", 401) in responses, responses
            app.load_url(BASE + "/redirect")
            wait_until(app, lambda: ("hello", 200) in responses, "the redirected page")
            assert redirects and redirects[0][0] == 302 and redirects[0][1].endswith("/hello"), redirects
            app.shutdown()
            print("OK")
        """)


    def test_the_app_handler_hooks_the_command_line_the_schemes_and_the_context(self):
        self.run_osr_script("""
            log, seen = [], []
            class Hooks(cefweaver.AppHandler):
                def on_before_command_line_processing(self, process_type, command_line):
                    log.append(("command line", process_type))
                    command_line.append_switch_with_value("cefweaver-hook", "yes")
                def on_register_custom_schemes(self, registrar):
                    log.append(("schemes", type(registrar).__name__))
                    options = types.SchemeOptions.STANDARD | types.SchemeOptions.SECURE
                    assert registrar.add_custom_scheme("myapp", options) is True
                def on_context_initialized(self):
                    log.append(("context",))
            app.set_app_handler(Hooks())
            class Page(cefweaver.ResourceHandler):
                body = b"<script>report('scheme', location.protocol, location.host)</script>"
                def open(self, request, callback):
                    return True, True
                def get_response_headers(self, response):
                    response.set_mime_type("text/html")
                    response.set_status(200)
                    return len(self.body), ""
                def read(self, data_out, callback):
                    data_out[:len(self.body)] = self.body
                    return True, len(self.body)
                def cancel(self):
                    pass
            class Factory(cefweaver.SchemeHandlerFactory):
                def create(self, browser, frame, scheme_name, request):
                    return Page()
            start(RED)
            assert [entry[0] for entry in log][:3] == ["command line", "schemes", "context"], log
            assert log[0] == ("command line", ""), log          # the browser process only
            assert log[1] == ("schemes", "SchemeRegistrar"), log
            line = cefweaver.CommandLine.get_global_command_line()
            assert line.get_switch_value("cefweaver-hook") == "yes", line.get_switches()
            # the scheme is standard in the renderer too: it has a host
            assert cefweaver.register_scheme_handler_factory("myapp", "test", Factory())
            app.load_url("myapp://test/page")
            wait_until(app, lambda: any(r[0] == "scheme" for r in js), "the page of the scheme")
            assert ("scheme", "myapp:", "test") in js, js
            app.shutdown()
            print("OK")
        """)


    def test_a_second_start_of_the_application_reaches_the_first_one(self):
        self.run_osr_script("""
            import os, subprocess, sys, tempfile
            cache = tempfile.mkdtemp()
            app.set_cache_path(cache)
            relaunched = []
            class Hooks(cefweaver.AppHandler):
                def on_already_running_app_relaunch(self, command_line, current_directory):
                    relaunched.append((command_line.get_switch_value("cefweaver-second"),
                                       current_directory))
                    return True                       # handled: no new window
            app.set_app_handler(Hooks())
            start(RED)
            second = (
                "import cefweaver\\n"
                "app = cefweaver.CefApp()\\n"
                "app.set_cache_path(%r)\\n"
                "app.add_command_line_switch('cefweaver-second', 'yes')\\n"
                "try:\\n"
                "    app.initialize('about:blank')\\n"
                "    print('SECOND RAN')\\n"
                "except RuntimeError as error:\\n"
                "    print('SECOND REFUSED')\\n" % cache)
            process = subprocess.Popen([sys.executable, "-I", "-c", second], cwd=cache,
                                       stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
            wait_until(app, lambda: relaunched, "the second start")
            assert relaunched[0][0] == "yes", relaunched
            assert os.path.realpath(relaunched[0][1]) == os.path.realpath(cache), relaunched
            process.wait(timeout=30)
            app.shutdown()
            print("OK")
        """)


    def test_dropping_drag_data_on_an_offscreen_page(self):
        self.run_osr_script("""
            entered = []
            class Drags(cefweaver.DragHandler):
                def on_drag_enter(self, browser, drag_data, mask):
                    entered.append((drag_data.get_fragment_text(), mask))
                    return False                          # let the page have it
            handlers["drag"] = Drags()
            start('<div style="position:fixed;left:0;top:0;width:200px;height:100px" '
                  'ondragover="event.preventDefault()" '
                  'ondrop="event.preventDefault(); report(\\'dropped\\', event.dataTransfer.getData(\\'text/plain\\'))">'
                  'drop here</div>')
            host = boxes[0].get_host()
            data = cefweaver.DragData.create()
            data.set_fragment_text("payload")
            copy = types.DragOperationsMask.COPY
            def drop():
                host.drag_target_drag_enter(data, (50, 50, 0), copy)
                host.drag_target_drag_over((60, 60, 0), copy)
                host.drag_target_drop((60, 60, 0))
            send_until(app, drop, lambda: ("dropped", "payload") in js, "the drop")
            assert entered and entered[0][0] == "payload" and entered[0][1] & copy, entered
            app.shutdown()
            print("OK")
        """)

    def test_starting_a_drag_from_an_offscreen_page(self):
        self.run_osr_script("""
            drag_return[0] = True                        # the host takes over the drag
            start('<div draggable="true" style="position:fixed;left:0;top:0;width:200px;height:100px"'
                  ' ondragstart="event.dataTransfer.setData(\\'text/plain\\', \\'carried\\')">drag me</div>')
            host = boxes[0].get_host()
            LEFT = 16                                    # EVENTFLAG_LEFT_MOUSE_BUTTON
            def pull():
                host.send_mouse_click_event((20, 20, 0), types.MouseButtonType.LEFT, False, 1)
                for x in (30, 50, 80, 120):
                    host.send_mouse_move_event((x, 30, LEFT), False)
            send_until(app, pull, lambda: dragged, "the drag")
            assert dragged[0][0] == "carried" and dragged[0][1] is True, dragged
            assert dragged[0][2] != 0, dragged            # the operations the page allows
            host.drag_source_ended_at(120, 30, types.DragOperationsMask.NONE)
            host.drag_source_system_drag_ended()
            app.shutdown()
            print("OK")
        """)


    def test_pending_queries_can_be_canceled_from_the_host(self):
        self.run_query_script("""
            pending, canceled = {}, []
            class Handler(cefweaver.QueryHandler):
                def on_query(self, browser, frame, query_id, request, persistent, callback):
                    pending[request] = (query_id, callback)
                    return True
                def on_query_canceled(self, browser, frame, query_id):
                    canceled.append(query_id)
            handler, other = Handler(), Handler()
            app.add_query_handler(handler)
            start()
            app.execute_javascript("ask('one', true); ask('two', true)")
            wait_until(app, lambda: len(pending) == 2, "two queries")
            assert app.cancel_pending_queries(None, other) is None     # not its queries: nothing
            for _ in range(50):
                app.do_message_loop_work(); time.sleep(0.005)
            assert canceled == [], canceled
            app.cancel_pending_queries(boxes[0], None)                 # all of one browser
            wait_until(app, lambda: len(canceled) == 2, "both cancellations")
            assert sorted(canceled) == sorted(q for q, _ in pending.values()), canceled
            wait_until(app, lambda: {r[1] for r in js if r[0] == "fail" and r[2] == -1} == {"one", "two"},
                       "the failures of the page")             # onFailure(-1, message)
            assert pending["one"][1].success("late") is False
            app.shutdown()
            print("OK")
        """)


    # -- the message pump of an application with an event loop of its own -------------------

    def test_cef_asks_for_message_loop_work_from_any_thread_when_the_application_asks_for_it(self):
        self.run_osr_script("""
            import threading
            main_thread = threading.get_ident()
            calls = []
            class Hooks(cefweaver.AppHandler):
                def on_schedule_message_pump_work(self, delay_ms):      # from any thread of CEF
                    assert type(delay_ms) is int
                    calls.append((delay_ms, threading.get_ident()))
            app.set_app_handler(Hooks())
            app.settings.external_message_pump = True
            start(RED)                                       # polling, as before
            wait_until(app, lambda: len(calls) > 5 and any(t != main_thread for _, t in calls),
                       "work scheduled from another thread")
            app.shutdown()
            print("OK")
        """)

    def test_a_message_pump_runs_cef_by_the_deadlines_cef_gives_and_never_waits_long(self):
        self.run_osr_script("""
            import threading
            woken = threading.Event()
            pump = cefweaver.MessagePump(app, wake=lambda delay: woken.set())
            app.offscreen = True
            app.set_client(MyClient())
            app.initialize(page(RED + '<script>report("loaded", 1)</script>'))
            runs, longest = 0, 0.0
            end = time.time() + 30
            while ("loaded", 1) not in js:                   # no polling: the deadlines only
                assert time.time() < end, "the page never loaded"
                wait = pump.timeout()
                longest = max(longest, wait)
                if wait > 0:
                    woken.wait(wait)                         # a toolkit would sleep in its event loop
                    woken.clear()
                if pump.run():
                    runs += 1
            assert runs > 0
            assert longest <= 1 / 30 + 0.005, longest        # the fall-back timer of cefclient: 30 fps
            app.shutdown()
            print("OK")
        """)

    def test_cef_does_not_schedule_work_unless_the_application_asks_for_it(self):
        self.run_osr_script("""
            calls = []
            class Hooks(cefweaver.AppHandler):
                def on_schedule_message_pump_work(self, delay_ms):
                    calls.append(delay_ms)
            app.set_app_handler(Hooks())
            start(RED)                                       # polling, as before
            for _ in range(100):
                app.do_message_loop_work(); time.sleep(0.005)
            assert calls == [], calls
            app.shutdown()
            print("OK")
        """)

    # -- the settings of a browser (CefBrowserSettings) ------------------------------------

    NOSCRIPT_PAGE = """
        NOSCRIPT = ('<style>html, body { margin: 0; background: rgb(255, 0, 0); }</style>'
                    '<noscript><style>body { background: rgb(0, 255, 0) !important; }</style></noscript>')
    """

    def test_a_browser_with_javascript_disabled_shows_its_noscript_content(self):
        self.run_osr_script(prelude=self.NOSCRIPT_PAGE, body="""
            State = types.State
            app.browser_settings = types.BrowserSettings(javascript=State.DISABLED)
            start(NOSCRIPT)
            wait_until(app, lambda: paints and paints[-1]["first"] == bytes([0, 255, 0, 255]), "green: no script")
            app.shutdown()
            print("OK")
        """)

    def test_each_browser_can_have_settings_of_its_own(self):
        self.run_osr_script(prelude=self.NOSCRIPT_PAGE, body="""
            State = types.State
            start(NOSCRIPT)                                   # JavaScript on: red
            wait_until(app, lambda: paints[-1]["first"] == bytes([0, 0, 255, 255]), "red")
            quiet = app.create_browser(page(NOSCRIPT), settings=types.BrowserSettings(javascript=State.DISABLED))
            loud = app.create_browser(page(NOSCRIPT))         # the settings of the app: JavaScript on
            def first(browser):
                return {p["first"] for p in paints if p["browser"] == browser.get_identifier()}
            wait_until(app, lambda: bytes([0, 255, 0, 255]) in first(quiet) and bytes([0, 0, 255, 255]) in first(loud),
                       "green for the quiet one and red for the loud one")
            assert bytes([0, 0, 255, 255]) not in first(quiet), first(quiet)
            assert bytes([0, 255, 0, 255]) not in first(loud), first(loud)
            app.shutdown()
            print("OK")
        """)

    IMAGE_PAGE = """
        SVG = ("<svg xmlns='http://www.w3.org/2000/svg' width='200' height='100'>"
               "<rect width='200' height='100' fill='red'/></svg>")
        IMG = ('<style>html, body { margin: 0; background: white; }</style>'
               '<img style="position: fixed; left: 0; top: 0; width: 200px; height: 100px"'
               ' src="http://img.test/red.svg">'
               '<script>try { localStorage.setItem("a", "1"); report("storage", "works"); }'
               'catch (e) { report("storage", "blocked"); }</script>')
        def show(settings):
            if settings is not None:
                app.browser_settings = settings
            probe[0] = lambda b, g, r: r > 200 and g < 60 and b < 60
            app.offscreen = True
            app.set_client(MyClient())
            app.initialize("about:blank")
            wait_until(app, lambda: boxes and app.is_ready_to_execute_javascript, "the browser")
            app.add_resource("http://img.test/red.svg", SVG, mime_type="image/svg+xml")
            app.add_resource("http://img.test/", "<html><body>" + IMG + "</body></html>")
            app.load_url("http://img.test/")
            wait_until(app, lambda: any(r[0] == "storage" for r in js), "the script")
            for _ in range(80):
                app.do_message_loop_work(); time.sleep(0.01)
            return max(p["found"] for p in paints)
    """

    def test_images_and_local_storage_can_be_turned_off(self):
        self.run_osr_script(prelude=self.IMAGE_PAGE, body="""
            State = types.State
            drawn = show(types.BrowserSettings(image_loading=State.DISABLED, local_storage=State.DISABLED))
            assert ("storage", "blocked") in js, js
            assert drawn == 0, "the image was drawn"
            app.shutdown()
            print("OK")
        """)
        # the control: the defaults draw the image
        self.run_osr_script(prelude=self.IMAGE_PAGE, body="""
            drawn = show(None)
            assert ("storage", "works") in js, js
            assert drawn > 1000, drawn
            app.shutdown()
            print("OK")
        """)

    FONT_PAGE = """
        def later(settings, script):
            # the value of `script` in a page made with `settings`, read 700 ms after the page began
            app.offscreen = True
            app.set_client(MyClient())
            app.initialize("about:blank")
            wait_until(app, lambda: boxes and app.is_ready_to_execute_javascript, "the browser")
            app.add_resource("http://fonts.test/", '<p id="p" style="font-size: medium">text</p>'
                             '<script>setTimeout(function () { var c = getComputedStyle(document.getElementById("p")); '
                             'report("page", %s); }, 700)</script>' % script)
            app.create_browser("http://fonts.test/", settings=settings)
            wait_until(app, lambda: any(r[0] == "page" for r in js), "the page")
            return [r for r in js if r[0] == "page"][0][1]
    """

    def test_the_font_family_of_the_browser_settings_stays(self):
        self.run_osr_script(prelude=self.FONT_PAGE, body="""
            found = later(types.BrowserSettings(standard_font_family="Courier New"), "c.fontFamily")
            assert "Courier New" in found, found
            app.shutdown()
            print("OK")
        """)

    @unittest.expectedFailure
    def test_known_cef_issue_the_integer_font_sizes_of_the_browser_settings_do_not_last(self):
        # They show in the first layout and are the profile's again within 100 ms (F64). When CEF
        # keeps them this test starts to succeed: then the note in known-constraints.md goes.
        self.run_osr_script(prelude=self.FONT_PAGE, body="""
            found = later(types.BrowserSettings(default_font_size=30), "c.fontSize")
            assert found == "30px", found
            app.shutdown()
            print("OK")
        """)

    @unittest.expectedFailure
    def test_known_cef_issue_the_default_encoding_of_the_browser_settings_is_not_used(self):
        self.run_osr_script("""
            app.offscreen = True
            app.browser_settings = types.BrowserSettings(default_encoding="euc-kr")
            app.set_client(MyClient())
            app.initialize("about:blank")
            wait_until(app, lambda: boxes and app.is_ready_to_execute_javascript, "the browser")
            app.add_resource("http://encoding.test/", '<script>report("page", document.characterSet)</script>')
            app.load_url("http://encoding.test/")                       # no charset is given
            wait_until(app, lambda: any(r[0] == "page" for r in js), "the page")
            found = [r for r in js if r[0] == "page"][0][1]
            assert found.lower() == "euc-kr", found
            app.shutdown()
            print("OK")
        """)

    def test_the_background_color_of_the_browser_settings_wins_for_an_opaque_browser(self):
        self.run_osr_script("""
            app.transparent = False
            app.settings.background_color = 0xFF00FF00         # the app says green
            app.browser_settings = types.BrowserSettings(background_color=0xFF0000FF)   # this one blue
            start("")
            wait_until(app, lambda: paints and paints[-1]["first"] == bytes([255, 0, 0, 255]), "blue (BGRA)")
            app.shutdown()
            print("OK")
        """)

    def test_create_browser_checks_the_settings(self):
        self.run_osr_script("""
            start(RED)
            for bad in (3, {"javascript": 2}, (1, 2)):
                try:
                    app.create_browser("about:blank", settings=bad)
                except TypeError:
                    continue
                raise AssertionError("accepted %r" % (bad,))
            assert len(boxes) == 1
            app.shutdown()
            print("OK")
        """)

    def test_the_app_can_be_used_from_on_after_created_of_the_first_browser(self):
        # The first browser is made inside initialize(): its on_after_created() runs before
        # initialize() has returned, and that is where an application wants to add resources
        # and load its page.
        self.run_osr_script("""
            problems, created = [], []
            class Early(cefweaver.LifeSpanHandler):
                def on_after_created(self, browser):
                    boxes.append(browser)
                    try:
                        app.add_resource("http://early.test/", '<script>report("early", 1)</script>')
                        assert app.load_url("http://early.test/") is True
                        app.execute_javascript("1")
                        created.append(True)
                    except BaseException as error:
                        problems.append(repr(error))
            MyClient.__init__ = lambda self: setattr(self, "render", Render()) or setattr(self, "life", Early())
            app.offscreen = True
            app.set_client(MyClient())
            app.initialize("about:blank")
            assert not problems, problems
            assert created == [True], created
            wait_until(app, lambda: ("early", 1) in js, "the page that was added and loaded from on_after_created")
            app.shutdown()
            print("OK")
        """)

    # -- JSON calls between JavaScript and Python (cefpython's JavascriptBindings) --------------

    BRIDGE_PAGE = """
        def page_with(script):
            return ('<script>function show(name) { return function (v) { report(name, JSON.stringify(v)); }; }'
                    'function fail(name) { return function (e) { report(name, "error: " + e.message); }; }'
                    + script + '</script>')
    """

    def test_python_functions_are_called_from_a_page_with_json_values_and_return_promises(self):
        self.run_osr_script(prelude=self.BRIDGE_PAGE, body="""
            bridge = cefweaver.JavascriptBridge(app)
            seen = []
            bridge.expose("add", lambda a, b: a + b)
            bridge.expose("describe", lambda value: seen.append(value) or {"got": value, "kinds": [None, True, 1.5, "s"]})
            bridge.expose("nothing", lambda: None)
            bridge.expose("boom", lambda: 1 / 0)
            bridge.expose("opaque", lambda: object())
            bridge.expose("loud", lambda text: text.upper())
            start(page_with('''
                add(1, 2).then(show("add"));
                describe({a: [1, {b: null}], c: "x", d: true}).then(show("describe"));
                nothing().then(show("nothing"));
                boom().catch(fail("boom"));
                opaque().catch(fail("opaque"));
                loud("hi").then(show("loud"));
                add(0.1, 0.2).then(show("float"));
                add("a", "b").then(show("strings"));
                Promise.all([add(1, 1), add(2, 2)]).then(show("all"));
            '''))
            def got(name):
                return [r[1] for r in js if r[0] == name]
            wait_until(app, lambda: all(got(n) for n in ("add", "describe", "nothing", "boom", "opaque",
                                                         "loud", "float", "strings", "all")), "every answer")
            assert got("add") == ["3"], js
            assert got("describe") == ['{"got":{"a":[1,{"b":null}],"c":"x","d":true},"kinds":[null,true,1.5,"s"]}'], got("describe")
            assert seen == [{"a": [1, {"b": None}], "c": "x", "d": True}], seen
            assert got("nothing") == ["null"], got("nothing")
            assert got("boom")[0].startswith("error: ") and "ZeroDivisionError" in got("boom")[0], got("boom")
            assert got("opaque")[0].startswith("error: ") and "TypeError" in got("opaque")[0], got("opaque")
            assert got("loud") == ['"HI"'], got("loud")
            assert got("float") == ["0.30000000000000004"] and got("strings") == ['"ab"'], (got("float"), got("strings"))
            assert got("all") == ["[2,4]"], got("all")
            app.shutdown()
            print("OK")
        """)

    def test_a_function_of_the_page_given_to_python_can_be_called_back(self):
        self.run_osr_script(prelude=self.BRIDGE_PAGE, body="""
            bridge = cefweaver.JavascriptBridge(app)
            held = []
            def subscribe(callback, label):
                assert isinstance(callback, cefweaver.JsCallback)
                held.append(callback)
                callback.call("first", {"n": 1})              # from inside the call: the page gets it too
                return "subscribed " + label
            bridge.expose("subscribe", subscribe)
            start(page_with('''
                subscribe(function (a, b) { report("callback", JSON.stringify([a, b])); }, "x").then(show("answer"));
            '''))
            wait_until(app, lambda: held and any(r[0] == "answer" for r in js), "the subscription")
            wait_until(app, lambda: ("callback", '["first",{"n":1}]') in js, "the first call back")
            held[0].call("later", [1, 2])                     # any time after, with several kinds of value
            wait_until(app, lambda: ("callback", '["later",[1,2]]') in js, "the later call back")
            held[0].release()                                 # the page forgets the function
            del js[:]
            held[0].call("after the release")
            for _ in range(50):
                app.do_message_loop_work(); time.sleep(0.01)
            assert not any(r[0] == "callback" for r in js), js
            app.shutdown()
            print("OK")
        """)

    def test_python_calls_a_function_of_the_page_and_evaluates_expressions(self):
        self.run_osr_script(prelude=self.BRIDGE_PAGE, body="""
            bridge = cefweaver.JavascriptBridge(app)
            bridge.expose("ready", lambda: True)
            start(page_with('''
                window.double = function (x) { report("double called", JSON.stringify(x)); return x * 2; };
                window.api = {greet: function (name, extra) { report("greet", name + JSON.stringify(extra)); }};
                window.later = function () { return new Promise(function (r) { setTimeout(function () { r({done: [1, 2]}); }, 100); }); };
                ready();
            '''))
            wait_until(app, lambda: boxes, "the browser")
            frame = boxes[0].get_main_frame()
            bridge.execute_function(frame, "api.greet", "Ada", {"k": [1, None]})   # no answer wanted
            wait_until(app, lambda: ("greet", 'Ada{"k":[1,null]}') in js, "greet")
            results = []
            bridge.evaluate(frame, "double(21)", lambda value, error: results.append(("double", value, error)))
            bridge.evaluate(frame, "later()", lambda value, error: results.append(("later", value, error)))
            bridge.evaluate(frame, "1 +", lambda value, error: results.append(("syntax", value, error)))
            bridge.evaluate(frame, "undefined", lambda value, error: results.append(("undefined", value, error)))
            bridge.evaluate(frame, "({a: [1, 2], b: 'x'})", lambda value, error: results.append(("object", value, error)))
            wait_until(app, lambda: len(results) == 5, "five results")
            by_name = {r[0]: r for r in results}
            assert by_name["double"] == ("double", 42, None), by_name
            assert by_name["later"] == ("later", {"done": [1, 2]}, None), by_name       # a promise is awaited
            assert by_name["syntax"][1] is None and "SyntaxError" in by_name["syntax"][2], by_name
            assert by_name["undefined"] == ("undefined", None, None), by_name
            assert by_name["object"] == ("object", {"a": [1, 2], "b": "x"}, None), by_name
            app.shutdown()
            print("OK")
        """)

    def test_a_bridge_answers_only_the_origins_it_was_given_and_leaves_other_queries_alone(self):
        self.run_osr_script(prelude=self.BRIDGE_PAGE, body="""
            bridge = cefweaver.JavascriptBridge(app, origins=["http://allowed.test/"])
            frames = []
            bridge.expose("whoami", lambda frame, tag: frames.append((frame.is_main(), frame.get_url(), tag)) or "ok",
                          with_frame=True)
            plain = []
            class Mine(cefweaver.QueryHandler):                 # the application's own queries still work
                def on_query(self, browser, frame, query_id, request, persistent, callback):
                    plain.append(request)
                    callback.success("mine:" + request)
                    return True
            app.add_query_handler(Mine())
            start("")
            PAGE = page_with('''
                whoami("a").then(show("whoami"), fail("whoami"));
                window.cefQuery({request: "plain", onSuccess: show("plain"), onFailure: fail("plain")});
            ''')
            app.add_resource("http://allowed.test/", PAGE)
            app.add_resource("http://denied.test/", PAGE)
            app.load_url("http://allowed.test/")
            wait_until(app, lambda: any(r[0] == "whoami" for r in js) and any(r[0] == "plain" for r in js), "allowed")
            assert ("whoami", '"ok"') in js and ("plain", '"mine:plain"') in js, js
            assert frames == [(True, "http://allowed.test/", "a")], frames
            del js[:]
            app.load_url("http://denied.test/")
            wait_until(app, lambda: any(r[0] == "whoami" for r in js) and any(r[0] == "plain" for r in js), "denied")
            denied = [r[1] for r in js if r[0] == "whoami"][0]
            assert denied.startswith("error: ") and "origin" in denied, denied
            assert ("plain", '"mine:plain"') in js and len(frames) == 1, (js, frames)
            app.shutdown()
            print("OK")
        """)

    def test_the_bridge_works_in_an_iframe_and_in_every_browser(self):
        self.run_osr_script(prelude=self.BRIDGE_PAGE, body="""
            bridge = cefweaver.JavascriptBridge(app)
            who = []
            bridge.expose("who", lambda frame, label: who.append((label, frame.is_main())) or label, with_frame=True)
            start("")
            CHILD = page_with('who("child").then(show("child"))')
            MAIN = page_with('who("main").then(show("main"))') + '<iframe src="http://one.test/child"></iframe>'
            app.add_resource("http://one.test/", MAIN)
            app.add_resource("http://one.test/child", CHILD)
            app.load_url("http://one.test/")
            wait_until(app, lambda: ("main", '"main"') in js and ("child", '"child"') in js, "main and iframe")
            assert ("main", True) in who and ("child", False) in who, who
            second = app.create_browser(page(page_with('who("second").then(show("second"))')))
            wait_until(app, lambda: ("second", '"second"') in js, "the second browser")
            assert ("second", True) in who, who
            app.shutdown()
            print("OK")
        """)

    def test_the_bridge_works_in_a_frame_of_another_site_with_a_renderer_of_its_own(self):
        self.run_osr_script(prelude=self.BRIDGE_PAGE + """
        import http.server, threading
        def serve(pages):
            class PageHandler(http.server.BaseHTTPRequestHandler):
                def log_message(self, *args):
                    pass
                def do_GET(self):
                    body = pages.get(self.path, "").encode()
                    self.send_response(200 if self.path in pages else 404)
                    self.send_header("Content-Type", "text/html")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
            server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), PageHandler)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            return server.server_address[1]
        """, body="""
            bridge = cefweaver.JavascriptBridge(app)
            who = []
            bridge.expose("who", lambda frame, label: who.append((label, frame.is_main(), frame.get_url())) or label,
                          with_frame=True)
            callbacks = []
            bridge.expose("hand", lambda callback: callbacks.append(callback) or True)
            child_port = serve({"/child": page_with('who("child").then(show("child")); hand(function (v) { report("called", v); });')})
            child_url = "http://localhost:%d/child" % child_port          # another site than 127.0.0.1
            main_port = serve({"/main": page_with('who("main").then(show("main"))') + '<iframe src="%s"></iframe>' % child_url})
            start("")
            app.load_url("http://127.0.0.1:%d/main" % main_port)
            wait_until(app, lambda: ("main", '"main"') in js and ("child", '"child"') in js and callbacks, "both frames")
            assert ("child", False, child_url) in who, who
            callbacks[0].call("from python")                           # into the frame of the other renderer
            wait_until(app, lambda: ("called", "from python") in js, "the callback of the other frame")
            app.shutdown()
            print("OK")
        """)

    # -- GPU accelerated painting (shared textures) -------------------------------------------

    DMABUF_SCRIPT = """
        import os
        T = cefweaver.types
        frames = []                                           # what on_accelerated_paint got
        pixel_paints = []                                     # on_paint() calls: none with shared textures
        class Shared(cefweaver.RenderHandler):
            def get_view_rect(self, browser):
                return cefweaver.Rect(0, 0, 200, 100)
            def get_screen_info(self, browser):
                return False, cefweaver.ScreenInfo(1.0, 24, 8, 0, cefweaver.Rect(0, 0, 0, 0), cefweaver.Rect(0, 0, 0, 0))
            def on_paint(self, browser, type, dirty_rects, buffer, width, height):
                pixel_paints.append(type)
            def on_accelerated_paint(self, browser, type, dirty_rects, info):
                inside = []
                for plane in info.planes:
                    try:
                        inside.append((plane.fd, os.fstat(plane.fd).st_mode, plane.stride, plane.offset, plane.size))
                    except OSError as error:
                        inside.append((plane.fd, error))
                pixels = None
                if info.planes and info.modifier == 0:
                    try:
                        pixels = cefweaver.read_plane(info.planes[0])
                    except OSError as error:
                        pixels = None
                frames.append(dict(type=type, rects=list(dirty_rects), info=info, inside=inside, pixels=pixels,
                                   browser=browser.get_identifier()))
        class Client2(cefweaver.Client):
            def __init__(self):
                self.render, self.life = Shared(), Life()
            def get_render_handler(self):
                return self.render
            def get_life_span_handler(self):
                return self.life
        app.offscreen = True
        app.shared_texture = True
    """

    # The GPU: a shared texture needs a display server with DRI3 and a GPU whose driver exports
    # dmabufs to ANGLE. Xvfb has none (CEF says "gbm device is missing" and draws with on_paint
    # instead), so these two run only with CEFWEAVER_TEST_GPU=1 on a real display (DISPLAY=:0,
    # XWayland; no window is opened). On the proprietary NVIDIA driver ANGLE has to use Vulkan;
    # CEFWEAVER_TEST_GPU_SWITCHES replaces the switches ("name=value;name=value").
    GPU_SWITCHES = ("ignore-gpu-blocklist;use-gl=angle;use-angle=vulkan;"
                    "enable-features=Vulkan,VulkanFromANGLE,DefaultANGLEVulkan")

    def run_gpu_script(self, body):
        import textwrap
        text = os.environ.get("CEFWEAVER_TEST_GPU_SWITCHES", self.GPU_SWITCHES)
        switches = [tuple(item.split("=", 1)) if "=" in item else (item, "") for item in text.split(";")]
        reader = open(os.path.join(os.path.dirname(__file__), "egl_dmabuf.py"), encoding="utf-8").read()
        head = "SWITCHES = %r\nREADER = %r\n" % (switches, reader)
        result = run_cef(head + textwrap.dedent(self.OSR_SCRIPT) + textwrap.dedent(self.DMABUF_SCRIPT)
                         + textwrap.dedent(body), timeout=120, without=("WAYLAND_DISPLAY", "XDG_SESSION_TYPE"))
        self.assertClean(result)
        self.assertIn("OK", result.stdout)

    @unittest.skipUnless(os.environ.get("CEFWEAVER_TEST_GPU") == "1",
                         "needs a GPU and a real display: CEFWEAVER_TEST_GPU=1")
    def test_a_shared_texture_arrives_as_dmabuf_planes_in_place_of_pixels(self):
        self.run_gpu_script("""
            for name, value in SWITCHES:
                app.add_command_line_switch(name, value)
            app.set_client(Client2())
            app.initialize(page(RED))
            wait_until(app, lambda: frames, "a shared texture", timeout=45)
            for _ in range(50):
                app.do_message_loop_work(); time.sleep(0.01)
            frame = frames[-1]
            info = frame["info"]
            assert isinstance(info, T.AcceleratedPaintInfo), info
            assert frame["type"] == T.PaintElementType.VIEW, frame["type"]
            assert len(info.planes) >= 1 and info.planes[0].stride >= 200 * 4 and info.planes[0].size > 0, info
            assert info.planes[0].fd >= 0 and isinstance(info.format, T.ColorType), info
            assert info.extra.coded_size.width >= 200 and info.extra.coded_size.height >= 100, info.extra
            assert frame["inside"] and all(len(x) == 5 for x in frame["inside"]), frame["inside"]   # open in the call
            assert frame["rects"], frame                                    # the dirty rectangles come as well
            assert not pixel_paints, "on_paint was called as well"
            # new frames come with changes of the page
            before = len(frames)
            app.execute_javascript("document.body.style.background = 'rgb(0, 255, 0)'")
            wait_until(app, lambda: len(frames) > before, "a frame after the change")
            app.shutdown()
            print("OK")
        """)

    @unittest.skipUnless(os.environ.get("CEFWEAVER_TEST_GPU_PIXELS") == "1",
                         "needs a GPU whose shared textures hold the picture: CEFWEAVER_TEST_GPU_PIXELS=1")
    def test_the_pixels_of_a_shared_texture_are_those_of_the_page(self):
        # Not run by default: on the NVIDIA laptop this was written on, the textures read as all
        # zero both by mmap and by EGL, also long after the call (F66, cause not found).
        self.run_gpu_script("""
            for name, value in SWITCHES:
                app.add_command_line_switch(name, value)
            exec(READER, globals())
            reader = []
            seen = []
            class Reading(Shared):
                def on_accelerated_paint(self, browser, type, dirty_rects, info):
                    if not reader:
                        reader.append(Reader())
                    plane = info.planes[0]
                    seen.append((info.modifier, cefweaver.read_plane(plane) if info.modifier == 0 else None,
                                 reader[0].read(plane, info.modifier, 200, 100)))
            Shared.on_accelerated_paint = Reading.on_accelerated_paint
            app.set_client(Client2())
            app.initialize(page(RED))
            wait_until(app, lambda: seen, "a texture")
            for _ in range(50):
                app.do_message_loop_work(); time.sleep(0.01)
            modifier, mapped, drawn = seen[-1]
            stride = 1024
            if mapped is not None:                                # BGRA through the mapping
                assert mapped[100 * 4 + 50 * stride: 100 * 4 + 50 * stride + 4] == b"\\x00\\x00\\xff\\xff", mapped[:8]
            middle = (50 * 200 + 100) * 4
            assert drawn[middle: middle + 4] == b"\\xff\\x00\\x00\\xff", drawn[middle: middle + 4]    # RGBA through EGL
            app.shutdown()
            print("OK")
        """)

    def test_a_shared_texture_browser_gets_a_frame_one_way_or_the_other(self):
        # With a GPU it is a shared texture. Without one (Xvfb) CEF draws with on_paint instead and
        # the browser works: the application has to handle both.
        self.run_osr_script(prelude=self.DMABUF_SCRIPT, body="""
            app.set_client(Client2())
            app.initialize(page(RED))
            assert app.shared_texture is True
            wait_until(app, lambda: frames or pixel_paints, "a frame, as a texture or as pixels")
            for _ in range(50):
                app.do_message_loop_work(); time.sleep(0.01)
            assert not (frames and pixel_paints), (len(frames), len(pixel_paints))   # one way
            app.shutdown()
            print("OK")
        """)


    # -- the handlers that were generated and not yet run -----------------------------------

    def test_a_killed_renderer_reaches_the_request_handler_and_cancels_the_queries(self):
        self.run_query_script("""
            import os, signal
            terminated, canceled, pending = [], [], {}
            class Requests(cefweaver.RequestHandler):
                def on_render_process_terminated(self, browser, status, error_code, error_string):
                    terminated.append((status, error_code))
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
            app.execute_javascript("ask('stay', true)")
            wait_until(app, lambda: pending, "the query")
            program = os.path.join(os.path.dirname(cefweaver.__file__), "cefsubprocess")
            def renderers():
                found = []
                for name in os.listdir("/proc"):
                    if name.isdigit():
                        try:
                            command = open("/proc/%s/cmdline" % name, "rb").read()
                        except OSError:
                            continue
                        # (Chromium rewrites the title of its child processes: one string)
                        if program.encode() in command and b"--type=renderer" in command:
                            found.append(int(name))
                return found
            assert renderers(), "no renderer process"
            for pid in renderers():
                os.kill(pid, signal.SIGKILL)
            wait_until(app, lambda: terminated and canceled, "the end of the renderer")
            assert terminated[0][0] in (types.TerminationStatus.PROCESS_WAS_KILLED,
                                        types.TerminationStatus.ABNORMAL_TERMINATION,
                                        types.TerminationStatus.PROCESS_CRASHED), terminated
            assert canceled == list(pending), (canceled, pending)    # the router cancelled its query
            app.shutdown()
            print("OK")
        """)

    def test_a_ctrl_click_on_a_link_asks_the_handler_before_a_new_tab(self):
        self.run_osr_script("""
            asked = []
            class Requests(cefweaver.RequestHandler):
                def on_open_url_from_tab(self, browser, frame, target_url, target_disposition, user_gesture):
                    asked.append((target_url, target_disposition, user_gesture))
                    return True                            # the host opens it (or not)
            handlers["request"] = Requests()
            start('<a href="http://tab.test/next" style="position:fixed;left:0;top:0;width:200px;'
                  'height:100px;display:block">go</a>')
            host = boxes[0].get_host()
            CTRL = 4                                       # EVENTFLAG_CONTROL_DOWN
            def click():
                host.send_mouse_click_event((50, 50, CTRL), types.MouseButtonType.LEFT, False, 1)
                host.send_mouse_click_event((50, 50, CTRL), types.MouseButtonType.LEFT, True, 1)
            send_until(app, click, lambda: asked, "the new tab request")
            url, disposition, gesture = asked[0]
            assert url == "http://tab.test/next" and gesture is True, asked
            assert disposition in (types.WindowOpenDisposition.NEW_BACKGROUND_TAB,
                                   types.WindowOpenDisposition.NEW_FOREGROUND_TAB), disposition
            assert len(boxes) == 1, boxes                  # nothing opened
            app.shutdown()
            print("OK")
        """)

    def test_an_external_protocol_reaches_the_resource_request_handler(self):
        self.run_osr_script("""
            asked = []
            class Resources(cefweaver.ResourceRequestHandler):
                def on_protocol_execution(self, browser, frame, request):
                    asked.append(request.get_url())
                    return False                           # do not let the OS run a program
            class Requests(cefweaver.RequestHandler):
                def get_resource_request_handler(self, browser, frame, request, is_navigation,
                                                 is_download, request_initiator):
                    return Resources(), False
            handlers["request"] = Requests()
            start('<a href="mailto:someone@example.test" style="position:fixed;left:0;top:0;'
                  'width:200px;height:100px;display:block">mail</a>')
            host = boxes[0].get_host()
            def click():
                host.send_mouse_click_event((50, 50, 0), types.MouseButtonType.LEFT, False, 1)
                host.send_mouse_click_event((50, 50, 0), types.MouseButtonType.LEFT, True, 1)
            send_until(app, click, lambda: asked, "the protocol execution")
            assert asked[0] == "mailto:someone@example.test", asked
            app.shutdown()
            print("OK")
        """)

    def test_a_certificate_error_is_decided_by_the_handler(self):
        self.run_osr_script(prelude=self.LOCAL_TLS_SERVER, body="""
            errors, texts, load_errors = [], [], []
            allow = [False]                                # refuse first: an allowed one is remembered
            class Requests(cefweaver.RequestHandler):
                def on_certificate_error(self, browser, cert_error, request_url, callback):
                    errors.append((cert_error, request_url))
                    if allow[0]:
                        callback.continue_()
                        return True
                    return False                           # CEF refuses the page
            class Text(cefweaver.StringVisitor):
                def visit(self, string):
                    texts.append(string)
            handlers["request"] = Requests()
            start(RED)
            app.load_url(SECURE + "/refused")
            wait_until(app, lambda: errors, "the certificate error")
            error, url = errors[0]
            assert isinstance(error, types.ErrorCode) and error == types.ErrorCode.CERT_AUTHORITY_INVALID, errors
            assert url == SECURE + "/refused", url
            for _ in range(100):
                app.do_message_loop_work(); time.sleep(0.005)
            boxes[0].get_main_frame().get_text(Text())
            wait_until(app, lambda: texts, "the text of the page")
            assert "secure hello" not in texts[-1], texts             # the page did not load
            # allowed: the page loads
            allow[0] = True
            app.load_url(SECURE + "/allowed")
            send_until(app, lambda: boxes[0].get_main_frame().get_text(Text()),
                       lambda: any(t.strip() == "secure hello" for t in texts), "the secure page")
            assert errors[-1][1] == SECURE + "/allowed", errors
            app.shutdown()
            print("OK")
        """)

    def test_the_request_context_handler_is_asked_about_the_requests_of_its_browser(self):
        self.run_osr_script(prelude=self.LOCAL_SERVER, body="""
            asked, loaded = [], []
            class Resources(cefweaver.ResourceRequestHandler):
                def on_before_resource_load(self, browser, frame, request, callback):
                    loaded.append(request.get_url())
                    return types.ReturnValue.CONTINUE
            class Contexts(cefweaver.RequestContextHandler):
                def get_resource_request_handler(self, browser, frame, request, is_navigation,
                                                is_download, request_initiator):
                    asked.append((browser is not None, frame is not None, request.get_url(), is_navigation))
                    return Resources(), False
            made = []
            class Hooks(cefweaver.AppHandler):
                def on_context_initialized(self):
                    # CEF runs: make a context of its own for the first browser
                    context = cefweaver.RequestContext.create_context(
                        types.RequestContextSettings(), Contexts())
                    app.set_request_context(context)
                    made.append(context)
            app.set_app_handler(Hooks())
            start(RED)
            assert made and made[0].is_global() is False
            app.load_url(BASE + "/hello")
            wait_until(app, lambda: any(a[2] == BASE + "/hello" for a in asked), "the request")
            entry = [a for a in asked if a[2] == BASE + "/hello"][0]
            assert entry[:2] == (True, True) and entry[3] is True, asked    # a browser, a frame, a navigation
            assert BASE + "/hello" in loaded, loaded       # the handler the context gave was used
            assert boxes[0].get_host().get_request_context().is_same(made[0]) is True
            app.shutdown()
            print("OK")
        """)

    CROSS_SITE_SCRIPT = """
        import http.server
        FUNCTIONS = ('<script>function ask(r, p) { window.cefQuery({request: r, persistent: !!p,'
                     'onSuccess: function (x) { report("ok", r, x); },'
                     'onFailure: function (c, m) { report("fail", r, c); }}); }</script>')
        def serve(pages):
            class PageHandler(http.server.BaseHTTPRequestHandler):
                def log_message(self, *args):
                    pass
                def do_GET(self):
                    body = pages.get(self.path, "").encode()
                    self.send_response(200 if self.path in pages else 404)
                    self.send_header("Content-Type", "text/html")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
            server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), PageHandler)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            return server.server_address[1]
        child_port = serve({"/child": FUNCTIONS + "<script>report('child-frame');</script>"})
        # 127.0.0.1 and localhost are different sites: the child is cross-site
        child_url = "http://localhost:%d/child" % child_port
        main_port = serve({"/main": FUNCTIONS + "<script>requestAnimationFrame(() => report('main-frame'));</script>"
                                    "<iframe src='%s'></iframe>" % child_url})
    """

    def test_a_cross_site_iframe_loads_and_its_queries_reach_the_handler(self):
        self.run_query_script(prelude=self.CROSS_SITE_SCRIPT, body="""
            seen = []
            class Handler(cefweaver.QueryHandler):
                def on_query(self, browser, frame, query_id, request, persistent, callback):
                    seen.append((frame.is_main(), frame.get_url()))
                    callback.success("pong:" + request + ":" + str(frame.is_main()))
                    return True
            app.add_query_handler(Handler())
            start()
            app.load_url("http://127.0.0.1:%d/main" % main_port)
            wait_until(app, lambda: ("main-frame",) in js and ("child-frame",) in js, "both frames")
            # the child frame has its own process: the main frame is answered too
            browser = boxes[0]
            frames = {browser.get_frame_by_identifier(i).get_url(): i for i in browser.get_frame_identifiers()}
            assert child_url in frames, frames
            browser.get_frame_by_identifier(frames[child_url]).execute_java_script("ask('from child')", "", 0)
            # execute_javascript() runs nothing while the page is loading (the child frame is
            # part of the load) and says so by returning False
            wait_until(app, lambda: app.is_ready_to_execute_javascript, "the end of the loading")
            assert app.execute_javascript("ask('from main')") is True
            wait_until(app, lambda: "from main" in answers(), "the answer for the main frame")
            wait_until(app, lambda: "from child" in answers(), "the answer for the child frame")
            found = answers()
            assert found["from child"] == ("ok", "pong:from child:False"), found
            assert found["from main"] == ("ok", "pong:from main:True"), found
            assert (False, child_url) in seen, seen
            app.shutdown()
            print("OK")
        """)

    def test_a_cross_site_iframe_of_added_resources_loads_and_asks(self):
        self.run_query_script(body="""
            CHILD = ('<script>function ask(r, p) { window.cefQuery({request: r, persistent: !!p,'
                     'onSuccess: function (x) { report("ok", r, x); },'
                     'onFailure: function (c, m) { report("fail", r, c); }}); }'
                     'report("child-frame");</script>')
            MAIN = ('<script>report("main-frame");</script>'
                    '<iframe src="http://other.test/child.html"></iframe>')
            seen = []
            class Handler(cefweaver.QueryHandler):
                def on_query(self, browser, frame, query_id, request, persistent, callback):
                    seen.append(frame.is_main())
                    callback.success("pong")
                    return True
            app.add_query_handler(Handler())
            start()
            app.add_resource("http://one.test/main.html", MAIN)
            app.add_resource("http://other.test/child.html", CHILD)
            app.load_url("http://one.test/main.html")
            wait_until(app, lambda: ("main-frame",) in js and ("child-frame",) in js, "both frames")
            browser = boxes[0]
            frames = {browser.get_frame_by_identifier(i).get_url(): i for i in browser.get_frame_identifiers()}
            browser.get_frame_by_identifier(frames["http://other.test/child.html"]).execute_java_script(
                "ask('from child')", "", 0)
            wait_until(app, lambda: ("ok", "from child", "pong") in js, "the answer for the child")
            assert seen == [False], seen
            app.shutdown()
            print("OK")
        """)

    # -- the fields of java-cef's CefSettings ------------------------------------------------

    def test_the_user_agent_and_its_product_are_set(self):
        self.run_osr_script("""
            app.settings.user_agent = "CefweaverTest/1.0"
            start('<script>report("ua", navigator.userAgent)</script>')
            wait_until(app, lambda: ("ua", "CefweaverTest/1.0") in js, "the user agent")
            app.shutdown()
            print("OK")
        """)
        self.run_osr_script("""
            app.settings.user_agent_product = "Product/9.9"
            start('<script>report("ua", navigator.userAgent)</script>')
            wait_until(app, lambda: any(r[0] == "ua" for r in js), "the user agent")
            ua = [r for r in js if r[0] == "ua"][0][1]
            assert "Product/9.9" in ua and "Chrome/" not in ua.split("Product/9.9")[0].split()[-1], ua
            app.shutdown()
            print("OK")
        """)

    def test_the_locale_and_the_javascript_flags_are_set(self):
        self.run_osr_script("""
            app.settings.locale = "ko"
            app.settings.javascript_flags = "--expose-gc"
            start('<script>report("page", navigator.language, typeof gc)</script>')
            wait_until(app, lambda: any(r[0] == "page" for r in js), "the page")
            found = [r for r in js if r[0] == "page"][0]
            assert found[1].startswith("ko") and found[2] == "function", found
            app.shutdown()
            print("OK")
        """)

    def test_the_log_file_and_severity_are_set(self):
        self.run_osr_script("""
            import os
            log = os.path.join(tempfile.mkdtemp(prefix="cefweaver-log-"), "cef.log")
            app.settings.log_file = log
            app.settings.log_severity = cefweaver.types.LogSeverity.VERBOSE
            start(RED)
            app.shutdown()
            assert os.path.getsize(log) > 0, "the log file is empty"
            print("OK")
        """)

    def test_the_remote_debugging_port_is_open(self):
        self.run_osr_script("""
            import json, socket, threading, urllib.request
            with socket.socket() as holder:
                holder.bind(("127.0.0.1", 0))
                port = holder.getsockname()[1]
            app.settings.remote_debugging_port = port
            start(RED)
            answers = []
            def fetch():
                try:
                    answers.append(json.load(urllib.request.urlopen("http://127.0.0.1:%d/json/version" % port, timeout=5)))
                except Exception as error:
                    answers.append(error)
            threading.Thread(target=fetch).start()
            wait_until(app, lambda: answers, "the debugging endpoint")
            assert isinstance(answers[0], dict) and "Browser" in answers[0], answers
            app.shutdown()
            print("OK")
        """)

    X11_PIXEL = """
        import ctypes
        x11 = ctypes.CDLL("libX11.so.6")
        x11.XOpenDisplay.restype = ctypes.c_void_p
        x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
        x11.XGetImage.restype = ctypes.c_void_p
        x11.XGetImage.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_int,
                                  ctypes.c_uint, ctypes.c_uint, ctypes.c_ulong, ctypes.c_int]
        x11.XGetPixel.restype = ctypes.c_ulong
        x11.XGetPixel.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
        x11_display = x11.XOpenDisplay(None)
        def window_pixel(browser, x=20, y=20):
            # the 0xRRGGBB colour at (x, y) of the window of a windowed browser, or None
            window = browser.get_host().get_window_handle()
            image = x11.XGetImage(x11_display, window, x, y, 1, 1, 0xFFFFFFFF, 2)   # ZPixmap
            return x11.XGetPixel(image, 0, 0) if image else None
    """

    def test_the_background_color_fills_the_window_where_a_page_draws_none(self):
        # the pixels of a window are read from the X server with Xlib
        for color, expected in ((None, 0xFFFFFF), (0xFF00FF00, 0x00FF00)):
            self.run_osr_script(prelude=self.X11_PIXEL, body="""
                if %r is not None:
                    app.settings.background_color = %r
                app.set_client(MyClient())
                app.initialize(page(""))
                wait_until(app, lambda: boxes and app.is_ready_to_execute_javascript, "the page")
                wait_until(app, lambda: window_pixel(boxes[0]) == %r, "the colour %x of the window")
                app.shutdown()
                print("OK")
            """ % (color, color, expected, expected))

    def test_the_root_cache_path_holds_the_profile_data_and_the_cache_path_lies_within(self):
        import os
        import tempfile as temporary
        with temporary.TemporaryDirectory(prefix="cefweaver-root-") as root:
            profile = os.path.join(root, "profile")
            self.run_osr_script("""
                app.settings.root_cache_path = %r
                app.set_cache_path(%r)                       # within the root, as CEF requires
                start(RED)
                app.shutdown()
                print("OK")
            """ % (root, profile))
            # CEF keeps the profile data (Local State, Default/) in the root; the cache path is made
            self.assertTrue(os.path.isdir(profile), os.listdir(root))
            self.assertTrue(os.path.exists(os.path.join(root, "Local State")), os.listdir(root))
            self.assertTrue(os.path.isdir(os.path.join(root, "Default")), os.listdir(root))
        with temporary.TemporaryDirectory(prefix="cefweaver-root-") as root:
            self.run_osr_script("""
                app.settings.root_cache_path = %r            # no cache path of its own: the root
                start(RED)
                app.shutdown()
                print("OK")
            """ % root)
            self.assertTrue(os.path.exists(os.path.join(root, "Local State")), os.listdir(root))

    def test_the_settings_without_a_visible_effect_are_accepted_by_cef(self):
        # Their effect needs more than a page (a policy file, a JavaScript exception handler of the
        # renderer, a scheme with cookies): here CEF only has to start with them.
        self.run_osr_script("""
            app.settings.chrome_policy_id = "cefweaver.test"
            app.settings.uncaught_exception_stack_size = 5
            app.settings.command_line_args_disabled = True
            app.settings.cookieable_schemes_list = "http,https,cwtest"
            app.settings.cookieable_schemes_exclude_defaults = False
            start('<script>report("alive")</script>')
            wait_until(app, lambda: ("alive",) in js, "the page")
            app.shutdown()
            print("OK")
        """)

    def test_an_offscreen_browser_needs_no_display_server_with_the_headless_platform(self):
        # no X server and no Wayland: the offscreen pixels do not come from a window system
        import textwrap
        body = textwrap.dedent("""
            start(RED)
            wait_until(app, lambda: any(p["first"] == b"\\x00\\x00\\xff\\xff" for p in paints), "a red frame")
            app.execute_javascript("report('alive', 1)")
            wait_until(app, lambda: ("alive", 1) in js, "the script")
            app.shutdown()
            print("OK")
        """)
        result = run_cef(textwrap.dedent(self.OSR_SCRIPT) + body, ozone="headless",
                         without=("DISPLAY", "WAYLAND_DISPLAY", "XDG_SESSION_TYPE"))
        self.assertClean(result)
        self.assertIn("OK", result.stdout)

    def test_an_offscreen_page_is_transparent_unless_told_otherwise(self):
        self.run_osr_script("""
            assert app.transparent is True                    # as before: nothing painted is clear
            start("")
            wait_until(app, lambda: paints and paints[-1]["first"] == bytes([0, 0, 0, 0]), "a clear pixel")
            app.shutdown()
            print("OK")
        """)
        self.run_osr_script("""
            app.transparent = False                           # java-cef: createBrowser(..., false)
            start("")
            wait_until(app, lambda: paints and paints[-1]["first"] == bytes([255, 255, 255, 255]), "a white pixel")
            app.shutdown()
            print("OK")
        """)

    def test_the_background_color_shows_where_an_opaque_page_draws_none(self):
        self.run_osr_script("""
            app.settings.background_color = 0xFF00FF00         # ARGB: opaque green
            app.transparent = False
            start("")
            wait_until(app, lambda: paints and paints[-1]["first"] == bytes([0, 255, 0, 255]), "the green")
            app.shutdown()
            print("OK")
        """)

    def test_session_cookies_survive_a_restart_only_when_asked_to(self):
        import tempfile as temporary
        with temporary.TemporaryDirectory(prefix="cefweaver-profile-") as profile:
            def run(persist, write):
                return self.run_osr_script("""
                    app.set_cache_path(%r)
                    app.settings.persist_session_cookies = %r
                    class Cookies(cefweaver.CompletionCallback):
                        done = False
                        def on_complete(self):
                            Cookies.done = True
                    start('<p>x</p>')
                    app.add_resource("http://persist.test/", "<p>cookie</p>")
                    app.load_url("http://persist.test/")
                    wait_until(app, lambda: app.is_ready_to_execute_javascript, "the page")
                    if %r:
                        app.execute_javascript("document.cookie = 'session=1'")
                        manager = cefweaver.CookieManager.get_global_manager(None)
                        for _ in range(100):
                            app.do_message_loop_work(); time.sleep(0.01)
                        manager.flush_store(Cookies())
                        wait_until(app, lambda: Cookies.done, "the flush")
                    else:
                        app.execute_javascript("report('cookie', document.cookie)")
                        wait_until(app, lambda: any(r[0] == "cookie" for r in js), "the cookie")
                        print("COOKIE", [r for r in js if r[0] == "cookie"][0][1])
                    app.shutdown()
                    print("OK")
                """ % (profile, persist, write))
            run(True, True)                                       # write a session cookie
            self.assertIn("COOKIE session=1", run(True, False))   # the next process still has it
            run(False, True)
            self.assertNotIn("COOKIE session=1", run(False, False))

    # -- tasks for the threads of CEF ----------------------------------------------------------

    def test_a_task_posted_from_any_thread_runs_on_the_ui_thread_in_the_message_loop(self):
        self.run_osr_script("""
            import threading
            T = cefweaver.types.ThreadId
            main = threading.get_ident()
            ran = []
            class Record(cefweaver.Task):
                def __init__(self, name):
                    self.name = name
                def execute(self):
                    ran.append((self.name, threading.get_ident(), cefweaver.currently_on(T.UI),
                                cefweaver.currently_on(T.IO)))
            start(RED)
            assert cefweaver.currently_on(T.UI) is True and cefweaver.currently_on(T.IO) is False
            assert cefweaver.post_task(T.UI, Record("from main")) is True
            assert ran == [], "a task must not run inside post_task"
            worker = threading.Thread(target=lambda: ran.append(("worker said", cefweaver.currently_on(T.UI)))
                                      or cefweaver.post_task(T.UI, Record("from a thread")))
            worker.start(); worker.join()
            wait_until(app, lambda: len([r for r in ran if r[0].startswith("from")]) == 2, "both tasks")
            assert ("worker said", False) in ran                # a Python thread is not the UI thread
            for name, thread, on_ui, on_io in [r for r in ran if r[0].startswith("from")]:
                assert thread == main and on_ui is True and on_io is False, (name, ran)
            app.shutdown()
            print("OK")
        """)

    def test_a_task_runs_on_the_io_thread_and_a_delayed_task_waits(self):
        self.run_osr_script("""
            import threading
            T = cefweaver.types.ThreadId
            main = threading.get_ident()
            ran = {}
            class Record(cefweaver.Task):
                def __init__(self, name):
                    self.name = name
                def execute(self):
                    ran[self.name] = (time.time(), threading.get_ident(), cefweaver.currently_on(T.IO))
            start(RED)
            assert cefweaver.post_task(T.IO, Record("io")) is True
            wait_until(app, lambda: "io" in ran, "the task on the IO thread")
            assert ran["io"][1] != main and ran["io"][2] is True, ran
            begin = time.time()
            assert cefweaver.post_delayed_task(T.UI, Record("later"), 300) is True
            for _ in range(20):                              # 100 ms: not yet
                app.do_message_loop_work(); time.sleep(0.005)
            assert "later" not in ran, "ran too early"
            wait_until(app, lambda: "later" in ran, "the delayed task")
            assert ran["later"][0] - begin >= 0.25, ran["later"][0] - begin
            assert ran["later"][1] == main
            app.shutdown()
            print("OK")
        """)

    def test_a_task_from_a_thread_wakes_the_message_pump_of_the_application(self):
        self.run_osr_script("""
            import threading
            T = cefweaver.types.ThreadId
            woken = threading.Event()
            pump = cefweaver.MessagePump(app, wake=lambda delay: woken.set())
            app.offscreen = True
            app.set_client(MyClient())
            app.initialize(page(RED))
            done = []
            class Finish(cefweaver.Task):
                def execute(self):
                    done.append(threading.get_ident())
            def drive(until):
                end = time.time() + 20
                while not until():
                    assert time.time() < end, "timed out"
                    wait = pump.timeout()
                    if wait > 0:
                        woken.wait(wait); woken.clear()
                    pump.run()
            drive(lambda: paints)
            threading.Thread(target=lambda: cefweaver.post_task(T.UI, Finish())).start()
            drive(lambda: done)                              # the deadlines of the pump only
            assert done == [threading.get_ident()], done
            app.shutdown()
            print("OK")
        """)

    # -- more than one browser (java-cef: CefClient.createBrowser) ----------------------------

    PAGE_WITH_QUERIES = """
        PAGE = ('<script>function ask(r) { window.cefQuery({request: r,'
                'onSuccess: function (x) { report("ok", r, x); },'
                'onFailure: function (c, m) { report("fail", r, c); }}); }'
                'report("page", "%s");</script>')
    """

    def test_a_second_offscreen_browser_paints_on_its_own_and_the_first_is_unaffected(self):
        self.run_osr_script("""
            start(RED)
            first = boxes[0]
            GREEN = "<style>html, body { margin: 0; background: rgb(0, 255, 0); }</style>"
            second = app.create_browser(page(GREEN), transparent=False)
            assert isinstance(second, cefweaver.Browser)
            wait_until(app, lambda: any(p["browser"] == second.get_identifier()
                                        and p["first"] == b"\\x00\\xff\\x00\\xff" for p in paints),
                       "the green frame of the second browser")
            wait_until(app, lambda: len(boxes) == 2, "the second browser")
            assert second.get_identifier() != first.get_identifier() and second.is_same(boxes[1])
            assert second.is_popup() is False
            reds = [p for p in paints if p["browser"] == first.get_identifier()]
            assert all(p["first"] == b"\\x00\\x00\\xff\\xff" for p in reds), reds   # still red
            app.shutdown()                                           # both are closed
            print("OK")
        """)

    def test_each_browser_has_its_own_transparency(self):
        self.run_osr_script("""
            start("")                                        # the first one: transparent
            clear = boxes[0]
            white = app.create_browser(page(""), transparent=False)
            also_clear = app.create_browser(page(""))        # as the app says
            def first_pixels(browser):
                return {p["first"] for p in paints if p["browser"] == browser.get_identifier()}
            wait_until(app, lambda: first_pixels(white) and first_pixels(also_clear), "the frames")
            assert first_pixels(white) == {bytes([255, 255, 255, 255])}, first_pixels(white)
            assert first_pixels(also_clear) == {bytes([0, 0, 0, 0])}, first_pixels(also_clear)
            assert first_pixels(clear) == {bytes([0, 0, 0, 0])}, first_pixels(clear)
            app.shutdown()
            print("OK")
        """)

    def test_the_bindings_and_the_router_work_in_every_browser(self):
        self.run_osr_script(prelude=self.PAGE_WITH_QUERIES, body="""
            seen = []
            class Handler(cefweaver.QueryHandler):
                def on_query(self, browser, frame, query_id, request, persistent, callback):
                    seen.append((browser.get_identifier(), frame.is_main(), request))
                    callback.success("pong:" + request)
                    return True
            app.add_query_handler(Handler())
            start(PAGE % "one")
            second = app.create_browser(page(PAGE % "two"))
            wait_until(app, lambda: ("page", "one") in js and ("page", "two") in js, "both pages")
            second.get_main_frame().execute_java_script("ask('from two')", "", 0)
            boxes[0].get_main_frame().execute_java_script("ask('from one')", "", 0)
            wait_until(app, lambda: ("ok", "from two", "pong:from two") in js
                       and ("ok", "from one", "pong:from one") in js, "both answers")
            assert (second.get_identifier(), True, "from two") in seen, seen
            assert (boxes[0].get_identifier(), True, "from one") in seen, seen
            app.shutdown()
            print("OK")
        """)

    def test_closing_one_browser_leaves_the_others_and_the_app_running(self):
        self.run_osr_script(prelude=self.LOCAL_SERVER + """
        import time as _time
        class SlowHandler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_GET(self):
                _time.sleep(4)
                self.send_response(200)
                self.send_header("Content-Length", "0")
                self.end_headers()
        slow = http.server.ThreadingHTTPServer(("127.0.0.1", 0), SlowHandler)
        threading.Thread(target=slow.serve_forever, daemon=True).start()
        SLOW = "http://127.0.0.1:%d/slow" % slow.server_address[1]
        """, body="""
            start(RED)
            wait_until(app, lambda: app.is_ready_to_execute_javascript, "the first page")
            second = app.create_browser(page(RED))
            wait_until(app, lambda: len(boxes) == 2, "the second browser")
            third = app.create_browser(SLOW)                   # still loading for seconds
            wait_until(app, lambda: len(boxes) == 3 and third.is_loading(), "the loading third browser")
            assert app.is_ready_to_execute_javascript is True  # that is about the first browser only
            assert app.execute_javascript("report('still', 1)") is True
            wait_until(app, lambda: ("still", 1) in js, "the script of the first browser")
            second.get_host().close_browser(True)
            wait_until(app, lambda: second.get_identifier() in closed, "the second browser to close")
            assert app.is_running is True
            assert boxes[0].is_valid() and third.is_valid()
            assert app.execute_javascript("report('after', 2)") is True
            wait_until(app, lambda: ("after", 2) in js, "the first browser after the close")
            app.shutdown()
            print("OK")
        """)

    def test_a_browser_can_have_a_request_context_of_its_own(self):
        self.run_osr_script(prelude=self.LOCAL_SERVER, body="""
            asked = []
            class Resources(cefweaver.ResourceRequestHandler):
                pass
            class Contexts(cefweaver.RequestContextHandler):
                def get_resource_request_handler(self, browser, frame, request, is_navigation,
                                                is_download, request_initiator):
                    asked.append((browser.get_identifier() if browser else None, request.get_url()))
                    return Resources(), False
            start(RED)
            context = cefweaver.RequestContext.create_context(types.RequestContextSettings(), Contexts())
            second = app.create_browser(BASE + "/hello", request_context=context)
            wait_until(app, lambda: (second.get_identifier(), BASE + "/hello") in asked, "the request")
            assert second.get_host().get_request_context().is_same(context)
            assert not boxes[0].get_host().get_request_context().is_same(context)
            app.shutdown()
            print("OK")
        """)

    def test_a_windowed_app_can_create_windowed_and_offscreen_browsers(self):
        self.run_osr_script("""
            app.set_client(MyClient())
            app.initialize(page(RED + '<script>report("page", "one")</script>'))
            wait_until(app, lambda: ("page", "one") in js and boxes, "the first page")
            windowed = app.create_browser(page(RED + '<script>report("page", "two")</script>'))
            drawn = app.create_browser(page(RED), offscreen=True)
            wait_until(app, lambda: ("page", "two") in js and len(boxes) == 3, "the browsers")
            wait_until(app, lambda: any(p["browser"] == drawn.get_identifier() for p in paints), "its frame")
            assert boxes[0].get_host().is_window_rendering_disabled() is False
            assert windowed.get_host().is_window_rendering_disabled() is False
            assert drawn.get_host().is_window_rendering_disabled() is True
            assert not any(p["browser"] in (boxes[0].get_identifier(), windowed.get_identifier()) for p in paints)
            app.shutdown()
            print("OK")
        """)

    def test_create_browser_checks_its_arguments(self):
        self.run_osr_script("""
            start(RED)
            for bad in ({"url": 3}, {"request_context": "no"}, {"offscreen": "yes"}, {"transparent": 1}):
                try:
                    app.create_browser(**dict({"url": "about:blank"}, **bad))
                except TypeError:
                    continue
                raise AssertionError("accepted %r" % (bad,))
            assert len(boxes) == 1
            app.shutdown()
            print("OK")
        """)

    # -- offscreen input beyond one letter, touch, IME, and the popup of a <select> ------------

    def test_keys_beyond_a_letter_edit_and_move_in_an_offscreen_input(self):
        self.run_osr_script("""
            KT = types.KeyEventType
            start('<input id="i" autofocus style="width:150px">'
                  '<script>var i = document.getElementById("i");'
                  'i.addEventListener("keydown", e => report("keydown", e.key));'
                  'i.addEventListener("keyup", e => report("keyup", e.key));</script>')
            host = boxes[0].get_host()
            host.set_focus(True)
            def key(kind, code, char=0, modifiers=0):
                host.send_key_event(cefweaver.KeyEvent(kind, modifiers, code, 0, 0, char, char, 0))
            def press(code, char=0, modifiers=0):
                key(KT.RAWKEYDOWN, code, char, modifiers)
                if char:
                    key(KT.CHAR, code, char, modifiers)
                key(KT.KEYUP, code, char, modifiers)
            send_until(app, lambda: press(88, 120), lambda: ("keydown", "x") in js, "the focus")  # 'x'
            def value(expected=None):
                # the (text, caret) of the input; with `expected`, waits until it is that
                end = time.time() + 20
                while True:
                    del js[:]
                    app.execute_javascript("report('value', i.value, i.selectionStart)")
                    wait_until(app, lambda: js, "the value")
                    if expected is None or js[-1][1:] == expected or time.time() > end:
                        return js[-1][1:]
            app.execute_javascript("i.value = ''")
            for code, char in ((65, 97), (66, 98), (67, 99)):      # a b c
                press(code, char)
            assert value(("abc", 3)) == ("abc", 3), value()
            press(8)                                               # Backspace
            assert value(("ab", 2)) == ("ab", 2), value()
            press(37)                                              # ArrowLeft
            assert value(("ab", 1)) == ("ab", 1), value()
            press(46)                                              # Delete (after the caret)
            assert value(("a", 1)) == ("a", 1), value()
            press(65, 65, 2)                                       # Shift+a: an upper case A
            assert value(("aA", 2)) == ("aA", 2), value()
            press(0, 0xac00)                                       # a Korean letter by CHAR only
            assert value(("aA\uac00", 3)) == ("aA\uac00", 3), value()
            del js[:]
            press(13)                                              # Enter reaches the page
            wait_until(app, lambda: ("keydown", "Enter") in js, "the Enter key")
            app.shutdown()
            print("OK")
        """)

    def test_a_touch_reaches_the_page_as_a_touch_event(self):
        self.run_osr_script("""
            app.add_command_line_switch("touch-events", "enabled")
            start('<div style="position:fixed;left:0;top:0;width:200px;height:100px"></div>'
                  '<script>document.addEventListener("touchstart", e => report("touchstart", e.touches.length));'
                  'document.addEventListener("touchend", e => report("touchend"));</script>')
            host = boxes[0].get_host()
            def touch():
                point = cefweaver.TouchEvent(1, 50.0, 50.0, 5.0, 5.0, 0.0, 1.0,
                                             types.TouchEventType.PRESSED, 0, types.PointerType.TOUCH)
                host.send_touch_event(point)
                host.send_touch_event(point._replace(type=types.TouchEventType.RELEASED))
            send_until(app, touch, lambda: ("touchstart", 1) in js, "the touch")
            wait_until(app, lambda: ("touchend",) in js, "the end of the touch")
            app.shutdown()
            print("OK")
        """)

    def test_an_ime_composition_becomes_text_in_an_offscreen_input(self):
        self.run_osr_script("""
            start('<input id="i" autofocus style="width:150px">'
                  '<script>var i = document.getElementById("i");'
                  '["compositionstart", "compositionupdate", "compositionend"].forEach(n =>'
                  'i.addEventListener(n, e => report(n, e.data)));</script>')
            host = boxes[0].get_host()
            host.set_focus(True)
            underline = cefweaver.CompositionUnderline(cefweaver.Range(0, 1), 0xFF000000, 0, 0,
                                                       types.CompositionUnderlineStyle.SOLID)
            none = cefweaver.Range(0xFFFFFFFF, 0xFFFFFFFF)
            send_until(app, lambda: host.ime_set_composition("\\uac00", [underline], none, cefweaver.Range(1, 1)),
                       lambda: ("compositionupdate", "\\uac00") in js, "the composition")
            host.ime_commit_text("\\uac00\\ub098", none, 0)       # the text replaces the composition
            wait_until(app, lambda: any(r[0] == "compositionend" for r in js), "the end of the composition")
            del js[:]
            app.execute_javascript("report('value', i.value)")
            wait_until(app, lambda: js, "the value")
            assert js[-1] == ("value", "\\uac00\\ub098"), js
            app.shutdown()
            print("OK")
        """)

    def test_a_korean_composition_reports_the_character_bounds_and_draws_its_underline(self):
        self.run_osr_script("""
            WHITE = "<style>html, body { margin: 0; background: white; } " \
                    "input { position: fixed; left: 10px; top: 20px; width: 150px; height: 30px; " \
                    "font-size: 20px; border: 0; padding: 0; outline: none; }</style>"
            start(WHITE + '<input id="i" autofocus>'
                  '<script>var i = document.getElementById("i");'
                  '["compositionstart", "compositionupdate", "compositionend"].forEach(n =>'
                  'i.addEventListener(n, e => report(n, e.data)));</script>')
            host = boxes[0].get_host()
            host.set_focus(True)
            probe[0] = lambda b, g, r: not (b > 250 and g > 250 and r > 250)   # the non-white pixels
            nothing = cefweaver.Range(0xFFFFFFFF, 0xFFFFFFFF)
            Style = types.CompositionUnderlineStyle
            def underline(length, thick=0, style=Style.SOLID, color=0xFF000000):
                return [cefweaver.CompositionUnderline(cefweaver.Range(0, length), color, 0, thick, style)]
            def compose(text, underlines):
                host.ime_set_composition(text, underlines, nothing, cefweaver.Range(len(text), len(text)))
            def last_bounds():
                return ranges[-1][1] if ranges else []
            def pixels_with(underlines, text="\uac01"):
                # the number of non-white pixels of the next paint of the composition
                before = len(paints)
                compose(text, underlines)
                wait_until(app, lambda: len(paints) > before, "the paint of the composition")
                for _ in range(20):                                # the last paint wins
                    app.do_message_loop_work(); time.sleep(0.01)
                return paints[-1]["found"]
            # a syllable is built letter by letter, as a Korean input method does
            send_until(app, lambda: compose("\u3131", underline(1)),
                       lambda: ("compositionupdate", "\u3131") in js, "the first letter")
            for text in ("\uac00", "\uac01"):                       # ga, gag
                compose(text, underline(1))
                wait_until(app, lambda: ("compositionupdate", text) in js, "the update to " + text)
            # the bounds of the characters are for the candidate window
            wait_until(app, lambda: len(last_bounds()) == 1, "the bounds of one character")
            x, y, w, h = last_bounds()[0]
            assert 10 <= x < 170 and 20 <= y < 50 and w > 0 and h > 0, last_bounds()   # inside the input
            compose("\uac01\ub098", underline(2))                  # a second syllable
            wait_until(app, lambda: len(last_bounds()) == 2, "the bounds of two characters")
            assert last_bounds()[0][0] == x and last_bounds()[1][0] > x, last_bounds()
            # the underline is drawn from the description: its thickness and style show in the paint
            compose("\uac01", underline(1))
            wait_until(app, lambda: len(last_bounds()) == 1, "one character again")
            default = pixels_with([])
            thin = pixels_with(underline(1))
            thick = pixels_with(underline(1, thick=1))
            dotted = pixels_with(underline(1, style=Style.DOT))
            assert thick > thin, (thin, thick)                     # a thick line has more pixels
            assert len({default, thin, dotted}) == 3, (default, thin, dotted)
            host.ime_commit_text("\uac01\ub098", nothing, 0)
            wait_until(app, lambda: any(r[0] == "compositionend" for r in js), "the end of the composition")
            del js[:]
            app.execute_javascript("report('value', i.value)")
            wait_until(app, lambda: js, "the value")
            assert js[-1] == ("value", "\uac01\ub098"), js
            app.shutdown()
            print("OK")
        """)

    def test_the_popup_of_a_select_is_drawn_as_a_second_element(self):
        self.run_osr_script("""
            start('<select id="s" style="position:fixed;left:10px;top:10px;width:120px;height:30px">'
                  '<option>one</option><option>two</option><option>three</option></select>')
            host = boxes[0].get_host()
            def click():
                host.send_mouse_click_event((40, 25, 0), types.MouseButtonType.LEFT, False, 1)
                host.send_mouse_click_event((40, 25, 0), types.MouseButtonType.LEFT, True, 1)
            send_until(app, click, lambda: ("show", True) in popups, "the popup")
            sizes = [p[1] for p in popups if p[0] == "size"]
            assert sizes and sizes[-1][2] > 0 and sizes[-1][3] > 0, popups        # a Rect
            wait_until(app, lambda: any(p["type"] == types.PaintElementType.POPUP for p in paints),
                       "the paint of the popup")
            frame = [p for p in paints if p["type"] == types.PaintElementType.POPUP][-1]
            assert frame["nbytes"] == frame["width"] * frame["height"] * 4, frame
            assert (frame["width"], frame["height"]) == (sizes[-1][2], sizes[-1][3]), (frame, sizes)
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
