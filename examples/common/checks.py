"""The checks every toolkit example has to pass, run against the real window with real X events.

The mouse and the keys are made with xdotool (XTEST), so the event handling and the input
method of the toolkit are on the way, as for a user. A toolkit gives an *adapter*; the checks
(``run``) are the same for all of them:

    adapter.runtime        the Runtime of the example (``.bridge`` is the cefweaver.JavascriptBridge)
    adapter.browser()      the cefweaver Browser
    adapter.scale          the device pixel ratio of the screen (1 or 2)
    adapter.messages       the list the page's appReady() calls are remembered in
    adapter.spin(cond, what, timeout)   run the toolkit's event loop until cond() (TimeoutError)
    adapter.settle(seconds)             run it for that time
    adapter.origin()       the top-left of the view on the X screen, in device pixels
    adapter.window_id()    the X window id of the top-level window (or None)
    adapter.view_size()    the size of the view in logical pixels
    adapter.picture_size() the size of the picture CEF painted, in device pixels
    adapter.title(), adapter.address(), adapter.can_go_back(), adapter.go_back()
    adapter.popup_visible()
    adapter.resize_window(width, height)
    adapter.snapshot(path)
    adapter.commit_text(text), adapter.set_preedit(text, cursor)    (what an input method sends)
    adapter.clipboard_get(), adapter.clipboard_set(text)
    adapter.shutdown()     close the window and wait until CEF is shut down
    adapter.cef_running()
"""

import os
import subprocess
import sys
import time

ENVIRONMENT = {"GDK_BACKEND": "x11", "QT_QPA_PLATFORM": "xcb"}   # never the real Wayland session


