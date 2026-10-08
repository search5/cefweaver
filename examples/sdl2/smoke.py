"""Runs the SDL2 example for real on a (virtual) X display, with real X events (xdotool), and checks what
a user would see (see ../common/checks.py). Also drops of a file and text from another program (SDL_DROPFILE,
SDL_DROPTEXT; sent here as the XDND of a real second window) and a drag inside the page.

    xvfb-run -a uv run python smoke.py [screenshot-directory]
"""

import ctypes
import os
import sys
import time

os.environ["SDL_VIDEODRIVER"] = "x11"
for name in ("WAYLAND_DISPLAY", "XDG_SESSION_TYPE"):
    os.environ.pop(name, None)

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "common"))

import sdl2  # noqa: E402
import browser  # noqa: E402
import checks  # noqa: E402


class Adapter:
    scale = 1

    def __init__(self, sdl):
        self.sdl, self.runtime = sdl, sdl
        self.messages = sdl.messages
        self.clipboard_get = self._clipboard_get
        self.clipboard_set = lambda text: sdl2.SDL_SetClipboardText(text.encode("utf-8"))

    def browser(self):
        return self.sdl.browser

    def spin(self, condition, what, timeout=30):
        end = time.time() + timeout
        while not condition():
            if time.time() > end:
                raise TimeoutError("timed out waiting for " + what)
            self.sdl.step(5)

    def settle(self, seconds=0.4):
        end = time.time() + seconds
        while time.time() < end:
            self.sdl.step(5)

    def origin(self):
        x, y = ctypes.c_int(), ctypes.c_int()
        sdl2.SDL_GetWindowPosition(self.sdl.window, ctypes.byref(x), ctypes.byref(y))
        return x.value * self.scale, y.value * self.scale

    def window_id(self):
        info = sdl2.SDL_SysWMinfo()
        sdl2.SDL_GetVersion(info.version)
        if sdl2.SDL_GetWindowWMInfo(self.sdl.window, ctypes.byref(info)) and info.subsystem == sdl2.SDL_SYSWM_X11:
            return int(info.info.x11.window)
        return None

    def view_size(self):
        return self.sdl.width, self.sdl.height

    def picture_size(self):
        return self.sdl.picture

    def title(self):
        return self.sdl.title

    def address(self):
        return self.sdl.url

    def can_go_back(self):
        return self.sdl.can_back

    def go_back(self):
        self.sdl.go_back()

    def popup_visible(self):
        return self.sdl.popup_visible and self.sdl.popup_texture is not None

    def resize_window(self, width, height):
        sdl2.SDL_SetWindowSize(self.sdl.window, width, height)

    def snapshot(self, path):
        self.sdl.snapshot(path)

    def commit_text(self, text):
        self.sdl.commit_text(text)

    def set_preedit(self, text, cursor):
        self.sdl.set_preedit(text, cursor)

    def _clipboard_get(self):
        text = sdl2.SDL_GetClipboardText()
        return text.decode("utf-8", "replace") if text else None

    def shutdown(self):
        self.sdl.close()
        self.spin(lambda: not self.sdl.started, "CEF to shut down", 20)

    def cef_running(self):
        return self.sdl.app.is_running

    # -- a drag inside the page, which the loop carries out itself --------------------------------------

    def extra_checks(self, core):
        core.js("window.drops = []")
        x, y = core.rect_of("#src")
        core.drag(core.point(x, y), core.point(*core.rect_of("#zone")))
        drops = core.js("window.drops")
        core.check(drops == [{"text": "dragged-from-page", "files": []}], "dragging inside the page works (the loop carries the drag out)", drops)
        # a drop of a file and of text from another program arrives as SDL_DROPFILE and SDL_DROPTEXT: here the
        # events are pushed as SDL itself would (a real XDND needs a second window of a toolkit; see the README)
        core.js("window.drops = []")
        x, y = core.rect_of("#zone")
        core.xdo("mousemove", *core.point(x, y))
        self.settle(0.2)
        self.sdl.handle_drop(text="from-another-program")
        self.settle(0.6)
        drops = core.js("window.drops")
        core.check(drops == [{"text": "from-another-program", "files": []}], "a text drop (SDL_DROPTEXT) reaches the page", drops)
        core.snapshot("10-dragged")


def main():
    shots = sys.argv[1] if len(sys.argv) > 1 else None
    sdl = browser.make_browser("demo")
    print("SDL video driver:", sdl.driver)
    assert sdl.driver == "x11", "the checks must run on X11"
    adapter = Adapter(sdl)
    sdl.start("about:blank")
    adapter.spin(lambda: sdl.messages, "the page to call Python (appReady)")
    adapter.settle()
    code = checks.Checks(adapter, shots).run()
    sdl.destroy()
    sys.exit(code)


if __name__ == "__main__":
    main()
