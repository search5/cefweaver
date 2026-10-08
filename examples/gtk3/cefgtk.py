"""A GTK 3 widget that shows a cefweaver offscreen browser.

``Runtime`` owns CEF (one per process) and runs it from the GLib main loop with
``cefweaver.MessagePump``: CEF says when it wants the loop, GLib calls back, nothing polls.
``CefWidget`` is a ``Gtk.DrawingArea``: the pixels of ``RenderHandler.on_paint()`` are copied
into a cairo surface, and the mouse, the wheel, the keys and an input method (``Gtk.IMContext``)
are turned into CEF events. Hangul and other composed text arrive through the input method.

The widget is for one browser (the one ``initialize()`` makes). More browsers would use
``CefApp.create_browser()`` and one widget each.
"""

import os

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib, GObject, Gtk  # noqa: E402

import cairo  # noqa: E402
import cefweaver  # noqa: E402
from cefweaver import types  # noqa: E402

# EVENTFLAG_* of CEF
SHIFT, CONTROL, ALT = 1 << 1, 1 << 2, 1 << 3
LEFT_BUTTON, MIDDLE_BUTTON, RIGHT_BUTTON = 1 << 4, 1 << 5, 1 << 6

_WINDOWS_KEYS = {  # Gdk keyval name -> the Windows virtual key code CEF expects
    "BackSpace": 8, "Tab": 9, "ISO_Left_Tab": 9, "Return": 13, "KP_Enter": 13, "Escape": 27,
    "space": 32, "Page_Up": 33, "Page_Down": 34, "End": 35, "Home": 36, "Left": 37, "Up": 38,
    "Right": 39, "Down": 40, "Insert": 45, "Delete": 46, "Shift_L": 16, "Shift_R": 16,
    "Control_L": 17, "Control_R": 17, "Alt_L": 18, "Alt_R": 18, "Caps_Lock": 20,
}
_CHAR_KEYS = {"Return": 13, "KP_Enter": 13, "Tab": 9, "BackSpace": 8}   # keys that also make a CHAR
_CURSORS = {  # CursorType -> a CSS cursor name
    types.CursorType.POINTER: "default", types.CursorType.HAND: "pointer", types.CursorType.IBEAM: "text",
    types.CursorType.CROSS: "crosshair", types.CursorType.WAIT: "wait", types.CursorType.HELP: "help",
    types.CursorType.MOVE: "move", types.CursorType.NOTALLOWED: "not-allowed", types.CursorType.NODROP: "no-drop",
    types.CursorType.PROGRESS: "progress", types.CursorType.COLUMNRESIZE: "col-resize",
    types.CursorType.ROWRESIZE: "row-resize", types.CursorType.EASTWESTRESIZE: "ew-resize",
    types.CursorType.NORTHSOUTHRESIZE: "ns-resize", types.CursorType.ZOOMIN: "zoom-in",
    types.CursorType.ZOOMOUT: "zoom-out", types.CursorType.CELL: "cell", types.CursorType.COPY: "copy",
    types.CursorType.ALIAS: "alias", types.CursorType.CONTEXTMENU: "context-menu",
    types.CursorType.VERTICALTEXT: "vertical-text",
}


_COPY, _LINK, _MOVE = types.DragOperationsMask.COPY, types.DragOperationsMask.LINK, types.DragOperationsMask.MOVE
_DRAG_TARGETS = [Gtk.TargetEntry.new("text/plain", 0, 0), Gtk.TargetEntry.new("text/uri-list", 0, 1),
                 Gtk.TargetEntry.new("text/html", 0, 2), Gtk.TargetEntry.new("UTF8_STRING", 0, 3)]


def gdk_actions(ops):
    """The Gdk.DragAction of the drag operations CEF allows."""
    actions = Gdk.DragAction(0)
    if ops & _COPY:
        actions |= Gdk.DragAction.COPY
    if ops & _MOVE:
        actions |= Gdk.DragAction.MOVE
    if ops & _LINK:
        actions |= Gdk.DragAction.LINK
    return actions


def cef_operations(actions):
    """The drag operations of a Gdk.DragAction."""
    ops = types.DragOperationsMask(0)
    if actions & Gdk.DragAction.COPY:
        ops |= _COPY
    if actions & Gdk.DragAction.MOVE:
        ops |= _MOVE
    if actions & Gdk.DragAction.LINK:
        ops |= _LINK
    return ops


