"""Runs the Kivy example for real on a (virtual) X display, with real X events (xdotool), and checks what
a user would see (see ../common/checks.py). Also a drag inside the page (carried out by the widget) and the
drops of text and a file, which Kivy's window reports (here handed to the same handlers).

    xvfb-run -a uv run python smoke.py [screenshot-directory]
"""

import os
import sys
import tempfile
import time

os.environ["SDL_VIDEODRIVER"] = "x11"
for name in ("WAYLAND_DISPLAY", "XDG_SESSION_TYPE"):
    os.environ.pop(name, None)

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "common"))

import browser  # noqa: E402
import checks  # noqa: E402
from kivy.base import EventLoop, runTouchApp  # noqa: E402
from kivy.clock import Clock  # noqa: E402
from kivy.core.clipboard import Clipboard  # noqa: E402
from kivy.core.window import Window  # noqa: E402


class Adapter:
    scale = 1

    def __init__(self, window_owner):
        self.owner, self.runtime, self.view = window_owner, window_owner.runtime, window_owner.view
        self.messages = window_owner.messages
        self.clipboard_get = lambda: Clipboard.paste() or None
        self.clipboard_set = Clipboard.copy

    def _step(self):
        EventLoop.idle()                                  # one turn of Kivy's own loop: input, the clock, drawing
        EventLoop.window.mainloop()                       # and the events of SDL

    def browser(self):
        return self.view.browser

    def spin(self, condition, what, timeout=30):
        end = time.time() + timeout
        while not condition():
            if time.time() > end:
                raise TimeoutError("timed out waiting for " + what)
            self._step()
            time.sleep(0.003)

    def settle(self, seconds=0.4):
        end = time.time() + seconds
        while time.time() < end:
            self._step()
            time.sleep(0.003)

    def origin(self):
        x, y = self.view.screen_origin()
        return x * self.scale, y * self.scale

    def window_id(self):
        try:
            return int(Window.get_window_info().window)
        except Exception:
            return None

    def view_size(self):
        return int(self.view.width), int(self.view.height)

    def picture_size(self):
        return self.view.picture

    def title(self):
        return self.owner.title

    def address(self):
        return self.owner.entry.text

    def can_go_back(self):
        return not self.owner.back.disabled

    def go_back(self):
        self.view.go_back()

    def popup_visible(self):
        return self.view.popup_visible and self.view.popup_texture is not None

    def resize_window(self, width, height):
        Window.size = (width, height + 36)                # the toolbar takes 36 pixels

    def snapshot(self, path):
        self.view.snapshot(path)

    def commit_text(self, text):
        self.view.commit_text(text)

    def set_preedit(self, text, cursor):
        self.view.set_preedit(text, cursor)

    def shutdown(self):
        done = []
        self.runtime.shutdown(lambda: done.append(True))
        self.spin(lambda: done or not self.runtime.started, "CEF to shut down", 20)

    def cef_running(self):
        return self.runtime.app.is_running

    # -- a drag inside the page, and drops from another program -------------------------------------

    def extra_checks(self, core):
        core.js("window.drops = []")
        x, y = core.rect_of("#src")
        core.drag(core.point(x, y), core.point(*core.rect_of("#zone")))
        drops = core.js("window.drops")
        core.check(drops == [{"text": "dragged-from-page", "files": []}], "dragging inside the page works (the widget carries the drag out)", drops)
        # What the window reports for a drop from another program, at the window position of the drop zone
        # (y downwards, as SDL gives it); a real XDND drag needs a second window, see the README.
        zx, zy = core.rect_of("#zone")
        wx_, wy_ = self.view.x + zx, (Window.height - self.view.top) + zy
        core.js("window.drops = []")
        self.view._on_drop_begin(Window, wx_, wy_)
        self.view._on_drop_text(Window, "from-another-program", wx_, wy_)
        self.settle(0.8)
        drops = core.js("window.drops")
        core.check(drops == [{"text": "from-another-program", "files": []}], "a text drop (on_drop_text) reaches the page", drops)
        info = core.js("document.getElementById('dropinfo').textContent")
        core.check(info == 'dropped text "from-another-program"', "the page shows what was dropped", info)
        temporary = tempfile.NamedTemporaryFile(suffix=".txt", prefix="dropped-", delete=False)
        temporary.close()
        core.js("window.drops = []")
        self.view._on_drop_file(Window, temporary.name.encode(), wx_, wy_)
        self.settle(0.8)
        drops = core.js("window.drops")
        core.check(len(drops) == 1 and drops[0]["files"] == [os.path.basename(temporary.name)], "a file drop (on_drop_file) reaches the page",
                   (drops, os.path.basename(temporary.name)))
        os.unlink(temporary.name)
        core.snapshot("10-dragged")


def main():
    shots = sys.argv[1] if len(sys.argv) > 1 else None
    owner = browser.Browser("demo")
    runTouchApp(owner.root, embedded=True)
    adapter = Adapter(owner)
    adapter.spin(lambda: owner.view.width > 100, "the window")
    Clock.schedule_once(lambda dt: owner.start(), 0)
    adapter.spin(lambda: owner.messages, "the page to call Python (appReady)")
    adapter.settle()
    code = checks.Checks(adapter, shots).run()
    sys.exit(code)


if __name__ == "__main__":
    main()
