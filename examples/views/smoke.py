"""Runs the Views example for real on a (virtual) X display, with real X events (xdotool), and checks what a user
would see: the window and its title, the toolbar and the browser in their places, a click in the address field, typing
an address and Return, the Back, Forward and Reload buttons, and the close of the window.

    env -u WAYLAND_DISPLAY -u XDG_SESSION_TYPE xvfb-run -a -s "-screen 0 1280x1024x24" uv run python smoke.py [screenshot-directory]
"""

import os
import subprocess
import sys
import time

for name in ("WAYLAND_DISPLAY", "XDG_SESSION_TYPE"):
    os.environ.pop(name, None)

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from browser import ADDRESS, BACK, FORWARD, RELOAD, ViewsBrowser  # noqa: E402

FIRST = "data:text/html,<title>first</title><h1>first</h1>"
SECOND = "data:text/html,<title>second</title><h1>second</h1>"
SHOTS = sys.argv[1] if len(sys.argv) > 1 else None

titles = []
failed = []
app = ViewsBrowser(FIRST, title_changed=titles.append)


def spin(condition, what, timeout=30):
    end = time.time() + timeout
    while not condition():
        if time.time() > end:
            raise TimeoutError("timed out waiting for " + what)
        app.step(0.005)


def settle(seconds=0.5):
    end = time.time() + seconds
    while time.time() < end:
        app.step(0.005)


def check(ok, what, detail=None):
    print(("ok    " if ok else "FAIL  ") + what + ("" if ok or detail is None else "   [%r]" % (detail,)), flush=True)
    if not ok:
        failed.append(what)


def xdotool(*args):
    subprocess.run(["xdotool"] + [str(a) for a in args], check=True)


def center(view):
    x, y, width, height = view.get_bounds_in_screen()
    return x + width // 2, y + height // 2


def click(view):
    x, y = center(view)
    xdotool("mousemove", x, y)
    time.sleep(0.15)
    xdotool("click", "1")
    settle(0.3)


def shot(name):
    if SHOTS:
        os.makedirs(SHOTS, exist_ok=True)
        subprocess.run(["import", "-window", "root", os.path.join(SHOTS, name + ".png")], check=False)


def send_delete_window(window):
    """Ask a window to close, as the close button does (WM_DELETE_WINDOW), without a window manager."""
    import ctypes
    x = ctypes.CDLL("libX11.so.6")
    x.XOpenDisplay.restype = ctypes.c_void_p
    x.XInternAtom.restype = ctypes.c_ulong
    x.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
    x.XSendEvent.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_long, ctypes.c_void_p]

    class Message(ctypes.Structure):
        _fields_ = [("type", ctypes.c_int), ("serial", ctypes.c_ulong), ("send_event", ctypes.c_int),
                    ("display", ctypes.c_void_p), ("window", ctypes.c_ulong), ("message_type", ctypes.c_ulong),
                    ("format", ctypes.c_int), ("data", ctypes.c_long * 5)]

    class Event(ctypes.Union):
        _fields_ = [("message", Message), ("pad", ctypes.c_long * 24)]
    display = x.XOpenDisplay(None)
    event = Event()
    event.message.type, event.message.window, event.message.format = 33, window, 32      # ClientMessage
    event.message.message_type = x.XInternAtom(display, b"WM_PROTOCOLS", 0)
    event.message.data[0] = x.XInternAtom(display, b"WM_DELETE_WINDOW", 0)
    x.XSendEvent(display, window, 0, 0, ctypes.byref(event))
    x.XFlush(display)


app.start()
spin(lambda: "first" in titles and app.window is not None and app.browser() is not None, "the first page")
settle(1.0)
window, browser_view = app.window, app.browser_view
check(window.is_visible() and window.get_title() == "first", "the window shows the title of the page", window.get_title())
shot("1-page")

view = lambda number: window.get_view_for_id(number)        # noqa: E731
back, forward, reload_, address = view(BACK), view(FORWARD), view(RELOAD), view(ADDRESS)
bounds = {n: v.get_bounds_in_screen() for n, v in (("back", back), ("forward", forward), ("reload", reload_),
                                                    ("address", address), ("browser", browser_view))}
check(bounds["back"][0] < bounds["forward"][0] < bounds["reload"][0] < bounds["address"][0],
      "the buttons and the address field are in a row, left to right", bounds)
check(bounds["back"][1] == bounds["forward"][1] == bounds["address"][1], "the row is one line", bounds)
check(bounds["browser"][1] >= bounds["address"][1] + bounds["address"][3], "the browser is below the toolbar", bounds)
check(bounds["address"][2] > 3 * bounds["back"][2], "the address field takes the width that is left", bounds)
check(address.get_text() == FIRST, "the address field shows the address of the page", address.get_text())

# an address typed into the field, then Return: real mouse and keyboard events
click(address)
xdotool("key", "ctrl+a")
time.sleep(0.2)
xdotool("type", "--delay", "30", SECOND)
time.sleep(0.2)
settle(0.3)
check(address.get_text() == SECOND, "typing in the address field changes its text", address.get_text())
shot("2-typed")
xdotool("key", "Return")
spin(lambda: "second" in titles, "the second page")
check(window.get_title() == "second", "Return in the address field loads the page", window.get_title())

click(back)
spin(lambda: titles[-1] == "first", "Back")
check(window.get_title() == "first" and address.get_text() == FIRST, "the Back button goes back", (window.get_title(), address.get_text()))
click(forward)
spin(lambda: titles[-1] == "second", "Forward")
check(window.get_title() == "second" and address.get_text() == SECOND, "the Forward button goes forward", (window.get_title(), address.get_text()))
count = len(titles)
click(reload_)
settle(1.0)
check(app.browser().get_main_frame().get_url() == SECOND and window.is_visible(), "the Reload button reloads the same page")
shot("3-after-buttons")

# the close button of a window: WM_DELETE_WINDOW (there is no window manager here)
ids = subprocess.run(["xdotool", "search", "--onlyvisible", "--pid", str(os.getpid())], capture_output=True, text=True).stdout.split()
check(bool(ids), "the window is an X window of this process", ids)
send_delete_window(int(ids[0]))
spin(lambda: app.done, "the window to be destroyed")
app.app.shutdown()
check(True, "the window is closed and CEF is shut down")
print("ALL OK" if not failed else "FAILED: " + ", ".join(failed))
sys.exit(1 if failed else 0)
