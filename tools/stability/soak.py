"""A soak test: load pages, call Python from the page and evaluate JavaScript for a given time, and sample
the memory, descriptors and threads of the process tree.

Usage: PYTHONPATH=tools/stability python -P tools/stability/soak.py SECONDS   (on a virtual X server)
"""
import sys, time, tempfile, json
from cefweaver import ui
from cefweaver.ui.headless import HeadlessAdapter
from common import sample

DURATION = float(sys.argv[1])
adapter = HeadlessAdapter(size=(800, 600))
session = ui.Session(adapter, cache_path=tempfile.mkdtemp())
stats = {"loads": 0, "calls": 0, "evals": 0, "errors": 0}

def page(n):
    rows = "".join("<li>row %d %s</li>" % (k, "x" * 40) for k in range(800))
    return ("<title>p%d</title><body><canvas id=c width=300 height=200></canvas><ul>%s</ul><script>"
            "var c=document.getElementById('c').getContext('2d');c.fillRect(0,0,%d,50);"
            "add(%d,1).then(function(v){document.title='p%d:'+v});</script></body>" % (n, rows, 20 + n % 200, n, n))

session.bridge.expose("add", lambda a, b: stats.__setitem__("calls", stats["calls"] + 1) or a + b)
view = ui.BrowserView(adapter)
titles = []
view.on_title = titles.append
state = {"n": 0}

def go():
    state["n"] += 1
    n = state["n"] % 20
    if n not in state.setdefault("added", set()):
        session.app.add_resource("http://app.test/p%d.html" % n, page(n)); state["added"].add(n)
    view.load_url("http://app.test/p%d.html" % n)
view.on_ready = go
session.start(view)

samples = []
t0 = time.monotonic(); last_sample = 0; last_load = 0
def evalcb(v, e):
    stats["evals"] += 1
    if e: stats["errors"] += 1
while time.monotonic() - t0 < DURATION:
    adapter.step(0.02)
    now = time.monotonic() - t0
    if view.browser is not None and now - last_load > 0.25:
        last_load = now
        go(); stats["loads"] += 1
        session.bridge.evaluate(view.browser.get_main_frame(), "document.querySelectorAll('li').length", evalcb, timeout=10)
    if now - last_sample >= 15:
        last_sample = now
        s = sample(); s.update(t=int(now), **stats); samples.append(s); print(json.dumps(s), flush=True)
done = []
session.shutdown(done=lambda: done.append(1))
adapter.run_until(lambda: done, "shutdown")
print("FINAL", json.dumps(stats), "titles", len(titles))
