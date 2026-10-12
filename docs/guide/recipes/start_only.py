"""Start CEF offscreen, wait for the browser, shut down. `python -P start_only.py [folder]` imports cefweaver from `folder`."""
import os
import sys
import tempfile

if len(sys.argv) > 1:
    sys.path.insert(0, sys.argv[1])
import cefweaver
from cefweaver import ui
from cefweaver.ui.headless import HeadlessAdapter

print("cefweaver from", os.path.basename(os.path.dirname(os.path.dirname(cefweaver.__file__))) or "(root)")
adapter = HeadlessAdapter(size=(320, 200))
cache = tempfile.mkdtemp()
session = ui.Session(adapter, cache_path=cache)
view = ui.BrowserView(adapter)
ready = []
view.on_ready = lambda: ready.append(1)
session.start(view)
adapter.run_until(lambda: ready, "the browser", timeout=15)
print("browser ready")
done = []
session.shutdown(done=lambda: done.append(1))
adapter.run_until(lambda: done, "shutdown")
print("shut down; log file in the cache folder:", os.path.exists(os.path.join(cache, "chrome_debug.log")))