def windows_key_code(event):
    """The virtual key code of a GTK key event (letters and digits are their ASCII capitals)."""
    name = Gdk.keyval_name(event.keyval) or ""
    if name in _WINDOWS_KEYS:
        return _WINDOWS_KEYS[name]
    if name.startswith("F") and name[1:].isdigit() and 1 <= int(name[1:]) <= 12:
        return 111 + int(name[1:])
    unicode_value = Gdk.keyval_to_unicode(event.keyval)
    if unicode_value:
        return ord(chr(unicode_value).upper()) if unicode_value < 128 else unicode_value
    return 0


def key_modifiers(state):
    flags = 0
    if state & Gdk.ModifierType.SHIFT_MASK:
        flags |= SHIFT
    if state & Gdk.ModifierType.CONTROL_MASK:
        flags |= CONTROL
    if state & Gdk.ModifierType.MOD1_MASK:
        flags |= ALT
    if state & Gdk.ModifierType.BUTTON1_MASK:
        flags |= LEFT_BUTTON
    if state & Gdk.ModifierType.BUTTON2_MASK:
        flags |= MIDDLE_BUTTON
    if state & Gdk.ModifierType.BUTTON3_MASK:
        flags |= RIGHT_BUTTON
    return flags


class Runtime:
    """CEF for a GTK application: ``Runtime(...)``, ``start(widget, url)``, ``shutdown(done)``."""

    def __init__(self, switches=(), cache_path=None):
        self.app = cefweaver.CefApp()
        self.app.offscreen = True
        self.app.transparent = False                    # a page without a background is white
        if cache_path:
            self.app.set_cache_path(cache_path)
        for name, value in switches:
            self.app.add_command_line_switch(name, value)
        self.bridge = cefweaver.JavascriptBridge(self.app)   # expose() functions before start()
        self._source = 0
        self.pump = cefweaver.MessagePump(self.app, wake=self._wake)
        self.started = False

    # -- the event loop: CEF asks, GLib calls ------------------------------------------------

    def _wake(self, delay):                             # any thread of CEF
        GLib.idle_add(self._schedule)

    def _schedule(self):
        if self._source:
            GLib.source_remove(self._source)
        self._source = GLib.timeout_add(int(self.pump.timeout() * 1000), self._tick)
        return False

    def _tick(self):
        self._source = 0
        if self.started:
            self.pump.run()
            self._schedule()
        return False

    def start(self, widget, url):
        self.app.set_client(widget.client)
        self.app.initialize(url)
        self.started = True
        self._schedule()

    def shutdown(self, done=None):
        """Close the browser, let CEF finish, shut it down and call ``done()``."""
        for widget in list(getattr(self, "widgets", ())):
            widget.close()

        def finish():
            if self.app.is_running:
                return True                             # CEF still closes the browser
            self.started = False
            if self._source:
                GLib.source_remove(self._source)
                self._source = 0
            self.app.shutdown()
            if done:
                done()
            return False
        GLib.timeout_add(20, finish)


class _Handlers(cefweaver.Client):
    """The handlers of CEF's client, forwarded to the widget."""

    def __init__(self, widget):
        super().__init__()
        self.render = _Render(widget)
        self.life = _Life(widget)
        self.display = _Display(widget)
        self.load = _Load(widget)

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
        return cefweaver.Rect(0, 0, max(1, self.w.view_width), max(1, self.w.view_height))

    def get_screen_info(self, browser):
        screen = self.w.get_screen()
        rect = cefweaver.Rect(0, 0, screen.get_width(), screen.get_height())
        return True, cefweaver.ScreenInfo(float(self.w.get_scale_factor()), 24, 8, 0, rect, rect)

    def get_screen_point(self, browser, view_x, view_y):
        window = self.w.get_window()
        if window is None:
            return False, 0, 0
        _, origin_x, origin_y = window.get_origin()
        return True, origin_x + view_x, origin_y + view_y

    def on_paint(self, browser, type, dirty_rects, buffer, width, height):
        self.w.paint(type, dirty_rects, buffer, width, height)

    def on_popup_show(self, browser, show):
        self.w.popup_show(show)

    def on_popup_size(self, browser, rect):
        self.w.popup_rect = rect

    def on_cursor_change(self, browser, cursor):
        self.w.set_cef_cursor(cursor)
        return True

    def start_dragging(self, browser, drag_data, allowed_ops, x, y):
        return self.w.begin_drag(drag_data, allowed_ops, x, y)

    def update_drag_cursor(self, browser, operation):
        self.w.set_drag_operation(operation)

    def on_ime_composition_range_changed(self, browser, selected_range, character_bounds):
        if character_bounds:                            # where the candidate window goes
            last = character_bounds[-1]
            self.w.im.set_cursor_location(Gdk.Rectangle(last.x, last.y, last.width, last.height))


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
        self.w.emit("title-changed", title)

    def on_address_change(self, browser, frame, url):
        if frame.is_main():
            self.w.emit("address-changed", url)


