"""A GTK 3 widget that shows a cefweaver offscreen browser, built on ``cefweaver.ui``.

``cefweaver.ui`` has the CEF side: ``BrowserView`` (handlers, event records, click counts, input method,
drag and drop) and ``Session`` (CEF in the main loop). This file is what GTK adds, the adapter:

* ``GlibLoop``: running something in the main loop (``post``) and later (``call_later``);
* ``GtkAdapter``: size, scale and place of the widget, drawing the frames with cairo, the cursor, the place
  of the candidate window, and the drag that GTK starts for the page;
* ``CefWidget``: a ``Gtk.DrawingArea`` that passes the events of GTK (mouse, wheel, keys, the input method
  ``Gtk.IMContext``, drag and drop) to the view.

The widget is for one browser (the one ``initialize()`` makes). More browsers would use
``CefApp.create_browser()`` and one widget each.

Checked: Xvfb with GDK_BACKEND=x11 and real X events from xdotool: the 27 checks of examples/gtk3/smoke.py at scale 1 and 2
(at scale 2 on a screen of 2560x2048).
Not checked: a real input method (ibus, fcitx), GTK on Wayland, rich text and images in the clipboard.
"""

import os

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib, GObject, Gtk  # noqa: E402

import cairo  # noqa: E402
import cefweaver  # noqa: E402
from cefweaver import types, ui  # noqa: E402
from cefweaver.ui import keys  # noqa: E402

_WINDOWS_KEYS = {  # Gdk keyval name -> the Windows virtual key code CEF expects
    "BackSpace": keys.VK_BACK, "Tab": keys.VK_TAB, "ISO_Left_Tab": keys.VK_TAB, "Return": keys.VK_RETURN,
    "KP_Enter": keys.VK_RETURN, "Escape": keys.VK_ESCAPE, "space": keys.VK_SPACE, "Page_Up": keys.VK_PRIOR,
    "Page_Down": keys.VK_NEXT, "End": keys.VK_END, "Home": keys.VK_HOME, "Left": keys.VK_LEFT, "Up": keys.VK_UP,
    "Right": keys.VK_RIGHT, "Down": keys.VK_DOWN, "Insert": keys.VK_INSERT, "Delete": keys.VK_DELETE,
    "Shift_L": keys.VK_SHIFT, "Shift_R": keys.VK_SHIFT, "Control_L": keys.VK_CONTROL, "Control_R": keys.VK_CONTROL,
    "Alt_L": keys.VK_ALT, "Alt_R": keys.VK_ALT, "Caps_Lock": keys.VK_CAPITAL,
}
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


_KEYS = ui.KeyTable({Gdk.keyval_from_name(name): code for name, code in _WINDOWS_KEYS.items()},
                    function=ui.function_range(Gdk.KEY_F1),
                    char=lambda keyval: chr(Gdk.keyval_to_unicode(keyval)) if Gdk.keyval_to_unicode(keyval) else None,
                    others_as_code_point=True)
_MODIFIERS = ui.MaskModifiers(
    shift=Gdk.ModifierType.SHIFT_MASK, control=Gdk.ModifierType.CONTROL_MASK, alt=Gdk.ModifierType.MOD1_MASK,
    left=Gdk.ModifierType.BUTTON1_MASK, middle=Gdk.ModifierType.BUTTON2_MASK, right=Gdk.ModifierType.BUTTON3_MASK)
_CURSOR_NAMES = ui.CursorTable(_CURSORS, default=None)


def windows_key_code(event):
    """The virtual key code of a GTK key event (letters and digits are their ASCII capitals)."""
    return _KEYS.code(event.keyval)


def key_modifiers(state):
    return _MODIFIERS.flags(state)


class _Source:
    """A GLib timeout that can be cancelled (and is not removed twice)."""

    def __init__(self, seconds, function):
        self.function = function
        self.id = GLib.timeout_add(int(seconds * 1000), self._run)

    def _run(self):
        self.id = 0
        self.function()
        return False

    def cancel(self):
        if self.id:
            GLib.source_remove(self.id)
            self.id = 0


class GlibLoop:
    """What ``ui.Session`` needs of a toolkit: the GLib main loop."""

    def post(self, function):                           # any thread
        GLib.idle_add(lambda: (function(), False)[1])

    def call_later(self, seconds, function):
        return _Source(seconds, function)


class GtkAdapter(GlibLoop):
    """``ui.ToolkitAdapter`` for a ``CefWidget``. GTK 3 lets CEF do the clipboard keys itself."""

    capabilities = frozenset({"native_clipboard", "drag_out"})

    def __init__(self, widget):
        self.w = widget

    def view_size(self):
        return self.w.view_width, self.w.view_height

    def scale(self):
        return float(self.w.get_scale_factor())

    def screen_origin(self):
        window = self.w.get_window()
        if window is None:
            return 0, 0
        _, x, y = window.get_origin()
        return x, y

    def screen_size(self):
        screen = self.w.get_screen()
        return screen.get_width(), screen.get_height()

    def present(self, frame):
        self.w.present_frame(frame)

    def set_cursor(self, cursor):
        self.w.set_cef_cursor(cursor)

    def set_ime_rect(self, x, y, width, height):         # where the candidate window goes
        self.w.im.set_cursor_location(Gdk.Rectangle(x, y, width, height))

    def start_drag_out(self, payload, allowed):
        return self.w.begin_drag(payload, allowed)

    def drag_operation_changed(self, operation):
        self.w.set_drag_operation(operation)


