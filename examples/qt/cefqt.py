"""A Qt widget that shows a cefweaver offscreen browser, for PyQt6 and for PySide6, built on ``cefweaver.ui``.

The same code runs with both: ``CEFQT_BINDING=pyqt6`` or ``pyside6`` chooses (default: PyQt6 if it is
installed). ``cefweaver.ui`` has the CEF side (``BrowserView``, ``Session``). This file is what Qt adds, the
adapter:

* ``QtLoop``: running something in the GUI thread from any thread (a signal, delivered by Qt) and later
  (``QTimer``);
* ``QtAdapter``: size, scale and place of the widget, drawing the frames into a ``QImage``, the cursor, the
  clipboard of Qt, the candidate window of the input method and the ``QDrag`` that Qt starts for the page;
* ``CefWidget``: a ``QWidget`` that passes the mouse, wheel, keys, input method and drag and drop events of
  Qt to the view.
"""

import os

BINDING = os.environ.get("CEFQT_BINDING", "").lower()
if BINDING not in ("pyqt6", "pyside6"):
    try:
        import PyQt6  # noqa: F401
        BINDING = "pyqt6"
    except ImportError:
        BINDING = "pyside6"

if BINDING == "pyqt6":
    from PyQt6.QtCore import QEvent, QMimeData, QObject, QPoint, QRect, Qt, QTimer, QUrl
    from PyQt6.QtCore import pyqtSignal as Signal
    from PyQt6.QtGui import QCursor, QDrag, QGuiApplication, QImage, QInputMethodEvent, QPainter
    from PyQt6.QtWidgets import QApplication, QWidget
else:
    from PySide6.QtCore import QEvent, QMimeData, QObject, QPoint, QRect, Qt, QTimer, QUrl
    from PySide6.QtCore import Signal
    from PySide6.QtGui import QCursor, QDrag, QGuiApplication, QImage, QInputMethodEvent, QPainter
    from PySide6.QtWidgets import QApplication, QWidget

from cefweaver import types, ui
from cefweaver.ui import keys

SHIFT, CONTROL, ALT = keys.SHIFT, keys.CONTROL, keys.ALT
LEFT_BUTTON, MIDDLE_BUTTON, RIGHT_BUTTON = keys.LEFT_BUTTON, keys.MIDDLE_BUTTON, keys.RIGHT_BUTTON

_KEYS = {
    Qt.Key.Key_Backspace: keys.VK_BACK, Qt.Key.Key_Tab: keys.VK_TAB, Qt.Key.Key_Backtab: keys.VK_TAB,
    Qt.Key.Key_Return: keys.VK_RETURN, Qt.Key.Key_Enter: keys.VK_RETURN, Qt.Key.Key_Escape: keys.VK_ESCAPE,
    Qt.Key.Key_Space: keys.VK_SPACE, Qt.Key.Key_PageUp: keys.VK_PRIOR, Qt.Key.Key_PageDown: keys.VK_NEXT,
    Qt.Key.Key_End: keys.VK_END, Qt.Key.Key_Home: keys.VK_HOME, Qt.Key.Key_Left: keys.VK_LEFT,
    Qt.Key.Key_Up: keys.VK_UP, Qt.Key.Key_Right: keys.VK_RIGHT, Qt.Key.Key_Down: keys.VK_DOWN,
    Qt.Key.Key_Insert: keys.VK_INSERT, Qt.Key.Key_Delete: keys.VK_DELETE, Qt.Key.Key_Shift: keys.VK_SHIFT,
    Qt.Key.Key_Control: keys.VK_CONTROL, Qt.Key.Key_Alt: keys.VK_ALT,
}
_CURSORS = {
    types.CursorType.POINTER: Qt.CursorShape.ArrowCursor, types.CursorType.HAND: Qt.CursorShape.PointingHandCursor,
    types.CursorType.IBEAM: Qt.CursorShape.IBeamCursor, types.CursorType.CROSS: Qt.CursorShape.CrossCursor,
    types.CursorType.WAIT: Qt.CursorShape.WaitCursor, types.CursorType.HELP: Qt.CursorShape.WhatsThisCursor,
    types.CursorType.MOVE: Qt.CursorShape.SizeAllCursor, types.CursorType.NOTALLOWED: Qt.CursorShape.ForbiddenCursor,
    types.CursorType.NODROP: Qt.CursorShape.ForbiddenCursor, types.CursorType.PROGRESS: Qt.CursorShape.BusyCursor,
    types.CursorType.COLUMNRESIZE: Qt.CursorShape.SplitHCursor, types.CursorType.ROWRESIZE: Qt.CursorShape.SplitVCursor,
    types.CursorType.EASTWESTRESIZE: Qt.CursorShape.SizeHorCursor, types.CursorType.NORTHSOUTHRESIZE: Qt.CursorShape.SizeVerCursor,
}
_COPY, _LINK, _MOVE = types.DragOperationsMask.COPY, types.DragOperationsMask.LINK, types.DragOperationsMask.MOVE


