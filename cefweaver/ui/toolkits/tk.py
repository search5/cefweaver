"""A Tkinter widget that shows a cefweaver offscreen browser, built on ``cefweaver.ui``.

``cefweaver.ui`` has the CEF side (``BrowserView``, ``Session``). This file is what Tk adds, the adapter:

* ``TkLoop``: running something in the Tk loop from any thread (``post``: a queue and a pipe that
  ``createfilehandler`` watches) and later (``call_later``: ``after``);
* ``TkAdapter``: size and place of the canvas, drawing the frames with Pillow (``ImageTk``), the cursor and
  the clipboard of Tk;
* ``CefCanvas``: a ``tkinter.Canvas`` that passes the events of Tk (mouse, wheel, keys) to the view.

What Tk cannot do is in the README: no input method preedit, no drag out of the page into Tk widgets.
A drag inside the page is carried out by the view itself (the adapter has no drag source). Drops from other
programs are not supported: tkinterdnd2 (the tkdnd extension) ends the process when CEF starts in it (README).

Checked: Xvfb and xdotool: the 24 checks of examples/tk/smoke.py (Tk 8.6 of uv's CPython, Pillow).
Not checked: a scale other than 1 (Tk gives none), the preedit of an input method (Tk gives none), drops from other programs (tkinterdnd2 ends the process when CEF starts: cause unknown).
"""

import collections
import os
import tkinter

from PIL import Image, ImageTk

from cefweaver import types, ui
from cefweaver.ui import keys

_KEYS = {
    "BackSpace": keys.VK_BACK, "Tab": keys.VK_TAB, "ISO_Left_Tab": keys.VK_TAB, "Return": keys.VK_RETURN,
    "KP_Enter": keys.VK_RETURN, "Escape": keys.VK_ESCAPE, "space": keys.VK_SPACE, "Prior": keys.VK_PRIOR,
    "Next": keys.VK_NEXT, "End": keys.VK_END, "Home": keys.VK_HOME, "Left": keys.VK_LEFT, "Up": keys.VK_UP,
    "Right": keys.VK_RIGHT, "Down": keys.VK_DOWN, "Insert": keys.VK_INSERT, "Delete": keys.VK_DELETE,
    "Shift_L": keys.VK_SHIFT, "Shift_R": keys.VK_SHIFT, "Control_L": keys.VK_CONTROL, "Control_R": keys.VK_CONTROL,
    "Alt_L": keys.VK_ALT, "Alt_R": keys.VK_ALT, "Caps_Lock": keys.VK_CAPITAL,
}
_CURSORS = {
    types.CursorType.POINTER: "arrow", types.CursorType.HAND: "hand2", types.CursorType.IBEAM: "xterm",
    types.CursorType.CROSS: "crosshair", types.CursorType.WAIT: "watch", types.CursorType.HELP: "question_arrow",
    types.CursorType.MOVE: "fleur", types.CursorType.NOTALLOWED: "X_cursor", types.CursorType.NODROP: "X_cursor",
    types.CursorType.COLUMNRESIZE: "sb_h_double_arrow", types.CursorType.ROWRESIZE: "sb_v_double_arrow",
    types.CursorType.EASTWESTRESIZE: "sb_h_double_arrow", types.CursorType.NORTHSOUTHRESIZE: "sb_v_double_arrow",
}


_KEYTABLE = ui.KeyTable(_KEYS,
                        function=lambda name: int(name[1:]) if name.startswith("F") and name[1:].isdigit() else None,
                        char=lambda name: name if len(name) == 1 else None)
_MODIFIERS = ui.MaskModifiers(shift=0x1, control=0x4, alt=0x8, left=0x100, middle=0x200, right=0x400)
_CURSOR_NAMES = ui.CursorTable(_CURSORS, default="arrow")


def windows_key_code(event):
    return _KEYTABLE.code(event.keysym)


def modifier_flags(state):
    return _MODIFIERS.flags(state)


class _After:
    def __init__(self, root, seconds, function):
        self.root, self.function = root, function
        self.id = root.after(int(seconds * 1000), self._run)

    def _run(self):
        self.id = None
        self.function()

    def cancel(self):
        if self.id is not None:
            self.root.after_cancel(self.id)
            self.id = None


class TkLoop:
    """What ``ui.Session`` needs of a toolkit: the Tk loop. ``post`` may be called from any thread (Tk's own
    ``after`` may not), so the function goes into a queue and a byte into a pipe that Tk watches."""

    def __init__(self, root):
        self.root = root
        self._queue = collections.deque()
        self._read, self._write = os.pipe()
        os.set_blocking(self._read, False)
        root.tk.createfilehandler(self._read, tkinter.READABLE, lambda *args: self._on_wake())

    def post(self, function):
        self._queue.append(function)
        try:
            os.write(self._write, b"x")
        except OSError:
            pass

    def _on_wake(self):
        try:
            os.read(self._read, 4096)
        except OSError:
            pass
        while self._queue:
            self._queue.popleft()()

    def call_later(self, seconds, function):
        return _After(self.root, seconds, function)

    def release(self):
        self.root.tk.deletefilehandler(self._read)


