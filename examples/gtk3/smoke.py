"""Runs the GTK 3 example for real on a (virtual) X display and checks what a user would see:
the page is drawn, the mouse and the keys reach it, Hangul can be composed, the page calls
Python and Python calls the page, a <select> popup is drawn, the wheel scrolls, links and
history work, the window resizes the page, copy, cut and paste go through the GTK clipboard,
text and files are dropped on the page and elements of the page are dragged out of it and
within it, and everything shuts down.

    xvfb-run -a uv run python smoke.py [screenshot-directory]      # GDK_SCALE=2 for a HiDPI run

The mouse and the keys are real X events (xdotool), so GTK's own event handling and input
method are on the way. Exit code 0 and "ALL OK" at the end mean it works.
"""

import os
import shutil
import subprocess
import sys
import time

os.environ.setdefault("GDK_BACKEND", "x11")

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GdkX11", "3.0")
from gi.repository import Gdk, GdkX11, GLib, Gtk  # noqa: E402,F401

import browser  # noqa: E402
from cefweaver import ui  # noqa: E402

failures = []
shots = sys.argv[1] if len(sys.argv) > 1 else None


def check(condition, what, detail=""):
    print("%s  %s%s" % ("ok  " if condition else "FAIL", what, ("   [" + str(detail) + "]") if detail and not condition else ""))
    if not condition:
        failures.append(what)


def spin(condition, what, timeout=30):
    end = time.time() + timeout
    while not condition():
        if time.time() > end:
            raise TimeoutError("timed out waiting for " + what)
        while Gtk.events_pending():
            Gtk.main_iteration()
        time.sleep(0.005)


def settle(seconds=0.4):
    end = time.time() + seconds
    while time.time() < end:
        while Gtk.events_pending():
            Gtk.main_iteration()
        time.sleep(0.005)


def xdo(*args):
    subprocess.run(["xdotool"] + [str(a) for a in args], check=True)


runtime = browser.make_runtime()
window = browser.BrowserWindow(runtime, "demo")
runtime.window_holder.append(window)
view = window.view
window.show_all()
spin(lambda: view.get_window() is not None, "the widget window")
GLib.idle_add(lambda: window.start() or False)
spin(lambda: window.messages, "the page to call Python (appReady)")
settle()


def js(expression, timeout=10):
    box = []
    runtime.bridge.evaluate(view.browser.get_main_frame(), expression, lambda v, e: box.append((v, e)))
    spin(lambda: box, "the value of " + expression, timeout)
    value, error = box[0]
    if error:
        raise RuntimeError("%s: %s" % (expression, error))
    return value


def snapshot(name):
    if shots:
        os.makedirs(shots, exist_ok=True)
        view.snapshot(os.path.join(shots, name + ".png"))


def origin():
    _, x, y = view.get_window().get_origin()
    return x, y


def point(x, y):
    """Where xdotool has to put the pointer for a point of the page: GTK counts in logical pixels,
    the X server (and so xdotool) in device pixels."""
    ox, oy = origin()
    scale = view.get_scale_factor()
    return int((ox + x) * scale), int((oy + y) * scale)


def rect_of(selector):
    r = js("(function(){var r = document.querySelector(%r).getBoundingClientRect(); return [r.x, r.y, r.width, r.height];})()" % selector)
    return r[0] + r[2] / 2, r[1] + r[3] / 2


def click(selector):
    x, y = rect_of(selector)
    xdo("mousemove", *point(x, y))
    settle(0.1)
    xdo("click", 1)
    settle(0.3)


scale = view.get_scale_factor()
xid = view.get_window().get_xid() if hasattr(view.get_window(), "get_xid") else None
xdo("windowfocus", window.get_window().get_xid())
settle()
view.grab_focus()
settle()

# 1. the page is drawn
ready = window.messages[0][1]
check(view.surface is not None and view.surface.get_width() == view.view_width * scale, "the picture has the size of the widget",
      (view.surface and view.surface.get_width(), view.view_width, scale))
