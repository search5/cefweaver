"""A wxPython window that shows a cefweaver offscreen browser, built on ``cefweaver.ui``.

``cefweaver.ui`` has the CEF side (``BrowserView``, ``Session``). This file is what wx adds, the adapter:

* ``WxLoop``: running something in the wx loop from any thread (``wx.CallAfter``) and later (``wx.CallLater``);
* ``WxAdapter``: size, scale and place of the panel, drawing the frames into a ``wx.Bitmap``, the cursor,
  the clipboard of wx and the drag that wx starts for the page (``wx.DropSource``);
* ``CefPanel``: a ``wx.Panel`` that passes the mouse, wheel and keys of wx and its drop target to the view.

wx hands over the dropped data only at the drop, so a drop from another program reaches the view as
``drop()``. The drag of the page itself, over its own panel, goes step by step. wx has no input method
preedit (README); what an input method commits arrives as characters.
"""

import wx

from cefweaver import types, ui
from cefweaver.ui import keys

SHIFT, CONTROL, ALT = keys.SHIFT, keys.CONTROL, keys.ALT
LEFT_BUTTON, MIDDLE_BUTTON, RIGHT_BUTTON = keys.LEFT_BUTTON, keys.MIDDLE_BUTTON, keys.RIGHT_BUTTON

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


def windows_key_code(code):
    if code in _KEYS:
        return _KEYS[code]
    if wx.WXK_F1 <= code <= wx.WXK_F12:
        return keys.vk_for_function(code - wx.WXK_F1 + 1)
    return keys.vk_for_char(chr(code)) if 0x20 <= code < 0x7F else 0


def modifier_flags(event):
    flags = 0
    if event.ShiftDown():
        flags |= SHIFT
    if event.ControlDown():
        flags |= CONTROL
    if event.AltDown():
        flags |= ALT
    if isinstance(event, wx.MouseEvent):
        if event.LeftIsDown():
            flags |= LEFT_BUTTON
        if event.MiddleIsDown():
            flags |= MIDDLE_BUTTON
        if event.RightIsDown():
            flags |= RIGHT_BUTTON
    return flags


class _Later:
    def __init__(self, seconds, function):
        self.timer = wx.CallLater(max(1, int(seconds * 1000)), function)

    def cancel(self):
        self.timer.Stop()


class WxLoop:
    """What ``ui.Session`` needs of a toolkit: the wx loop."""

    def post(self, function):                           # any thread
        wx.CallAfter(function)

    def call_later(self, seconds, function):
        return _Later(seconds, function)


class Runtime(ui.Session):
    """CEF for a wx application: ``Runtime(...)``, ``start(panel, url)``, ``shutdown(done)``."""

    def __init__(self, switches=(), cache_path=None):
        super().__init__(WxLoop(), switches, cache_path)

    def start(self, panel, url):
        super().start(panel.view, url)


class WxAdapter(WxLoop):
    """``ui.ToolkitAdapter`` for a ``CefPanel``. wx has a drag source for the page (``drag_out``) and a text
    clipboard, but not one CEF could use from this thread."""

    capabilities = frozenset({"drag_out"})

    def __init__(self, panel):
        self.p = panel

    def view_size(self):
        return tuple(self.p.GetClientSize())

    def scale(self):
        return float(self.p.GetContentScaleFactor())

    def screen_origin(self):
        point = self.p.ClientToScreen(wx.Point(0, 0))
        return point.x, point.y

    def screen_size(self):
        return tuple(wx.GetDisplaySize())

    def present(self, frame):
        self.p.present_frame(frame)

    def set_cursor(self, cursor):
        self.p.SetCursor(wx.Cursor(_CURSORS.get(cursor, wx.CURSOR_ARROW)))

    def clipboard_get(self):
        data = wx.TextDataObject()
        if not wx.TheClipboard.Open():
            return None
        found = wx.TheClipboard.GetData(data)
        wx.TheClipboard.Close()
        return data.GetText() if found else None

    def clipboard_set(self, text):
        if wx.TheClipboard.Open():
            wx.TheClipboard.SetData(wx.TextDataObject(text))
            wx.TheClipboard.Flush()
            wx.TheClipboard.Close()

    def start_drag_out(self, payload, allowed):
        return self.p.begin_drag(payload)


