"""Runs the wxPython example for real on a (virtual) X display, with real X events (xdotool), and checks
what a user would see (see ../common/checks.py). Also drag and drop between wx widgets and the page.

    GDK_BACKEND=x11 xvfb-run -a uv run python smoke.py [screenshot-directory]

Always on X11: GTK would otherwise connect to a running Wayland session even under xvfb.
"""

import os
import sys
import tempfile
import time

os.environ["GDK_BACKEND"] = "x11"
for name in ("WAYLAND_DISPLAY", "XDG_SESSION_TYPE"):
    os.environ.pop(name, None)

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "common"))

import wx  # noqa: E402

import browser  # noqa: E402
import checks  # noqa: E402


class Label(wx.Panel):
    """A label with a window of its own (wx.StaticText has none on GTK, so it gets no mouse events)."""

    def __init__(self, parent, label, size):
        super().__init__(parent, size=size)
        self.label = label
        self.SetMinSize(size)
        self.SetBackgroundColour(wx.Colour(235, 235, 250))
        self.Bind(wx.EVT_PAINT, self._on_paint)

    def set_label(self, label):
        self.label = label
        self.Refresh()

    def _on_paint(self, event):
        dc = wx.PaintDC(self)
        dc.DrawText(self.label, 6, 6)


class DragSource(Label):
    """A wx widget that drags text or a file (a drag starts when the pointer moves with the button down)."""

    def __init__(self, parent, label, make_data):
        super().__init__(parent, label, (190, 30))
        self.make_data = make_data
        self.Bind(wx.EVT_MOTION, self._on_motion)

    def _on_motion(self, event):
        if event.Dragging() and event.LeftIsDown():
            data = self.make_data()                     # wx.DropSource does not own it: it must live through the drag
            source = wx.DropSource(self)
            source.SetData(data)
            source.DoDragDrop(wx.Drag_CopyOnly)


class TextTarget(wx.TextDropTarget):
    def __init__(self, label):
        super().__init__()
        self.label = label
        self.dropped = []

    def OnDropText(self, x, y, text):
        self.dropped.append(text)
        self.label.set_label(text)
        return True


class Adapter:
    def __init__(self, app, window):
        self.app, self.window, self.runtime = app, window, window.runtime
        self.view = window.view
        self.scale = int(round(self.view.GetContentScaleFactor()))
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
            self.app.Yield(True)
            time.sleep(0.005)

    def settle(self, seconds=0.4):
        end = time.time() + seconds
        while time.time() < end:
            self.app.Yield(True)
            time.sleep(0.005)

    def origin(self):
        point = self.view.ClientToScreen(wx.Point(0, 0))
        return point.x * self.scale, point.y * self.scale

    def window_id(self):
        return None                                     # wx gives the GtkWidget, not the X window

    def view_size(self):
        return tuple(self.view.GetClientSize())

    def picture_size(self):
        return self.view.picture

    def title(self):
        return self.window.GetTitle()

    def address(self):
        return self.window.entry.GetValue()

    def can_go_back(self):
        return self.window.back.IsEnabled()

    def go_back(self):
        self.view.go_back()

    def popup_visible(self):
        return self.view.popup_visible and self.view.popup_bitmap is not None

    def resize_window(self, width, height):
        self.window.SetClientSize(width, height + self.window.GetClientSize().height - self.view.GetClientSize().height)

    def snapshot(self, path):
        self.view.snapshot(path)

    def commit_text(self, text):
        self.view.commit_text(text)

    def set_preedit(self, text, cursor):
        self.view.set_preedit(text, cursor)

    def _clipboard_get(self):
        data = wx.TextDataObject()
        if not wx.TheClipboard.Open():
            return None
        found = wx.TheClipboard.GetData(data)
        wx.TheClipboard.Close()
        return data.GetText() if found else None

    def _clipboard_set(self, text):
        if wx.TheClipboard.Open():
            wx.TheClipboard.SetData(wx.TextDataObject(text))
            wx.TheClipboard.Flush()
            wx.TheClipboard.Close()

    def shutdown(self):
        done = []
        self.runtime.shutdown(lambda: done.append(True))
        self.spin(lambda: done or not self.runtime.started, "CEF to shut down", 20)

    def cef_running(self):
        return self.runtime.app.is_running

    # -- drag and drop between wx widgets and the page ------------------------------------------

    def extra_checks(self, core):
        check = core.check
        temporary = tempfile.NamedTemporaryFile(suffix=".txt", prefix="dragged-", delete=False)
        temporary.write(b"file body")
        temporary.close()

        def text_data():
            return wx.TextDataObject("from-wx")

        def file_data():
            data = wx.FileDataObject()
            data.AddFile(temporary.name)
            return data

        row = wx.Panel(self.window)
        text_source = DragSource(row, "  drag text from wx  ", text_data)
        file_source = DragSource(row, "  drag a file from wx  ", file_data)
        target = Label(row, "drop text from the page here", (240, 30))
        receiver = TextTarget(target)
        target.SetDropTarget(receiver)
        box = wx.BoxSizer(wx.HORIZONTAL)
        for widget in (text_source, file_source):
            box.Add(widget, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 8)
        box.Add(target, 1, wx.ALL | wx.EXPAND, 4)
        row.SetSizer(box)
        self.window.GetSizer().Add(row, 0, wx.EXPAND)
        self.window.Layout()
        self.settle(1.0)

        def center_of(widget):
            width, height = widget.GetSize()
            point = widget.ClientToScreen(wx.Point(width // 2, height // 2))
            return point.x * self.scale, point.y * self.scale

        def zone_point():
            x, y = core.rect_of("#zone")
            return core.point(x, y)

        core.js("window.drops = []")
        core.drag(center_of(text_source), zone_point(), threaded=True)
        drops = core.js("window.drops")
        check(drops == [{"text": "from-wx", "files": []}], "text dragged from a wx widget is dropped on the page", drops)
        info = core.js("document.getElementById('dropinfo').textContent")
        check(info == 'dropped text "from-wx"', "the page shows what was dropped", info)
        core.js("window.drops = []")
        core.drag(center_of(file_source), zone_point(), threaded=True)
        drops = core.js("window.drops")
        check(len(drops) == 1 and drops[0]["files"] == [os.path.basename(temporary.name)], "a file dragged from a wx widget is dropped on the page",
              (drops, os.path.basename(temporary.name)))
        x, y = core.rect_of("#src")
        core.drag(core.point(x, y), center_of(target), threaded=True)
        check(receiver.dropped == ["dragged-from-page"], "an element dragged out of the page is dropped on a wx drop target", receiver.dropped)
        core.js("window.drops = []")
        x, y = core.rect_of("#src")
        core.drag(core.point(x, y), zone_point(), threaded=True)
        drops = core.js("window.drops")
        check(drops == [{"text": "dragged-from-page", "files": []}], "dragging inside the page works (the panel is source and target)", drops)
        core.snapshot("10-dragged")
        os.unlink(temporary.name)


def main():
    shots = sys.argv[1] if len(sys.argv) > 1 else None
    app = wx.App()
    holder = []
    runtime = browser.make_runtime(holder)
    window = browser.BrowserWindow(runtime, "demo")
    holder.append(window)
    window.Show()
    adapter = Adapter(app, window)
    adapter.spin(lambda: window.view.GetClientSize().width > 100, "the window")
    wx.CallAfter(window.start)
    adapter.spin(lambda: window.messages, "the page to call Python (appReady)")
    adapter.settle()
    sys.exit(checks.Checks(adapter, shots).run())


if __name__ == "__main__":
    main()
