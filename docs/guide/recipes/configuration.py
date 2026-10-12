"""Settings, Chromium switches and a custom scheme, and how to see that CEF got them (no screen needed)."""
import json
import os
import socket
import tempfile
import threading
import urllib.request

import cefweaver
from cefweaver import types, ui
from cefweaver.ui.headless import HeadlessAdapter

tmp = tempfile.mkdtemp()
with socket.socket() as probe:                          # a free port for the remote debugging server
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
seen = {}


class Hooks(cefweaver.AppHandler):
    def on_before_command_line_processing(self, process_type, command_line):
        seen["before"] = command_line.get_switches()    # CEF's own switches; the application's come after
        seen["process_type"] = process_type

    def on_register_custom_schemes(self, registrar):
        seen["scheme"] = registrar.add_custom_scheme("myapp", types.SchemeOptions.STANDARD | types.SchemeOptions.SECURE)


class Page(cefweaver.ResourceHandler):
    body = b"<title>from myapp</title><h1>hello</h1>"

    def __init__(self):
        self.offset = 0

    def open(self, request, callback):
        return True, True                               # handled; the response can be read right away

    def get_response_headers(self, response):
        response.set_mime_type("text/html")
        response.set_status(200)
        return len(self.body), ""

    def read(self, data_out, callback):
        count = min(len(data_out), len(self.body) - self.offset)
        if count <= 0:
            return False, 0
        data_out[:count] = self.body[self.offset:self.offset + count]
        self.offset += count
        return True, count

    def cancel(self):
        pass


class Factory(cefweaver.SchemeHandlerFactory):
    def create(self, browser, frame, scheme_name, request):
        return Page()


adapter = HeadlessAdapter(size=(640, 360))
cache = os.path.join(tmp, "cache")
session = ui.Session(adapter, switches=[("autoplay-policy", "no-user-gesture-required")], cache_path=cache)
app = session.app
app.set_app_handler(Hooks())
settings = app.settings                                 # a cefweaver.Settings; CEF reads it in initialize()
settings.user_agent = "MyApp/1.0"
settings.javascript_flags = "--expose-gc"
settings.log_file = os.path.join(tmp, "cef.log")
settings.log_severity = types.LogSeverity.INFO
settings.remote_debugging_port = port
settings.locale = "ko"

view = ui.BrowserView(adapter)
titles = []
view.on_title = titles.append


def ready():
    cefweaver.register_scheme_handler_factory("myapp", "app", Factory())
    view.load_url("myapp://app/index.html")


view.on_ready = ready
session.start(view)
adapter.run_until(lambda: "from myapp" in titles, "the page of the custom scheme")

result = {}
session.bridge.evaluate(view.browser.get_main_frame(),
                        "({ua: navigator.userAgent, gc: typeof gc, language: navigator.language, "
                        "location: location.protocol + '//' + location.host, secure: isSecureContext})",
                        lambda value, error: result.update(value=value, error=error))
adapter.run_until(lambda: result, "evaluate")
print("page:", result["value"])

switches = cefweaver.CommandLine.get_global_command_line().get_switches()
print("switches:", {name: switches[name] for name in ("autoplay-policy", "js-flags", "lang", "no-sandbox",
                                                       "ozone-platform", "user-agent")})
print("before the application's switches:", "autoplay-policy" in seen["before"], "| process type:", repr(seen["process_type"]))
print("scheme registered:", seen["scheme"])

version = {}
threading.Thread(target=lambda: version.update(
    v=json.load(urllib.request.urlopen("http://127.0.0.1:%d/json/version" % port, timeout=10))["Browser"])).start()
adapter.run_until(lambda: version, "the debugging server")
print("remote debugging:", version["v"].startswith("Chrome/"))
print("log file written:", os.path.getsize(settings.log_file) > 0)
print("cache folder:", [name for name in ("Default", "Local State") if name in os.listdir(cache)])
try:
    settings.user_agent = "late"
except RuntimeError as error:
    print("after initialize:", error)
done = []
session.shutdown(done=lambda: done.append(1))
adapter.run_until(lambda: done, "shutdown")
