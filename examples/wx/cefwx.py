"""A wxPython window that shows a cefweaver offscreen browser.

``Runtime`` owns CEF and runs it from the wx event loop with ``cefweaver.MessagePump``: CEF says (from any
thread) when it wants the loop, ``wx.CallAfter`` (thread safe) carries that into the main thread and a
``wx.Timer`` carries the deadline. ``CefPanel`` is a ``wx.Panel``: the pixels of ``on_paint`` go into a
``wx.Bitmap``, and wx's mouse, wheel and key events become CEF events.

Drag and drop is wx's own: the panel has a ``wx.DropTarget`` (text and files from other programs, and what
the page itself drags), and what the page drags is started with ``wx.DropSource``. wx hands over the dropped
data only at the drop, so a drop from another program reaches the page as enter, over and drop at once.
wx has no input method preedit (README); what an input method commits arrives as characters.
"""

import time

import wx

import cefweaver
from cefweaver import types

SHIFT, CONTROL, ALT = 1 << 1, 1 << 2, 1 << 3                       # EVENTFLAG_* of CEF
LEFT_BUTTON, MIDDLE_BUTTON, RIGHT_BUTTON = 1 << 4, 1 << 5, 1 << 6

_KEYS = {
    wx.WXK_BACK: 8, wx.WXK_TAB: 9, wx.WXK_RETURN: 13, wx.WXK_NUMPAD_ENTER: 13, wx.WXK_ESCAPE: 27, wx.WXK_SPACE: 32,
    wx.WXK_PAGEUP: 33, wx.WXK_PAGEDOWN: 34, wx.WXK_END: 35, wx.WXK_HOME: 36, wx.WXK_LEFT: 37, wx.WXK_UP: 38,
    wx.WXK_RIGHT: 39, wx.WXK_DOWN: 40, wx.WXK_INSERT: 45, wx.WXK_DELETE: 46, wx.WXK_SHIFT: 16, wx.WXK_CONTROL: 17,
    wx.WXK_ALT: 18,
}
_CHAR_KEYS = {wx.WXK_RETURN: 13, wx.WXK_NUMPAD_ENTER: 13, wx.WXK_TAB: 9, wx.WXK_BACK: 8}
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
        return 112 + code - wx.WXK_F1
    if 0x20 <= code < 0x7F:
        return ord(chr(code).upper())
    return 0


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


class Runtime:
    """CEF for a wx application: ``Runtime(...)``, ``start(panel, url)``, ``shutdown(done)``."""

    def __init__(self, switches=(), cache_path=None):
        self.app = cefweaver.CefApp()
        self.app.offscreen = True
        self.app.transparent = False
        if cache_path:
            self.app.set_cache_path(cache_path)
        for name, value in switches:
            self.app.add_command_line_switch(name, value)
        self.bridge = cefweaver.JavascriptBridge(self.app)
        self.pump = cefweaver.MessagePump(self.app, wake=self._wake)
        self.timer = wx.Timer()
        self.timer.Bind(wx.EVT_TIMER, lambda event: self._tick())
        self.started = False
        self.panels = []

    def _wake(self, delay):                             # any thread of CEF
        wx.CallAfter(self._schedule)

    def _schedule(self):
        if self.started:
            self.timer.StartOnce(max(1, int(self.pump.timeout() * 1000)))

    def _tick(self):
        if self.started:
            self.pump.run()
            self._schedule()

    def start(self, panel, url):
        self.panels = [panel]
        self.app.set_client(panel.client)
        self.app.initialize(url)
        self.started = True
        self._schedule()

    def shutdown(self, done=None):
        for panel in list(self.panels):
            panel.close_browser()

        def finish():
            if self.app.is_running:
                wx.CallLater(20, finish)
                return
            self.started = False
            self.timer.Stop()
            self.app.shutdown()
            if done:
                done()
        wx.CallLater(20, finish)


class _Handlers(cefweaver.Client):
    def __init__(self, panel):
        super().__init__()
        self.render, self.life = _Render(panel), _Life(panel)
        self.display, self.load = _Display(panel), _Load(panel)

    def get_render_handler(self):
        return self.render

    def get_life_span_handler(self):
        return self.life

    def get_display_handler(self):
        return self.display

    def get_load_handler(self):
        return self.load


