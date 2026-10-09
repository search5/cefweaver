"""Runs the Qt example for real on a (virtual) X display, with real X events (xdotool), and checks
what a user would see (see ../common/checks.py). Also drag and drop between Qt widgets and the page.

    QT_QPA_PLATFORM=xcb xvfb-run -a uv run python smoke.py [screenshot-directory]

Always on X11 (xcb): Qt would otherwise connect to a running Wayland session even under xvfb.
"""

import os
import sys
import tempfile
import time

os.environ["QT_QPA_PLATFORM"] = "xcb"
for name in ("WAYLAND_DISPLAY", "XDG_SESSION_TYPE"):
    os.environ.pop(name, None)

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "common"))

import browser  # noqa: E402
from cefweaver.ui.toolkits.qt import BINDING, QApplication, QMimeData, QPoint, QTimer, QUrl, Qt  # noqa: E402
import checks  # noqa: E402

if BINDING == "pyqt6":
    from PyQt6.QtGui import QDrag
    from PyQt6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QWidget
else:
    from PySide6.QtGui import QDrag
    from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QWidget


class DragSource(QLabel):
    """A Qt widget that drags text or a file (a drag starts after the pointer moved a little)."""

    def __init__(self, label, make_mime):
        super().__init__(label)
        self.make_mime = make_mime

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            drag = QDrag(self)
            drag.setMimeData(self.make_mime())
            drag.exec(Qt.DropAction.CopyAction)


