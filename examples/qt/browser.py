"""A small browser: the CefWidget in a Qt window, with a toolbar and the demo page.

    uv sync --extra pyqt                          # or: UV_PROJECT_ENVIRONMENT=.venv-pyside uv sync --extra pyside
    uv run python browser.py [address | demo]     # CEFQT_BINDING=pyside6 for PySide6
"""

import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "common"))

import demo  # noqa: E402
from cefweaver import ui  # noqa: E402
from cefweaver.ui.toolkits.qt import (BINDING, QApplication, QObject, Qt, QTimer, QtLoop, CefWidget)  # noqa: E402

if BINDING == "pyqt6":
    from PyQt6.QtGui import QAction
    from PyQt6.QtWidgets import QLineEdit, QMainWindow, QToolBar
else:
    from PySide6.QtGui import QAction
    from PySide6.QtWidgets import QLineEdit, QMainWindow, QToolBar


class BrowserWindow(QMainWindow):
    def __init__(self, runtime, url):
        super().__init__()
        self.runtime = runtime
        self.start_url = url
        self.messages = []                              # what the page told Python (the smoke test reads it)
        self.resize(900, 640)
        self.view = CefWidget(runtime)
        self.setCentralWidget(self.view)
        bar = QToolBar()
        self.addToolBar(bar)
        self.back = bar.addAction("◀")
        self.forward = bar.addAction("▶")
        self.reload_action = bar.addAction("⟳")
        self.entry = QLineEdit()
        bar.addWidget(self.entry)
        self.back.setEnabled(False)
        self.forward.setEnabled(False)
        self.back.triggered.connect(self.view.go_back)
        self.forward.triggered.connect(self.view.go_forward)
        self.reload_action.triggered.connect(self.view.reload)
        self.entry.returnPressed.connect(lambda: self.view.load_url(self.address(self.entry.text())))
        self.view.title_changed.connect(lambda title: self.setWindowTitle(title or "cefweaver Qt"))
        self.view.address_changed.connect(self.entry.setText)
        self.view.loading_changed.connect(self.on_loading)
        self.view.browser_ready_signal.connect(self.on_ready)
        self.closing = False
        self.setWindowTitle("cefweaver Qt")

    @staticmethod
    def address(text):
        text = text.strip()
        if text == "demo":
            return demo.DEMO_URL
        return text if "://" in text or text.startswith(("about:", "data:")) else "https://" + text

    def on_loading(self, loading, can_back, can_forward):
        self.back.setEnabled(can_back)
        self.forward.setEnabled(can_forward)

    def on_ready(self):
        app = self.runtime.app
        app.add_resource(demo.DEMO_URL, demo.DEMO_PAGE)
        app.add_resource(demo.DEMO_URL + "other", "<h1>another page</h1><a href='/'>back</a>")
        self.view.load_url(self.address(self.start_url))

    def closeEvent(self, event):
        if self.closing:
            event.accept()
            return
        event.ignore()                                  # the window goes when CEF has closed the browser
        self.closing = True
        self.runtime.shutdown(lambda: QTimer.singleShot(0, self.close))

    def start(self):
        self.runtime.start(self.view, "about:blank")


def make_runtime(window_holder):
    text = os.environ.get("CEFQT_SWITCHES", "")           # "name=value;name=value": Chromium switches
    switches = [tuple(item.split("=", 1)) if "=" in item else (item, "") for item in text.split(";") if item]
    runtime = ui.Session(QtLoop(), switches, cache_path=tempfile.mkdtemp(prefix="cefweaver-qt-"))
    demo.install(runtime.bridge, lambda info: window_holder[0].messages.append(info))
    return runtime


def main(argv=None):
    argv = list(sys.argv if argv is None else argv)
    app = QApplication(argv)
    holder = []
    runtime = make_runtime(holder)
    window = BrowserWindow(runtime, argv[1] if len(argv) > 1 else "demo")
    holder.append(window)
    window.show()
    QTimer.singleShot(0, window.start)
    app.lastWindowClosed.connect(app.quit)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