class Checks:
    def __init__(self, adapter, shots=None):
        self.a = adapter
        self.shots = shots
        self.failures = []

    # -- helpers -------------------------------------------------------------------------------

    def check(self, condition, what, detail=""):
        print("%s  %s%s" % ("ok  " if condition else "FAIL", what, ("   [" + str(detail) + "]") if detail and not condition else ""))
        sys.stdout.flush()
        if not condition:
            self.failures.append(what)
        return condition

    @staticmethod
    def xdo(*args):
        result = subprocess.run(["xdotool"] + [str(a) for a in args], capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError("xdotool %s failed: %s" % (" ".join(str(a) for a in args), result.stderr.strip()))

    def js(self, expression, timeout=10):
        box = []
        self.a.runtime.bridge.evaluate(self.a.browser().get_main_frame(), expression, lambda v, e: box.append((v, e)))
        self.a.spin(lambda: box, "the value of " + expression, timeout)
        value, error = box[0]
        if error:
            raise RuntimeError("%s: %s" % (expression, error))
        return value

    def snapshot(self, name):
        if self.shots:
            os.makedirs(self.shots, exist_ok=True)
            self.a.snapshot(os.path.join(self.shots, name + ".png"))

    def point(self, x, y):
        """Where xdotool puts the pointer for a point of the page (CSS pixels)."""
        ox, oy = self.a.origin()
        return int(ox + x * self.a.scale), int(oy + y * self.a.scale)

    def rect_of(self, selector):
        r = self.js("(function(){var r = document.querySelector(%r).getBoundingClientRect(); return [r.x, r.y, r.width, r.height];})()" % selector)
        return r[0] + r[2] / 2, r[1] + r[3] / 2

    def click(self, selector):
        x, y = self.rect_of(selector)
        self.xdo("mousemove", *self.point(x, y))
        self.a.settle(0.1)
        self.xdo("click", 1)
        self.a.settle(0.3)

    def value(self, selector):
        return self.js("document.querySelector(%r).value" % selector)

    # -- the checks -----------------------------------------------------------------------------

    def run(self):
        a, check, js, xdo, settle = self.a, self.check, self.js, self.xdo, self.a.settle
        scale = a.scale
        wid = a.window_id()
        if wid:
            xdo("windowfocus", wid)
        settle()

        # 1. the page is drawn
        ready = a.messages[0]
        view_w, view_h = a.view_size()
        check(a.picture_size() == (int(view_w * scale), int(view_h * scale)), "the picture has the size of the view",
              (a.picture_size(), (view_w, view_h, scale)))
        check(ready["dpr"] == scale, "the page sees the device pixel ratio of the screen (%dx)" % scale, ready["dpr"])
        check(js("document.title") == "cefweaver demo" and a.title() == "cefweaver demo", "the title reaches the window", a.title())
        check("Python" in js("document.getElementById('log').textContent"), "Python's answer to appReady() is in the page")
        self.snapshot("1-page")

        # 2. the mouse and the keyboard
        self.click("#text")
        check(js("document.activeElement.id") == "text", "a click focuses the input of the page")
        xdo("type", "--delay", 40, "hello")
        settle(0.5)
        check(self.value("#text") == "hello", "typed keys reach the input", self.value("#text"))
        xdo("key", "BackSpace")
        settle(0.3)
        check(self.value("#text") == "hell", "BackSpace edits it")
        xdo("key", "ctrl+a")
        settle(0.2)

        # 3. Hangul as an input method sends it (preedit, then commit)
        a.set_preedit("하", 1)
        settle(0.4)
        a.set_preedit("한", 1)
        settle(0.3)
        a.commit_text("한")
        a.set_preedit("", 0)
        settle(0.5)
        check("한" in self.value("#text"), "composed Hangul is committed into the input", self.value("#text"))
        compositions = js("window.compositions")
        check(any(c.startswith("compositionupdate:") for c in compositions), "the page sees the composition", compositions)
        self.snapshot("3-hangul")

        # 4. the page calls Python and Python calls the page
        self.click("#add")
        a.spin(lambda: "= 5" in js("document.getElementById('log').textContent"), "add(2, 3) = 5 in the page")
        check(True, "the page calls Python (add) and shows the answer")
        answers = []
        a.runtime.bridge.evaluate(a.browser().get_main_frame(), "fromPython('hello from Python')", lambda v, e: answers.append((v, e)))
        a.spin(lambda: answers, "the answer of fromPython")
        check(answers == [(len("hello from Python"), None)], "Python calls a function of the page and gets its value", answers)

        # 5. the popup of a <select>
        self.click("#fruit")
        try:
            a.spin(a.popup_visible, "the popup of the select", 10)
        except TimeoutError:
            pass
        settle(0.5)
        check(a.popup_visible(), "the popup of a select is drawn")
        self.snapshot("5-popup")
        xdo("key", "Escape")
        settle(0.5)
        check(not a.popup_visible(), "Escape closes the popup")

        # 6. the wheel (buttons 4 and 5 of X are the wheel)
        before = js("window.scrollY")
        x, y = self.rect_of("#log")
        xdo("mousemove", *self.point(x, y))
        for _ in range(5):
            xdo("click", 5)
            settle(0.15)
        settle(0.5)
        after = js("window.scrollY")
        check(before == 0 and after > 0, "the wheel scrolls the page", (before, after))

        # 7. links and history
        js("window.scrollTo(0, 0)")
        settle(0.3)
        self.click("#link")
        a.spin(lambda: a.address().endswith("/other"), "the address of the other page", 10)
        check(a.address().endswith("/other"), "a click on a link navigates and the address follows", a.address())
        a.spin(a.can_go_back, "the back button")
        check(a.can_go_back(), "back is possible")
        a.go_back()
        a.spin(lambda: a.address().endswith("demo.test/"), "the address after back", 10)
        check(a.address().endswith("demo.test/"), "back returns to the first page")
        settle(0.5)

        # 8. the window size is the size of the page
        before = js("innerWidth")
        a.resize_window(700, 500)
        try:
            a.spin(lambda: js("innerWidth") != before, "the page to change its width", 10)
        except TimeoutError:
            print("resize diagnostics: view", a.view_size(), "innerWidth", js("innerWidth"))
        check(js("innerWidth") == a.view_size()[0], "resizing the window resizes the page", (js("innerWidth"), a.view_size()))
        self.snapshot("8-resized")

        # 9. the clipboard
        if a.clipboard_get is not None:
            self.clipboard_checks()

        # 10. what only some toolkits do (drag and drop)
        extra = getattr(a, "extra_checks", None)
        if extra:
            extra(self)

        # 11. shutdown
        a.shutdown()
        check(not a.cef_running(), "the browser is closed and CEF is shut down")
        print("ALL OK" if not self.failures else "FAILED: %s" % ", ".join(self.failures))
        return 1 if self.failures else 0

    def clipboard_checks(self):
        a, check, xdo, settle = self.a, self.check, self.xdo, self.a.settle

        def clipboard_is(text, timeout=5):
            try:
                a.spin(lambda: a.clipboard_get() == text, "the clipboard to hold %r" % text, timeout)
                return True
            except TimeoutError:
                return False

        a.resize_window(900, 700)
        settle(1.0)
        self.click("#text")
        xdo("key", "ctrl+a")
        xdo("type", "--delay", 40, "copy me")
        settle(0.4)
        xdo("key", "ctrl+a")
        settle(0.4)
        xdo("key", "ctrl+c")
        check(clipboard_is("copy me"), "Ctrl+C copies the selection of an input to the clipboard", a.clipboard_get())
        xdo("key", "ctrl+x")
        settle(0.5)
        check(self.value("#text") == "" and clipboard_is("copy me"), "Ctrl+X cuts it (the input is empty)", self.value("#text"))
        a.clipboard_set("붙여넣기 text")
        settle(0.3)
        self.click("#area")
        xdo("key", "ctrl+v")
        settle(0.6)
        check(self.value("#area") == "붙여넣기 text", "Ctrl+V pastes the clipboard (Hangul too) into a textarea", self.value("#area"))
        xdo("key", "ctrl+a")
        xdo("key", "BackSpace")
        settle(0.3)
        x, y = self.rect_of("#para")
        xdo("mousemove", *self.point(x, y))
        settle(0.1)
        xdo("click", "--repeat", 3, "--delay", 60, 1)
        settle(0.6)
        xdo("key", "ctrl+c")
        settle(0.6)
        check("Selectable paragraph text" in (a.clipboard_get() or ""), "Ctrl+C copies selected text of the page (not editable)", a.clipboard_get())
        self.snapshot("9-clipboard")

    # -- the drag helpers the toolkits use for their own checks -----------------------------------

    def drag(self, start, end, steps=12, threaded=False):
        """A real drag with the pointer: press, move in small steps, release.

        ``threaded``: for toolkits whose drag source blocks (Qt's QDrag.exec() runs an event loop
        until the drag ends): the pointer is driven from another thread while the toolkit's loop runs."""
        xdo = self.xdo
        sx, sy = start
        ex, ey = end

        def steps_of(pause):
            pause(0.2)
            xdo("mousemove", sx, sy)
            pause(0.2)
            xdo("mousedown", 1)
            pause(0.2)
            for step in range(1, steps + 1):
                xdo("mousemove", sx + (ex - sx) * step // steps, sy + (ey - sy) * step // steps)
                pause(0.08)
            pause(0.3)
            xdo("mouseup", 1)

        if not threaded:
            steps_of(self.a.settle)
            self.a.settle(0.8)
            return
        import threading
        failure = []

        def worker():
            try:
                steps_of(time.sleep)
            except BaseException as error:
                failure.append(error)
        thread = threading.Thread(target=worker)
        thread.start()
        self.a.spin(lambda: not thread.is_alive(), "the drag to finish", 60)
        if failure:
            raise failure[0]
        self.a.settle(0.8)
