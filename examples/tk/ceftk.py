"""A Tkinter widget that shows a cefweaver offscreen browser.

``Runtime`` owns CEF and runs it from the Tk event loop with ``cefweaver.MessagePump``: CEF says (from
any thread) when it wants the loop, a pipe wakes Tk (``createfilehandler``, which is thread safe) and
``after`` carries the deadline. ``CefCanvas`` is a ``tkinter.Canvas``: the pixels of ``on_paint`` are
converted with Pillow (``ImageTk``), and Tk's mouse, wheel and key events become CEF events.

What Tk cannot do is in the README: no input method preedit, no drag out of the page into Tk widgets.
A drag inside the page is carried out by the widget itself (see ``begin_drag``). Drops from other programs
are not supported: tkinterdnd2 (the tkdnd extension) ends the process when CEF starts in it (README).
"""

import os
import time
import tkinter

from PIL import Image, ImageTk

import cefweaver
from cefweaver import types

SHIFT, CONTROL, ALT = 1 << 1, 1 << 2, 1 << 3                       # EVENTFLAG_* of CEF
LEFT_BUTTON, MIDDLE_BUTTON, RIGHT_BUTTON = 1 << 4, 1 << 5, 1 << 6

_KEYS = {
    "BackSpace": 8, "Tab": 9, "ISO_Left_Tab": 9, "Return": 13, "KP_Enter": 13, "Escape": 27, "space": 32,
    "Prior": 33, "Next": 34, "End": 35, "Home": 36, "Left": 37, "Up": 38, "Right": 39, "Down": 40,
    "Insert": 45, "Delete": 46, "Shift_L": 16, "Shift_R": 16, "Control_L": 17, "Control_R": 17,
    "Alt_L": 18, "Alt_R": 18, "Caps_Lock": 20,
}
_CHAR_KEYS = {"Return": 13, "KP_Enter": 13, "Tab": 9, "BackSpace": 8}
_CURSORS = {
    types.CursorType.POINTER: "arrow", types.CursorType.HAND: "hand2", types.CursorType.IBEAM: "xterm",
    types.CursorType.CROSS: "crosshair", types.CursorType.WAIT: "watch", types.CursorType.HELP: "question_arrow",
    types.CursorType.MOVE: "fleur", types.CursorType.NOTALLOWED: "X_cursor", types.CursorType.NODROP: "X_cursor",
    types.CursorType.COLUMNRESIZE: "sb_h_double_arrow", types.CursorType.ROWRESIZE: "sb_v_double_arrow",
    types.CursorType.EASTWESTRESIZE: "sb_h_double_arrow", types.CursorType.NORTHSOUTHRESIZE: "sb_v_double_arrow",
}


def windows_key_code(event):
    name = event.keysym
    if name in _KEYS:
        return _KEYS[name]
    if name.startswith("F") and name[1:].isdigit() and 1 <= int(name[1:]) <= 12:
        return 111 + int(name[1:])
    if len(name) == 1 and 0x20 <= ord(name) < 0x7F:
        return ord(name.upper())
    return 0


def modifier_flags(state):
    flags = 0
    if state & 0x1:
        flags |= SHIFT
    if state & 0x4:
        flags |= CONTROL
    if state & 0x8:
        flags |= ALT
    if state & 0x100:
        flags |= LEFT_BUTTON
    if state & 0x200:
        flags |= MIDDLE_BUTTON
    if state & 0x400:
        flags |= RIGHT_BUTTON
    return flags