class _Render(cefweaver.RenderHandler):
    def __init__(self, panel):
        self.p = panel

    def get_view_rect(self, browser):
        width, height = self.p.GetClientSize()
        return cefweaver.Rect(0, 0, max(1, width), max(1, height))

    def get_screen_info(self, browser):
        width, height = wx.GetDisplaySize()
        rect = cefweaver.Rect(0, 0, width, height)
        return True, cefweaver.ScreenInfo(float(self.p.GetContentScaleFactor()), 24, 8, 0, rect, rect)

    def get_screen_point(self, browser, view_x, view_y):
        point = self.p.ClientToScreen(wx.Point(view_x, view_y))
        return True, point.x, point.y

    def on_paint(self, browser, type, dirty_rects, buffer, width, height):
        self.p.paint(type, dirty_rects, buffer, width, height)

    def on_popup_show(self, browser, show):
        self.p.popup_show(show)

    def on_popup_size(self, browser, rect):
        self.p.popup_rect = rect

    def on_cursor_change(self, browser, cursor):
        self.p.SetCursor(wx.Cursor(_CURSORS.get(cursor, wx.CURSOR_ARROW)))
        return True

    def on_text_selection_changed(self, browser, selected_text, selected_range):
        self.p.selected_text = selected_text

    def start_dragging(self, browser, drag_data, allowed_ops, x, y):
        return self.p.begin_drag(drag_data, allowed_ops)

    def update_drag_cursor(self, browser, operation):
        self.p.drag_operation = operation
        self.p._over_answered = True


class _Life(cefweaver.LifeSpanHandler):
    def __init__(self, panel):
        self.p = panel

    def on_after_created(self, browser):
        self.p.browser = browser
        self.p.browser_ready()

    def on_before_close(self, browser):
        self.p.browser = None


class _Display(cefweaver.DisplayHandler):
    def __init__(self, panel):
        self.p = panel

    def on_title_change(self, browser, title):
        self.p.on_title(title)

    def on_address_change(self, browser, frame, url):
        if frame.is_main():
            self.p.on_address(url)


