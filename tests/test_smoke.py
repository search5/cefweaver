"""Smoke tests for the installed cefweaver wheel (Linux).

Run against the *installed* wheel, on a virtual X server so that no window opens
on the desktop (Chromium prefers Wayland when WAYLAND_DISPLAY is set)::

    uv build --wheel && uv pip install dist/cefweaver-*.whl
    env -u WAYLAND_DISPLAY xvfb-run -a python -m unittest discover -s tests -v

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


@unittest.skipUnless(RUNTIME_OK and HAS_X, "needs the Linux wheel with the CEF runtime "
                     "and a virtual X server (see the module docstring)")
class WithCef(unittest.TestCase):
    def assertClean(self, result):
        # A TimeoutError in the script names the awaited event in its traceback.
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
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


if __name__ == "__main__":
    unittest.main()
