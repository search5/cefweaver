"""The exceptions of the Python side of cefweaver when the order of the calls is wrong. Prints one line per case."""
import tempfile

import cefweaver
from cefweaver import ui
from cefweaver.ui.headless import HeadlessAdapter


def show(label, call):
    try:
        print("%-38s returned %r" % (label, call()))
    except Exception as error:
        print("%-38s %s: %s" % (label, type(error).__name__, error))


app = cefweaver.CefApp()
show("load_url() before initialize()", lambda: app.load_url("http://a.test/"))
show("add_resource() before initialize()", lambda: app.add_resource("http://a.test/", "x"))
show("Settings(foo=1)", lambda: cefweaver.Settings(foo=1))
settings = cefweaver.Settings()
show("settings.foo = 1", lambda: setattr(settings, "foo", 1))
show("settings.log_file = 5", lambda: setattr(settings, "log_file", 5))
show("settings.persist_session_cookies = 1", lambda: setattr(settings, "persist_session_cookies", 1))
show("settings.remote_debugging_port = 70000", lambda: setattr(settings, "remote_debugging_port", 70000))

adapter = HeadlessAdapter(size=(320, 200))
session = ui.Session(adapter, cache_path=tempfile.mkdtemp())
running = session.app
view = ui.BrowserView(adapter)
ready = []
view.on_ready = lambda: ready.append(1)
session.start(view)
adapter.run_until(lambda: ready, "the browser")
show("initialize() twice", lambda: running.initialize("about:blank"))
show("set_cache_path() after initialize()", lambda: running.set_cache_path("/tmp/x"))
show("add_command_line_switch() after it", lambda: running.add_command_line_switch("disable-gpu"))
show("settings.user_agent = ... after it", lambda: setattr(running.settings, "user_agent", "x"))
show("offscreen = False after it", lambda: setattr(running, "offscreen", False))
show("add_resource() with an ftp URL", lambda: running.add_resource("ftp://x/", "y"))
done = []
session.shutdown(done=lambda: done.append(1))
adapter.run_until(lambda: done, "shutdown")
show("do_message_loop_work() after shutdown", running.do_message_loop_work)
show("CefApp().initialize() after shutdown", lambda: cefweaver.CefApp().initialize())