def windows_key_code(key):
    """The virtual key code of a Qt key (letters and digits are their ASCII capitals)."""
    key = int(key)
    for qt_key, code in _KEYS.items():
        if int(qt_key) == key:
            return code
    if int(Qt.Key.Key_F1) <= key <= int(Qt.Key.Key_F12):
        return keys.vk_for_function(key - int(Qt.Key.Key_F1) + 1)
    return key if 0x20 <= key < 0x7F else 0


def modifier_flags(modifiers, buttons=None):
    flags = 0
    if modifiers & Qt.KeyboardModifier.ShiftModifier:
        flags |= SHIFT
    if modifiers & Qt.KeyboardModifier.ControlModifier:
        flags |= CONTROL
    if modifiers & Qt.KeyboardModifier.AltModifier:
        flags |= ALT
    if buttons is not None:
        if buttons & Qt.MouseButton.LeftButton:
            flags |= LEFT_BUTTON
        if buttons & Qt.MouseButton.MiddleButton:
            flags |= MIDDLE_BUTTON
        if buttons & Qt.MouseButton.RightButton:
            flags |= RIGHT_BUTTON
    return flags


def drop_actions(ops):
    actions = Qt.DropAction.IgnoreAction
    if ops & _COPY:
        actions |= Qt.DropAction.CopyAction
    if ops & _MOVE:
        actions |= Qt.DropAction.MoveAction
    if ops & _LINK:
        actions |= Qt.DropAction.LinkAction
    return actions


def cef_operations(actions):
    ops = types.DragOperationsMask(0)
    if actions & Qt.DropAction.CopyAction:
        ops |= _COPY
    if actions & Qt.DropAction.MoveAction:
        ops |= _MOVE
    if actions & Qt.DropAction.LinkAction:
        ops |= _LINK
    return ops


class _Timer:
    def __init__(self, parent, seconds, function):
        self.timer = QTimer(parent)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(lambda: (function(), self.timer.deleteLater()))
        self.timer.start(int(seconds * 1000))

    def cancel(self):
        self.timer.stop()
        self.timer.deleteLater()


class QtLoop(QObject):
    """What ``ui.Session`` needs of a toolkit: the Qt event loop."""

    _run = Signal(object)                               # emitted from any thread, delivered in the GUI thread

    def __init__(self):
        super().__init__()
        # queued even when it is emitted in the GUI thread: post() means "from the loop, not in this call"
        self._run.connect(self._invoke, Qt.ConnectionType.QueuedConnection)

    def _invoke(self, function):
        function()

    def post(self, function):
        self._run.emit(function)

    def call_later(self, seconds, function):
        return _Timer(self, seconds, function)


class Runtime(ui.Session):
    """CEF for a Qt application: ``Runtime(...)``, ``start(widget, url)``, ``shutdown(done)``."""

    def __init__(self, switches=(), cache_path=None):
        self.loop = QtLoop()
        super().__init__(self.loop, switches, cache_path)

    def start(self, widget, url):
        super().start(widget.view, url)


class QtAdapter:
    """``ui.ToolkitAdapter`` for a ``CefWidget``. Qt has a drag source for the page (``drag_out``). Qt reads the
    X selection synchronously while CEF, in this thread, would have to answer it: the view does the clipboard
    keys with the clipboard of Qt (no ``native_clipboard``)."""

    capabilities = frozenset({"drag_out"})
    drag_start = "posted"           # QDrag.exec() runs an event loop of its own: not inside the callback of CEF

    def __init__(self, widget, loop):
        self.w, self.loop = widget, loop

    def post(self, function):
        self.loop.post(function)

    def call_later(self, seconds, function):
        return self.loop.call_later(seconds, function)

    def view_size(self):
        return self.w.width(), self.w.height()

    def scale(self):
        return float(self.w.devicePixelRatioF())

    def screen_origin(self):
        point = self.w.mapToGlobal(QPoint(0, 0))
        return point.x(), point.y()

    def screen_size(self):
        screen = self.w.screen().geometry() if self.w.screen() else QRect(0, 0, 1280, 1024)
        return screen.width(), screen.height()

    def present(self, frame):
        self.w.present_frame(frame)

    def set_cursor(self, cursor):
        self.w.setCursor(QCursor(_CURSORS.get(cursor, Qt.CursorShape.ArrowCursor)))

    def set_ime_rect(self, x, y, width, height):         # where the candidate window goes
        self.w.cursor_rect = QRect(x, y, width, height)
        QGuiApplication.inputMethod().update(Qt.InputMethodQuery.ImCursorRectangle)

    def clipboard_get(self):
        return QApplication.clipboard().text() or None

    def clipboard_set(self, text):
        QApplication.clipboard().setText(text)

    def start_drag_out(self, payload, allowed):
        return self.w.run_drag(payload, allowed)         # runs until the drag is over


