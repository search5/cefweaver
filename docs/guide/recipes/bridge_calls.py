import json
import tempfile

from cefweaver import ui
from cefweaver.ui.headless import HeadlessAdapter

PAGE = """
<script>
window.api = {greet: function (name, extra) { report({greet: name + JSON.stringify(extra)}); }};
window.double = function (x) { return x * 2; };
window.later = function () { return new Promise(function (resolve) { setTimeout(function () { resolve({done: [1, 2]}); }, 100); }); };

async function main() {
  var out = {};
  out.add = await add(2, 3);
  out.float = await add(0.1, 0.2);
  out.user = await user("42");
  out.nothing = await nothing();
  out.where = await where();
  for (const name of ["boom", "notjson", "nan"]) {
    try { await window[name](); } catch (e) { out[name] = e instanceof Error ? e.message : String(e); }
  }
  report(out);
  await listen(function (text) { report({heard: text}); });
  ready();
}
main();
</script>
"""

adapter = HeadlessAdapter(size=(320, 200))
session = ui.Session(adapter, cache_path=tempfile.mkdtemp())
bridge = session.bridge
reports, callbacks, ready = [], [], []


def boom():
    raise ValueError("no good")


# Expose before session.start(). Arguments and results are JSON values.
bridge.expose("add", lambda a, b: a + b)
bridge.expose("user", lambda ident: {"id": ident, "name": "Ada", "tags": ["admin"]})
bridge.expose("nothing", lambda: None)
bridge.expose("where", lambda frame: frame.get_url(), with_frame=True)
bridge.expose("boom", boom)
bridge.expose("notjson", lambda: object())
bridge.expose("nan", lambda: float("nan"))
bridge.expose("report", lambda value: reports.append(value))
bridge.expose("listen", callbacks.append)                    # a function of the page arrives as a JsCallback
bridge.expose("ready", lambda: ready.append(True))

view = ui.BrowserView(adapter)


def on_ready():
    session.app.add_resource("http://app.test/index.html", PAGE)
    view.load_url("http://app.test/index.html")


view.on_ready = on_ready
session.start(view)
adapter.run_until(lambda: ready, "the page")
print("page -> Python:")
for key, value in reports[0].items():
    print("  %-8s %s" % (key, json.dumps(value)))
print("JsCallback:", type(callbacks[0]).__name__)

# Python -> page.
frame = view.browser.get_main_frame()
callbacks[0].call("hello from Python")
bridge.execute_function(frame, "api.greet", "Ada", {"k": [1, None]})
results = {}
for name, expression in [("double", "double(21)"), ("later", "later()"), ("object", "({a: [1, 2], b: 'x'})"),
                         ("undefined", "undefined"), ("syntax", "1 +"), ("thrown", "throw new RangeError('r')"),
                         ("nowhere", "missing.name")]:
    bridge.evaluate(frame, expression, lambda value, error, name=name: results.update({name: (value, error)}))
bridge.evaluate(frame, "new Promise(function () {})", lambda value, error: results.update(never=(value, error)), timeout=0.5)
adapter.run_until(lambda: len(results) == 8 and len(reports) == 3, "the answers")
print("Python -> page:")
for item in sorted(reports[1:], key=str):           # the two calls reach the page in either order
    print("  report:", item)
for name in ("double", "later", "object", "undefined", "syntax", "thrown", "nowhere", "never"):
    print("  evaluate %-9s %s" % (name, results[name]))

done = []
session.shutdown(done=lambda: done.append(1))
adapter.run_until(lambda: done, "shutdown")
