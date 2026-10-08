"""The smallest program that shows a page in a Qt window (PyQt6, or PySide6 with CEFQT_BINDING=pyside6).
uv run python quickstart.py [address]"""

import sys

from cefweaver import ui
from cefweaver.ui.toolkits.qt import CefWidget, QApplication, QTimer, QtLoop

URL = sys.argv[1] if len(sys.argv) > 1 else "https://example.org/"

app = QApplication(sys.argv[:1])
session = ui.Session(QtLoop())                        # CEF, run by the Qt loop


class Window(CefWidget):                              # the browser, a QWidget
    closing = False

    def closeEvent(self, event):
        if self.closing:
            event.accept()
            return
        event.ignore()                                # close the browser first, then the window
        self.closing = True
        session.shutdown(lambda: QTimer.singleShot(0, self.close))


window = Window(session)
window.browser_ready_signal.connect(lambda: window.load_url(URL))
window.title_changed.connect(lambda title: print("title:", title, flush=True))
window.resize(900, 640)
window.show()
QTimer.singleShot(0, lambda: session.start(window))
sys.exit(app.exec())
