"""A GTK 3 widget that shows a cefweaver offscreen browser, built on :mod:`cefweaver.ui`.

:mod:`cefweaver.ui` has the CEF side (:class:`~cefweaver.ui.BrowserView`,
:class:`~cefweaver.ui.Session`). This module adds the GTK side:

* :class:`GlibLoop`: runs functions in the GLib main loop, at once or later.
* :class:`GtkAdapter`: the :class:`~cefweaver.ui.ToolkitAdapter` for a :class:`CefWidget` (size,
  scale and position, drawing frames with cairo, cursor, input method candidate window, context
  menu, clipboard and drags started by the page).
* :class:`CefWidget`: a ``Gtk.DrawingArea`` that passes mouse, wheel, key, input method and
  drag-and-drop events to the view.

Note:
    A widget shows one browser, the one made by ``initialize()``. Use ``CefApp.create_browser()``
    and one widget each for more browsers.

Checked: Xvfb with GDK_BACKEND=x11 and real X events from xdotool: the 39 checks of examples/gtk3/smoke.py at scale 1 and 2
(at scale 2 on a screen of 2560x2048).
At scale 1 also with CEF on Wayland (ozone-platform=wayland, the widget on X11): the 39 checks.
Not checked: a real input method (ibus, fcitx) by the smoke (typing Korean was tried by hand once on a real screen), GTK on
Wayland, rich text and images in the clipboard.
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
    """Convert CEF drag operations to GDK drag actions.

    Args:
        ops (types.DragOperationsMask): The operations CEF allows.

    Returns:
        Gdk.DragAction: The matching COPY, MOVE and LINK actions.
    """
    actions = Gdk.DragAction(0)
    if ops & _COPY:
        actions |= Gdk.DragAction.COPY
    if ops & _MOVE:
        actions |= Gdk.DragAction.MOVE
    if ops & _LINK:
        actions |= Gdk.DragAction.LINK
    return actions


def cef_operations(actions):
    """Convert GDK drag actions to CEF drag operations.

    Args:
        actions (Gdk.DragAction): The GDK actions.

    Returns:
        types.DragOperationsMask: The matching COPY, MOVE and LINK operations.
    """
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
    """Return the Windows virtual key code of a GTK key event.

    Letters and digits map to their ASCII capitals; a character with no virtual key maps to its
    code point; other keys map to 0.

    Args:
        event (Gdk.EventKey): The key event.

    Returns:
        int: The virtual key code CEF expects.
    """
    return _KEYS.code(event.keyval)


def key_modifiers(state):
    """Convert a GDK modifier state to CEF event flags.

    Args:
        state (Gdk.ModifierType): The ``state`` of a GDK event.

    Returns:
        int: The CEF flags for Shift, Control, Alt and the mouse buttons that are down.
    """
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
    """The loop object :class:`~cefweaver.ui.Session` needs, on the GLib main loop."""

    def post(self, function):                           # any thread
        """Run ``function`` once in the GLib main loop; callable from any thread."""
        GLib.idle_add(lambda: (function(), False)[1])

    def call_later(self, seconds, function):
        """Run ``function`` in the main loop after ``seconds`` and return an object with ``cancel()``."""
        return _Source(seconds, function)


class GtkAdapter(GlibLoop):
    """The :class:`~cefweaver.ui.ToolkitAdapter` for a :class:`CefWidget`.

    The view does the clipboard keys, using the GTK clipboard. Declares the ``"drag_out"``
    capability.

    Args:
        widget (CefWidget): The widget this adapter serves.

    Attributes:
        capabilities (frozenset): ``{"drag_out"}``.
        last_menu (Gtk.Menu): The last context menu shown by :meth:`show_menu` (set on first use).
    """

    capabilities = frozenset({"drag_out"})

    def __init__(self, widget):
        self.w = widget

    def show_menu(self, items, x, y, done):
        """Show the context menu of the page as a ``Gtk.Menu``.

        The menu pops up for the last right button press of the widget, or at the given position
        when there was none.

        Args:
            items (list): The menu entries, with ``kind``, ``label``, ``checked``, ``enabled``,
                ``command_id`` and ``children`` attributes.
            x (int): The x position in the widget, used when the widget has no recorded press.
            y (int): The y position in the widget, used when the widget has no recorded press.
            done (callable): Called once as ``done(command_id)`` with the command id of the
                picked item, or None when the menu is left without a pick.
        """
        picked = []

        def pick(command_id):
            if not picked:
                picked.append(command_id)
                done(command_id)

        def fill(shell, entries):
            for entry in entries:
                if entry.kind == "separator":
                    shell.append(Gtk.SeparatorMenuItem())
                    continue
                if entry.kind in ("check", "radio"):
                    widget = Gtk.CheckMenuItem.new_with_label(entry.label)
                    widget.set_active(entry.checked)
                    widget.set_draw_as_radio(entry.kind == "radio")
                else:
                    widget = Gtk.MenuItem.new_with_label(entry.label)
                widget.set_sensitive(entry.enabled)
                if entry.kind == "submenu":
                    sub = Gtk.Menu()
                    fill(sub, entry.children)
                    widget.set_submenu(sub)
                else:
                    widget.connect("activate", lambda w, command_id=entry.command_id: pick(command_id))
                shell.append(widget)
        menu = Gtk.Menu()
        fill(menu, items)
        # "activate" of the picked item comes after "selection-done": leaving the menu is told only when nothing was picked
        menu.connect("selection-done", lambda m: GLib.timeout_add(50, lambda: (pick(None), False)[1]))
        menu.show_all()
        self.last_menu = menu
        # CEF answers after the event handler of the click has returned, so GTK has no current event to pop the menu up
        # for. The right button press that the widget got is given instead: with its time and device the menu gets
        # the grab, the release that follows at once does not close it, and it comes up where the pointer is.
        press = getattr(self.w, "last_press", None)
        if press is not None:
            menu.popup_at_pointer(press)
        else:                                                  # no click of the widget (the program asked for a menu)
            event = Gdk.Event.new(Gdk.EventType.BUTTON_PRESS)
            event.button.window = self.w.get_window()
            event.button.button = 3
            event.button.time = Gdk.CURRENT_TIME
            event.set_device(Gdk.Display.get_default().get_default_seat().get_pointer())
            menu.popup_at_rect(self.w.get_window(), Gdk.Rectangle(int(x), int(y), 1, 1), Gdk.Gravity.NORTH_WEST,
                               Gdk.Gravity.NORTH_WEST, event)

    def clipboard_get(self):
        """Return the text of the GTK clipboard, or None if it has none."""
        return Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).wait_for_text()

    def clipboard_set(self, text):
        """Put ``text`` on the GTK clipboard."""
        Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).set_text(text, -1)

    def view_size(self):
        """Return the size of the widget as ``(width, height)`` in logical pixels."""
        return self.w.view_width, self.w.view_height

    def scale(self):
        """Return the scale factor of the widget (device pixels per logical pixel)."""
        return float(self.w.get_scale_factor())

    def screen_origin(self):
        """Return the screen position of the widget's top-left corner, or ``(0, 0)`` if it has no window."""
        window = self.w.get_window()
        if window is None:
            return 0, 0
        _, x, y = window.get_origin()
        return x, y

    def screen_size(self):
        """Return the size of the widget's screen as ``(width, height)``."""
        screen = self.w.get_screen()
        return screen.get_width(), screen.get_height()

    def present(self, frame):
        """Hand a painted frame to the widget, which draws it with cairo."""
        self.w.present_frame(frame)

    def set_cursor(self, cursor):
        """Show the cursor CEF asks for (a ``types.CursorType``) on the widget's window."""
        self.w.set_cef_cursor(cursor)

    def set_ime_rect(self, x, y, width, height):         # where the candidate window goes
        """Place the input method candidate window at the given rectangle of the widget."""
        self.w.im.set_cursor_location(Gdk.Rectangle(x, y, width, height))

    def start_drag_out(self, payload, allowed):
        """Start a GTK drag of what the page drags; return True if it started."""
        return self.w.begin_drag(payload, allowed)

    def drag_operation_changed(self, operation):
        """Tell the widget that CEF's answer to a drag over the view changed."""
        self.w.set_drag_operation(operation)


