import sys, tempfile
from cefweaver import ui
from cefweaver.ui.headless import HeadlessAdapter
adapter = HeadlessAdapter(size=(640, 360))
session = ui.Session(adapter, cache_path=tempfile.mkdtemp())
session.bridge.expose("ping", lambda: "pong")
view = ui.BrowserView(adapter)
titles = []
view.on_title = titles.append
view.on_ready = lambda: view.load_url("data:text/html,<title>t</title><script>ping().then(function(v){document.title=v})</script>")
session.start(view)
adapter.run_until(lambda: "pong" in titles, "bridge answer")
done = []
session.shutdown(done=lambda: done.append(1))
adapter.run_until(lambda: done, "shutdown")
print("ok")