class CefWidget(QWidget):
    title_changed = Signal(str)
    address_changed = Signal(str)
    loading_changed = Signal(bool, bool, bool)
    browser_ready_signal = Signal()

    def __init__(self, runtime, parent=None):
        super().__init__(parent)
        self.runtime = runtime
        self.view = ui.BrowserView(QtAdapter(self, runtime.loop))
        self.view.on_title = self.title_changed.emit
        self.view.on_address = self.address_changed.emit
        self.view.on_loading = self.loading_changed.emit
        self.view.on_ready = self._on_ready
        self.pixels = None                              # the picture: BGRA, device pixels
        self.image = None
        self.popup_image = None
        self.cursor_rect = QRect(0, 0, 1, 20)
        self._dropping = False
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_InputMethodEnabled, True)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.setAcceptDrops(True)
        self.setMinimumSize(200, 150)

    # -- the browser -----------------------------------------------------------------------------

    @property
    def browser(self):
        return self.view.browser

    @property
    def popup_visible(self):
        return self.view.popup_visible

    def _on_ready(self):
        self.view.focus(self.hasFocus())
        self.browser_ready_signal.emit()

    def load_url(self, url):
        self.view.load_url(url)

    def go_back(self):
        self.view.go_back()

    def go_forward(self):
        self.view.go_forward()

    def reload(self):
        self.view.reload()

    def close_browser(self):
        self.view.close_browser()

    # -- painting --------------------------------------------------------------------------------

    def present_frame(self, frame):
        ratio = self.devicePixelRatioF()
        buffer, width, height = frame.buffer, frame.width, frame.height
        if frame.kind == ui.Frame.POPUP_HIDDEN:
            self.popup_image = None
            self.update()
            return
        if frame.kind == ui.Frame.POPUP:
            data = bytearray(buffer)                    # the memoryview is valid during this call only
            image = QImage(data, width, height, width * 4, QImage.Format.Format_ARGB32)
            image.setDevicePixelRatio(ratio)
            self.popup_data, self.popup_image = data, image
            self.update()
            return
        if self.image is None or self.image.width() != width or self.image.height() != height:
            self.pixels = bytearray(buffer)
            self.image = QImage(self.pixels, width, height, width * 4, QImage.Format.Format_ARGB32)
            self.image.setDevicePixelRatio(ratio)
            self.update()
            return
        stride = width * 4
        for rect in frame.dirty_rects:                  # only the rows that changed
            x0, x1 = max(0, rect.x), min(width, rect.x + rect.width)
            for y in range(max(0, rect.y), min(height, rect.y + rect.height)):
                start = y * stride + x0 * 4
                self.pixels[start:start + (x1 - x0) * 4] = buffer[start:start + (x1 - x0) * 4]
            self.update(QRect(int(rect.x / ratio), int(rect.y / ratio), int(rect.width / ratio) + 2, int(rect.height / ratio) + 2))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.GlobalColor.white)
        if self.image is not None:
            painter.drawImage(0, 0, self.image)
        rect = self.view.popup_rect
        if self.view.popup_visible and self.popup_image is not None and rect is not None:
            painter.drawImage(rect.x, rect.y, self.popup_image)
        painter.end()

    def snapshot(self, path):
        return self.image is not None and self.image.save(path)

    def resizeEvent(self, event):
        self.view.resized()

    def showEvent(self, event):
        self.view.shown(True)

    def hideEvent(self, event):
        self.view.shown(False)

    # -- the mouse -------------------------------------------------------------------------------

    _BUTTONS = {Qt.MouseButton.LeftButton: "left", Qt.MouseButton.MiddleButton: "middle", Qt.MouseButton.RightButton: "right"}

    def mousePressEvent(self, event):
        self.setFocus()
        point = event.position()
        self.view.mouse_button(int(point.x()), int(point.y()), self._BUTTONS.get(event.button()), True,
                               modifier_flags(event.modifiers(), event.buttons()))

    def mouseReleaseEvent(self, event):
        point = event.position()
        self.view.mouse_button(int(point.x()), int(point.y()), self._BUTTONS.get(event.button()), False,
                               modifier_flags(event.modifiers(), event.buttons()))

    def mouseMoveEvent(self, event):
        point = event.position()
        self.view.mouse_move(int(point.x()), int(point.y()), modifier_flags(event.modifiers(), event.buttons()))

    def leaveEvent(self, event):
        self.view.mouse_move(0, 0, 0, leave=True)

    def wheelEvent(self, event):
        delta, point = event.angleDelta(), event.position()
        self.view.wheel(int(point.x()), int(point.y()), delta.x(), delta.y(),
                        modifier_flags(event.modifiers(), event.buttons()))

    # -- the keyboard and the input method -----------------------------------------------------

    def focusInEvent(self, event):
        self.view.focus(True)

    def focusOutEvent(self, event):
        self.view.focus(False)

    def event(self, event):
        if event.type() == QEvent.Type.KeyPress and event.key() in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
            self.keyPressEvent(event)                   # the tab key goes to the page, not to the focus chain
            return True
        return super().event(event)

    def keyPressEvent(self, event):
        text = event.text()
        self.view.key(True, windows_key_code(event.key()), event.nativeScanCode(), modifier_flags(event.modifiers()),
                      char=text[0] if text and text.isprintable() else None)

    def keyReleaseEvent(self, event):
        if not event.isAutoRepeat():
            self.view.key(False, windows_key_code(event.key()), event.nativeScanCode(), modifier_flags(event.modifiers()))

    def inputMethodEvent(self, event):
        commit, preedit = event.commitString(), event.preeditString()
        if commit:
            self.commit_text(commit)
        self.set_preedit(preedit, len(preedit))
        event.accept()

    def inputMethodQuery(self, query):
        if query == Qt.InputMethodQuery.ImCursorRectangle:
            return self.cursor_rect
        if query == Qt.InputMethodQuery.ImEnabled:
            return True
        return super().inputMethodQuery(query)

    def commit_text(self, text):
        self.view.commit_text(text)

    def set_preedit(self, text, cursor):
        self.view.preedit(text, cursor)

    # -- drag and drop: into the page ----------------------------------------------------------------

    @staticmethod
    def _drag_data_of(mime):
        """What the drag carries, as the arguments of ``BrowserView.drag_enter`` (None: nothing usable)."""
        data = {}
        if mime.hasUrls():
            files = [url.toLocalFile() for url in mime.urls() if url.isLocalFile()]
            links = [url.toString() for url in mime.urls() if not url.isLocalFile()]
            if files:
                data["files"] = files
            if links:
                data["url"] = links[-1]
        if mime.hasHtml():
            data["html"] = mime.html()
        if mime.hasText():
            data["text"] = mime.text()
        return data or None

    @staticmethod
    def _drop_point(event):
        point = event.position()
        return int(point.x()), int(point.y())

    def dragEnterEvent(self, event):
        data = self._drag_data_of(event.mimeData())
        if data is None or self.browser is None:
            event.ignore()
            return
        self.view.drag_enter(*self._drop_point(event), cef_operations(event.possibleActions()), **data)
        event.acceptProposedAction()                    # CEF's answer comes later; a drop on a place the page refuses does nothing

    def dragMoveEvent(self, event):
        self.view.drag_over(*self._drop_point(event), cef_operations(event.possibleActions()))
        event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        if not self._dropping:
            self.view.drag_leave()

    def dropEvent(self, event):
        self._dropping = True
        self.view.drag_drop(*self._drop_point(event), cef_operations(event.possibleActions()))
        event.acceptProposedAction()
        self._dropping = False

    # -- drag and drop: out of the page -------------------------------------------------------------

    def run_drag(self, payload, allowed_ops):
        """``QtAdapter.start_drag_out``: a QDrag of what the page drags. QDrag.exec() runs an event loop of its
        own, in which CEF goes on."""
        mime = QMimeData()
        text = payload.text or payload.url
        if text:
            mime.setText(text)
        if payload.files:
            mime.setUrls([QUrl.fromLocalFile(path) for path in payload.files])
        elif payload.url:
            mime.setUrls([QUrl(payload.url)])
        if payload.html:
            mime.setHtml(payload.html)
        if not mime.formats():
            return False
        drag = QDrag(self)
        drag.setMimeData(mime)
        result = drag.exec(drop_actions(allowed_ops) or Qt.DropAction.CopyAction, Qt.DropAction.CopyAction)
        position = self.mapFromGlobal(QCursor.pos())
        operation = cef_operations(result) if result != Qt.DropAction.IgnoreAction else types.DragOperationsMask.NONE
        self.view.drag_out_finished(position.x(), position.y(), operation)
        return True
