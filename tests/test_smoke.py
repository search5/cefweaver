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

def page(body):
    html = '<html><head><meta charset="utf-8"></head><body>' + body + '</body></html>'
    return "data:text/html;base64," + base64.b64encode(html.encode()).decode()

app = cefweaver.CefApp()
app.set_cache_path(tempfile.mkdtemp(prefix="cefweaver-test-"))
app.add_command_line_switch("ozone-platform", "x11")
"""


def run_cef(script, timeout=90):
    """Run `script` (after PRELUDE) in a new process; return CompletedProcess."""
    code = PRELUDE + textwrap.dedent(script)
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


if __name__ == "__main__":
    unittest.main()