check(ready["dpr"] == scale, "the page sees the device pixel ratio of the screen (%dx)" % scale, ready["dpr"])
check(js("document.title") == "cefweaver GTK 3" and window.get_title() == "cefweaver GTK 3", "the title reaches the window", window.get_title())
check("Python" in js("document.getElementById('log').textContent"), "Python's answer to appReady() is in the page")
snapshot("1-page")

# 2. the mouse and the keyboard
click("#text")
check(js("document.activeElement.id") == "text", "a click focuses the input of the page")
xdo("type", "--delay", 40, "hello")
settle(0.5)
check(js("document.getElementById('text').value") == "hello", "typed keys reach the input", js("document.getElementById('text').value"))
xdo("key", "BackSpace")
settle(0.3)
check(js("document.getElementById('text').value") == "hell", "BackSpace edits it")
xdo("key", "ctrl+a")
settle(0.2)
snapshot("2-typed")

# 3. Hangul through the input method (the commit and preedit signals of Gtk.IMContext)
view.set_preedit("하", 1)
settle(0.4)
view.set_preedit("한", 1)
settle(0.3)
view.commit_text("한")
view.set_preedit("", 0)
settle(0.5)
value = js("document.getElementById('text').value")
check("한" in value, "composed Hangul is committed into the input", value)
compositions = js("window.compositions")
check(any(c.startswith("compositionupdate:") for c in compositions), "the page sees the composition", compositions)
snapshot("3-hangul")

# 4. the page calls Python and Python calls the page
click("#add")
spin(lambda: "= 5" in js("document.getElementById('log').textContent"), "add(2, 3) = 5 in the page")
check(True, "the page calls Python (add) and shows the answer")
answers = []
runtime.bridge.evaluate(view.browser.get_main_frame(), "fromPython('hello from Python')", lambda v, e: answers.append((v, e)))
spin(lambda: answers, "the answer of fromPython")
check(answers == [(len("hello from Python"), None)], "Python calls a function of the page and gets its value", answers)

# 5. the popup of a <select> is drawn as a second element
click("#fruit")
spin(lambda: view.popup_visible, "the popup of the select", 10)
settle(0.5)
check(view.popup_surface is not None and view.popup_rect is not None and view.popup_rect.width > 0,
      "the popup of a select is drawn", view.popup_rect)
snapshot("5-popup")
xdo("key", "Escape")
settle(0.5)
check(not view.popup_visible, "Escape closes the popup")

# 6. the wheel
before = js("window.scrollY")
x, y = rect_of("#log")                   # inside the visible part of the page
xdo("mousemove", *point(x, y))
for _ in range(5):
    xdo("click", 5)
    settle(0.15)
settle(0.5)
after = js("window.scrollY")
check(before == 0 and after > 0, "the wheel scrolls the page", (before, after))
snapshot("6-scrolled")

# 7. links and history
js("window.scrollTo(0, 0)")
settle(0.3)
click("#link")
spin(lambda: "other" in window.entry.get_text(), "the address of the other page", 10)
check(window.entry.get_text().endswith("/other"), "a click on a link navigates and the address bar follows", window.entry.get_text())
spin(lambda: window.back.get_sensitive(), "the back button")
check(window.back.get_sensitive(), "the back button is on")
view.go_back()
spin(lambda: window.entry.get_text() == browser.DEMO_URL, "the address after back", 10)
check(window.entry.get_text() == browser.DEMO_URL, "back returns to the first page")
settle(0.5)

# 8. the window size is the size of the page
width_before = js("innerWidth")
window.resize(700, 500)
try:
    spin(lambda: js("innerWidth") != width_before, "the page to change its width", 10)
except TimeoutError:
    print("resize diagnostics: widget", view.view_width, view.view_height, "window", window.get_size(), "innerWidth", js("innerWidth"))
    raise
check(js("innerWidth") == view.view_width, "resizing the window resizes the page", (js("innerWidth"), view.view_width))
snapshot("8-resized")

