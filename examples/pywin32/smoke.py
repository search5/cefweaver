"""Runs the pywin32 example for real on the Windows desktop, with real input events (SendInput, ../common/winxdo.py),
and checks what a user would see (see ../common/checks.py). Also a drag inside the page, files dropped as the Explorer
drops them (WM_DROPFILES with a real DROPFILES block) and the context menu of the page (the Windows menu loop,
left with Escape).

    python smoke.py [screenshot-directory]

The window opens on the desktop and the checks move the pointer and type: leave the machine alone for the minute it takes.
"""

import ctypes
import os
import struct
import sys
import tempfile
import threading
import time
from ctypes import wintypes

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "common"))

import win32con  # noqa: E402
import win32gui  # noqa: E402
import browser  # noqa: E402
import checks  # noqa: E402
import winxdo  # noqa: E402

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
kernel32.GlobalAlloc.restype = wintypes.HANDLE
kernel32.GlobalLock.argtypes = [wintypes.HANDLE]
kernel32.GlobalLock.restype = ctypes.c_void_p
kernel32.GlobalUnlock.argtypes = [wintypes.HANDLE]


class Adapter:
    def __init__(self, win):
        self.win, self.runtime = win, win
        self.messages = win.messages
        self.scale = win.scale()
        self.clipboard_get = win.clipboard_get
        self.clipboard_set = win.clipboard_set

    def browser(self):
        return self.win.browser

    def spin(self, condition, what, timeout=30):
        end = time.time() + timeout
        while not condition():
            if time.time() > end:
                raise TimeoutError("timed out waiting for " + what)
            self.win.step(5)

    def settle(self, seconds=0.4):
        end = time.time() + seconds
        while time.time() < end:
            self.win.step(5)

    def origin(self):
        return self.win.screen_origin()                      # device pixels

    def window_id(self):
        return self.win.hwnd

    def view_size(self):
        return self.win.view_size()

    def picture_size(self):
        return self.win.picture

    def title(self):
        return self.win.title

    def address(self):
        return self.win.url

    def can_go_back(self):
        return self.win.can_back

    def go_back(self):
        self.win.go_back()

    def popup_visible(self):
        return self.win.popup_visible and self.win._popup_bits is not None

    def resize_window(self, width, height):
        from cefweaver.ui.toolkits.pywin32 import _window_rect_for_client
        outer = _window_rect_for_client(int(width * self.scale), int(height * self.scale),
                                        win32gui.GetWindowLong(self.win.hwnd, win32con.GWL_STYLE))
        left, top, _, _ = win32gui.GetWindowRect(self.win.hwnd)
        win32gui.SetWindowPos(self.win.hwnd, 0, left, top, outer[0], outer[1], win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE)

    def snapshot(self, path):
        self.win.snapshot(path)

    def commit_text(self, text):
        self.win.commit_text(text)

    def set_preedit(self, text, cursor):
        self.win.set_preedit(text, cursor)

    def shutdown(self):
        self.win.close()
        self.spin(lambda: not self.win.started, "CEF to shut down", 20)

    def cef_running(self):
        return self.win.app.is_running

    # -- what only this toolkit does -------------------------------------------------------------------

    def extra_checks(self, core):
        # a drag inside the page, which the view carries out itself
        core.js("window.drops = []")
        x, y = core.rect_of("#src")
        core.drag(core.point(x, y), core.point(*core.rect_of("#zone")))
        drops = core.js("window.drops")
        core.check(drops == [{"text": "dragged-from-page", "files": []}], "dragging inside the page works (the view carries the drag out)", drops)
        self.settle(0.3)
        # files dropped from the Explorer arrive as WM_DROPFILES (a real DROPFILES block in global memory)
        core.js("window.drops = []")
        x, y = core.rect_of("#zone")
        px, py = core.point(x, y)
        winxdo.run("mousemove", px, py)
        self.settle(0.2)
        path = os.path.join(tempfile.mkdtemp(prefix="cefweaver-drop-"), "dropped.txt")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("hello")
        cx, cy = win32gui.ScreenToClient(self.win.hwnd, (px, py))
        win32gui.PostMessage(self.win.hwnd, win32con.WM_DROPFILES, self._drop_block([path], cx, cy), 0)
        self.settle(0.8)
        drops = core.js("window.drops")
        core.check(drops == [{"text": "", "files": ["dropped.txt"]}], "a file dropped from the Explorer (WM_DROPFILES) reaches the page", drops)
        core.snapshot("10-dragged")
        self.menu_checks(core)

    @staticmethod
    def _drop_block(files, x, y):
        """An HDROP: a DROPFILES header (20 bytes) and the wide file names, a double null at the end."""
        names = ("\0".join(files) + "\0\0").encode("utf-16-le")
        handle = kernel32.GlobalAlloc(0x0002 | 0x0040, 20 + len(names))      # GMEM_MOVEABLE | GMEM_ZEROINIT
        pointer = kernel32.GlobalLock(handle)
        ctypes.memmove(pointer, struct.pack("<Iiiii", 20, x, y, 0, 1), 20)     # pFiles, pt, fNC = 0, fWide = 1
        ctypes.memmove(pointer + 20, names, len(names))
        kernel32.GlobalUnlock(handle)
        return handle

    def menu_checks(self, core):
        """The context menu is a TrackPopupMenu: Windows runs a loop of its own in it and CEF has to go on there
        (the page answers a query while the menu is open); Escape leaves the menu."""
        seen = []
        original = self.win.show_menu

        def show_menu(items, x, y, done):
            seen.append(len(items))

            def leave():
                time.sleep(1.0)
                winxdo.run("key", "Escape")
            threading.Thread(target=leave, daemon=True).start()
            original(items, x, y, done)
        self.win.show_menu = show_menu
        x, y = core.rect_of("#para")
        winxdo.run("mousemove", *core.point(x, y))
        self.settle(0.2)
        winxdo.run("click", 3)
        self.spin(lambda: seen, "the context menu to open", 10)
        self.settle(1.5)
        core.check(seen and seen[0] > 0, "a right click opens the context menu of the page (%s entries)" % (seen[:1] or 0,))
        core.check(core.js("1 + 1") == 2, "CEF goes on after the menu was left with Escape")
        self.win.show_menu = original


def main():
    shots = sys.argv[1] if len(sys.argv) > 1 else None
    win = browser.make_browser("demo")
    adapter = Adapter(win)
    win.start("about:blank")
    adapter.spin(lambda: win.messages, "the page to call Python (appReady)")
    adapter.settle()
    code = checks.Checks(adapter, shots).run()
    win.destroy()
    sys.exit(code)


if __name__ == "__main__":
    main()
