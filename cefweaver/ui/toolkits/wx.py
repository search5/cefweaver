"""A wxPython panel and adapter that show a cefweaver offscreen browser.

The module provides:

* :class:`WxLoop`: the wx implementation of the loop that :class:`~cefweaver.ui.Session` needs.
* :class:`WxAdapter`: the :class:`~cefweaver.ui.ToolkitAdapter` for a :class:`CefPanel`.
* :class:`CefPanel`: a ``wx.Panel`` that forwards mouse, wheel, keyboard and drop events to a
  :class:`~cefweaver.ui.BrowserView`.

Note:
    wx reports dropped data only at the drop, so a drop from another program reaches the view as
    :meth:`~cefweaver.ui.BrowserView.drop`. wx has no input method preedit; text committed by an input
    method arrives as characters.

Checked: Xvfb with GDK_BACKEND=x11 and xdotool: the 33 checks of examples/wx/smoke.py (wxPython 4.2.5 for GTK 3), also with CEF on Wayland.
Not checked: wx on Windows or macOS, a real input method, a scale other than 1.
"""

import wx

from cefweaver import types, ui
from cefweaver.ui import keys

_KEYS = {
    wx.WXK_BACK: keys.VK_BACK, wx.WXK_TAB: keys.VK_TAB, wx.WXK_RETURN: keys.VK_RETURN, wx.WXK_NUMPAD_ENTER: keys.VK_RETURN,
    wx.WXK_ESCAPE: keys.VK_ESCAPE, wx.WXK_SPACE: keys.VK_SPACE, wx.WXK_PAGEUP: keys.VK_PRIOR, wx.WXK_PAGEDOWN: keys.VK_NEXT,
    wx.WXK_END: keys.VK_END, wx.WXK_HOME: keys.VK_HOME, wx.WXK_LEFT: keys.VK_LEFT, wx.WXK_UP: keys.VK_UP,
    wx.WXK_RIGHT: keys.VK_RIGHT, wx.WXK_DOWN: keys.VK_DOWN, wx.WXK_INSERT: keys.VK_INSERT, wx.WXK_DELETE: keys.VK_DELETE,
    wx.WXK_SHIFT: keys.VK_SHIFT, wx.WXK_CONTROL: keys.VK_CONTROL, wx.WXK_ALT: keys.VK_ALT,
}
_CURSORS = {
    types.CursorType.POINTER: wx.CURSOR_ARROW, types.CursorType.HAND: wx.CURSOR_HAND, types.CursorType.IBEAM: wx.CURSOR_IBEAM,
    types.CursorType.CROSS: wx.CURSOR_CROSS, types.CursorType.WAIT: wx.CURSOR_WAIT, types.CursorType.HELP: wx.CURSOR_QUESTION_ARROW,
    types.CursorType.MOVE: wx.CURSOR_SIZING, types.CursorType.NOTALLOWED: wx.CURSOR_NO_ENTRY, types.CursorType.NODROP: wx.CURSOR_NO_ENTRY,
    types.CursorType.COLUMNRESIZE: wx.CURSOR_SIZEWE, types.CursorType.ROWRESIZE: wx.CURSOR_SIZENS,
    types.CursorType.EASTWESTRESIZE: wx.CURSOR_SIZEWE, types.CursorType.NORTHSOUTHRESIZE: wx.CURSOR_SIZENS,
}


_KEYTABLE = ui.KeyTable(_KEYS, function=ui.function_range(wx.WXK_F1),
                        char=lambda code: chr(code) if 0x20 <= code < 0x7F else None)
_MODIFIERS = ui.EventModifiers()
_CURSOR_SHAPES = ui.CursorTable(_CURSORS, default=wx.CURSOR_ARROW)


def windows_key_code(code):
    """Return the Windows virtual key code of a wx key code.

    Args:
        code (int): The ``wx.WXK_*`` or character code from ``wx.KeyEvent.GetKeyCode()``.

    Returns:
        int: The ``VK_*`` code, or 0 if the key has none.
    """
    return _KEYTABLE.code(code)


