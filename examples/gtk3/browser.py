"""A small browser: the CefWidget in a GTK 3 window, with a toolbar and a demo page.

    uv sync                                  # once (see README.md)
    uv run python browser.py                 # the demo page
    uv run python browser.py https://example.org/

The demo page ("demo" or http://demo.test/) calls Python through cefweaver.JavascriptBridge:
``add(a, b)`` and ``appReady(info)``; Python calls the page back with ``bridge.evaluate()``.
"""

import argparse
import os
import platform
import sys
import tempfile

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk  # noqa: E402

from cefgtk import CefWidget, Runtime  # noqa: E402

DEMO_URL = "http://demo.test/"
DEMO_PAGE = """<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>cefweaver GTK 3</title>
<style>
 body { font: 16px/1.4 sans-serif; margin: 16px; background: #fafafa; }
 #log { white-space: pre; background: #eef; padding: 8px; min-height: 3em; }
 .tall { height: 1400px; background: linear-gradient(#fff, #cde); margin-top: 16px; padding: 8px; }
</style></head><body>
<h1>cefweaver in GTK 3</h1>
<p><input id="text" placeholder="type here (한글 입력도)" size="30">
 <button id="add" onclick="calc()">2 + 3 in Python</button>
 <select id="fruit"><option>apple</option><option>banana</option><option>cherry</option></select>
 <a id="link" href="http://demo.test/other">a link</a></p>
<div id="log">waiting for Python...</div>
<p id="para">Selectable paragraph text</p>
<p><textarea id="area" rows="2" cols="28" placeholder="paste here"></textarea>
 <span id="src" draggable="true" style="display:inline-block;padding:6px;background:#fe9;border:1px solid #cb5">drag me</span>
 <span id="zone" style="display:inline-block;padding:6px 20px;background:#9fe;border:1px solid #5cb">drop zone</span></p>
<div class="tall">scroll me (device pixel ratio: <b id="dpr"></b>)</div>
<script>
 function log(text) { document.getElementById("log").textContent += text + "\\n"; }
 function calc() { add(2, 3).then(function (sum) { log("add(2, 3) = " + sum); }); }
 document.getElementById("dpr").textContent = window.devicePixelRatio;
 appReady({dpr: window.devicePixelRatio, width: innerWidth, agent: navigator.userAgent})
   .then(function (answer) { document.getElementById("log").textContent = answer + "\\n"; });
 window.fromPython = function (message) { log("from Python: " + message); return message.length; };
 window.drops = [];
 document.getElementById("src").addEventListener("dragstart", function (e) { e.dataTransfer.setData("text/plain", "dragged-from-page"); });
 var zone = document.getElementById("zone");
 // a drop zone cancels dragenter as well as dragover (the HTML drag and drop rules)
 ["dragenter", "dragover"].forEach(function (name) { zone.addEventListener(name, function (e) { e.preventDefault(); }); });
 zone.addEventListener("drop", function (e) {
   e.preventDefault();
   window.drops.push({text: e.dataTransfer.getData("text/plain"), files: Array.prototype.map.call(e.dataTransfer.files, function (f) { return f.name; })});
 });
 window.compositions = [];
 ["compositionstart", "compositionupdate", "compositionend"].forEach(function (name) {
   document.getElementById("text").addEventListener(name, function (e) { window.compositions.push(name + ":" + e.data); });
 });
</script></body></html>"""


class BrowserWindow(Gtk.Window):
    def __init__(self, runtime, url):
        super().__init__(title="cefweaver GTK 3")
        self.runtime = runtime
        self.start_url = url
        self.set_default_size(900, 640)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        bar = Gtk.Box(spacing=4)
        self.back = Gtk.Button.new_from_icon_name("go-previous", Gtk.IconSize.BUTTON)
        self.forward = Gtk.Button.new_from_icon_name("go-next", Gtk.IconSize.BUTTON)
        self.reload_button = Gtk.Button.new_from_icon_name("view-refresh", Gtk.IconSize.BUTTON)
        self.entry = Gtk.Entry()
        for widget in (self.back, self.forward, self.reload_button):
            bar.pack_start(widget, False, False, 0)
        bar.pack_start(self.entry, True, True, 0)
        self.view = CefWidget(runtime)
        box.pack_start(bar, False, False, 4)
        box.pack_start(self.view, True, True, 0)
        self.add(box)
        self.back.connect("clicked", lambda b: self.view.go_back())
        self.forward.connect("clicked", lambda b: self.view.go_forward())
        self.reload_button.connect("clicked", lambda b: self.view.reload())
        self.entry.connect("activate", lambda e: self.view.load_url(self.address(e.get_text())))
        self.view.connect("title-changed", lambda w, title: self.set_title(title or "cefweaver GTK 3"))
        self.view.connect("address-changed", lambda w, url: self.entry.set_text(url))
        self.view.connect("loading-changed", self.on_loading)
        self.view.connect("browser-ready", self.on_ready)
        self.connect("delete-event", self.on_delete)
        self.back.set_sensitive(False)
        self.forward.set_sensitive(False)
        self.messages = []                              # what the page told Python (the smoke test reads it)

    @staticmethod
    def address(text):
        text = text.strip()
        if text == "demo":
            return DEMO_URL
        return text if "://" in text or text.startswith(("about:", "data:")) else "https://" + text

    def on_loading(self, widget, loading, can_back, can_forward):
        self.back.set_sensitive(can_back)
        self.forward.set_sensitive(can_forward)

    def on_ready(self, widget):
        app = self.runtime.app
        app.add_resource(DEMO_URL, DEMO_PAGE)
        app.add_resource(DEMO_URL + "other", "<h1>another page</h1><a href='/'>back</a>")
        self.view.load_url(self.address(self.start_url))

    def on_delete(self, widget, event):
        self.runtime.shutdown(Gtk.main_quit)             # the window goes when CEF has closed the browser
        return True

    def start(self):
        self.runtime.start(self.view, "about:blank")


def make_runtime():
    # CEFGTK_SWITCHES="name=value;name=value" gives Chromium command line switches
    text = os.environ.get("CEFGTK_SWITCHES", "")
    switches = [tuple(item.split("=", 1)) if "=" in item else (item, "") for item in text.split(";") if item]
    runtime = Runtime(switches, cache_path=tempfile.mkdtemp(prefix="cefweaver-gtk-"))
    window_holder = []

    def add(a, b):
        return a + b

    def app_ready(info):
        window_holder[0].messages.append(("ready", info))
        return "Python %s on %s: the page is %d px wide at %sx" % (
            platform.python_version(), platform.system(), info["width"], info["dpr"])

    runtime.bridge.expose("add", add)
    runtime.bridge.expose("appReady", app_ready)
    runtime.window_holder = window_holder
    return runtime


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("url", nargs="?", default="demo", help='an address, or "demo"')
    args = parser.parse_args(argv)
    runtime = make_runtime()
    window = BrowserWindow(runtime, args.url)
    runtime.window_holder.append(window)
    window.show_all()
    GLib.idle_add(lambda: window.start() or False)
    Gtk.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