# 9. copy, cut and paste through the GTK clipboard
clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)


def clipboard_text(expected, timeout=5):
    try:
        spin(lambda: clipboard.wait_for_text() == expected, "the clipboard to hold %r" % expected, timeout)
        return True
    except TimeoutError:
        return False


window.resize(900, 700)
settle(1.0)
click("#text")
xdo("key", "ctrl+a")
xdo("type", "--delay", 40, "copy me")
settle(0.4)
xdo("key", "ctrl+a")
settle(0.4)
xdo("key", "ctrl+c")
check(clipboard_text("copy me"), "Ctrl+C copies the selection of an input to the GTK clipboard", clipboard.wait_for_text())
xdo("key", "ctrl+x")
settle(0.5)
check(js("document.getElementById('text').value") == "" and clipboard_text("copy me"), "Ctrl+X cuts it (the input is empty)",
      js("document.getElementById('text').value"))
clipboard.set_text("붙여넣기 text", -1)
click("#area")
xdo("key", "ctrl+v")
settle(0.6)
check(js("document.getElementById('area').value") == "붙여넣기 text", "Ctrl+V pastes the clipboard (Hangul too) into a textarea",
      js("document.getElementById('area').value"))
xdo("key", "ctrl+a")
xdo("key", "BackSpace")
settle(0.3)
x, y = rect_of("#para")
xdo("mousemove", *point(x, y))
settle(0.1)
xdo("click", "--repeat", 3, "--delay", 60, 1)
settle(0.6)
xdo("key", "ctrl+c")
check(clipboard_text("Selectable paragraph text") or "Selectable paragraph text" in (clipboard.wait_for_text() or ""),
      "Ctrl+C copies selected text of the page (not editable)", clipboard.wait_for_text())
snapshot("9-clipboard")

# 10. drag and drop. A drag source and a drop target of GTK sit under the page.
import tempfile                                   # noqa: E402

box = window.get_child()
source = Gtk.EventBox()
source.add(Gtk.Label(label="  drag text from GTK  "))
source.drag_source_set(Gdk.ModifierType.BUTTON1_MASK, [Gtk.TargetEntry.new("text/plain", 0, 0)], Gdk.DragAction.COPY)
source.connect("drag-data-get", lambda w, ctx, data, info, t: data.set_text("from-gtk", -1))
file_source = Gtk.EventBox()
file_source.add(Gtk.Label(label="  drag a file from GTK  "))
file_source.drag_source_set(Gdk.ModifierType.BUTTON1_MASK, [Gtk.TargetEntry.new("text/uri-list", 0, 0)], Gdk.DragAction.COPY)
temporary = tempfile.NamedTemporaryFile(suffix=".txt", prefix="dragged-", delete=False)
temporary.write(b"file body")
temporary.close()
file_source.connect("drag-data-get", lambda w, ctx, data, info, t: data.set_uris([GLib.filename_to_uri(temporary.name)]))
target = Gtk.Entry()
target.set_placeholder_text("drop text from the page here")
row = Gtk.Box(spacing=8)
for widget in (source, file_source, target):
    row.pack_start(widget, True, True, 4)
box.pack_end(row, False, False, 6)
row.show_all()
settle(1.0)


