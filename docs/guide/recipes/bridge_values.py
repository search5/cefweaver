import tempfile

from cefweaver import ui
from cefweaver.ui.headless import HeadlessAdapter

# The page passes a function as the first argument; functions inside a list or an object are not converted.
PAGE = """<script>
listen(function (text) { report('heard ' + text); }, [function () {}], {f: function () {}}).then(function () { ready(); });
</script>"""

adapter = HeadlessAdapter(size=(320, 200))
session = ui.Session(adapter, cache_path=tempfile.mkdtemp())
bridge = session.bridge
reports, arguments, ready = [], [], []
bridge.expose("listen", lambda *args: arguments.append(args))
bridge.expose("report", reports.append)
bridge.expose("ready", lambda: ready.append(True))

view = ui.BrowserView(adapter)


def on_ready():
    session.app.add_resource("http://app.test/values.html", PAGE)
    view.load_url("http://app.test/values.html")


view.on_ready = on_ready
session.start(view)
adapter.run_until(lambda: ready, "the page")

callback, in_list, in_object = arguments[0]
print("arguments:", type(callback).__name__, in_list, in_object)
callback.call("one")
adapter.run_until(lambda: reports, "the first call")
callback.release()
callback.call("two")                                   # after release(): nothing happens
adapter.run_for(0.5)
print("page heard:", reports)

# What evaluate() makes of the result of a JavaScript expression.
frame = view.browser.get_main_frame()
results = {}
expressions = ["[1, 2.5, 1e21]", "NaN", "new Date(0)", "new Map([[1, 2]])", "var a = {}; a.a = a; a", "10n", "Symbol('s')"]
for expression in expressions:
    bridge.evaluate(frame, expression, lambda value, error, key=expression: results.update({key: (value, error)}))
adapter.run_until(lambda: len(results) == len(expressions), "the results")
for expression in expressions:
    value, error = results[expression]
    print("%-24s %r %s" % (expression, value, error.splitlines()[0] if error else error))

done = []
session.shutdown(done=lambda: done.append(True))
adapter.run_until(lambda: done, "shutdown")