class CefWidget(ui.BrowserWidget, Gtk.DrawingArea):
    """A ``Gtk.DrawingArea`` that shows a browser.

    Args:
        runtime: The runtime (as returned by ``initialize()``) that makes the browser; stored as
            ``runtime``.
        audio (optional): The audio handler options passed to the :class:`~cefweaver.ui.BrowserView`.
            Default None.

    Attributes:
        runtime: The runtime given to the constructor.
        im (Gtk.IMMulticontext): The input method context of the widget.
        surface (cairo.ImageSurface | None): The surface of the current view frame.
        popup_surface (cairo.ImageSurface | None): The surface of the current popup, if any.
        view_width (int): The width of the widget in GTK pixels (800 until the first allocation).
        view_height (int): The height of the widget in GTK pixels (600 until the first allocation).
        last_press (Gdk.Event | None): A copy of the last right button press.

    Signals:
        title-changed (str): The page title changed.
        address-changed (str): The page address changed.
        loading-changed (bool, bool, bool): ``loading``, ``can_back``, ``can_forward``.
        browser-ready: The browser was created.
    """

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
        self.last_press = None                         # the last right button press (the context menu is popped up for it)
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
        """types.DragOperationsMask: The operations CEF allows for the drag over the view."""
        return self.view.drag_operation

    def browser_title(self, title):
        """Emit ``title-changed`` with the new page title."""
        self.emit("title-changed", title)

    def browser_address(self, url):
        """Emit ``address-changed`` with the new page address."""
        self.emit("address-changed", url)

    def browser_loading(self, loading, can_back, can_forward):
        """Emit ``loading-changed`` with the loading state and the navigation flags."""
        self.emit("loading-changed", loading, can_back, can_forward)

    def browser_ready(self):
        """Give the browser the widget's focus state and emit ``browser-ready``."""
        self.view.focus(self.has_focus())
        self.emit("browser-ready")

    # -- painting ------------------------------------------------------------------------------

    def present_frame(self, frame):
        """Wrap or update the cairo surface for a painted frame and queue a redraw of what changed."""
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
        """Paint a white background, the view frame and the popup, if shown."""
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
        """Set the cursor of the widget's window for a ``types.CursorType`` (the default cursor if unmapped)."""
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
        """Focus the widget and pass a button press, with its click count, to the view."""
        self.grab_focus()
        if event.button == 3:
            self.last_press = event.copy()            # the event that the context menu is popped up for (CEF answers later)
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
        """Pass a button release to the view."""
        self.view.mouse_button(int(event.x), int(event.y), _BUTTON_NAMES.get(event.button), False,
                               key_modifiers(event.state), clicks=self._click_count)
        return True

    def do_motion_notify_event(self, event):
        """Pass a pointer move to the view."""
        self.view.mouse_move(int(event.x), int(event.y), key_modifiers(event.state))
        return True

    def do_leave_notify_event(self, event):
        """Tell the view that the pointer left the widget."""
        self.view.mouse_move(int(event.x), int(event.y), key_modifiers(event.state), leave=True)
        return False

    def do_scroll_event(self, event):
        """Pass a scroll event to the view as a wheel delta (smooth deltas are scaled by 100)."""
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
        """Focus the input method and the view."""
        self.im.focus_in()
        self.view.focus(True)
        return False

    def do_focus_out_event(self, event):
        """Unfocus the input method and the view."""
        self.im.focus_out()
        self.view.focus(False)
        return False

    def do_key_press_event(self, event):
        """Pass a key press to the input method first, then to the view if it was not consumed."""
        if self.im.filter_keypress(event):              # composing (Hangul, dead keys): the text arrives as signals
            return True
        self._send_key(event, True)
        return True

    def do_key_release_event(self, event):
        """Pass a key release to the input method first, then to the view if it was not consumed."""
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
        """Report the new drop action to GTK for the drag over the widget.

        Called when CEF's answer to a drag over the view arrives; does nothing unless a drag has
        entered the page.

        Args:
            operation (types.DragOperationsMask): The operations CEF allows for the drop.
        """
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
        """Start a GTK drag of what the page drags (text, a link, files or HTML).

        This is what :meth:`GtkAdapter.start_drag_out` calls.

        Args:
            payload (DragPayload): What the page drags and where in the view the drag started.
            allowed_ops (types.DragOperationsMask): The operations the page allows.

        Returns:
            bool: True if the drag started; False if the payload had nothing to carry or GTK
            refused.
        """
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