class Runtime:
    """CEF for a Tk application: ``Runtime(root, ...)``, ``start(widget, url)``, ``shutdown(done)``."""

    def __init__(self, root, switches=(), cache_path=None):
        self.root = root
        self.app = cefweaver.CefApp()
        self.app.offscreen = True
        self.app.transparent = False
        if cache_path:
            self.app.set_cache_path(cache_path)
        for name, value in switches:
            self.app.add_command_line_switch(name, value)
        self.bridge = cefweaver.JavascriptBridge(self.app)
        self._read, self._write = os.pipe()
        os.set_blocking(self._read, False)
        root.tk.createfilehandler(self._read, tkinter.READABLE, lambda *args: self._on_wake())
        self.pump = cefweaver.MessagePump(self.app, wake=self._wake)
        self._after = None
        self.started = False
        self.widgets = []

    def _wake(self, delay):                             # any thread of CEF
        try:
            os.write(self._write, b"x")
        except OSError:
            pass

    def _on_wake(self):
        try:
            os.read(self._read, 4096)
        except OSError:
            pass
        self._schedule()

    def _schedule(self):
        if self._after is not None:
            self.root.after_cancel(self._after)
        self._after = self.root.after(int(self.pump.timeout() * 1000), self._tick)

    def _tick(self):
        self._after = None
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

        def finish():
            if self.app.is_running:
                self.root.after(20, finish)
                return
            self.started = False
            if self._after is not None:
                self.root.after_cancel(self._after)
                self._after = None
            self.root.tk.deletefilehandler(self._read)
            self.app.shutdown()
            if done:
                done()
        self.root.after(20, finish)


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
        return cefweaver.Rect(0, 0, max(1, self.w.view_width), max(1, self.w.view_height))

    def get_screen_info(self, browser):
        rect = cefweaver.Rect(0, 0, self.w.winfo_screenwidth(), self.w.winfo_screenheight())
        return True, cefweaver.ScreenInfo(1.0, 24, 8, 0, rect, rect)

    def get_screen_point(self, browser, view_x, view_y):
        return True, self.w.winfo_rootx() + view_x, self.w.winfo_rooty() + view_y

    def on_paint(self, browser, type, dirty_rects, buffer, width, height):
        self.w.paint(type, buffer, width, height)

    def on_popup_show(self, browser, show):
        self.w.popup_show(show)

    def on_popup_size(self, browser, rect):
        self.w.popup_rect = rect

    def on_cursor_change(self, browser, cursor):
        self.w.configure(cursor=_CURSORS.get(cursor, "arrow"))
        return True

    def on_text_selection_changed(self, browser, selected_text, selected_range):
        self.w.selected_text = selected_text

    def start_dragging(self, browser, drag_data, allowed_ops, x, y):
        return self.w.begin_drag(drag_data, allowed_ops)

    def update_drag_cursor(self, browser, operation):
        self.w.drag_operation = operation


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
        self.w.on_title(title)

    def on_address_change(self, browser, frame, url):
        if frame.is_main():
            self.w.on_address(url)


class _Load(cefweaver.LoadHandler):
    def __init__(self, widget):
        self.w = widget

    def on_loading_state_change(self, browser, is_loading, can_go_back, can_go_forward):
        if not is_loading:
            # a page restored by "back" from the back-forward cache ignores size changes until CEF is
            # told that the screen information changed (see the GTK example and the wiki, F67)
            self.w.host(lambda h: h.notify_screen_info_changed())
        self.w.on_loading(is_loading, can_go_back, can_go_forward)


