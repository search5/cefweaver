"""Do the JavaScript bridge and add_javascript_binding survive reloads and navigations?

Meant to catch what cefpython issue 699 (bindings break after Reload() on Chromium 146+) and issue 406 (a cross-site
navigation starts a new renderer) report. It reloads three times, then navigates to a page of the same site, to another
site and back, and waits for both kinds of call from the page each time.

Usage: PYTHONPATH=tools/stability python -P tools/stability/reload_bindings.py   (on a virtual X server)
"""
import tempfile
from cefweaver import ui
from cefweaver.ui.headless import HeadlessAdapter
import cefweaver

adapter = HeadlessAdapter(size=(640, 360))
session = ui.Session(adapter, cache_path=tempfile.mkdtemp())
calls = {"bridge": 0, "binding": 0}
session.bridge.expose("add", lambda a, b: calls.__setitem__("bridge", calls["bridge"] + 1) or a + b)
session.app.add_javascript_binding("hello", lambda *a: calls.__setitem__("binding", calls["binding"] + 1))
PAGE = ("<title>p</title><script>"
        "typeof add==='function' ? add(1,2).then(function(v){document.title='bridge:'+v}) : document.title='bridge:MISSING';"
        "if (typeof hello==='function') hello(1); else document.title+=' binding:MISSING';"
        "</script>")
view = ui.BrowserView(adapter)
titles = []
view.on_title = titles.append
def ready():
    session.app.add_resource("http://app.test/a.html", PAGE)
    session.app.add_resource("http://app.test/b.html", PAGE.replace("<title>p</title>", "<title>b</title>"))
    view.load_url("http://app.test/a.html")
view.on_ready = ready
session.start(view)
def wait(n_bridge, n_binding, what):
    adapter.run_until(lambda: calls["bridge"] >= n_bridge and calls["binding"] >= n_binding, what)
wait(1, 1, "first load")
for i in range(2, 5):
    view.reload()
    wait(i, i, "reload %d" % i)
view.load_url("http://app.test/b.html")           # a same-site navigation
wait(5, 5, "same-site navigation")
session.app.add_resource("http://other.example/c.html", PAGE.replace("<title>p</title>", "<title>c</title>"))
view.load_url("http://other.example/c.html")      # a cross-site navigation (cefpython issue 406)
wait(6, 6, "cross-site navigation")
view.load_url("http://app.test/a.html")             # and back to the first site
wait(7, 7, "back")
print("calls", calls, "missing in titles:", [t for t in titles if "MISSING" in t])
done = []
session.shutdown(done=lambda: done.append(1))
adapter.run_until(lambda: done, "shutdown")
print("ok")
