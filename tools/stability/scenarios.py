"""One stability scenario per process (CEF starts once per process).

Usage: PYTHONPATH=tools/stability python -P tools/stability/scenarios.py NAME   (on a virtual X server)

Names: renderer_crash, handler_exceptions, large_payload, unreachable, shutdown_while_loading, parent_killed,
sigterm_shutdown, wrong_thread, idle_cpu. Each prints a RESULT line.
"""
import sys, os, time, tempfile, json, signal, threading
from cefweaver import ui
from cefweaver.ui.headless import HeadlessAdapter
import cefweaver

name = sys.argv[1]
adapter = HeadlessAdapter(size=(640, 360))
session = ui.Session(adapter, cache_path=tempfile.mkdtemp())
view = ui.BrowserView(adapter)
titles = []
view.on_title = titles.append
errors = []
sys.excepthook = lambda t, v, tb: errors.append("%s: %s" % (t.__name__, v))

def start(url, ready=None):
    view.on_ready = lambda: (ready() if ready else None, view.load_url(url))
    session.start(view)

def finish(extra=None):
    done = []
    session.shutdown(done=lambda: done.append(1))
    adapter.run_until(lambda: done, "shutdown")
    print("RESULT", name, "OK", json.dumps(extra or {}), "excepthook:", errors)

if name == "renderer_crash":
    # a page crashes its renderer; the application must live, report it, and load another page afterwards
    session.bridge.expose("ping", lambda: "pong")
    start("data:text/html,<title>before</title>")
    adapter.run_until(lambda: "before" in titles, "first page")
    view.load_url("chrome://crash")
    adapter.run_for(3.0)
    view.load_url("data:text/html,<title>after</title><script>ping().then(function(v){document.title='after:'+v})</script>")
    adapter.run_until(lambda: "after:pong" in titles, "a page after the renderer crash")
    finish({"titles": titles})

elif name == "handler_exceptions":
    def boom(): raise ValueError("python side failure")
    session.bridge.expose("boom", boom)
    session.bridge.expose("ok", lambda: "fine")
    got = []
    session.bridge.expose("got", lambda v: got.append(v))
    start("data:text/html,<title>x</title><script>boom().then(function(){got('resolved')},function(e){got('rejected:'+String(e).slice(0,60))}).then(function(){return ok()}).then(function(v){got(v)})</script>")
    adapter.run_until(lambda: len(got) >= 2, "bridge results")
    view.on_title = lambda t: 1 / 0          # an exception in a hook
    view.load_url("data:text/html,<title>y</title>")
    adapter.run_for(2.0)
    view.on_title = titles.append
    view.load_url("data:text/html,<title>z</title>")
    adapter.run_until(lambda: "z" in titles, "the app still runs after a hook exception")
    finish({"got": got})

elif name == "large_payload":
    session.bridge.expose("echo", lambda s: s)
    n = 8 * 1024 * 1024
    res = {}
    start("data:text/html,<title>x</title>")
    adapter.run_until(lambda: "x" in titles, "page")
    frame = view.browser.get_main_frame()
    t = time.monotonic()
    session.bridge.evaluate(frame, "(function(){var s='a'.repeat(%d);return echo(s).then(function(r){return r.length})})()" % n,
                            lambda v, e: res.update(v=v, e=e), timeout=60)
    adapter.run_until(lambda: "v" in res, "round trip of 8 MB")
    res["seconds"] = round(time.monotonic() - t, 2)
    finish(res)

elif name == "unreachable":
    # a host that does not resolve and a port nobody listens on: the load fails, nothing hangs
    loads = []
    view.on_loading = lambda loading, b, f: loads.append(loading)
    start("http://nonexistent.invalid/")
    adapter.run_until(lambda: loads.count(False) >= 1, "the failed load")
    view.load_url("http://127.0.0.1:9/")
    adapter.run_for(3.0)
    view.load_url("data:text/html,<title>alive</title>")
    adapter.run_until(lambda: "alive" in titles, "a page after failed loads")
    finish({"loading_events": len(loads)})

elif name == "shutdown_while_loading":
    # a local server that never answers; shutdown must still finish
    import socket, threading
    srv = socket.socket(); srv.bind(("127.0.0.1", 0)); srv.listen(5)
    port = srv.getsockname()[1]
    start("http://127.0.0.1:%d/" % port)
    adapter.run_for(1.5)
    t = time.monotonic()
    finish({"shutdown_seconds": None})
    print("shutdown took", round(time.monotonic() - t, 2))

elif name == "parent_killed":
    start("data:text/html,<title>x</title>")
    adapter.run_until(lambda: "x" in titles, "page")
    print("PID", os.getpid(), flush=True)
    time.sleep(1)
    os.kill(os.getpid(), signal.SIGKILL)

elif name == "sigterm_shutdown":
    start("data:text/html,<title>x</title>")
    adapter.run_until(lambda: "x" in titles, "page")
    print("PID", os.getpid(), flush=True)
    stop = []
    signal.signal(signal.SIGTERM, lambda *a: stop.append(1))
    adapter.run_until(lambda: stop, "SIGTERM")
    finish()

if name == "wrong_thread":
    import threading
    start("data:text/html,<title>x</title>")
    adapter.run_until(lambda: "x" in titles, "page")
    out = {}
    def other():
        try:
            view.load_url("data:text/html,<title>fromthread</title>")
            out["load_url"] = "returned"
        except BaseException as e:
            out["load_url"] = "%s: %s" % (type(e).__name__, e)
    t = threading.Thread(target=other); t.start(); t.join(10)
    adapter.run_for(2.0)
    out["title_seen"] = "fromthread" in titles
    # the supported way: post to the loop
    adapter.post(lambda: view.load_url("data:text/html,<title>posted</title>"))
    adapter.run_until(lambda: "posted" in titles, "posted load")
    finish(out)

if name == "idle_cpu":
    start("data:text/html,<title>idle</title>")
    adapter.run_until(lambda: "idle" in titles, "page")
    from common import sample
    def cpu():
        tot = 0
        import common
        for p in common.tree_pids():
            try:
                f = open("/proc/%d/stat" % p).read().rsplit(")", 1)[1].split()
                tot += int(f[11]) + int(f[12])
            except Exception: pass
        return tot / os.sysconf("SC_CLK_TCK")
    adapter.run_for(3.0)
    c0 = cpu(); t0 = time.monotonic()
    adapter.run_for(30.0)
    out = {"cpu_seconds_in_30s": round(cpu() - c0, 2), "wall": round(time.monotonic() - t0, 1)}
    finish(out)