def center_of(widget):
    """The middle of a widget in the device pixels of the X server (for xdotool)."""
    allocation = widget.get_allocation()
    top = widget.get_toplevel()
    _, base_x, base_y = top.get_window().get_origin()
    x, y = widget.translate_coordinates(top, allocation.width // 2, allocation.height // 2)
    scale = widget.get_scale_factor()
    return int((base_x + x) * scale), int((base_y + y) * scale)


def drag(start, end):
    """A real drag with the pointer: press, move in small steps (GTK starts a drag after a few pixels), release."""
    xdo("mousemove", *start)
    settle(0.2)
    xdo("mousedown", 1)
    settle(0.2)
    sx, sy = start
    ex, ey = end
    for step in range(1, 13):
        xdo("mousemove", sx + (ex - sx) * step // 12, sy + (ey - sy) * step // 12)
        settle(0.08)
    settle(0.3)
    xdo("mouseup", 1)
    settle(0.8)


def zone_point():
    x, y = rect_of("#zone")
    return point(x, y)


# 10a. text from GTK into the page
js("window.drops = []")
drag(center_of(source), zone_point())
drops = js("window.drops")
check(drops == [{"text": "from-gtk", "files": []}], "text dragged from GTK is dropped on the page", drops)
info = js("document.getElementById('dropinfo').textContent")
check(info == 'dropped text "from-gtk"', "the page shows what was dropped (so that the drop zone can be tried by hand)", info)
# 10b. a file from GTK into the page
js("window.drops = []")
drag(center_of(file_source), zone_point())
drops = js("window.drops")
check(len(drops) == 1 and drops[0]["files"] == [os.path.basename(temporary.name)], "a file dragged from GTK is dropped on the page",
      (drops, os.path.basename(temporary.name)))
# 10c. an element of the page into a GTK widget
x, y = rect_of("#src")
drag(point(x, y), center_of(target))
check(target.get_text() == "dragged-from-page", "an element dragged out of the page is dropped on a GTK entry", target.get_text())
# 10d. an element of the page onto another place of the page
js("window.drops = []")
x, y = rect_of("#src")
drag(point(x, y), zone_point())
drops = js("window.drops")
check(drops == [{"text": "dragged-from-page", "files": []}], "dragging inside the page works (the widget is source and target)", drops)
snapshot("10-dragged")

# 11. the context menu of the page: a real right click, a real click on an item of the application, and leaving the menu
mine, shown = [], []
adapter = view.view.adapter
original_show = adapter.show_menu
adapter.show_menu = lambda items, x, y, done: (shown.append((x, y, [i.label for i in items])), original_show(items, x, y, done))[1]
view.view.on_context_menu = lambda info, items: items + [ui.menu.MenuItem("Smoke item", action=lambda: mine.append("run"))]
x, y = rect_of("#para")
xdo("mousemove", *point(x, y))
settle(0.2)
xdo("click", 3)
spin(lambda: shown and adapter.last_menu.get_visible(), "the context menu")
check(len(shown) == 1 and "Smoke item" in shown[0][2], "a right click shows the menu of the page with the item of the application", shown)
item = next(c for c in adapter.last_menu.get_children() if isinstance(c, Gtk.MenuItem) and c.get_label() == "Smoke item")
xdo("mousemove", *center_of(item))
settle(0.2)
xdo("click", 1)
spin(lambda: mine, "the action of the menu item")
check(mine == ["run"], "clicking an item of the application runs its action", mine)
settle(0.3)
check(not adapter.last_menu.get_visible(), "the menu closes after the pick")
snapshot("11-menu")
xdo("mousemove", *point(x, y))
settle(0.2)
xdo("click", 3)
spin(lambda: len(shown) == 2 and adapter.last_menu.get_visible(), "the context menu again")
xdo("key", "Escape")
spin(lambda: not adapter.last_menu.get_visible(), "the menu to close with Escape")
settle(0.3)
check(mine == ["run"], "leaving the menu with Escape picks nothing", mine)
xdo("mousemove", *point(x, y))
settle(0.2)
xdo("click", 3)
spin(lambda: len(shown) == 3 and adapter.last_menu.get_visible(), "the menu after it was left")
check(js("1 + 1") == 2, "the page still answers after a menu was left")
xdo("key", "Escape")
settle(0.3)
view.view.on_context_menu = None
os.unlink(temporary.name)

# 9. shutdown
done = []
window.on_delete(None, None)
runtime.shutdown_done = done
GLib.timeout_add(50, lambda: Gtk.main_quit() if False else True)
spin(lambda: not runtime.started, "CEF to shut down", 20)
check(not runtime.app.is_running, "the browser is closed and CEF is shut down")

print("ALL OK" if not failures else "FAILED: %s" % ", ".join(failures))
sys.exit(1 if failures else 0)
