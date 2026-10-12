"""A Qt widget and adapter that show a cefweaver offscreen browser, for PyQt6 and PySide6.

The binding is chosen by the ``CEFQT_BINDING`` environment variable (``"pyqt6"`` or ``"pyside6"``); if it is
unset or invalid, PyQt6 is used when it is installed, otherwise PySide6. The module-level ``BINDING`` holds
the name of the binding in use.

The module provides:

* :class:`QtLoop`: the Qt implementation of the loop that :class:`~cefweaver.ui.Session` needs.
* :class:`QtAdapter`: the :class:`~cefweaver.ui.ToolkitAdapter` for a :class:`CefWidget`.
* :class:`QtSink`: an audio sink that plays the page's sound with QtMultimedia.
* :class:`CefWidget`: a ``QWidget`` that forwards mouse, wheel, keyboard, input method and drag and drop
  events to a :class:`~cefweaver.ui.BrowserView`.

Checked: Xvfb with QT_QPA_PLATFORM=xcb and xdotool, PyQt6 and PySide6: the 35 checks of examples/qt/smoke.py at scale 1 and 2; PyQt6 also with CEF on Wayland.
Not checked: a real input method (ibus, fcitx), Qt on Wayland, anything but plain text in the clipboard.
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
    from PyQt6.QtGui import QAction, QCursor, QDrag, QGuiApplication, QImage, QInputMethodEvent, QPainter
    from PyQt6.QtWidgets import QApplication, QMenu, QWidget
else:
    from PySide6.QtCore import QEvent, QMimeData, QObject, QPoint, QRect, Qt, QTimer, QUrl
    from PySide6.QtCore import Signal
    from PySide6.QtGui import QAction, QCursor, QDrag, QGuiApplication, QImage, QInputMethodEvent, QPainter
    from PySide6.QtWidgets import QApplication, QMenu, QWidget

from cefweaver import types, ui
from cefweaver.ui import keys

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


_KEYTABLE = ui.KeyTable({int(qt_key): code for qt_key, code in _KEYS.items()},
                        function=ui.function_range(int(Qt.Key.Key_F1)),
                        char=lambda key: chr(key) if 0x20 <= key < 0x7F else None)    # Qt's letters are the capitals
_MODIFIERS = ui.MaskModifiers(
    shift=Qt.KeyboardModifier.ShiftModifier, control=Qt.KeyboardModifier.ControlModifier,
    alt=Qt.KeyboardModifier.AltModifier, left=Qt.MouseButton.LeftButton, middle=Qt.MouseButton.MiddleButton,
    right=Qt.MouseButton.RightButton)
_CURSOR_SHAPES = ui.CursorTable(_CURSORS, default=Qt.CursorShape.ArrowCursor)


def windows_key_code(key):
    """Return the Windows virtual key code of a Qt key.

    Args:
        key (Qt.Key or int): The Qt key, as returned by ``QKeyEvent.key()``.

    Returns:
        int: The ``VK_*`` code, or 0 if the key has none.
    """
    return _KEYTABLE.code(int(key))


def modifier_flags(modifiers, buttons=Qt.MouseButton.NoButton):
    """Return the CEF event flags for Qt modifiers and mouse buttons.

    Args:
        modifiers (Qt.KeyboardModifier): The keyboard modifiers of the event.
        buttons (Qt.MouseButton, optional): The mouse buttons that are down. Defaults to no button.

    Returns:
        int: The combined ``EVENTFLAG_*`` bit mask.
    """
    return _MODIFIERS.flags(modifiers, buttons)


def drop_actions(ops):
    """Convert CEF drag operations to Qt drop actions.

    Args:
        ops (types.DragOperationsMask): The operations CEF allows.

    Returns:
        Qt.DropAction: The corresponding actions; ``IgnoreAction`` if none.
    """
    actions = Qt.DropAction.IgnoreAction
    if ops & _COPY:
        actions |= Qt.DropAction.CopyAction
    if ops & _MOVE:
        actions |= Qt.DropAction.MoveAction
    if ops & _LINK:
        actions |= Qt.DropAction.LinkAction
    return actions


def cef_operations(actions):
    """Convert Qt drop actions to CEF drag operations.

    Args:
        actions (Qt.DropAction): The Qt drop actions.

    Returns:
        types.DragOperationsMask: The corresponding operations; empty if none.
    """
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
    """The Qt event loop as the loop of a :class:`~cefweaver.ui.Session`.

    It provides ``post`` and ``call_later`` and needs no widget. Create it in the GUI thread.
    """

    _run = Signal(object)                               # emitted from any thread, delivered in the GUI thread

    def __init__(self):
        super().__init__()
        # queued even when it is emitted in the GUI thread: post() means "from the loop, not in this call"
        self._run.connect(self._invoke, Qt.ConnectionType.QueuedConnection)

    def _invoke(self, function):
        function()

    def post(self, function):
        """Run ``function`` in the GUI thread, queued through a Qt signal.

        Args:
            function (callable): A callable without arguments.

        Note:
            Callable from any thread. ``function`` never runs inside this call, even in the GUI thread.
        """
        self._run.emit(function)

    def call_later(self, seconds, function):
        """Run ``function`` in the GUI thread after a delay, using a single-shot ``QTimer``.

        Args:
            seconds (float): The delay in seconds.
            function (callable): A callable without arguments.

        Returns:
            object: A handle with a ``cancel()`` method.

        Note:
            Call from the GUI thread.
        """
        return _Timer(self, seconds, function)


def _multimedia():
    """QtMultimedia of the binding in use: (QAudioFormat, QAudioSink, QMediaDevices), or None if it is not there."""
    try:
        if BINDING == "pyqt6":
            from PyQt6.QtMultimedia import QAudioFormat, QAudioSink, QMediaDevices
        else:
            from PySide6.QtMultimedia import QAudioFormat, QAudioSink, QMediaDevices
    except ImportError:
        return None
    return QAudioFormat, QAudioSink, QMediaDevices


class QtSink:
    """An audio sink that plays the page's sound through a ``QAudioSink`` (QtMultimedia) in push mode.

    ``start``, ``write`` and ``stop`` may be called from CEF's audio thread; they post their work to the GUI
    thread in order.

    Args:
        loop (QtLoop): The loop used to reach the GUI thread.
        volume (float, optional): The volume from 0.0 to 1.0. Defaults to 1.0.
        latency (float, optional): The size of the device buffer in seconds. Defaults to 0.1.
        max_latency (float, optional): The most audio, in seconds, that may wait to be written; older
            samples are dropped beyond it. Defaults to 0.5.

    Attributes:
        loop (QtLoop): The loop passed in.
        latency (float): The device buffer size in seconds.
        max_latency (float): The limit of queued audio in seconds.
        volume (float): The volume of the ``QAudioSink``, from 0.0 to 1.0.
    """

    def __init__(self, loop, volume=1.0, latency=0.1, max_latency=0.5):
        self.loop, self.latency, self.max_latency = loop, latency, max_latency
        self._volume = volume
        self._sink = self._io = None
        self._rate = self._channels = 0
        self._pending = bytearray()
        self._counters = dict(written=0, dropped=0, underruns=0)
        self._timer = None
        self._processed = 0
        self._was_idle = True

    def _processed_frames(self, sink):
        return int(sink.processedUSecs() * self._rate / 1_000_000)

    @property
    def volume(self):
        """float: The volume from 0.0 to 1.0. Setting it applies it to the running sink."""
        return self._volume

    @volume.setter
    def volume(self, value):
        """Set the volume and apply it to the running sink in the GUI thread."""
        self._volume = value
        self.loop.post(lambda: self._sink.setVolume(value) if self._sink is not None else None)

    # called in the thread of CEF's audio stream: they only post
    def start(self, sample_rate, channels):
        """Start playback of a stream, replacing any running one.

        Args:
            sample_rate (int): The sample rate in Hz.
            channels (int): The number of channels.

        Note:
            Callable from any thread.
        """
        self.loop.post(lambda: self._start(sample_rate, channels))

    def write(self, samples, frames):
        """Queue interleaved 32-bit float samples for playback.

        Args:
            samples (bytes): The samples, ``frames * channels * 4`` bytes.
            frames (int): The number of frames in ``samples``.

        Note:
            Callable from any thread.
        """
        self.loop.post(lambda: self._write(samples, frames))

    def stop(self):
        """Stop playback and discard queued samples.

        Note:
            Callable from any thread.
        """
        self.loop.post(self._stop)

    # in the GUI thread
    def _start(self, sample_rate, channels):
        self._stop()
        QAudioFormat, QAudioSink, QMediaDevices = _multimedia()
        form = QAudioFormat()
        form.setSampleRate(sample_rate)
        form.setChannelCount(channels)
        form.setSampleFormat(QAudioFormat.SampleFormat.Float)
        sink = QAudioSink(QMediaDevices.defaultAudioOutput(), form)
        sink.setBufferSize(int(sample_rate * self.latency) * channels * 4)
        sink.setVolume(self._volume)
        self._sink, self._io = sink, sink.start()
        self._rate, self._channels = sample_rate, channels
        self._pending.clear()
        self._timer = QTimer(self.loop)
        self._timer.timeout.connect(self._flush)
        self._timer.start(5)                                    # the sink takes more as it plays

    def _write(self, samples, frames):
        if self._io is None:
            return
        self._pending += samples
        self._counters["written"] += frames
        limit = int(self._rate * self.max_latency) * self._channels * 4
        if len(self._pending) > limit:                          # the application cannot keep up
            extra = len(self._pending) - limit
            del self._pending[:extra]
            self._counters["dropped"] += extra // (4 * self._channels)
        self._flush()

    def _flush(self):
        if self._sink is not None:
            idle = "Idle" in str(self._sink.state())            # it ran empty (polled: the signal does not convert in PySide)
            if idle and not self._was_idle and self._counters["written"]:
                self._counters["underruns"] += 1
            self._was_idle = idle
        if self._io is not None and self._pending:
            taken = self._io.write(bytes(self._pending))
            if taken > 0:
                del self._pending[:taken]

    def _stop(self):
        if self._timer is not None:
            self._timer.stop()
            self._timer = None
        sink, self._sink, self._io = self._sink, None, None
        if sink is not None:
            self._processed = self._processed_frames(sink)
            sink.stop()
        self._pending.clear()

    def stats(self):
        """Return playback counters, in frames.

        Returns:
            dict: ``written``, ``dropped``, ``underruns``, ``queued`` and ``consumed``. ``consumed`` is what the
            device has played, as ``QAudioSink`` counts it.

        Note:
            Call from the GUI thread.
        """
        queued = len(self._pending) // (4 * max(1, self._channels))
        counters = dict(self._counters)
        counters["queued"] = queued
        # what the device has played, as QAudioSink counts it (in the GUI thread: that is where it may be asked)
        counters["consumed"] = self._processed_frames(self._sink) if self._sink is not None else self._processed
        return counters


class QtAdapter:
    """The :class:`~cefweaver.ui.ToolkitAdapter` for a :class:`CefWidget`.

    It supports ``drag_out`` and uses Qt's clipboard (there is no ``native_clipboard`` capability).

    Args:
        widget (CefWidget): The widget that shows the frames.
        loop (QtLoop): The loop used by ``post`` and ``call_later``.

    Attributes:
        capabilities (frozenset): ``{"drag_out"}``.
        drag_start (str): ``"posted"``: a drag starts from the loop, outside CEF's callback.
        w (CefWidget): The widget.
        loop (QtLoop): The loop.
        last_menu (QMenu): The most recent context menu, set by :meth:`show_menu`.
    """

    capabilities = frozenset({"drag_out"})
    drag_start = "posted"           # QDrag.exec() runs an event loop of its own: not inside the callback of CEF

    def __init__(self, widget, loop):
        self.w, self.loop = widget, loop

    def post(self, function):
        """Run ``function`` in the GUI thread through the loop."""
        self.loop.post(function)

    def call_later(self, seconds, function):
        """Run ``function`` in the GUI thread after ``seconds`` through the loop; return its cancel handle."""
        return self.loop.call_later(seconds, function)

    def audio_sink(self):
        """Return a :class:`QtSink`, or None if QtMultimedia or an audio output device is missing.

        Returns:
            QtSink or None: The sink used by ``BrowserView(audio="auto")``.
        """
        parts = _multimedia()
        if parts is None or parts[2].defaultAudioOutput().isNull():
            return None
        return QtSink(self.loop)

    def view_size(self):
        """Return the size of the widget in logical pixels."""
        return self.w.width(), self.w.height()

    def scale(self):
        """Return the device pixel ratio of the widget."""
        return float(self.w.devicePixelRatioF())

    def screen_origin(self):
        """Return the position of the widget's top left corner in global screen coordinates."""
        point = self.w.mapToGlobal(QPoint(0, 0))
        return point.x(), point.y()

    def screen_size(self):
        """Return the size of the widget's screen, or 1280x1024 if the widget has no screen."""
        screen = self.w.screen().geometry() if self.w.screen() else QRect(0, 0, 1280, 1024)
        return screen.width(), screen.height()

    def present(self, frame):
        """Pass the frame to :meth:`CefWidget.present_frame`."""
        self.w.present_frame(frame)

    def set_cursor(self, cursor):
        """Set the widget's cursor to the Qt shape for the CEF cursor type."""
        self.w.setCursor(QCursor(_CURSOR_SHAPES.get(cursor)))

    def set_ime_rect(self, x, y, width, height):         # where the candidate window goes
        """Store the cursor rectangle in the widget and notify the input method, which places its candidate window there."""
        self.w.cursor_rect = QRect(x, y, width, height)
        QGuiApplication.inputMethod().update(Qt.InputMethodQuery.ImCursorRectangle)

    def show_menu(self, items, x, y, done):
        """Pop up the page's context menu as a ``QMenu`` at (``x``, ``y``) in widget coordinates.

        Args:
            items (list): The menu entries, each with ``kind``, ``label``, ``enabled``, ``checked``,
                ``command_id`` and, for submenus, ``children``.
            x (int): The horizontal position in widget coordinates.
            y (int): The vertical position in widget coordinates.
            done (callable): Called once with the command id of the chosen item, or None if the menu closed
                without a choice.
        """
        picked = []

        def pick(command_id):
            if not picked:
                picked.append(command_id)
                done(command_id)

        def fill(menu, entries):
            for entry in entries:
                if entry.kind == "separator":
                    menu.addSeparator()
                elif entry.kind == "submenu":
                    fill(menu.addMenu(entry.label.replace("&", "&&")), entry.children)      # & marks a mnemonic in Qt
                    menu.actions()[-1].setEnabled(entry.enabled)
                else:
                    action = QAction(entry.label.replace("&", "&&"), menu)
                    action.setEnabled(entry.enabled)
                    if entry.kind in ("check", "radio"):
                        action.setCheckable(True)
                        action.setChecked(entry.checked)
                    action.triggered.connect(lambda checked=False, command_id=entry.command_id: pick(command_id))
                    menu.addAction(action)
        menu = QMenu(self.w)
        fill(menu, items)
        # an action is triggered after the menu hid: leaving the menu is told only when nothing was picked
        menu.aboutToHide.connect(lambda: QTimer.singleShot(50, lambda: pick(None)))
        self.last_menu = menu
        menu.popup(self.w.mapToGlobal(QPoint(int(x), int(y))))

    def clipboard_get(self):
        """Return the text on the Qt clipboard, or None if it is empty."""
        return QApplication.clipboard().text() or None

    def clipboard_set(self, text):
        """Put ``text`` on the Qt clipboard."""
        QApplication.clipboard().setText(text)

    def start_drag_out(self, payload, allowed):
        """Start a ``QDrag`` for the page's drag through :meth:`CefWidget.run_drag`.

        Returns:
            bool: True if a drag ran.

        Note:
            Blocks until the drag ends.
        """
        return self.w.run_drag(payload, allowed)         # runs until the drag is over


