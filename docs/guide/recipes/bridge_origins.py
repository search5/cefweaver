import tempfile
import time

import cefweaver

reports = []
app = cefweaver.CefApp()
app.set_cache_path(tempfile.mkdtemp())
app.add_command_line_switch("ozone-platform", "x11")

# Only frames whose URL starts with one of the origins are answered.
bridge = cefweaver.JavascriptBridge(app, origins=["http://trusted.test/"])
bridge.expose("add", lambda a, b: a + b)
app.add_javascript_binding("report", lambda *args: reports.append(args))    # a binding is not part of the bridge

PAGE = "<script>add(2, 3).then(function (v) { report('add', String(v)); }, function (e) { report('add failed', e.message); });</script>"


def wait_until(condition, what, timeout=30):
    end = time.monotonic() + timeout
    while not condition():
        if time.monotonic() > end:
            raise TimeoutError("timed out waiting for " + what)
        app.do_message_loop_work()
        time.sleep(0.005)


app.initialize("about:blank")
app.add_resource("http://trusted.test/", PAGE)
app.add_resource("http://other.test/", PAGE)
for url in ("http://trusted.test/", "http://other.test/"):
    count = len(reports)
    app.load_url(url)
    wait_until(lambda: len(reports) > count, url)
    print(url, reports[-1])
app.shutdown()