class _Load(cefweaver.LoadHandler):
    def __init__(self, widget):
        self.w = widget

    def on_loading_state_change(self, browser, is_loading, can_go_back, can_go_forward):
        if not is_loading:
            # A page restored by "back" from Chromium's back-forward cache keeps ignoring size
            # changes of the view (innerWidth stays), while the picture follows. Telling CEF the
            # screen information changed wakes it (verified: F67); a plain was_resized() does not.
            self.w._host(lambda h: h.notify_screen_info_changed())
        self.w.emit("loading-changed", is_loading, can_go_back, can_go_forward)


class CefWidget(Gtk.DrawingArea):
    __gsignals__ = {
        "title-changed": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "address-changed": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "loading-changed": (GObject.SignalFlags.RUN_FIRST, None, (bool, bool, bool)),
        "browser-ready": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self, runtime):
        super().__init__()
        self.runtime = runtime
        runtime.widgets = [self]
        self.client = _Handlers(self)
        self.browser = None
        self.view_width, self.view_height = 800, 600    # in GTK pixels, until the first allocation
        self.pixels = None                              # the picture: BGRA, device pixels
        self.surface = None
        self.popup_rect = None
        self.popup_surface = None
        self.popup_visible = False
        self.set_can_focus(True)
        self.add_events(Gdk.EventMask.POINTER_MOTION_MASK | Gdk.EventMask.BUTTON_PRESS_MASK
                        | Gdk.EventMask.BUTTON_RELEASE_MASK | Gdk.EventMask.SCROLL_MASK
                        | Gdk.EventMask.SMOOTH_SCROLL_MASK | Gdk.EventMask.KEY_PRESS_MASK
                        | Gdk.EventMask.KEY_RELEASE_MASK | Gdk.EventMask.LEAVE_NOTIFY_MASK
                        | Gdk.EventMask.ENTER_NOTIFY_MASK | Gdk.EventMask.FOCUS_CHANGE_MASK)
        self.im = Gtk.IMMulticontext()
        self.im.connect("commit", self._on_commit)
        self.im.connect("preedit-changed", self._on_preedit_changed)
        self.im.connect("preedit-end", self._on_preedit_end)
        self._click_count = 1
        # drag and drop: this widget is a drop target of text, links and files, and the source of
        # what the page starts to drag
        self.drag_operation = _COPY                     # what CEF says it would do with the drop
        self._drop_state = None                         # None, "asking" (GTK is fetching the data), "entered"
        self._drag_context, self._drag_time = None, 0   # of the drag over this widget (for the late answers of CEF)
        self._dropped = False
        self._drag_out = None
        self.drag_dest_set(0, _DRAG_TARGETS, Gdk.DragAction.COPY | Gdk.DragAction.MOVE | Gdk.DragAction.LINK)
        self.connect("drag-motion", self._on_drag_motion)
        self.connect("drag-leave", self._on_drag_leave)
        self.connect("drag-drop", self._on_drag_drop)
        self.connect("drag-data-received", self._on_drag_data_received)
        self.connect("drag-data-get", self._on_drag_data_get)
        self.connect("drag-end", self._on_drag_end)
        self.connect("realize", lambda w: self.im.set_client_window(self.get_window()))
        self.connect("unrealize", lambda w: self.im.set_client_window(None))
        self.connect("size-allocate", self._on_size_allocate)
        self.connect("notify::scale-factor", lambda *a: self._host(lambda h: (h.notify_screen_info_changed(), h.was_resized())))
        self.connect("map", lambda w: self._host(lambda h: h.was_hidden(False)))
        self.connect("unmap", lambda w: self._host(lambda h: h.was_hidden(True)))

    # -- the browser ---------------------------------------------------------------------------

    def _host(self, function):
        if self.browser is not None:
            return function(self.browser.get_host())

    def browser_ready(self):
        self._host(lambda h: h.set_focus(self.has_focus()))
        self.emit("browser-ready")

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

    def close(self):
        self._host(lambda h: h.close_browser(True))

    # -- painting ------------------------------------------------------------------------------

    def paint(self, type, dirty_rects, buffer, width, height):
        if type == types.PaintElementType.POPUP:
            data = bytearray(buffer)                    # the memoryview is valid during this call only
            self.popup_surface = cairo.ImageSurface.create_for_data(data, cairo.FORMAT_ARGB32, width, height, width * 4)
            self.popup_surface.set_device_scale(self.get_scale_factor(), self.get_scale_factor())
            self.popup_data = data
            self.queue_draw()
            return
        if self.pixels is None or self.surface is None or self.surface.get_width() != width or self.surface.get_height() != height:
            self.pixels = bytearray(buffer)
            self.surface = cairo.ImageSurface.create_for_data(self.pixels, cairo.FORMAT_ARGB32, width, height, width * 4)
            scale = self.get_scale_factor()
            self.surface.set_device_scale(scale, scale)
            self.queue_draw()
            return
        stride = width * 4
        for rect in dirty_rects:                        # only the rows that changed
            x0, x1 = max(0, rect.x), min(width, rect.x + rect.width)
            for y in range(max(0, rect.y), min(height, rect.y + rect.height)):
                start = y * stride + x0 * 4
                self.pixels[start:start + (x1 - x0) * 4] = buffer[start:start + (x1 - x0) * 4]
        self.surface.mark_dirty()
        scale = self.get_scale_factor()
        for rect in dirty_rects:
            self.queue_draw_area(rect.x // scale, rect.y // scale, rect.width // scale + 2, rect.height // scale + 2)

    def popup_show(self, show):
        self.popup_visible = show
        if not show:
            self.popup_surface = None
        self.queue_draw()

    def do_draw(self, cr):
        cr.set_source_rgb(1, 1, 1)
        cr.paint()
        if self.surface is not None:
            cr.set_source_surface(self.surface, 0, 0)
            cr.paint()
        if self.popup_visible and self.popup_surface is not None and self.popup_rect is not None:
            cr.set_source_surface(self.popup_surface, self.popup_rect.x, self.popup_rect.y)
            cr.paint()
        return False

    def snapshot(self, path):
        """Save the picture of the browser as PNG."""
        if self.surface is None:
            return False
        self.surface.write_to_png(path)
        return True

    def set_cef_cursor(self, cursor):
        window = self.get_window()
        if window is not None:
            name = _CURSORS.get(cursor)
            window.set_cursor(Gdk.Cursor.new_from_name(window.get_display(), name) if name else None)

    def _on_size_allocate(self, widget, allocation):
        if (allocation.width, allocation.height) != (self.view_width, self.view_height):
            self.view_width, self.view_height = allocation.width, allocation.height
            self._host(lambda h: h.was_resized())

    # -- the mouse -----------------------------------------------------------------------------

    def _mouse(self, event):
        return types.MouseEvent(int(event.x), int(event.y), key_modifiers(event.state))

    def do_button_press_event(self, event):
        self.grab_focus()
        if event.type == Gdk.EventType.BUTTON_PRESS:
            self._click_count = 1
        elif event.type == Gdk.EventType._2BUTTON_PRESS:
            self._click_count = 2
        elif event.type == Gdk.EventType._3BUTTON_PRESS:
            self._click_count = 3
        button = {1: types.MouseButtonType.LEFT, 2: types.MouseButtonType.MIDDLE, 3: types.MouseButtonType.RIGHT}.get(event.button)
        if button is not None:
            self._host(lambda h: h.send_mouse_click_event(self._mouse(event), button, False, self._click_count))
        return True

    def do_button_release_event(self, event):
        button = {1: types.MouseButtonType.LEFT, 2: types.MouseButtonType.MIDDLE, 3: types.MouseButtonType.RIGHT}.get(event.button)
        if button is not None:
            self._host(lambda h: h.send_mouse_click_event(self._mouse(event), button, True, self._click_count))
        return True

    def do_motion_notify_event(self, event):
        self._host(lambda h: h.send_mouse_move_event(self._mouse(event), False))
        return True

    def do_leave_notify_event(self, event):
        self._host(lambda h: h.send_mouse_move_event(self._mouse(event), True))
        return False

    def do_scroll_event(self, event):
        if event.direction == Gdk.ScrollDirection.SMOOTH:
            ok, dx, dy = event.get_scroll_deltas()
            dx, dy = int(-dx * 100), int(-dy * 100)
        else:
            dx, dy = {Gdk.ScrollDirection.UP: (0, 100), Gdk.ScrollDirection.DOWN: (0, -100),
                      Gdk.ScrollDirection.LEFT: (100, 0), Gdk.ScrollDirection.RIGHT: (-100, 0)}.get(event.direction, (0, 0))
        self._host(lambda h: h.send_mouse_wheel_event(self._mouse(event), dx, dy))
        return True

    # -- the keyboard and the input method -----------------------------------------------------

    def do_focus_in_event(self, event):
        self.im.focus_in()
        self._host(lambda h: h.set_focus(True))
        return False

    def do_focus_out_event(self, event):
        self.im.focus_out()
        self._host(lambda h: h.set_focus(False))
        return False

    def do_key_press_event(self, event):
        if self.im.filter_keypress(event):              # composing (Hangul, dead keys): the text arrives as signals
            return True
        self._send_key(event, False)
        return True

    def do_key_release_event(self, event):
        if self.im.filter_keypress(event):
            return True
        self._send_key(event, True)
        return True

    def _send_key(self, event, release):
        code = windows_key_code(event)
        modifiers = key_modifiers(event.state)
        base = dict(modifiers=modifiers, windows_key_code=code, native_key_code=event.hardware_keycode)
        name = Gdk.keyval_name(event.keyval) or ""
        character = _CHAR_KEYS.get(name) or Gdk.keyval_to_unicode(event.keyval)
        if release:
            self._host(lambda h: h.send_key_event(types.KeyEvent(types.KeyEventType.KEYUP, **base)))
            return
        self._host(lambda h: h.send_key_event(types.KeyEvent(types.KeyEventType.RAWKEYDOWN, **base)))
        if character and not modifiers & (CONTROL | ALT):
            self._host(lambda h: h.send_key_event(types.KeyEvent(
                types.KeyEventType.CHAR, character=character, unmodified_character=character, **base)))

    def commit_text(self, text):
        """Text from the input method (also called by the tests)."""
        nothing = cefweaver.Range(0xFFFFFFFF, 0xFFFFFFFF)
        self._host(lambda h: h.ime_commit_text(text, nothing, 0))

    def set_preedit(self, text, cursor):
        """The text being composed (underlined in the page)."""
        if not text:
            self._host(lambda h: h.ime_cancel_composition())
            return
        underline = cefweaver.CompositionUnderline(cefweaver.Range(0, len(text)), 0xFF000000, 0, 0,
                                                   types.CompositionUnderlineStyle.SOLID)
        nothing = cefweaver.Range(0xFFFFFFFF, 0xFFFFFFFF)
        self._host(lambda h: h.ime_set_composition(text, [underline], nothing, cefweaver.Range(cursor, cursor)))

    def _on_commit(self, context, text):
        self.commit_text(text)

    def _on_preedit_changed(self, context):
        text, attributes, cursor = context.get_preedit_string()
        self.set_preedit(text, cursor)

    def _on_preedit_end(self, context):
        self._host(lambda h: h.ime_cancel_composition())

    # -- drag and drop: into the page --------------------------------------------------------------

    def _gdk_action(self, context):
        """What GTK shows for the drop: what CEF would do, among what the source offers."""
        offered = context.get_actions()
        for operation, action in ((_COPY, Gdk.DragAction.COPY), (_MOVE, Gdk.DragAction.MOVE), (_LINK, Gdk.DragAction.LINK)):
            if self.drag_operation & operation and offered & action:
                return action
        return context.get_suggested_action() if self.drag_operation else Gdk.DragAction(0)

    def set_drag_operation(self, operation):
        """CEF answers a drag_target_drag_over() later, from the renderer: tell GTK again what
        the drop would do, or the answer to the motion that came before it is the one GTK keeps
        (and a drag over a drop zone is refused)."""
        self.drag_operation = operation
        if self._drop_state == "entered" and self._drag_context is not None:
            Gdk.drag_status(self._drag_context, self._gdk_action(self._drag_context), self._drag_time)

    def _on_drag_motion(self, widget, context, x, y, time):
        self._drag_context, self._drag_time = context, time
        if self.browser is None:
            return False
        if self._drop_state is None:
            target = self.drag_dest_find_target(context, None)
            if target is None or target.name() == "NONE":
                return False
            self._drop_state = "asking"                 # GTK needs the data before CEF can be told
            self.drag_get_data(context, target, time)
        elif self._drop_state == "entered":
            event = types.MouseEvent(int(x), int(y), 0)
            ops = cef_operations(context.get_actions())
            self._host(lambda h: h.drag_target_drag_over(event, ops))
        Gdk.drag_status(context, self._gdk_action(context), time)
        return True

    def _on_drag_data_received(self, widget, context, x, y, selection, info, time):
        if self._drop_state != "asking":
            return
        data = self._drag_data_of(selection)
        if data is None:
            self._drop_state = None
            return
        self._drop_state = "entered"
        event = types.MouseEvent(int(x), int(y), 0)
        ops = cef_operations(context.get_actions())
        self._host(lambda h: h.drag_target_drag_enter(data, event, ops))
        Gdk.drag_status(context, self._gdk_action(context), time)

    @staticmethod
    def _drag_data_of(selection):
        data = cefweaver.DragData.create()
        target = selection.get_target().name()
        if target == "text/uri-list":
            for uri in selection.get_uris() or []:
                path = GLib.filename_from_uri(uri)[0] if uri.startswith("file://") else None
                if path:
                    data.add_file(path, os.path.basename(path))
                else:
                    data.set_link_url(uri)
        elif target == "text/html":
            data.set_fragment_html(bytes(selection.get_data()).decode("utf-8", "replace"))
        else:
            text = selection.get_text()
            if text is None:
                return None
            data.set_fragment_text(text)
        return data

    def _on_drag_leave(self, widget, context, time):
        # GTK sends drag-leave before drag-drop too: decide in an idle callback, after the drop
        self._dropped = False
        GLib.idle_add(self._finish_leave)

    def _finish_leave(self):
        if not self._dropped and self._drop_state in ("entered", "asking"):
            if self._drop_state == "entered":
                self._host(lambda h: h.drag_target_drag_leave())
            self._drop_state = None
            self.drag_operation = _COPY
        return False

    def _on_drag_drop(self, widget, context, x, y, time):
        if self._drop_state != "entered":
            return False
        self._dropped = True
        event = types.MouseEvent(int(x), int(y), 0)
        ops = cef_operations(context.get_actions())
        self._host(lambda h: (h.drag_target_drag_over(event, ops), h.drag_target_drop(event)))
        self._drop_state = None
        self._drag_context = None
        Gtk.drag_finish(context, True, False, time)
        return True

    # -- drag and drop: out of the page ------------------------------------------------------------

    def begin_drag(self, data, allowed_ops, x, y):
        """CEF's start_dragging(): a GTK drag of what the page drags (text, a link, files, HTML)."""
        text = data.get_fragment_text() or data.get_link_url()
        uris = []
        if data.is_file():
            ok, paths = data.get_file_paths()
            uris = [GLib.filename_to_uri(path) for path in paths] if ok else []
        elif data.is_link():
            uris = [data.get_link_url()]
        html = data.get_fragment_html()
        entries = []
        if text:
            entries += [Gtk.TargetEntry.new("text/plain", 0, 0), Gtk.TargetEntry.new("UTF8_STRING", 0, 3)]
        if uris:
            entries.append(Gtk.TargetEntry.new("text/uri-list", 0, 1))
        if html:
            entries.append(Gtk.TargetEntry.new("text/html", 0, 2))
        if not entries:
            return False
        self._drag_out = dict(text=text, uris=uris, html=html, data=data)
        actions = gdk_actions(allowed_ops) or Gdk.DragAction.COPY
        context = self.drag_begin_with_coordinates(Gtk.TargetList.new(entries), actions, 1, None, int(x), int(y))
        if context is None:
            self._drag_out = None
            return False
        return True

    def _on_drag_data_get(self, widget, context, selection, info, time):
        out = self._drag_out
        if out is None:
            return
        name = selection.get_target().name()
        if name in ("text/plain", "UTF8_STRING"):
            selection.set_text(out["text"], -1)
        elif name == "text/uri-list":
            selection.set_uris(out["uris"])
        elif name == "text/html":
            selection.set(selection.get_target(), 8, out["html"].encode("utf-8"))

    def _on_drag_end(self, widget, context):
        if self._drag_out is None:
            return
        self._drag_out = None
        pointer = self.get_display().get_default_seat().get_pointer()
        _, px, py = pointer.get_position()           # screen, x, y
        window = self.get_window()
        _, ox, oy = window.get_origin() if window is not None else (False, 0, 0)
        operation = cef_operations(context.get_selected_action())
        self._host(lambda h: (h.drag_source_ended_at(int(px - ox), int(py - oy), operation), h.drag_source_system_drag_ended()))
