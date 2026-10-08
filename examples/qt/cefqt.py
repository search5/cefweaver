"""A Qt widget that shows a cefweaver offscreen browser, for PyQt6 and for PySide6.

The same code runs with both: ``CEFQT_BINDING=pyqt6`` or ``pyside6`` chooses (default: PyQt6 if it
is installed). ``Runtime`` owns CEF and runs it from the Qt event loop with ``cefweaver.MessagePump``;
``CefWidget`` paints the pixels of ``on_paint`` and turns Qt's mouse, wheel, keyboard, input method,
and drag and drop events into CEF events. Copy and paste need no code: the key events go to CEF and
Chromium's clipboard is the system clipboard.
"""

import os
import time

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

import cefweaver
from cefweaver import types

SHIFT, CONTROL, ALT = 1 << 1, 1 << 2, 1 << 3                       # EVENTFLAG_* of CEF
LEFT_BUTTON, MIDDLE_BUTTON, RIGHT_BUTTON = 1 << 4, 1 << 5, 1 << 6

_KEYS = {
    Qt.Key.Key_Backspace: 8, Qt.Key.Key_Tab: 9, Qt.Key.Key_Backtab: 9, Qt.Key.Key_Return: 13, Qt.Key.Key_Enter: 13,
    Qt.Key.Key_Escape: 27, Qt.Key.Key_Space: 32, Qt.Key.Key_PageUp: 33, Qt.Key.Key_PageDown: 34, Qt.Key.Key_End: 35,
    Qt.Key.Key_Home: 36, Qt.Key.Key_Left: 37, Qt.Key.Key_Up: 38, Qt.Key.Key_Right: 39, Qt.Key.Key_Down: 40,
    Qt.Key.Key_Insert: 45, Qt.Key.Key_Delete: 46, Qt.Key.Key_Shift: 16, Qt.Key.Key_Control: 17, Qt.Key.Key_Alt: 18,
}
_CHAR_KEYS = {Qt.Key.Key_Return: 13, Qt.Key.Key_Enter: 13, Qt.Key.Key_Tab: 9, Qt.Key.Key_Backspace: 8}
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
        return 112 + key - int(Qt.Key.Key_F1)
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


class Runtime(QObject):
    """CEF for a Qt application: ``Runtime(...)``, ``start(widget, url)``, ``shutdown()``."""

    woke = Signal()                                     # emitted from any thread, delivered in the GUI thread

    def __init__(self, switches=(), cache_path=None):
        super().__init__()
        self.app = cefweaver.CefApp()
        self.app.offscreen = True
        self.app.transparent = False
        if cache_path:
            self.app.set_cache_path(cache_path)
        for name, value in switches:
            self.app.add_command_line_switch(name, value)
        self.bridge = cefweaver.JavascriptBridge(self.app)
        self.pump = cefweaver.MessagePump(self.app, wake=lambda delay: self.woke.emit())
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._tick)
        self.woke.connect(self._schedule)
        self.started = False
        self.widgets = []

    def _schedule(self):
        self.timer.start(int(self.pump.timeout() * 1000))

    def _tick(self):
        if self.started:
            self.pump.run()
            self._schedule()

    def start(self, widget, url):
        self.widgets = [widget]
        self.app.set_client(widget.client)
        self.app.initialize(url)
        self.started = True
        self._schedule()

    def shutdown(self, done=None):
        for widget in list(self.widgets):
            widget.close_browser()
        probe = QTimer(self)

        def finish():
            if self.app.is_running:
                return
            probe.stop()
            self.started = False
            self.timer.stop()
            self.app.shutdown()
            if done:
                done()
        probe.timeout.connect(finish)
        probe.start(20)


class _Handlers(cefweaver.Client):
    def __init__(self, widget):
        super().__init__()
        self.render, self.life = _Render(widget), _Life(widget)
        self.display, self.load = _Display(widget), _Load(widget)

    def get_render_handler(self):
        return self.render

    def get_life_span_handler(self):
        return self.life

    def get_display_handler(self):
        return self.display

    def get_load_handler(self):
        return self.load