def modifier_flags(event):
    """Return the CEF event flags for the modifiers and mouse buttons of a wx event.

    Args:
        event (wx.KeyEvent or wx.MouseEvent): The event to read.

    Returns:
        int: The combined ``EVENTFLAG_*`` bit mask.
    """
    return _MODIFIERS.flags(event)


class _Later:
    def __init__(self, seconds, function):
        self.timer = wx.CallLater(max(1, int(seconds * 1000)), function)

    def cancel(self):
        self.timer.Stop()


class WxLoop:
    """The wx event loop as the loop of a :class:`~cefweaver.ui.Session`.

    It provides ``post`` and ``call_later`` and needs no panel.
    """

    def post(self, function):                           # any thread
        """Run ``function`` in the wx main loop with ``wx.CallAfter``.

        Args:
            function (callable): A callable without arguments.

        Note:
            Callable from any thread.
        """
        wx.CallAfter(function)

    def call_later(self, seconds, function):
        """Run ``function`` in the wx main loop after a delay with ``wx.CallLater``.

        Args:
            seconds (float): The delay in seconds, at least 1 ms.
            function (callable): A callable without arguments.

        Returns:
            object: A handle with a ``cancel()`` method.
        """
        return _Later(seconds, function)


class WxAdapter(WxLoop):
    """The :class:`~cefweaver.ui.ToolkitAdapter` for a :class:`CefPanel`.

    It supports ``drag_out`` and uses wx's clipboard (there is no ``native_clipboard`` capability).

    Args:
        panel (CefPanel): The panel that shows the frames.

    Attributes:
        capabilities (frozenset): ``{"drag_out"}``.
        drag_start (str): ``"on_motion"``: a drag starts with the next pointer move.
        p (CefPanel): The panel.
        menu_open (bool): True while a context menu is shown.
        last_menu (wx.Menu): The most recent context menu, set by :meth:`show_menu`.
    """

    capabilities = frozenset({"drag_out"})
    drag_start = "on_motion"        # wx (GTK) starts a drag only inside a mouse event handler

    def __init__(self, panel):
        self.p = panel
        self.menu_open = False                                   # a context menu is up (for tests)
        self.last_menu = self._waiting = None

    def view_size(self):
        """Return the client size of the panel in logical pixels."""
        return tuple(self.p.GetClientSize())

    def scale(self):
        """Return the content scale factor of the panel."""
        return float(self.p.GetContentScaleFactor())

    def screen_origin(self):
        """Return the position of the panel's top left corner in screen coordinates."""
        point = self.p.ClientToScreen(wx.Point(0, 0))
        return point.x, point.y

    def screen_size(self):
        """Return the size of the display."""
        return tuple(wx.GetDisplaySize())

    def present(self, frame):
        """Pass the frame to :meth:`CefPanel.present_frame`."""
        self.p.present_frame(frame)

    def set_cursor(self, cursor):
        """Set the panel's cursor to the wx cursor for the CEF cursor type."""
        self.p.SetCursor(wx.Cursor(_CURSOR_SHAPES.get(cursor)))

    def show_menu(self, items, x, y, done):
        """Pop up the page's context menu as a ``wx.Menu`` at (``x``, ``y``) in panel coordinates.

        The menu opens through ``wx.CallAfter``, after the right mouse button has been released (waiting at most
        about one second), because ``PopupMenu`` runs a nested event loop.

        Args:
            items (list): The menu entries, each with ``kind``, ``label``, ``enabled``, ``checked``,
                ``command_id`` and, for submenus, ``children``.
            x (int): The horizontal position in panel coordinates.
            y (int): The vertical position in panel coordinates.
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
                    menu.AppendSeparator()
                    continue
                label = entry.label.replace("&", "&&")             # & marks a mnemonic in wx
                if entry.kind == "submenu":
                    sub = wx.Menu()
                    fill(sub, entry.children)
                    item = menu.AppendSubMenu(sub, label)
                elif entry.kind == "check":
                    item = menu.AppendCheckItem(wx.ID_ANY, label)
                    item.Check(entry.checked)
                elif entry.kind == "radio":
                    item = menu.AppendRadioItem(wx.ID_ANY, label)
                    item.Check(entry.checked)
                else:
                    item = menu.Append(wx.ID_ANY, label)
                item.Enable(entry.enabled)
                if entry.kind != "submenu":
                    menu.Bind(wx.EVT_MENU, lambda event, command_id=entry.command_id: pick(command_id), item)

        def show():
            menu = wx.Menu()
            fill(menu, items)
            self.last_menu, self.menu_open = menu, True
            try:
                self.p.PopupMenu(menu, wx.Point(int(x), int(y)))      # returns when the menu is closed
            finally:
                self.menu_open = False
            pick(None)                                                # nothing was picked
            menu.Destroy()
        def when_released(attempt=0):
            # CEF asks for the menu when the right button goes down. A menu that comes up while the button is still down is
            # closed by the release that follows, so it waits for the button (at most a second)
            if wx.GetMouseState().RightIsDown() and attempt < 100:
                self._waiting = wx.CallLater(10, when_released, attempt + 1)      # wx drops a timer that nobody holds
            else:
                self._waiting = None
                show()
        wx.CallAfter(when_released)

    def clipboard_get(self):
        """Return the text on the wx clipboard, or None if it is empty or cannot be opened."""
        data = wx.TextDataObject()
        if not wx.TheClipboard.Open():
            return None
        found = wx.TheClipboard.GetData(data)
        wx.TheClipboard.Close()
        return data.GetText() if found else None

    def clipboard_set(self, text):
        """Put ``text`` on the wx clipboard; do nothing if the clipboard cannot be opened."""
        if wx.TheClipboard.Open():
            wx.TheClipboard.SetData(wx.TextDataObject(text))
            wx.TheClipboard.Flush()
            wx.TheClipboard.Close()

    def start_drag_out(self, payload, allowed):
        """Start a ``wx.DropSource`` drag for the page's drag through :meth:`CefPanel.run_drag`.

        Returns:
            bool: Always True.

        Note:
            Blocks until the drag ends.
        """
        self.p.run_drag(payload)                        # runs until the drag is over
        return True


class _DropTarget(wx.DropTarget):
    """A drop target for text and files from other programs and for the page's own drags.

    Args:
        panel (CefPanel): The panel that receives the drag events.
    """

    def __init__(self, panel):
        super().__init__()
        self.p = panel
        self.files, self.text = wx.FileDataObject(), wx.TextDataObject()
        both = wx.DataObjectComposite()
        both.Add(self.files)
        both.Add(self.text, True)
        self.SetDataObject(both)
        self.both = both

    def OnEnter(self, x, y, default):
        """Tell the panel that a drag entered; propose copying."""
        self.p.drag_enter(x, y)
        return wx.DragCopy

    def OnDragOver(self, x, y, default):
        """Tell the panel that a drag moved; propose copying."""
        self.p.drag_over(x, y)
        return wx.DragCopy

    def OnLeave(self):
        """Tell the panel that the drag left."""
        self.p.drag_leave()

    def OnDrop(self, x, y):
        """Accept the drop so that its data is requested."""
        return True

    def OnData(self, x, y, default):
        """Pass the dropped files or text to the panel; return ``wx.DragNone`` if no data arrived."""
        if not self.GetData():
            return wx.DragNone
        if self.both.GetReceivedFormat().GetType() == wx.DF_FILENAME:
            self.p.drag_drop(x, y, files=list(self.files.GetFilenames()))
        else:
            self.p.drag_drop(x, y, text=self.text.GetText())
        return wx.DragCopy


class CefPanel(ui.BrowserWidget, wx.Panel):
    """A ``wx.Panel`` that shows a cefweaver browser.

    It is a :class:`~cefweaver.ui.BrowserWidget`, so the navigation methods and ``view`` are available.
    The application sets the ``on_*`` callbacks to receive browser notifications.

    Args:
        parent (wx.Window): The parent window.
        runtime (object): The running runtime.
        audio (optional): The ``audio`` option of :class:`~cefweaver.ui.BrowserView`.

    Attributes:
        runtime (object): The runtime passed in.
        bitmap (wx.Bitmap): The latest view frame, or None.
        popup_bitmap (wx.Bitmap): The latest popup frame, or None.
        picture (tuple): ``(width, height)`` of the latest view frame in device pixels.
        on_title (callable): Called with the page title.
        on_address (callable): Called with the page URL.
        on_loading (callable): Called with ``loading``, ``can_go_back`` and ``can_go_forward``.
        on_ready (callable): Called when the browser has been created.
    """

    def __init__(self, parent, runtime, audio=None):
        super().__init__(parent, style=wx.WANTS_CHARS)
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.runtime = runtime
        self.attach_view(WxAdapter(self), audio=audio)
        self.bitmap = self.popup_bitmap = None
        self.picture = (0, 0)
        self.on_title = self.on_address = lambda value: None
        self.on_loading = lambda loading, back, forward: None
        self.on_ready = lambda: None
        self.SetDropTarget(_DropTarget(self))
        self.Bind(wx.EVT_PAINT, self._on_paint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, lambda event: None)
        self.Bind(wx.EVT_SIZE, self._on_size)
        self.Bind(wx.EVT_MOUSE_EVENTS, self._on_mouse)
        self.Bind(wx.EVT_KEY_DOWN, self._on_key_down)
        self.Bind(wx.EVT_KEY_UP, self._on_key_up)
        self.Bind(wx.EVT_CHAR, self._on_char)
        self.Bind(wx.EVT_SET_FOCUS, lambda event: self.view.focus(True))
        self.Bind(wx.EVT_KILL_FOCUS, lambda event: self.view.focus(False))
        self.Bind(wx.EVT_SHOW, lambda event: self.view.shown(event.IsShown()))

    # -- the browser -----------------------------------------------------------------------------

    def browser_title(self, title):
        """Call :attr:`on_title` with the page title."""
        self.on_title(title)

    def browser_address(self, url):
        """Call :attr:`on_address` with the page URL."""
        self.on_address(url)

    def browser_loading(self, loading, can_back, can_forward):
        """Call :attr:`on_loading` with the loading state and the navigation flags."""
        self.on_loading(loading, can_back, can_forward)

    def browser_ready(self):
        """Pass the panel's focus state to the view and call :attr:`on_ready`."""
        self.view.focus(self.HasFocus())
        self.on_ready()

    def _on_size(self, event):
        self.view.resized()
        event.Skip()

    # -- painting --------------------------------------------------------------------------------

    def _bitmap(self, buffer, width, height):
        bitmap = wx.Bitmap(width, height, 32)
        bitmap.CopyFromBuffer(bytes(buffer), wx.BitmapBufferFormat_ARGB32)   # BGRA bytes are ARGB words
        bitmap.SetScaleFactor(self.GetContentScaleFactor())
        return bitmap

    def present_frame(self, frame):
        """Store a frame as a ``wx.Bitmap`` and refresh the panel.

        Args:
            frame (Frame): The frame to show.
        """
        if frame.kind == ui.Frame.POPUP_HIDDEN:
            self.popup_bitmap = None
        elif frame.kind == ui.Frame.POPUP:
            self.popup_bitmap = self._bitmap(frame.buffer, frame.width, frame.height)
        else:
            self.bitmap = self._bitmap(frame.buffer, frame.width, frame.height)
            self.picture = (frame.width, frame.height)
        self.Refresh(False)

    def _on_paint(self, event):
        dc = wx.AutoBufferedPaintDC(self)
        dc.SetBackground(wx.WHITE_BRUSH)
        dc.Clear()
        if self.bitmap is not None:
            dc.DrawBitmap(self.bitmap, 0, 0)
        rect = self.view.popup_rect
        if self.view.popup_visible and self.popup_bitmap is not None and rect is not None:
            dc.DrawBitmap(self.popup_bitmap, rect.x, rect.y)

    # -- the mouse -------------------------------------------------------------------------------

    _BUTTONS = {wx.MOUSE_BTN_LEFT: "left", wx.MOUSE_BTN_MIDDLE: "middle", wx.MOUSE_BTN_RIGHT: "right"}

    def _on_mouse(self, event):
        x, y, mods = event.GetX(), event.GetY(), modifier_flags(event)
        if event.ButtonDown():
            self.SetFocus()
        if event.Entering() or event.Leaving():
            self.view.mouse_move(x, y, mods, leave=event.Leaving())
        elif event.GetWheelRotation():
            rotation = event.GetWheelRotation()
            horizontal = event.GetWheelAxis() == wx.MOUSE_WHEEL_HORIZONTAL
            self.view.wheel(x, y, rotation if horizontal else 0, 0 if horizontal else rotation, mods)
        elif event.ButtonDown() or event.ButtonUp() or event.ButtonDClick():
            self.view.mouse_button(x, y, self._BUTTONS.get(event.GetButton()), not event.ButtonUp(), mods)
        elif event.Moving() or event.Dragging():
            self.view.mouse_move(x, y, mods)
        event.Skip()

    # -- the keyboard --------------------------------------------------------------------------------

    def _on_key_down(self, event):
        if self.view.key(True, windows_key_code(event.GetKeyCode()), event.GetRawKeyCode(), modifier_flags(event)):
            return                                      # the clipboard keys: done by the view
        event.Skip()                                    # EVT_CHAR follows for characters

    def _on_key_up(self, event):
        if not self.view.key(False, windows_key_code(event.GetKeyCode()), event.GetRawKeyCode(), modifier_flags(event)):
            event.Skip()

    def _on_char(self, event):
        character = event.GetUnicodeKey()
        if character >= 0x20 and not event.ControlDown() and not event.AltDown():
            self.view.text(chr(character))              # a letter, or what an input method committed

    # -- drag and drop: into the page ------------------------------------------------------------

    def drag_enter(self, x, y):
        """Tell the view that a drag entered at (``x``, ``y``); the operation offered is copy."""
        self.view.drag_enter(x, y, types.DragOperationsMask.COPY)     # the view ignores it for another program

    def drag_over(self, x, y):
        """Tell the view that a drag moved to (``x``, ``y``); the operation offered is copy."""
        self.view.drag_over(x, y, types.DragOperationsMask.COPY)

    def drag_leave(self):
        """Tell the view that the drag left."""
        self.view.drag_leave()

    def drag_drop(self, x, y, text=None, files=None):
        """Send a drop at (``x``, ``y``) with its data to the view.

        Args:
            x (int): The horizontal position in panel coordinates.
            y (int): The vertical position in panel coordinates.
            text (str, optional): Dropped text.
            files (list, optional): Dropped file names.
        """
        self.view.drag_drop(x, y, types.DragOperationsMask.COPY, text=text, files=files)   # data only now

    # -- drag and drop: out of the page ------------------------------------------------------------

    def run_drag(self, payload):
        """Run a ``wx.DropSource`` drag for data the page drags out, then report the result to the view.

        Args:
            payload (DragPayload): What the page drags; files are dragged if present, otherwise its text or URL.

        Note:
            Blocks in ``DoDragDrop()`` until the drag ends. Only copying is offered.
        """
        if payload.files:
            data = wx.FileDataObject()
            for name in payload.files:
                data.AddFile(name)
        else:
            data = wx.TextDataObject(payload.text or payload.url)   # DropSource does not own it: keep it alive
        source = wx.DropSource(self)
        source.SetData(data)
        result = source.DoDragDrop(wx.Drag_CopyOnly)
        position = self.ScreenToClient(wx.GetMousePosition())
        operation = types.DragOperationsMask.COPY if result == wx.DragCopy else types.DragOperationsMask.NONE
        self.view.drag_out_finished(position.x, position.y, operation)