class _Load(cefweaver.LoadHandler):
    def __init__(self, panel):
        self.p = panel

    def on_loading_state_change(self, browser, is_loading, can_go_back, can_go_forward):
        if not is_loading:
            # a page restored by "back" from the back-forward cache ignores size changes until CEF is
            # told that the screen information changed (see the GTK example and the wiki, F67)
            self.p.host(lambda h: h.notify_screen_info_changed())
        self.p.on_loading(is_loading, can_go_back, can_go_forward)


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
        self.client = _Handlers(self)
        self.browser = None
        self.bitmap = self.popup_bitmap = None
        self.picture = (0, 0)
        self.popup_rect, self.popup_visible = None, False
        self.selected_text = ""
        self.drag_operation = types.DragOperationsMask.COPY
        self._clicks = (0.0, 0, 0, 0)
        self._internal = None                           # the DragData of a drag that starts in the page
        self._pending_drag = None                       # what to drag at the next pointer move
        self._leaving = False
        self._over_answered = False
        self._internal_allowed = types.DragOperationsMask.COPY
        self._last_key = None
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
        self.Bind(wx.EVT_SET_FOCUS, lambda event: self.host(lambda h: h.set_focus(True)))
        self.Bind(wx.EVT_KILL_FOCUS, lambda event: self.host(lambda h: h.set_focus(False)))
        self.Bind(wx.EVT_SHOW, lambda event: self.host(lambda h: h.was_hidden(not event.IsShown())))

    # -- the browser -----------------------------------------------------------------------------

    def host(self, function):
        if self.browser is not None:
            return function(self.browser.get_host())

    def browser_ready(self):
        self.host(lambda h: h.set_focus(self.HasFocus()))
        self.on_ready()

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

    def _on_size(self, event):
        self.host(lambda h: h.was_resized())
        event.Skip()

    # -- painting --------------------------------------------------------------------------------

    def _bitmap(self, buffer, width, height):
        bitmap = wx.Bitmap(width, height, 32)
        bitmap.CopyFromBuffer(bytes(buffer), wx.BitmapBufferFormat_ARGB32)   # BGRA bytes are ARGB words
        bitmap.SetScaleFactor(self.GetContentScaleFactor())
        return bitmap

    def paint(self, type, dirty_rects, buffer, width, height):
        if type == types.PaintElementType.POPUP:
            self.popup_bitmap = self._bitmap(buffer, width, height)
        else:
            self.bitmap = self._bitmap(buffer, width, height)
            self.picture = (width, height)
        self.Refresh(False)

    def popup_show(self, show):
        self.popup_visible = show
        if not show:
            self.popup_bitmap = None
        self.Refresh(False)

    def _on_paint(self, event):
        dc = wx.AutoBufferedPaintDC(self)
        dc.SetBackground(wx.WHITE_BRUSH)
        dc.Clear()
        if self.bitmap is not None:
            dc.DrawBitmap(self.bitmap, 0, 0)
        if self.popup_visible and self.popup_bitmap is not None and self.popup_rect is not None:
            dc.DrawBitmap(self.popup_bitmap, self.popup_rect.x, self.popup_rect.y)

    def snapshot(self, path):
        if self.bitmap is None:
            return False
        return self.bitmap.ConvertToImage().SaveFile(path, wx.BITMAP_TYPE_PNG)

    # -- the mouse -------------------------------------------------------------------------------

    def _mouse(self, event):
        return types.MouseEvent(event.GetX(), event.GetY(), modifier_flags(event))

    def _on_mouse(self, event):
        if event.ButtonDown():
            self.SetFocus()
        if event.Entering() or event.Leaving():
            self.host(lambda h: h.send_mouse_move_event(self._mouse(event), event.Leaving()))
        elif event.GetWheelRotation():
            dx, dy = (event.GetWheelRotation(), 0) if event.GetWheelAxis() == wx.MOUSE_WHEEL_HORIZONTAL else (0, event.GetWheelRotation())
            self.host(lambda h: h.send_mouse_wheel_event(self._mouse(event), dx, dy))
        elif event.ButtonUp() and self._pending_drag is not None:
            self._cancel_pending_drag()
        elif event.ButtonDown() or event.ButtonUp() or event.ButtonDClick():
            button = event.GetButton()
            kind = {wx.MOUSE_BTN_LEFT: types.MouseButtonType.LEFT, wx.MOUSE_BTN_MIDDLE: types.MouseButtonType.MIDDLE,
                    wx.MOUSE_BTN_RIGHT: types.MouseButtonType.RIGHT}.get(button)
            if kind is not None:
                release = event.ButtonUp()
                if not release:
                    self._count_click(event)
                self.host(lambda h: h.send_mouse_click_event(self._mouse(event), kind, release, self._clicks[3]))
        elif event.Dragging() and self._pending_drag is not None and event.LeftIsDown():
            text, names = self._pending_drag
            self._pending_drag = None
            self._run_drag(text, names)
        elif event.Moving() or event.Dragging():
            self.host(lambda h: h.send_mouse_move_event(self._mouse(event), False))
        event.Skip()

    def _count_click(self, event):
        now = time.monotonic()
        last_time, last_x, last_y, count = self._clicks
        near = abs(event.GetX() - last_x) <= 4 and abs(event.GetY() - last_y) <= 4
        count = count + 1 if now - last_time < 0.4 and near and count < 3 else 1
        self._clicks = (now, event.GetX(), event.GetY(), count)

    # -- the keyboard --------------------------------------------------------------------------------

    def _on_key_down(self, event):
        code = event.GetKeyCode()
        if event.ControlDown() and not event.AltDown() and code in (ord("C"), ord("X"), ord("V")):
            self._clipboard_key(code)       # not CEF: the X selection of this very process (see README)
            return
        base = dict(modifiers=modifier_flags(event), windows_key_code=windows_key_code(code), native_key_code=event.GetRawKeyCode())
        self._last_key = base
        self.host(lambda h: h.send_key_event(types.KeyEvent(types.KeyEventType.RAWKEYDOWN, **base)))
        character = _CHAR_KEYS.get(code)
        if character and not event.ControlDown() and not event.AltDown():
            self.host(lambda h: h.send_key_event(types.KeyEvent(
                types.KeyEventType.CHAR, character=character, unmodified_character=character, **base)))
        event.Skip()                                    # EVT_CHAR follows for characters

    def _on_key_up(self, event):
        code = event.GetKeyCode()
        if event.ControlDown() and code in (ord("C"), ord("X"), ord("V")):
            return
        base = dict(modifiers=modifier_flags(event), windows_key_code=windows_key_code(code), native_key_code=event.GetRawKeyCode())
        self.host(lambda h: h.send_key_event(types.KeyEvent(types.KeyEventType.KEYUP, **base)))
        event.Skip()

    def _on_char(self, event):
        character = event.GetUnicodeKey()
        if character < 0x20 or event.ControlDown() or event.AltDown():
            return
        if character > 0x7F:
            self.commit_text(chr(character))            # what an input method committed
            return
        base = self._last_key or dict(modifiers=0, windows_key_code=windows_key_code(character), native_key_code=0)
        self.host(lambda h: h.send_key_event(types.KeyEvent(
            types.KeyEventType.CHAR, character=character, unmodified_character=character, **base)))

    def _clipboard_key(self, code):
        clipboard = wx.TheClipboard
        if code == ord("V"):
            data = wx.TextDataObject()
            if clipboard.Open():
                found = clipboard.GetData(data)
                clipboard.Close()
                if found and data.GetText():
                    self.commit_text(data.GetText())
            return
        if self.selected_text and clipboard.Open():
            clipboard.SetData(wx.TextDataObject(self.selected_text))
            clipboard.Flush()
            clipboard.Close()
        if code == ord("X") and self.browser is not None:
            self.browser.get_main_frame().delete()

    def commit_text(self, text):
        nothing = cefweaver.Range(0xFFFFFFFF, 0xFFFFFFFF)
        self.host(lambda h: h.ime_commit_text(text, nothing, 0))

    def set_preedit(self, text, cursor):
        """wx gives no preedit of an input method; this is for applications that have one."""
        if not text:
            self.host(lambda h: h.ime_cancel_composition())
            return
        underline = cefweaver.CompositionUnderline(cefweaver.Range(0, len(text)), 0xFF000000, 0, 0, types.CompositionUnderlineStyle.SOLID)
        nothing = cefweaver.Range(0xFFFFFFFF, 0xFFFFFFFF)
        self.host(lambda h: h.ime_set_composition(text, [underline], nothing, cefweaver.Range(cursor, cursor)))

    # -- drag and drop: into the page ------------------------------------------------------------

    def _drag_mouse(self, x, y):
        return types.MouseEvent(x, y, 0)

    def drag_enter(self, x, y):
        if self._internal is not None:                  # the page's own drag: CEF knows the data already
            mouse = self._drag_mouse(x, y)
            self.host(lambda h: h.drag_target_drag_enter(self._internal, mouse, self._internal_allowed))

    def drag_over(self, x, y):
        if self._internal is not None:
            mouse = self._drag_mouse(x, y)
            self.host(lambda h: h.drag_target_drag_over(mouse, self._internal_allowed))

    def drag_leave(self):
        """GTK says "leave" just before a drop, so CEF is told after the next turn of the loop, if no drop came."""
        if self._internal is not None:
            self._leaving = True
            wx.CallAfter(self._finish_leave)

    def _finish_leave(self):
        if self._leaving and self._internal is not None:
            self.host(lambda h: h.drag_target_drag_leave())
        self._leaving = False

    def drag_drop(self, x, y, text=None, files=None):
        self._leaving = False
        mouse = self._drag_mouse(x, y)
        if self._internal is not None:
            self.host(lambda h: (h.drag_target_drag_over(mouse, self._internal_allowed), h.drag_target_drop(mouse)))
            return
        # from another program: wx has the data only now, so the page gets enter, over and drop together
        data = cefweaver.DragData.create()
        if files:
            for name in files:
                data.add_file(name, name.rsplit("/", 1)[-1])
        else:
            data.set_fragment_text(text or "")
        ops = types.DragOperationsMask.COPY
        self._over_answered = False
        self.host(lambda h: (h.drag_target_drag_enter(data, mouse, ops), h.drag_target_drag_over(mouse, ops)))
        self._drop_when_answered(mouse, time.monotonic() + 0.5)

    def _drop_when_answered(self, mouse, deadline):
        """CEF answers a drag_target_drag_over() later (update_drag_cursor); a drop sent before the answer came
        reached the page as dragleave (observed: the first drop from another program was lost that way)."""
        if self._over_answered or time.monotonic() > deadline:
            self.host(lambda h: h.drag_target_drop(mouse))
        else:
            wx.CallLater(10, self._drop_when_answered, mouse, deadline)

    # -- drag and drop: out of the page -------------------------------------------------------------

    def begin_drag(self, data, allowed_ops):
        """CEF's start_dragging(): a wx.DropSource of what the page drags. wx (GTK) starts a drag only inside a
        mouse event handler, so it starts with the next pointer move (``_on_mouse``); DoDragDrop() then runs
        a loop of its own, in which CEF goes on through the timer."""
        text = data.get_fragment_text() or data.get_link_url()
        ok, names = data.get_file_paths() if data.is_file() else (False, [])
        if not text and not (ok and names):
            return False
        self._internal, self._internal_allowed = data, allowed_ops
        self._pending_drag = (text, list(names) if ok else [])
        return True

    def _cancel_pending_drag(self):
        """The button went up before the pointer moved again: there is no drag, CEF has to be told."""
        self._pending_drag = self._internal = None
        self.host(lambda h: (h.drag_source_ended_at(0, 0, types.DragOperationsMask.NONE), h.drag_source_system_drag_ended()))

    def _run_drag(self, text, names):
        if names:
            payload = wx.FileDataObject()
            for name in names:
                payload.AddFile(name)
        else:
            payload = wx.TextDataObject(text)
        source = wx.DropSource(self)
        source.SetData(payload)
        result = source.DoDragDrop(wx.Drag_CopyOnly)
        position = self.ScreenToClient(wx.GetMousePosition())
        self._internal = None
        operation = types.DragOperationsMask.COPY if result == wx.DragCopy else types.DragOperationsMask.NONE
        self.host(lambda h: (h.drag_source_ended_at(position.x, position.y, operation), h.drag_source_system_drag_ended()))