class _Render(cefweaver.RenderHandler):
    def __init__(self, widget):
        self.w = widget

    def get_view_rect(self, browser):
        return cefweaver.Rect(0, 0, max(1, self.w.width()), max(1, self.w.height()))

    def get_screen_info(self, browser):
        screen = self.w.screen().geometry() if self.w.screen() else QRect(0, 0, 1280, 1024)
        rect = cefweaver.Rect(0, 0, screen.width(), screen.height())
        return True, cefweaver.ScreenInfo(float(self.w.devicePixelRatioF()), 24, 8, 0, rect, rect)

    def get_screen_point(self, browser, view_x, view_y):
        point = self.w.mapToGlobal(QPoint(int(view_x), int(view_y)))
        return True, point.x(), point.y()

    def on_paint(self, browser, type, dirty_rects, buffer, width, height):
        self.w.paint(type, dirty_rects, buffer, width, height)

    def on_popup_show(self, browser, show):
        self.w.popup_show(show)

    def on_popup_size(self, browser, rect):
        self.w.popup_rect = rect

    def on_cursor_change(self, browser, cursor):
        self.w.setCursor(QCursor(_CURSORS.get(cursor, Qt.CursorShape.ArrowCursor)))
        return True

    def start_dragging(self, browser, drag_data, allowed_ops, x, y):
        return self.w.begin_drag(drag_data, allowed_ops)

    def update_drag_cursor(self, browser, operation):
        self.w.drag_operation = operation

    def on_text_selection_changed(self, browser, selected_text, selected_range):
        if os.environ.get("CEFQT_DEBUG"):
            print("DBG on_text_selection_changed", repr(selected_text), tuple(selected_range))
        self.w.selected_text = selected_text

    def on_ime_composition_range_changed(self, browser, selected_range, character_bounds):
        if character_bounds:                            # where the candidate window goes
            last = character_bounds[-1]
            self.w.cursor_rect = QRect(last.x, last.y, last.width, last.height)
            QGuiApplication.inputMethod().update(Qt.InputMethodQuery.ImCursorRectangle)


class _Life(cefweaver.LifeSpanHandler):
    def __init__(self, widget):
        self.w = widget

    def on_after_created(self, browser):
        self.w.browser = browser
        self.w.browser_ready()

    def on_before_close(self, browser):
        self.w.browser = None


class _Display(cefweaver.DisplayHandler):
    def __init__(self, widget):
        self.w = widget

    def on_title_change(self, browser, title):
        self.w.title_changed.emit(title)

    def on_address_change(self, browser, frame, url):
        if frame.is_main():
            self.w.address_changed.emit(url)


class _Load(cefweaver.LoadHandler):
    def __init__(self, widget):
        self.w = widget

    def on_loading_state_change(self, browser, is_loading, can_go_back, can_go_forward):
        if not is_loading:
            # a page restored by "back" from the back-forward cache ignores size changes until CEF is
            # told that the screen information changed (see the GTK example and the wiki, F67)
            self.w.host(lambda h: h.notify_screen_info_changed())
        self.w.loading_changed.emit(is_loading, can_go_back, can_go_forward)