class Adapter:
    def __init__(self, app, window):
        self.app, self.window, self.runtime = app, window, window.runtime
        self.view = window.view
        self.scale = int(round(self.view.devicePixelRatioF()))
        self.messages = window.messages
        self.clipboard_get = lambda: self.app.clipboard().text()
        self.clipboard_set = lambda text: self.app.clipboard().setText(text)

    def browser(self):
        return self.view.browser

    def spin(self, condition, what, timeout=30):
        end = time.time() + timeout
        while not condition():
            if time.time() > end:
                raise TimeoutError("timed out waiting for " + what)
            self.app.processEvents()
            time.sleep(0.005)

    def settle(self, seconds=0.4):
        end = time.time() + seconds
        while time.time() < end:
            self.app.processEvents()
            time.sleep(0.005)

    def origin(self):
        point = self.view.mapToGlobal(QPoint(0, 0))
        return int(point.x() * self.scale), int(point.y() * self.scale)

    def window_id(self):
        return int(self.window.winId())

    def view_size(self):
        return self.view.width(), self.view.height()

    def picture_size(self):
        image = self.view.image
        return (image.width(), image.height()) if image is not None else (0, 0)

    def title(self):
        return self.window.windowTitle()

    def address(self):
        return self.window.entry.text()

    def can_go_back(self):
        return self.window.back.isEnabled()

    def go_back(self):
        self.view.go_back()

    def popup_visible(self):
        return self.view.popup_visible and self.view.popup_image is not None

    def resize_window(self, width, height):
        self.window.resize(width, height)

    def snapshot(self, path):
        self.view.snapshot(path)

    def commit_text(self, text):
        self.view.commit_text(text)

    def set_preedit(self, text, cursor):
        self.view.set_preedit(text, cursor)

    def shutdown(self):
        self.window.close()
        self.spin(lambda: not self.runtime.started, "CEF to shut down", 20)

    def cef_running(self):
        return self.runtime.app.is_running

    # -- drag and drop between Qt widgets and the page ------------------------------------------

    def extra_checks(self, core):
        check = core.check
        temporary = tempfile.NamedTemporaryFile(suffix=".txt", prefix="dragged-", delete=False)
        temporary.write(b"file body")
        temporary.close()

        def text_mime():
            mime = QMimeData()
            mime.setText("from-qt")
            return mime

        def file_mime():
            mime = QMimeData()
            mime.setUrls([QUrl.fromLocalFile(temporary.name)])
            return mime

        row = QWidget(self.window)
        layout = QHBoxLayout(row)
        text_source = DragSource("  drag text from Qt  ", text_mime)
        file_source = DragSource("  drag a file from Qt  ", file_mime)
        target = QLineEdit()
        target.setPlaceholderText("drop text from the page here")
        for widget in (text_source, file_source, target):
            layout.addWidget(widget)
        # below the page: the page keeps its size, the window grows
        self.window.resize(self.window.width(), self.window.height() + 60)
        row.setGeometry(0, self.window.height() - 60, self.window.width(), 56)
        row.show()
        self.settle(1.0)

        def center_of(widget):
            point = widget.mapToGlobal(QPoint(widget.width() // 2, widget.height() // 2))
            return int(point.x() * self.scale), int(point.y() * self.scale)

        def zone_point():
            x, y = core.rect_of("#zone")
            return core.point(x, y)

        core.js("window.drops = []")
        core.drag(center_of(text_source), zone_point(), threaded=True)
        drops = core.js("window.drops")
        check(drops == [{"text": "from-qt", "files": []}], "text dragged from a Qt widget is dropped on the page", drops)
        info = core.js("document.getElementById('dropinfo').textContent")
        check(info == 'dropped text "from-qt"', "the page shows what was dropped (so that the drop zone can be tried by hand)", info)
        core.js("window.drops = []")
        core.drag(center_of(file_source), zone_point(), threaded=True)
        drops = core.js("window.drops")
        check(len(drops) == 1 and drops[0]["files"] == [os.path.basename(temporary.name)], "a file dragged from a Qt widget is dropped on the page",
              (drops, os.path.basename(temporary.name)))
        x, y = core.rect_of("#src")
        core.drag(core.point(x, y), center_of(target), threaded=True)
        check(target.text() == "dragged-from-page", "an element dragged out of the page is dropped on a Qt line edit", target.text())
        core.js("window.drops = []")
        x, y = core.rect_of("#src")
        core.drag(core.point(x, y), zone_point(), threaded=True)
        drops = core.js("window.drops")
        check(drops == [{"text": "dragged-from-page", "files": []}], "dragging inside the page works (the widget is source and target)", drops)
        core.snapshot("10-dragged")
        os.unlink(temporary.name)
        self.menu_checks(core)
        self.sink_checks(core)

    def menu_checks(self, core):
        """The context menu: a real right click, a real click on an item of the application, and leaving the menu."""
        from cefweaver import ui
        check = core.check
        mine, shown = [], []
        adapter = self.view.view.adapter
        original = adapter.show_menu
        adapter.show_menu = lambda items, x, y, done: (shown.append((x, y, [i.label for i in items])), original(items, x, y, done))[1]
        self.view.view.on_context_menu = lambda info, items: items + [ui.menu.MenuItem("Smoke item", action=lambda: mine.append("run"))]
        x, y = core.rect_of("#para")
        core.xdo("mousemove", *core.point(x, y))
        self.settle(0.2)
        core.xdo("click", 3)
        self.spin(lambda: shown and adapter.last_menu.isVisible(), "the context menu")
        check(len(shown) == 1 and "Smoke item" in shown[0][2], "a right click shows the menu of the page with the item of the application", shown)
        menu = adapter.last_menu
        action = next(a for a in menu.actions() if a.text() == "Smoke item")
        rect = menu.actionGeometry(action)
        target = menu.mapToGlobal(rect.center())
        core.xdo("mousemove", int(target.x() * self.scale), int(target.y() * self.scale))
        self.settle(0.2)
        core.xdo("click", 1)
        self.spin(lambda: mine, "the action of the menu item")
        check(mine == ["run"], "clicking an item of the application runs its action", mine)
        self.settle(0.3)
        check(not menu.isVisible(), "the menu closes after the pick")
        core.xdo("mousemove", *core.point(x, y))
        self.settle(0.2)
        core.xdo("click", 3)
        self.spin(lambda: len(shown) == 2 and adapter.last_menu.isVisible(), "the context menu again")
        core.xdo("key", "Escape")
        self.spin(lambda: not adapter.last_menu.isVisible(), "the menu to close with Escape")
        self.settle(0.3)
        check(mine == ["run"], "leaving the menu with Escape picks nothing", mine)
        core.xdo("mousemove", *core.point(x, y))
        self.settle(0.2)
        core.xdo("click", 3)
        self.spin(lambda: len(shown) == 3 and adapter.last_menu.isVisible(), "the menu after it was left")
        check(core.js("1 + 1") == 2, "the page still answers after a menu was left")
        core.xdo("key", "Escape")
        self.settle(0.3)
        self.view.view.on_context_menu = None

    def sink_checks(self, core):
        """The audio sink of Qt on the real device, with silence (volume 0): what is written is played, in time."""
        from cefweaver.ui.toolkits.qt import QtSink, _multimedia
        parts = _multimedia()
        if parts is None or parts[2].defaultAudioOutput().isNull():
            return                                           # no output device
        sink = QtSink(self.runtime.adapter)
        sink.volume = 0.0
        sink.start(44100, 2)
        packet = bytes(4 * 2 * 1024)
        for _ in range(43):
            sink.write(packet, 1024)
            self.settle(1024 / 44100)
        self.settle(0.3)
        stats = sink.stats()
        sink.stop()
        self.settle(0.1)
        core.check(stats["written"] == 43 * 1024 and stats["dropped"] == 0, "the Qt sink takes all that is written", stats)
        core.check(stats["consumed"] >= stats["written"] - 6 * 1024 and stats["underruns"] <= 3,
                   "the device plays it as fast as it comes (a small latency, no gaps)", stats)


def main():
    shots = sys.argv[1] if len(sys.argv) > 1 else None
    app = QApplication(sys.argv)
    print("binding", BINDING, "| Qt platform", app.platformName())
    assert app.platformName() == "xcb", "the checks must run on X11"
    holder = []
    runtime = browser.make_runtime(holder)
    window = browser.BrowserWindow(runtime, "demo")
    holder.append(window)
    window.show()
    adapter = Adapter(app, window)
    adapter.spin(lambda: window.isVisible() and window.view.width() > 100, "the window")
    QTimer.singleShot(0, window.start)
    adapter.spin(lambda: window.messages, "the page to call Python (appReady)")
    adapter.settle()
    sys.exit(checks.Checks(adapter, shots).run())


if __name__ == "__main__":
    main()