class TkAdapter:
    """``ui.ToolkitAdapter`` for a ``CefCanvas``. Tk has no drag source for the page and no native clipboard
    that CEF could use: the view does both."""

    capabilities = frozenset()

    def __init__(self, widget, loop):
        self.w, self.loop = widget, loop

    def post(self, function):
        self.loop.post(function)

    def call_later(self, seconds, function):
        return self.loop.call_later(seconds, function)

    def view_size(self):
        return self.w.view_width, self.w.view_height

    def scale(self):
        return 1.0                                      # Tk gives no scale

    def screen_origin(self):
        return self.w.winfo_rootx(), self.w.winfo_rooty()

    def screen_size(self):
        return self.w.winfo_screenwidth(), self.w.winfo_screenheight()

    def present(self, frame):
        self.w.present_frame(frame)

    def set_cursor(self, cursor):
        self.w.configure(cursor=_CURSOR_NAMES.get(cursor))

    def clipboard_get(self):
        try:
            return self.w.clipboard_get()
        except tkinter.TclError:
            return None

    def clipboard_set(self, text):
        self.w.clipboard_clear()
        self.w.clipboard_append(text)


class CefCanvas(ui.BrowserWidget, tkinter.Canvas):
    """The browser. ``on_title``, ``on_address``, ``on_loading`` and ``on_ready`` are set by the application."""

    def __init__(self, master, runtime, **options):
        super().__init__(master, highlightthickness=0, background="white", takefocus=True, **options)
        self.runtime = runtime
        self.attach_view(TkAdapter(self, runtime.adapter))
        self.view_width, self.view_height = 800, 600
        self.image = None                               # the picture (PIL) and what Tk shows of it
        self.photo = None
        self.item = None
        self.popup_image = None
        self.popup_photo = None
        self.popup_item = None
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
        self.bind("<Button-4>", lambda e: self.view.wheel(e.x, e.y, 0, 120, modifier_flags(e.state)))
        self.bind("<Button-5>", lambda e: self.view.wheel(e.x, e.y, 0, -120, modifier_flags(e.state)))
        self.bind("<Leave>", lambda e: self.view.mouse_move(e.x, e.y, 0, leave=True))
        self.bind("<KeyPress>", lambda e: self._send_key(e, True))
        self.bind("<KeyRelease>", lambda e: self._send_key(e, False))
        self.bind("<FocusIn>", lambda e: self.view.focus(True))
        self.bind("<FocusOut>", lambda e: self.view.focus(False))
        self.bind("<Map>", lambda e: self.view.shown(True))
        self.bind("<Unmap>", lambda e: self.view.shown(False))

    # -- the browser -----------------------------------------------------------------------------

    def browser_title(self, title):
        self.on_title(title)

    def browser_address(self, url):
        self.on_address(url)

    def browser_loading(self, loading, can_back, can_forward):
        self.on_loading(loading, can_back, can_forward)

    def browser_ready(self):
        self.view.focus(self.focus_get() is self)
        self.on_ready()

    def _on_configure(self, event):
        if (event.width, event.height) != (self.view_width, self.view_height):
            self.view_width, self.view_height = event.width, event.height
            self.view.resized()

    # -- painting --------------------------------------------------------------------------------

    def present_frame(self, frame):
        if frame.kind == ui.Frame.POPUP_HIDDEN:
            self.popup_image = None
            if self.popup_item is not None:
                self.itemconfigure(self.popup_item, state="hidden")
            return
        image = Image.frombuffer("RGBA", (frame.width, frame.height), bytes(frame.buffer), "raw", "BGRA", 0, 1)   # the buffer is valid during this call only
        if frame.kind == ui.Frame.POPUP:
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
        rect = self.popup_rect
        if not self.popup_visible or self.popup_image is None or rect is None:
            return
        self.popup_photo = ImageTk.PhotoImage(self.popup_image, master=self)
        if self.popup_item is None:
            self.popup_item = self.create_image(rect.x, rect.y, anchor="nw", image=self.popup_photo)
        else:
            self.itemconfigure(self.popup_item, image=self.popup_photo, state="normal")
            self.coords(self.popup_item, rect.x, rect.y)
        self.tag_raise(self.popup_item)

    # -- the mouse -------------------------------------------------------------------------------

    @staticmethod
    def _button(event):
        return {1: "left", 2: "middle", 3: "right"}[event.num]

    def _on_press(self, event):
        self.focus_set()
        self.view.mouse_button(event.x, event.y, self._button(event), True, modifier_flags(event.state))

    def _on_release(self, event):
        self.view.mouse_button(event.x, event.y, self._button(event), False, modifier_flags(event.state))

    def _on_motion(self, event):
        self.view.mouse_move(event.x, event.y, modifier_flags(event.state))

    # -- the keyboard --------------------------------------------------------------------------------

    def _send_key(self, event, down):
        text = event.char
        if down and text and (len(text) > 1 or ord(text[0]) > 0x7F):
            self.view.commit_text(text)                 # composed text of an input method (XIM) arrives whole
            return
        self.view.key(down, windows_key_code(event), event.keycode, modifier_flags(event.state),
                      char=text if down and text and text.isprintable() else None)