class CefWidget(QWidget):
    title_changed = Signal(str)
    address_changed = Signal(str)
    loading_changed = Signal(bool, bool, bool)
    browser_ready_signal = Signal()

    def __init__(self, runtime, parent=None):
        super().__init__(parent)
        self.runtime = runtime
        self.client = _Handlers(self)
        self.browser = None
        self.pixels = None                              # the picture: BGRA, device pixels
        self.image = None
        self.popup_rect = None
        self.popup_image = None
        self.popup_visible = False
        self.cursor_rect = QRect(0, 0, 1, 20)
        self.selected_text = ""
        self.drag_operation = _COPY
        self._clicks = (0.0, 0, 0, 0)                   # when, x, y and count of the last press
        self._drag_out = None
        self._dropping = False
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_InputMethodEnabled, True)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.setAcceptDrops(True)
        self.setMinimumSize(200, 150)

    # -- the browser -----------------------------------------------------------------------------

    def host(self, function):
        if self.browser is not None:
            return function(self.browser.get_host())

    def browser_ready(self):
        self.host(lambda h: h.set_focus(self.hasFocus()))
        self.browser_ready_signal.emit()

    def load_url(self, url):
        if self.browser is not None:
            self.browser.get_main_frame().load_url(url)

    def go_back(self):
        if self.browser is not None:
            self.browser.go_back()

    def go_forward(self):
        if self.browser is not None:
            self.browser.go_forward()

    def reload(self):
        if self.browser is not None:
            self.browser.reload()

    def close_browser(self):
        self.host(lambda h: h.close_browser(True))

    # -- painting --------------------------------------------------------------------------------

    def paint(self, type, dirty_rects, buffer, width, height):
        ratio = self.devicePixelRatioF()
        if type == types.PaintElementType.POPUP:
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
        for rect in dirty_rects:                        # only the rows that changed
            x0, x1 = max(0, rect.x), min(width, rect.x + rect.width)
            for y in range(max(0, rect.y), min(height, rect.y + rect.height)):
                start = y * stride + x0 * 4
                self.pixels[start:start + (x1 - x0) * 4] = buffer[start:start + (x1 - x0) * 4]
            self.update(QRect(int(rect.x / ratio), int(rect.y / ratio), int(rect.width / ratio) + 2, int(rect.height / ratio) + 2))

    def popup_show(self, show):
        self.popup_visible = show
        if not show:
            self.popup_image = None
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.GlobalColor.white)
        if self.image is not None:
            painter.drawImage(0, 0, self.image)
        if self.popup_visible and self.popup_image is not None and self.popup_rect is not None:
            painter.drawImage(self.popup_rect.x, self.popup_rect.y, self.popup_image)
        painter.end()

    def snapshot(self, path):
        return self.image is not None and self.image.save(path)

    def resizeEvent(self, event):
        self.host(lambda h: h.was_resized())

    def showEvent(self, event):
        self.host(lambda h: h.was_hidden(False))

    def hideEvent(self, event):
        self.host(lambda h: h.was_hidden(True))

    # -- the mouse -------------------------------------------------------------------------------

    def _mouse(self, event):
        point = event.position()
        return types.MouseEvent(int(point.x()), int(point.y()), modifier_flags(event.modifiers(), event.buttons()))

    @staticmethod
    def _button(event):
        return {Qt.MouseButton.LeftButton: types.MouseButtonType.LEFT, Qt.MouseButton.MiddleButton: types.MouseButtonType.MIDDLE,
                Qt.MouseButton.RightButton: types.MouseButtonType.RIGHT}.get(event.button())

    def mousePressEvent(self, event):
        self.setFocus()
        point = event.position()
        now = time.monotonic()
        last_time, last_x, last_y, count = self._clicks       # Qt has no triple click: count them here
        near = abs(point.x() - last_x) <= 4 and abs(point.y() - last_y) <= 4
        count = count + 1 if now - last_time < QApplication.doubleClickInterval() / 1000.0 and near and count < 3 else 1
        self._clicks = (now, point.x(), point.y(), count)
        button = self._button(event)
        if button is not None:
            self.host(lambda h: h.send_mouse_click_event(self._mouse(event), button, False, count))

    def mouseReleaseEvent(self, event):
        button = self._button(event)
        if button is not None:
            self.host(lambda h: h.send_mouse_click_event(self._mouse(event), button, True, self._clicks[3]))

    def mouseMoveEvent(self, event):
        self.host(lambda h: h.send_mouse_move_event(self._mouse(event), False))

    def leaveEvent(self, event):
        self.host(lambda h: h.send_mouse_move_event(types.MouseEvent(0, 0, 0), True))

    def wheelEvent(self, event):
        delta = event.angleDelta()
        point = event.position()
        mouse = types.MouseEvent(int(point.x()), int(point.y()), modifier_flags(event.modifiers(), event.buttons()))
        self.host(lambda h: h.send_mouse_wheel_event(mouse, delta.x(), delta.y()))

    # -- the keyboard and the input method -----------------------------------------------------

    def focusInEvent(self, event):
        self.host(lambda h: h.set_focus(True))

    def focusOutEvent(self, event):
        self.host(lambda h: h.set_focus(False))

    def event(self, event):
        if event.type() == QEvent.Type.KeyPress and event.key() in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
            self.keyPressEvent(event)                   # the tab key goes to the page, not to the focus chain
            return True
        return super().event(event)

    def keyPressEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier and event.key() in (Qt.Key.Key_C, Qt.Key.Key_X):
            # Copy and cut are done here. If CEF did them it would own the X selection, and Qt reads
            # a selection synchronously, without letting CEF (this very thread) answer: it would hang.
            if self.selected_text:
                QApplication.clipboard().setText(self.selected_text)
            if event.key() == Qt.Key.Key_X:
                self.host(lambda h: None) if self.browser is None else self.browser.get_main_frame().delete()
            return
        self._send_key(event, False)

    def keyReleaseEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier and event.key() in (Qt.Key.Key_C, Qt.Key.Key_X):
            return
        self._send_key(event, True)

    def _send_key(self, event, release):
        if event.isAutoRepeat() and release:
            return
        modifiers = modifier_flags(event.modifiers())
        base = dict(modifiers=modifiers, windows_key_code=windows_key_code(event.key()), native_key_code=event.nativeScanCode())
        if release:
            self.host(lambda h: h.send_key_event(types.KeyEvent(types.KeyEventType.KEYUP, **base)))
            return
        self.host(lambda h: h.send_key_event(types.KeyEvent(types.KeyEventType.RAWKEYDOWN, **base)))
        text = event.text()
        character = _CHAR_KEYS.get(event.key()) or (ord(text[0]) if text and text.isprintable() else 0)
        if character and not modifiers & (CONTROL | ALT):
            self.host(lambda h: h.send_key_event(types.KeyEvent(
                types.KeyEventType.CHAR, character=character, unmodified_character=character, **base)))

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
        nothing = cefweaver.Range(0xFFFFFFFF, 0xFFFFFFFF)
        self.host(lambda h: h.ime_commit_text(text, nothing, 0))

    def set_preedit(self, text, cursor):
        if not text:
            self.host(lambda h: h.ime_cancel_composition())
            return
        underline = cefweaver.CompositionUnderline(cefweaver.Range(0, len(text)), 0xFF000000, 0, 0, types.CompositionUnderlineStyle.SOLID)
        nothing = cefweaver.Range(0xFFFFFFFF, 0xFFFFFFFF)
        self.host(lambda h: h.ime_set_composition(text, [underline], nothing, cefweaver.Range(cursor, cursor)))

    # -- drag and drop: into the page ----------------------------------------------------------------

    def _drag_data_of(self, mime):
        data = cefweaver.DragData.create()
        usable = False
        if mime.hasUrls():
            for url in mime.urls():
                if url.isLocalFile():
                    data.add_file(url.toLocalFile(), os.path.basename(url.toLocalFile()))
                else:
                    data.set_link_url(url.toString())
                usable = True
        if mime.hasHtml():
            data.set_fragment_html(mime.html())
            usable = True
        if mime.hasText():
            data.set_fragment_text(mime.text())
            usable = True
        return data if usable else None

    def _drop_point(self, event):
        point = event.position()
        return types.MouseEvent(int(point.x()), int(point.y()), 0)

    def dragEnterEvent(self, event):
        data = self._drag_data_of(event.mimeData())
        if data is None or self.browser is None:
            event.ignore()
            return
        self.drag_operation = _COPY
        ops = cef_operations(event.possibleActions())
        mouse = self._drop_point(event)
        self.host(lambda h: h.drag_target_drag_enter(data, mouse, ops))
        event.acceptProposedAction()                    # CEF's answer comes later; a drop on a place the page refuses does nothing

    def dragMoveEvent(self, event):
        ops = cef_operations(event.possibleActions())
        mouse = self._drop_point(event)
        self.host(lambda h: h.drag_target_drag_over(mouse, ops))
        event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        if not self._dropping:
            self.host(lambda h: h.drag_target_drag_leave())

    def dropEvent(self, event):
        self._dropping = True
        ops = cef_operations(event.possibleActions())
        mouse = self._drop_point(event)
        self.host(lambda h: (h.drag_target_drag_over(mouse, ops), h.drag_target_drop(mouse)))
        event.acceptProposedAction()
        self._dropping = False

    # -- drag and drop: out of the page -------------------------------------------------------------

    def begin_drag(self, data, allowed_ops):
        """CEF's start_dragging(): a QDrag of what the page drags. It starts from the event loop (not
        inside this callback): QDrag.exec() runs an event loop of its own, in which CEF has to go on."""
        mime = QMimeData()
        text = data.get_fragment_text() or data.get_link_url()
        if text:
            mime.setText(text)
        if data.is_file():
            ok, paths = data.get_file_paths()
            if ok:
                mime.setUrls([QUrl.fromLocalFile(path) for path in paths])
        elif data.is_link():
            mime.setUrls([QUrl(data.get_link_url())])
        if data.get_fragment_html():
            mime.setHtml(data.get_fragment_html())
        if not mime.formats():
            return False
        self._drag_out = (mime, drop_actions(allowed_ops) or Qt.DropAction.CopyAction, data)
        QTimer.singleShot(0, self._run_drag)
        return True

    def _run_drag(self):
        if self._drag_out is None:
            return
        mime, actions, _data = self._drag_out
        drag = QDrag(self)
        drag.setMimeData(mime)
        result = drag.exec(actions, Qt.DropAction.CopyAction)
        position = self.mapFromGlobal(QCursor.pos())
        self._drag_out = None
        operation = cef_operations(result) if result != Qt.DropAction.IgnoreAction else types.DragOperationsMask.NONE
        self.host(lambda h: (h.drag_source_ended_at(position.x(), position.y(), operation), h.drag_source_system_drag_ended()))