class CefWidget(ui.BrowserWidget, Gtk.DrawingArea):
    __gsignals__ = {
        "title-changed": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "address-changed": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "loading-changed": (GObject.SignalFlags.RUN_FIRST, None, (bool, bool, bool)),
        "browser-ready": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self, runtime, audio=None):
        super().__init__()
        self.runtime = runtime
        self.attach_view(GtkAdapter(self), audio=audio)
        self.view_width, self.view_height = 800, 600    # in GTK pixels, until the first allocation
        self.surface = None
        self.popup_surface = None
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
        self.connect("notify::scale-factor", lambda *a: self.view.host(lambda h: (h.notify_screen_info_changed(), h.was_resized())))
        self.connect("map", lambda w: self.view.shown(True))
        self.connect("unmap", lambda w: self.view.shown(False))

    # -- the browser ---------------------------------------------------------------------------

    @property
    def drag_operation(self):
        return self.view.drag_operation

    def browser_title(self, title):
        self.emit("title-changed", title)

    def browser_address(self, url):
        self.emit("address-changed", url)

    def browser_loading(self, loading, can_back, can_forward):
        self.emit("loading-changed", loading, can_back, can_forward)

    def browser_ready(self):
        self.view.focus(self.has_focus())
        self.emit("browser-ready")

    # -- painting ------------------------------------------------------------------------------

    def present_frame(self, frame):
        change, store = frame.change, self.view.store
        scale = self.get_scale_factor()
        if change.kind == ui.PictureStore.POPUP_HIDDEN:
            self.popup_surface = None
        elif change.kind == ui.PictureStore.POPUP:
            width, height = store.popup_size
            self.popup_surface = cairo.ImageSurface.create_for_data(store.popup_pixels, cairo.FORMAT_ARGB32, width, height, width * 4)
            self.popup_surface.set_device_scale(scale, scale)
        elif change.kind == ui.PictureStore.NEW:
            width, height = store.size
            self.surface = cairo.ImageSurface.create_for_data(store.pixels, cairo.FORMAT_ARGB32, width, height, width * 4)
            self.surface.set_device_scale(scale, scale)
        else:
            self.surface.mark_dirty()
            for rect in change.rects:
                self.queue_draw_area(rect.x // scale, rect.y // scale, rect.width // scale + 2, rect.height // scale + 2)
            return
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

    def set_cef_cursor(self, cursor):
        window = self.get_window()
        if window is not None:
            name = _CURSOR_NAMES.get(cursor)
            window.set_cursor(Gdk.Cursor.new_from_name(window.get_display(), name) if name else None)

    def _on_size_allocate(self, widget, allocation):
        if (allocation.width, allocation.height) != (self.view_width, self.view_height):
            self.view_width, self.view_height = allocation.width, allocation.height
            self.view.resized()

    # -- the mouse -----------------------------------------------------------------------------

    def do_button_press_event(self, event):
        self.grab_focus()
        if event.type == Gdk.EventType.BUTTON_PRESS:
            self._click_count = 1
        elif event.type == Gdk.EventType._2BUTTON_PRESS:
            self._click_count = 2
        elif event.type == Gdk.EventType._3BUTTON_PRESS:
            self._click_count = 3
        self.view.mouse_button(int(event.x), int(event.y), _BUTTON_NAMES.get(event.button), True,
                               key_modifiers(event.state), clicks=self._click_count)
        return True

    def do_button_release_event(self, event):
        self.view.mouse_button(int(event.x), int(event.y), _BUTTON_NAMES.get(event.button), False,
                               key_modifiers(event.state), clicks=self._click_count)
        return True

    def do_motion_notify_event(self, event):
        self.view.mouse_move(int(event.x), int(event.y), key_modifiers(event.state))
        return True

    def do_leave_notify_event(self, event):
        self.view.mouse_move(int(event.x), int(event.y), key_modifiers(event.state), leave=True)
        return False

    def do_scroll_event(self, event):
        if event.direction == Gdk.ScrollDirection.SMOOTH:
            ok, dx, dy = event.get_scroll_deltas()
            dx, dy = int(-dx * 100), int(-dy * 100)
        else:
            dx, dy = {Gdk.ScrollDirection.UP: (0, 100), Gdk.ScrollDirection.DOWN: (0, -100),
                      Gdk.ScrollDirection.LEFT: (100, 0), Gdk.ScrollDirection.RIGHT: (-100, 0)}.get(event.direction, (0, 0))
        self.view.wheel(int(event.x), int(event.y), dx, dy, key_modifiers(event.state))
        return True

    # -- the keyboard and the input method -----------------------------------------------------

    def do_focus_in_event(self, event):
        self.im.focus_in()
        self.view.focus(True)
        return False

    def do_focus_out_event(self, event):
        self.im.focus_out()
        self.view.focus(False)
        return False

    def do_key_press_event(self, event):
        if self.im.filter_keypress(event):              # composing (Hangul, dead keys): the text arrives as signals
            return True
        self._send_key(event, True)
        return True

    def do_key_release_event(self, event):
        if self.im.filter_keypress(event):
            return True
        self._send_key(event, False)
        return True

    def _send_key(self, event, down):
        unicode_value = Gdk.keyval_to_unicode(event.keyval)
        self.view.key(down, windows_key_code(event), event.hardware_keycode, key_modifiers(event.state),
                      char=chr(unicode_value) if unicode_value and down else None)

    def _on_commit(self, context, text):
        self.commit_text(text)

    def _on_preedit_changed(self, context):
        text, attributes, cursor = context.get_preedit_string()
        self.set_preedit(text, cursor)

    def _on_preedit_end(self, context):
        self.view.preedit("", 0)

    # -- drag and drop: into the page --------------------------------------------------------------

    def _gdk_action(self, context):
        """What GTK shows for the drop: what CEF would do, among what the source offers."""
        offered = context.get_actions()
        for operation, action in ((_COPY, Gdk.DragAction.COPY), (_MOVE, Gdk.DragAction.MOVE), (_LINK, Gdk.DragAction.LINK)):
            if self.drag_operation & operation and offered & action:
                return action
        return context.get_suggested_action() if self.drag_operation else Gdk.DragAction(0)

    def set_drag_operation(self, operation):
        """CEF answers a drag over the view later, from the renderer: tell GTK again what the drop
        would do, or the answer to the motion that came before it is the one GTK keeps (and a drag
        over a drop zone is refused)."""
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
            self.view.drag_over(int(x), int(y), cef_operations(context.get_actions()))
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
        self.view.drag_enter(int(x), int(y), cef_operations(context.get_actions()), **data)
        Gdk.drag_status(context, self._gdk_action(context), time)

    @staticmethod
    def _drag_data_of(selection):
        """What the drag carries, as the arguments of ``BrowserView.drag_enter`` (None: nothing usable)."""
        target = selection.get_target().name()
        if target == "text/uri-list":
            data = {"files": []}
            for uri in selection.get_uris() or []:
                path = GLib.filename_from_uri(uri)[0] if uri.startswith("file://") else None
                if path:
                    data["files"].append(path)
                else:
                    data["url"] = uri
            return data
        if target == "text/html":
            return {"html": bytes(selection.get_data()).decode("utf-8", "replace")}
        text = selection.get_text()
        return None if text is None else {"text": text}

    def _on_drag_leave(self, widget, context, time):
        # GTK sends drag-leave before drag-drop too: the view tells CEF after a turn of the loop, the
        # state of this widget is decided in an idle callback, after the drop
        self._dropped = False
        if self._drop_state == "entered":
            self.view.drag_leave()
        GLib.idle_add(self._finish_leave)

    def _finish_leave(self):
        if not self._dropped and self._drop_state in ("entered", "asking"):
            self._drop_state = None
        return False

    def _on_drag_drop(self, widget, context, x, y, time):
        if self._drop_state != "entered":
            return False
        self._dropped = True
        self.view.drag_drop(int(x), int(y), cef_operations(context.get_actions()))
        self._drop_state = None
        self._drag_context = None
        Gtk.drag_finish(context, True, False, time)
        return True

    # -- drag and drop: out of the page ------------------------------------------------------------

    def begin_drag(self, payload, allowed_ops):
        """``GtkAdapter.start_drag_out``: a GTK drag of what the page drags (text, a link, files, HTML)."""
        text = payload.text or payload.url
        uris = [GLib.filename_to_uri(path) for path in payload.files] or ([payload.url] if payload.url else [])
        entries = []
        if text:
            entries += [Gtk.TargetEntry.new("text/plain", 0, 0), Gtk.TargetEntry.new("UTF8_STRING", 0, 3)]
        if uris:
            entries.append(Gtk.TargetEntry.new("text/uri-list", 0, 1))
        if payload.html:
            entries.append(Gtk.TargetEntry.new("text/html", 0, 2))
        if not entries:
            return False
        self._drag_out = dict(text=text, uris=uris, html=payload.html)
        actions = gdk_actions(allowed_ops) or Gdk.DragAction.COPY
        context = self.drag_begin_with_coordinates(Gtk.TargetList.new(entries), actions, 1, None, int(payload.x), int(payload.y))
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
        self.view.drag_out_finished(int(px - ox), int(py - oy), cef_operations(context.get_selected_action()))


_BUTTON_NAMES = {1: "left", 2: "middle", 3: "right"}