class _DropTarget(wx.DropTarget):
    """Text and files from other programs, and what the page itself drags."""

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
        self.p.drag_enter(x, y)
        return wx.DragCopy

    def OnDragOver(self, x, y, default):
        self.p.drag_over(x, y)
        return wx.DragCopy

    def OnLeave(self):
        self.p.drag_leave()

    def OnDrop(self, x, y):
        return True

    def OnData(self, x, y, default):
        if not self.GetData():
            return wx.DragNone
        if self.both.GetReceivedFormat().GetType() == wx.DF_FILENAME:
            self.p.drag_drop(x, y, files=list(self.files.GetFilenames()))
        else:
            self.p.drag_drop(x, y, text=self.text.GetText())
        return wx.DragCopy


class CefPanel(wx.Panel):
    """The browser. ``on_title``, ``on_address``, ``on_loading`` and ``on_ready`` are set by the application."""

    def __init__(self, parent, runtime):
        super().__init__(parent, style=wx.WANTS_CHARS)
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.runtime = runtime
        self.view = ui.BrowserView(WxAdapter(self))
        self.bitmap = self.popup_bitmap = None
        self.picture = (0, 0)
        self._pending_drag = None                       # the payload to drag at the next pointer move
        self._dragging_out = False                      # inside wx.DropSource.DoDragDrop
        self.on_title = self.on_address = lambda value: None
        self.on_loading = lambda loading, back, forward: None
        self.on_ready = lambda: None
        self.view.on_title = lambda title: self.on_title(title)
        self.view.on_address = lambda url: self.on_address(url)
        self.view.on_loading = lambda *state: self.on_loading(*state)
        self.view.on_ready = self._on_ready
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

    @property
    def browser(self):
        return self.view.browser

    @property
    def popup_visible(self):
        return self.view.popup_visible

    def _on_ready(self):
        self.view.focus(self.HasFocus())
        self.on_ready()

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

    def snapshot(self, path):
        if self.bitmap is None:
            return False
        return self.bitmap.ConvertToImage().SaveFile(path, wx.BITMAP_TYPE_PNG)

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
        elif event.ButtonUp() and self._pending_drag is not None:
            self._pending_drag = None                   # the button went up before the pointer moved again
            self.view.drag_out_finished(x, y, types.DragOperationsMask.NONE)
        elif event.ButtonDown() or event.ButtonUp() or event.ButtonDClick():
            self.view.mouse_button(x, y, self._BUTTONS.get(event.GetButton()), not event.ButtonUp(), mods)
        elif event.Dragging() and self._pending_drag is not None and event.LeftIsDown():
            payload, self._pending_drag = self._pending_drag, None
            self._run_drag(payload)
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

    def commit_text(self, text):
        self.view.commit_text(text)

    def set_preedit(self, text, cursor):
        """wx gives no preedit of an input method; this is for applications that have one."""
        self.view.preedit(text, cursor)

    # -- drag and drop: into the page ------------------------------------------------------------

    def drag_enter(self, x, y):
        if self._dragging_out:                          # the page's own drag: CEF knows the data already
            self.view.drag_enter(x, y, types.DragOperationsMask.COPY)

    def drag_over(self, x, y):
        if self._dragging_out:
            self.view.drag_over(x, y, types.DragOperationsMask.COPY)

    def drag_leave(self):
        if self._dragging_out:
            self.view.drag_leave()

    def drag_drop(self, x, y, text=None, files=None):
        if self._dragging_out:
            self.view.drag_drop(x, y, types.DragOperationsMask.COPY)
        else:                                           # from another program: wx has the data only now
            self.view.drop(x, y, text=text, files=files)

    # -- drag and drop: out of the page ------------------------------------------------------------

    def begin_drag(self, payload):
        """``WxAdapter.start_drag_out``. wx (GTK) starts a drag only inside a mouse event handler, so it
        starts with the next pointer move (``_on_mouse``); DoDragDrop() then runs a loop of its own, in
        which CEF goes on through the timers."""
        if not (payload.files or payload.text or payload.url):
            return False
        self._pending_drag = payload
        return True

    def _run_drag(self, payload):
        if payload.files:
            data = wx.FileDataObject()
            for name in payload.files:
                data.AddFile(name)
        else:
            data = wx.TextDataObject(payload.text or payload.url)   # DropSource does not own it: keep it alive
        source = wx.DropSource(self)
        source.SetData(data)
        self._dragging_out = True
        try:
            result = source.DoDragDrop(wx.Drag_CopyOnly)
        finally:
            self._dragging_out = False
        position = self.ScreenToClient(wx.GetMousePosition())
        operation = types.DragOperationsMask.COPY if result == wx.DragCopy else types.DragOperationsMask.NONE
        self.view.drag_out_finished(position.x, position.y, operation)
