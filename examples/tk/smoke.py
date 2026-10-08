"""Runs the Tk example for real on a (virtual) X display, with real X events (xdotool), and checks what
a user would see (see ../common/checks.py). Also a drag inside the page, which the widget carries out itself.

    xvfb-run -a uv run python smoke.py [screenshot-directory]
"""

import os
import sys
import time

for name in ("WAYLAND_DISPLAY", "XDG_SESSION_TYPE"):
    os.environ.pop(name, None)

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "common"))

import browser  # noqa: E402
import checks  # noqa: E402


class Adapter:
    scale = 1

    def __init__(self, root, window):
        self.root, self.window, self.runtime = root, window, window.runtime
        self.view = window.view
        self.messages = window.messages
        self.clipboard_get = self._clipboard_get
        self.clipboard_set = self._clipboard_set

    def browser(self):
        return self.view.browser

    def spin(self, condition, what, timeout=30):
        end = time.time() + timeout
        while not condition():
            if time.time() > end:
                raise TimeoutError("timed out waiting for " + what)
            self.root.update()
            time.sleep(0.005)

    def settle(self, seconds=0.4):
        end = time.time() + seconds
        while time.time() < end:
            self.root.update()
            time.sleep(0.005)

    def origin(self):
        return self.view.winfo_rootx(), self.view.winfo_rooty()

    def window_id(self):
        return self.root.winfo_id()

    def view_size(self):
        return self.view.view_width, self.view.view_height

    def picture_size(self):
        return self.view.image.size if self.view.image is not None else (0, 0)

    def title(self):
        return self.root.title()

    def address(self):
        return self.window.entry.get()

    def can_go_back(self):
        return str(self.window.back.cget("state")) == "normal"

    def go_back(self):
        self.view.go_back()

    def popup_visible(self):
        return self.view.popup_visible and self.view.popup_image is not None

    def resize_window(self, width, height):
        self.root.geometry("%dx%d" % (width, height + 30))      # the toolbar takes about 30 pixels

    def snapshot(self, path):
        self.view.snapshot(path)

    def commit_text(self, text):
        self.view.commit_text(text)

    def set_preedit(self, text, cursor):
        self.view.set_preedit(text, cursor)

    def _clipboard_get(self):
        try:
            return self.root.selection_get(selection="CLIPBOARD")
        except Exception:
            return None

    def _clipboard_set(self, text):
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.root.update()

    def shutdown(self):
        done = []
        self.window.runtime.shutdown(lambda: done.append(True))
        self.spin(lambda: done or not self.runtime.started, "CEF to shut down", 20)

    def cef_running(self):
        return self.runtime.app.is_running

    # -- a drag inside the page, which the widget carries out itself --------------------------------

    def extra_checks(self, core):
        core.js("window.drops = []")
        x, y = core.rect_of("#src")
        core.drag(core.point(x, y), core.point(*core.rect_of("#zone")))
        drops = core.js("window.drops")
        core.check(drops == [{"text": "dragged-from-page", "files": []}], "dragging inside the page works (the widget carries the drag out)", drops)
        core.snapshot("10-dragged")


def main():
    shots = sys.argv[1] if len(sys.argv) > 1 else None
    root = browser.RootClass()
    holder = []
    runtime = browser.make_runtime(root, holder)
    window = browser.BrowserWindow(root, runtime, "demo")
    holder.append(window)
    adapter = Adapter(root, window)
    adapter.spin(lambda: window.view.winfo_width() > 100, "the window")
    root.after(0, window.start)
    adapter.spin(lambda: window.messages, "the page to call Python (appReady)")
    adapter.settle()
    sys.exit(checks.Checks(adapter, shots).run())


if __name__ == "__main__":
    main()
