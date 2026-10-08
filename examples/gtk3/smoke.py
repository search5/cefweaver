"""Runs the GTK 3 example for real on a (virtual) X display and checks what a user would see:
the page is drawn, the mouse and the keys reach it, Hangul can be composed, the page calls
Python and Python calls the page, a <select> popup is drawn, the wheel scrolls, links and
history work, the window resizes the page, and everything shuts down.

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

# 9. shutdown
done = []
window.on_delete(None, None)
runtime.shutdown_done = done
GLib.timeout_add(50, lambda: Gtk.main_quit() if False else True)
spin(lambda: not runtime.started, "CEF to shut down", 20)
check(not runtime.app.is_running, "the browser is closed and CEF is shut down")

print("ALL OK" if not failures else "FAILED: %s" % ", ".join(failures))
sys.exit(1 if failures else 0)
