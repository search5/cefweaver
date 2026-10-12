import tempfile, os
from cefweaver import ui
from cefweaver.ui.headless import HeadlessAdapter

adapter = HeadlessAdapter(size=(640, 360))
session = ui.Session(adapter, cache_path=tempfile.mkdtemp())
calls, results = [], {}

# recipe: page from memory, Python function called by the page
PAGE = "<h1 id=t>hello</h1><script>add(2, 3).then(function (s) { document.title = 'sum=' + s; });</script>"
session.bridge.expose("add", lambda a, b: a + b)

view = ui.BrowserView(adapter)
titles = []
view.on_title = titles.append
def ready():
    session.app.add_resource("http://app.test/index.html", PAGE)
    view.load_url("http://app.test/index.html")
view.on_ready = ready
session.start(view)
adapter.run_until(lambda: "sum=5" in titles, "the sum from Python")

# recipe: run JavaScript from Python
frame = view.browser.get_main_frame()
session.bridge.evaluate(frame, "document.getElementById('t').textContent", lambda v, e: results.update(v=v, e=e))
adapter.run_until(lambda: "v" in results, "evaluate")
print("evaluate:", results)

# recipe: screenshot
path = os.path.join(tempfile.mkdtemp(), "page.png")
print("snapshot:", view.snapshot(path), os.path.getsize(path) > 0)

done = []
session.shutdown(done=lambda: done.append(1))
adapter.run_until(lambda: done, "shutdown")
print("ok", titles)