class CefWidget(ui.BrowserWidget, QWidget):
    """A ``QWidget`` that shows a cefweaver browser.

    It is a :class:`~cefweaver.ui.BrowserWidget`, so the navigation methods and ``view`` are available.
    Qt mouse, wheel, key, input method and drag and drop events are forwarded to the
    :class:`~cefweaver.ui.BrowserView`.

    Args:
        runtime (object): The running runtime; its ``adapter`` attribute is the :class:`QtLoop`.
        parent (QWidget, optional): The parent widget.
        audio (optional): The ``audio`` option of :class:`~cefweaver.ui.BrowserView`.

    Attributes:
        runtime (object): The runtime passed in.
        image (QImage): The latest view frame, or None.
        popup_image (QImage): The latest popup frame, or None.
        cursor_rect (QRect): The cursor rectangle reported to the input method.
        title_changed (Signal): Emitted with the page title (``str``).
        address_changed (Signal): Emitted with the page URL (``str``).
        loading_changed (Signal): Emitted with ``loading``, ``can_go_back`` and ``can_go_forward`` (``bool``
            each).
        browser_ready_signal (Signal): Emitted when the browser has been created.
    """
    title_changed = Signal(str)
    address_changed = Signal(str)
    loading_changed = Signal(bool, bool, bool)
    browser_ready_signal = Signal()

    def __init__(self, runtime, parent=None, audio=None):
        super().__init__(parent)
        self.runtime = runtime
        self.attach_view(QtAdapter(self, runtime.adapter), audio=audio)
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

    def browser_title(self, title):
        """Emit :attr:`title_changed` with the page title."""
        self.title_changed.emit(title)

    def browser_address(self, url):
        """Emit :attr:`address_changed` with the page URL."""
        self.address_changed.emit(url)

    def browser_loading(self, loading, can_back, can_forward):
        """Emit :attr:`loading_changed` with the loading state and the navigation flags."""
        self.loading_changed.emit(loading, can_back, can_forward)

    def browser_ready(self):
        """Pass the widget's focus state to the view and emit :attr:`browser_ready_signal`."""
        self.view.focus(self.hasFocus())
        self.browser_ready_signal.emit()

    # -- painting --------------------------------------------------------------------------------

    def present_frame(self, frame):
        """Store a frame as a ``QImage`` and schedule a repaint of the changed area.

        Args:
            frame (Frame): The frame to show.
        """
        change, store = frame.change, self.view.store
        ratio = self.devicePixelRatioF()
        if change.kind == ui.PictureStore.POPUP_HIDDEN:
            self.popup_image = None
        elif change.kind == ui.PictureStore.POPUP:
            width, height = store.popup_size
            self.popup_image = QImage(store.popup_pixels, width, height, width * 4, QImage.Format.Format_ARGB32)
            self.popup_image.setDevicePixelRatio(ratio)
        elif change.kind == ui.PictureStore.NEW:
            width, height = store.size
            self.image = QImage(store.pixels, width, height, width * 4, QImage.Format.Format_ARGB32)
            self.image.setDevicePixelRatio(ratio)
        else:
            for rect in change.rects:                   # only what changed
                self.update(QRect(int(rect.x / ratio), int(rect.y / ratio), int(rect.width / ratio) + 2, int(rect.height / ratio) + 2))
            return
        self.update()

    def paintEvent(self, event):
        """Paint a white background, the view image and the popup, if visible."""
        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.GlobalColor.white)
        if self.image is not None:
            painter.drawImage(0, 0, self.image)
        rect = self.view.popup_rect
        if self.view.popup_visible and self.popup_image is not None and rect is not None:
            painter.drawImage(rect.x, rect.y, self.popup_image)
        painter.end()

    def resizeEvent(self, event):
        """Tell the view that the widget was resized."""
        self.view.resized()

    def showEvent(self, event):
        """Tell the view that the widget is shown."""
        self.view.shown(True)

    def hideEvent(self, event):
        """Tell the view that the widget is hidden."""
        self.view.shown(False)

    # -- the mouse -------------------------------------------------------------------------------

    _BUTTONS = {Qt.MouseButton.LeftButton: "left", Qt.MouseButton.MiddleButton: "middle", Qt.MouseButton.RightButton: "right"}

    def mousePressEvent(self, event):
        """Focus the widget and send the button press to the view."""
        self.setFocus()
        point = event.position()
        self.view.mouse_button(int(point.x()), int(point.y()), self._BUTTONS.get(event.button()), True,
                               modifier_flags(event.modifiers(), event.buttons()))

    def mouseReleaseEvent(self, event):
        """Send the button release to the view."""
        point = event.position()
        self.view.mouse_button(int(point.x()), int(point.y()), self._BUTTONS.get(event.button()), False,
                               modifier_flags(event.modifiers(), event.buttons()))

    def mouseMoveEvent(self, event):
        """Send the pointer move to the view."""
        point = event.position()
        self.view.mouse_move(int(point.x()), int(point.y()), modifier_flags(event.modifiers(), event.buttons()))

    def leaveEvent(self, event):
        """Tell the view that the pointer left the widget."""
        self.view.mouse_move(0, 0, 0, leave=True)

    def wheelEvent(self, event):
        """Send the wheel delta to the view."""
        delta, point = event.angleDelta(), event.position()
        self.view.wheel(int(point.x()), int(point.y()), delta.x(), delta.y(),
                        modifier_flags(event.modifiers(), event.buttons()))

    # -- the keyboard and the input method -----------------------------------------------------

    def focusInEvent(self, event):
        """Tell the view that the widget gained focus."""
        self.view.focus(True)

    def focusOutEvent(self, event):
        """Tell the view that the widget lost focus."""
        self.view.focus(False)

    def event(self, event):
        """Route Tab and Backtab presses to the page instead of the focus chain; handle other events as usual."""
        if event.type() == QEvent.Type.KeyPress and event.key() in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
            self.keyPressEvent(event)                   # the tab key goes to the page, not to the focus chain
            return True
        return super().event(event)

    def keyPressEvent(self, event):
        """Send the key press, with its printable character if any, to the view."""
        text = event.text()
        self.view.key(True, windows_key_code(event.key()), event.nativeScanCode(), modifier_flags(event.modifiers()),
                      char=text[0] if text and text.isprintable() else None)

    def keyReleaseEvent(self, event):
        """Send the key release to the view; auto-repeat releases are ignored."""
        if not event.isAutoRepeat():
            self.view.key(False, windows_key_code(event.key()), event.nativeScanCode(), modifier_flags(event.modifiers()))

    def inputMethodEvent(self, event):
        """Commit the input method's committed text and set its preedit text on the page."""
        commit, preedit = event.commitString(), event.preeditString()
        if commit:
            self.commit_text(commit)
        self.set_preedit(preedit, len(preedit))
        event.accept()

    def inputMethodQuery(self, query):
        """Answer the input method's cursor rectangle and enabled queries; delegate other queries to ``QWidget``."""
        if query == Qt.InputMethodQuery.ImCursorRectangle:
            return self.cursor_rect
        if query == Qt.InputMethodQuery.ImEnabled:
            return True
        return super().inputMethodQuery(query)

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
        """Accept a drag that carries files, a URL, HTML or text, and start it in the view; ignore other drags."""
        data = self._drag_data_of(event.mimeData())
        if data is None or self.browser is None:
            event.ignore()
            return
        self.view.drag_enter(*self._drop_point(event), cef_operations(event.possibleActions()), **data)
        event.acceptProposedAction()                    # CEF's answer comes later; a drop on a place the page refuses does nothing

    def dragMoveEvent(self, event):
        """Send the drag position and allowed operations to the view."""
        self.view.drag_over(*self._drop_point(event), cef_operations(event.possibleActions()))
        event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        """Tell the view that the drag left, unless a drop is in progress."""
        if not self._dropping:
            self.view.drag_leave()

    def dropEvent(self, event):
        """Send the drop to the view."""
        self._dropping = True
        self.view.drag_drop(*self._drop_point(event), cef_operations(event.possibleActions()))
        event.acceptProposedAction()
        self._dropping = False

    # -- drag and drop: out of the page -------------------------------------------------------------

    def run_drag(self, payload, allowed_ops):
        """Run a ``QDrag`` for data the page drags out, then report the result to the view.

        Args:
            payload (DragPayload): What the page drags.
            allowed_ops (types.DragOperationsMask): The operations the page allows.

        Returns:
            bool: False if the payload has no usable data and no drag started, otherwise True.

        Note:
            Blocks in the nested event loop of ``QDrag.exec()`` until the drag ends.
        """
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
