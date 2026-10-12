"""An exception in a hook of the view goes to sys.excepthook; the loop and the browser go on."""
import sys
import tempfile

from cefweaver import ui
from cefweaver.ui.headless import HeadlessAdapter

caught = []
sys.excepthook = lambda kind, error, traceback: caught.append("%s: %s" % (kind.__name__, error))

adapter = HeadlessAdapter(size=(320, 200))
session = ui.Session(adapter, cache_path=tempfile.mkdtemp())
view = ui.BrowserView(adapter)
titles = []


def on_title(title):
    titles.append(title)
    raise ValueError("raised in on_title")


view.on_title = on_title
view.on_ready = lambda: (session.app.add_resource("http://app.test/", "<title>first</title>"), view.load_url("http://app.test/"))
session.start(view)
adapter.run_until(lambda: titles, "the title")
adapter.run_for(0.5)
print("titles:", titles)
print("caught:", caught)
done = []
session.shutdown(done=lambda: done.append(1))
adapter.run_until(lambda: done, "shutdown")
print("shut down")