class CefCanvas(tkinter.Canvas):
    """The browser. ``on_title``, ``on_address``, ``on_loading`` and ``on_ready`` are set by the application."""

    def __init__(self, master, runtime, **options):
        super().__init__(master, highlightthickness=0, background="white", takefocus=True, **options)
        self.runtime = runtime
        self.client = _Handlers(self)
        self.browser = None
        self.view_width, self.view_height = 800, 600
        self.image = None                               # the picture (PIL) and what Tk shows of it
        self.photo = None
        self.item = None
        self.popup_rect = None
        self.popup_visible = False
        self.popup_image = None
        self.popup_photo = None
        self.popup_item = None
        self.drag_operation = types.DragOperationsMask.COPY
        self._clicks = (0.0, 0, 0, 0)
        self._drag_emulated = None                      # the DragData of a drag inside the page
        self.selected_text = ""
        self.on_title = self.on_address = lambda value: None
        self.on_loading = lambda loading, back, forward: None
        self.on_ready = lambda: None
        self.bind("<Configure>", self._on_configure)
        self.bind("<Motion>", self._on_motion)
        self.bind("<B1-Motion>", self._on_motion)
        self.bind("<B2-Motion>", self._on_motion)
        self.bind("<B3-Motion>", self._on_motion)
        for number in (1, 2, 3):
            self.bind("<ButtonPress-%d>" % number, self._on_press)
            self.bind("<ButtonRelease-%d>" % number, self._on_release)
        # the wheel of X is the buttons 4 and 5 (Tk has no 6 and 7: sideways scrolling is Shift and the wheel)
        self.bind("<Button-4>", lambda e: self._wheel(e, 0, 120))
        self.bind("<Button-5>", lambda e: self._wheel(e, 0, -120))
        self.bind("<Leave>", lambda e: self.host(lambda h: h.send_mouse_move_event(types.MouseEvent(e.x, e.y, 0), True)))
        self.bind("<KeyPress>", lambda e: self._send_key(e, False))
        self.bind("<KeyRelease>", lambda e: self._send_key(e, True))
        self.bind("<FocusIn>", lambda e: self.host(lambda h: h.set_focus(True)))
        self.bind("<FocusOut>", lambda e: self.host(lambda h: h.set_focus(False)))
        self.bind("<Map>", lambda e: self.host(lambda h: h.was_hidden(False)))
        self.bind("<Unmap>", lambda e: self.host(lambda h: h.was_hidden(True)))

    # -- the browser -----------------------------------------------------------------------------

    def host(self, function):
        if self.browser is not None:
            return function(self.browser.get_host())

    def browser_ready(self):
        self.host(lambda h: h.set_focus(self.focus_get() is self))
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

    def _on_configure(self, event):
        if (event.width, event.height) != (self.view_width, self.view_height):
            self.view_width, self.view_height = event.width, event.height
            self.host(lambda h: h.was_resized())

    # -- painting --------------------------------------------------------------------------------

    def paint(self, type, buffer, width, height):
        image = Image.frombuffer("RGBA", (width, height), bytes(buffer), "raw", "BGRA", 0, 1)   # the buffer is valid during this call only
        if type == types.PaintElementType.POPUP:
            self.popup_image = image
            self._show_popup()
            return
        self.image = image
        self.photo = ImageTk.PhotoImage(image, master=self)
        if self.item is None:
            self.item = self.create_image(0, 0, anchor="nw", image=self.photo)
        else:
            self.itemconfigure(self.item, image=self.photo)
        if self.popup_item is not None:
            self.tag_raise(self.popup_item)

    def _show_popup(self):
        if not self.popup_visible or self.popup_image is None or self.popup_rect is None:
            return
        self.popup_photo = ImageTk.PhotoImage(self.popup_image, master=self)
        if self.popup_item is None:
            self.popup_item = self.create_image(self.popup_rect.x, self.popup_rect.y, anchor="nw", image=self.popup_photo)
        else:
            self.itemconfigure(self.popup_item, image=self.popup_photo, state="normal")
            self.coords(self.popup_item, self.popup_rect.x, self.popup_rect.y)
        self.tag_raise(self.popup_item)

    def popup_show(self, show):
        self.popup_visible = show
        if not show:
            self.popup_image = None
            if self.popup_item is not None:
                self.itemconfigure(self.popup_item, state="hidden")
        else:
            self._show_popup()

    def snapshot(self, path):
        if self.image is None:
            return False
        self.image.convert("RGB").save(path)
        return True

    # -- the mouse -------------------------------------------------------------------------------

    def _mouse(self, event):
        return types.MouseEvent(event.x, event.y, modifier_flags(event.state))

    def _on_press(self, event):
        self.focus_set()
        now = time.monotonic()
        last_time, last_x, last_y, count = self._clicks       # Tk has no click count on X11 for all buttons: count here
        near = abs(event.x - last_x) <= 4 and abs(event.y - last_y) <= 4
        count = count + 1 if now - last_time < 0.4 and near and count < 3 else 1
        self._clicks = (now, event.x, event.y, count)
        button = {1: types.MouseButtonType.LEFT, 2: types.MouseButtonType.MIDDLE, 3: types.MouseButtonType.RIGHT}[event.num]
        self.host(lambda h: h.send_mouse_click_event(self._mouse(event), button, False, count))

    def _on_release(self, event):
        button = {1: types.MouseButtonType.LEFT, 2: types.MouseButtonType.MIDDLE, 3: types.MouseButtonType.RIGHT}[event.num]
        if self._drag_emulated is not None and event.num == 1:
            self._end_drag(event)
            return
        self.host(lambda h: h.send_mouse_click_event(self._mouse(event), button, True, self._clicks[3]))

    def _on_motion(self, event):
        if self._drag_emulated is not None:
            mouse = types.MouseEvent(event.x, event.y, 0)
            self.host(lambda h: h.drag_target_drag_over(mouse, self._drag_allowed))
            return
        self.host(lambda h: h.send_mouse_move_event(self._mouse(event), False))

    def _wheel(self, event, dx, dy):
        mouse = self._mouse(event)
        self.host(lambda h: h.send_mouse_wheel_event(mouse, dx, dy))

    # -- the keyboard --------------------------------------------------------------------------------

    def _clipboard_key(self, event, release):
        """Ctrl+C, Ctrl+X and Ctrl+V are done here. Done by CEF, the Tk process would own the X selection
        and CEF (this very thread) would read it at the same time: nobody could answer, the page hangs."""
        if not event.state & 0x4 or event.keysym.lower() not in ("c", "x", "v"):
            return False
        if release:
            return True
        key = event.keysym.lower()
        if key == "v":
            try:
                text = self.clipboard_get()
            except tkinter.TclError:
                text = ""
            if text:
                self.commit_text(text)
            return True
        if self.selected_text:
            self.clipboard_clear()
            self.clipboard_append(self.selected_text)
        if key == "x" and self.browser is not None:
            self.browser.get_main_frame().delete()
        return True

    def _send_key(self, event, release):
        if self._clipboard_key(event, release):
            return
        name = event.keysym
        modifiers = modifier_flags(event.state)
        base = dict(modifiers=modifiers, windows_key_code=windows_key_code(event), native_key_code=event.keycode)
        if release:
            self.host(lambda h: h.send_key_event(types.KeyEvent(types.KeyEventType.KEYUP, **base)))
            return
        text = event.char
        if text and len(text) > 1 or (text and ord(text[0]) > 0x7F):
            self.commit_text(text)                      # composed text of an input method (XIM) arrives whole
            return
        self.host(lambda h: h.send_key_event(types.KeyEvent(types.KeyEventType.RAWKEYDOWN, **base)))
        character = _CHAR_KEYS.get(name) or (ord(text) if text and text.isprintable() else 0)
        if character and not modifiers & (CONTROL | ALT):
            self.host(lambda h: h.send_key_event(types.KeyEvent(
                types.KeyEventType.CHAR, character=character, unmodified_character=character, **base)))

    def commit_text(self, text):
        nothing = cefweaver.Range(0xFFFFFFFF, 0xFFFFFFFF)
        self.host(lambda h: h.ime_commit_text(text, nothing, 0))

    def set_preedit(self, text, cursor):
        """Tk gives no preedit of an input method; this is for applications that have one."""
        if not text:
            self.host(lambda h: h.ime_cancel_composition())
            return
        underline = cefweaver.CompositionUnderline(cefweaver.Range(0, len(text)), 0xFF000000, 0, 0, types.CompositionUnderlineStyle.SOLID)
        nothing = cefweaver.Range(0xFFFFFFFF, 0xFFFFFFFF)
        self.host(lambda h: h.ime_set_composition(text, [underline], nothing, cefweaver.Range(cursor, cursor)))

    # -- drag and drop -----------------------------------------------------------------------------

    def begin_drag(self, data, allowed_ops):
        """CEF's start_dragging(): Tk cannot start a drag of its own, so the widget carries it out:
        the pointer moves are handed to CEF as drag_target_drag_over() and the release as the drop.
        That makes drags inside the page work (an element onto another), not drags out of it."""
        self._drag_emulated = data
        self._drag_allowed = allowed_ops
        mouse = types.MouseEvent(self.winfo_pointerx() - self.winfo_rootx(), self.winfo_pointery() - self.winfo_rooty(), 0)
        self.host(lambda h: h.drag_target_drag_enter(data, mouse, allowed_ops))
        return True

    def _end_drag(self, event):
        mouse = types.MouseEvent(event.x, event.y, 0)
        inside = 0 <= event.x < self.view_width and 0 <= event.y < self.view_height
        operation = self.drag_operation if inside else types.DragOperationsMask.NONE
        if inside:
            self.host(lambda h: (h.drag_target_drag_over(mouse, self._drag_allowed), h.drag_target_drop(mouse)))
        else:
            self.host(lambda h: h.drag_target_drag_leave())
        self.host(lambda h: (h.drag_source_ended_at(event.x, event.y, operation), h.drag_source_system_drag_ended()))
        self._drag_emulated = None
        self.drag_operation = types.DragOperationsMask.COPY
