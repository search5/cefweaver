"""The smallest program that shows a page in a GTK 3 window.   uv run python quickstart.py [address]"""

import sys

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk  # noqa: E402

from cefweaver import ui  # noqa: E402
from cefweaver.ui.toolkits.gtk3 import CefWidget, GlibLoop  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else "https://example.org/"

session = ui.Session(GlibLoop())                      # CEF, run by the GLib loop
widget = CefWidget(session)                           # the browser, a Gtk.DrawingArea
widget.connect("browser-ready", lambda w: w.load_url(URL))
widget.connect("title-changed", lambda w, title: print("title:", title, flush=True))
window = Gtk.Window(title="cefweaver")
window.set_default_size(900, 640)
window.add(widget)
window.connect("delete-event", lambda w, e: session.shutdown(Gtk.main_quit) or True)   # close the browser first
window.show_all()


def start():
    session.start(widget)
    return False


GLib.idle_add(start)
Gtk.main()
