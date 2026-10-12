"""A Tkinter widget that shows a cefweaver offscreen browser.

Classes:
    :class:`TkLoop`: runs functions in the Tk main loop (the loop object :class:`~cefweaver.ui.Session` needs).
    :class:`TkAdapter`: the :class:`~cefweaver.ui.ToolkitAdapter` for a :class:`CefCanvas`.
    :class:`CefCanvas`: a :class:`tkinter.Canvas` that shows the browser and passes mouse, wheel and key events
    to its :class:`~cefweaver.ui.BrowserView`.

Frames are drawn with Pillow (``PIL.ImageTk``), which this module requires.

Note:
    Tk gives no scale (``scale()`` is always 1.0) and no input method preedit. The adapter has no drag source and no
    native clipboard for CEF, so a drag inside the page and the clipboard keys are carried out by the view. Drops
    from other programs are not supported.

Checked: Xvfb and xdotool: the 30 checks of examples/tk/smoke.py (Tk 8.6 of uv's CPython, Pillow), also with CEF on Wayland.
Not checked: a scale other than 1 (Tk gives none), the preedit of an input method (Tk gives none; on a real screen the Korean/English key of the input method does not work: cause not looked for), drops from other programs (tkinterdnd2 ends the process when CEF starts: cause unknown).
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
    """Return the Windows virtual key code for a Tk key event.

    Args:
        event (tkinter.Event): A key event; its ``keysym`` is looked up.

    Returns:
        int: A ``cefweaver.ui.keys.VK_*`` code, or 0 if the key has none.
    """
    return _KEYTABLE.code(event.keysym)


def modifier_flags(state):
    """Return the CEF event flags for a Tk event ``state``.

    Args:
        state (int): The ``state`` field of a Tk event (modifier and mouse button bits).

    Returns:
        int: The matching ``cefweaver.ui.keys`` modifier and mouse button flags.
    """
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
    """The Tk main loop as the loop object of :class:`~cefweaver.ui.Session`.

    Functions passed to :meth:`post` are queued; a byte is written to a pipe that Tk watches (``createfilehandler``),
    and the functions run in the Tk main loop.

    Args:
        root (tkinter.Tk): The root window whose loop runs the functions.

    Attributes:
        root (tkinter.Tk): The root window.
    """

    def __init__(self, root):
        self.root = root
        self._queue = collections.deque()
        self._read, self._write = os.pipe()
        os.set_blocking(self._read, False)
        root.tk.createfilehandler(self._read, tkinter.READABLE, lambda *args: self._on_wake())

    def post(self, function):
        """Run ``function`` in the Tk main loop.

        Args:
            function (callable): Called with no arguments.

        Note:
            Callable from any thread.
        """
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
        """Run ``function`` in the Tk main loop after a delay, using ``after``.

        Args:
            seconds (float): The delay in seconds.
            function (callable): Called with no arguments.

        Returns:
            object: A handle with ``cancel()``.
        """
        return _After(self.root, seconds, function)

    def release(self):
        """Remove the file handler that watches the wake-up pipe."""
        self.root.tk.deletefilehandler(self._read)


class TkAdapter:
    """The :class:`~cefweaver.ui.ToolkitAdapter` for a :class:`CefCanvas`.

    Args:
        widget (CefCanvas): The canvas that shows the browser.
        loop (TkLoop): The loop that runs posted and delayed functions.

    Attributes:
        capabilities (frozenset): Empty; the view handles drags out and the clipboard itself.
        w (CefCanvas): The canvas.
        loop (TkLoop): The loop.
        last_menu (tkinter.Menu): The menu most recently shown by :meth:`show_menu`; set after the first call.
    """

    capabilities = frozenset()

    def __init__(self, widget, loop):
        self.w, self.loop = widget, loop

    def post(self, function):
        """Run ``function`` in the Tk main loop; callable from any thread."""
        self.loop.post(function)

    def call_later(self, seconds, function):
        """Run ``function`` in the Tk main loop after ``seconds``; return an object with ``cancel()``."""
        return self.loop.call_later(seconds, function)

    def view_size(self):
        """Return the size of the canvas in logical pixels."""
        return self.w.view_width, self.w.view_height

    def scale(self):
        """Return the scale, always 1.0 (Tk gives none)."""
        return 1.0                                      # Tk gives no scale

    def screen_origin(self):
        """Return the position of the canvas on the screen."""
        return self.w.winfo_rootx(), self.w.winfo_rooty()

    def screen_size(self):
        """Return the size of the screen."""
        return self.w.winfo_screenwidth(), self.w.winfo_screenheight()

    def present(self, frame):
        """Draw ``frame`` on the canvas."""
        self.w.present_frame(frame)

    def set_cursor(self, cursor):
        """Show the Tk cursor that matches the CEF cursor type."""
        self.w.configure(cursor=_CURSOR_NAMES.get(cursor))

    def show_menu(self, items, x, y, done):
        """Show the context menu of the page as a :class:`tkinter.Menu`.

        Args:
            items (list): The menu entries; each has ``kind``, ``label``, ``enabled``, ``checked``, ``command_id`` and
                ``children``.
            x (int): The x coordinate in the widget.
            y (int): The y coordinate in the widget.
            done (callable): Called once with the ``command_id`` of the picked item, or None if the menu is left
                without a pick.
        """
        picked, variables = [], []

        def pick(command_id):
            if not picked:
                picked.append(command_id)
                done(command_id)

        def fill(menu, entries):
            for entry in entries:
                state = "normal" if entry.enabled else "disabled"
                if entry.kind == "separator":
                    menu.add_separator()
                elif entry.kind == "submenu":
                    sub = tkinter.Menu(menu, tearoff=False)
                    fill(sub, entry.children)
                    menu.add_cascade(label=entry.label, menu=sub, state=state)
                elif entry.kind in ("check", "radio"):
                    variables.append(tkinter.BooleanVar(value=entry.checked))
                    menu.add_checkbutton(label=entry.label, variable=variables[-1], state=state,
                                         command=lambda command_id=entry.command_id: pick(command_id))
                else:
                    menu.add_command(label=entry.label, state=state, command=lambda command_id=entry.command_id: pick(command_id))
        menu = tkinter.Menu(self.w, tearoff=False)
        menu.variables = variables                       # Tk keeps no reference of the variables
        fill(menu, items)
        # the command of an item runs after the menu was unmapped: leaving the menu is told only when nothing was picked
        menu.bind("<Unmap>", lambda event: event.widget is menu and menu.after(50, lambda: pick(None)))
        self.last_menu = menu
        try:
            menu.tk_popup(self.w.winfo_rootx() + int(x), self.w.winfo_rooty() + int(y))
        finally:
            menu.grab_release()

    def clipboard_get(self):
        """Return the text of the Tk clipboard, or None if it has none."""
        try:
            return self.w.clipboard_get()
        except tkinter.TclError:
            return None

    def clipboard_set(self, text):
        """Replace the text of the Tk clipboard with ``text``."""
        self.w.clipboard_clear()
        self.w.clipboard_append(text)


class CefCanvas(ui.BrowserWidget, tkinter.Canvas):
    """A :class:`tkinter.Canvas` that shows a CEF offscreen browser.

    Args:
        master (tkinter.Misc): The parent widget.
        runtime (object): The object with the :class:`TkLoop` as its ``adapter`` attribute.
        audio (optional): The ``audio`` option of :class:`~cefweaver.ui.BrowserView`.
        **options: Passed to :class:`tkinter.Canvas`.

    Attributes:
        view (cefweaver.ui.BrowserView): The browser view.
        runtime (object): The ``runtime`` argument.
        view_width (int): The canvas width in pixels (800 until the first ``<Configure>`` event).
        view_height (int): The canvas height in pixels (600 until the first ``<Configure>`` event).
        on_title (callable): ``on_title(title)``; called when the page title changes.
        on_address (callable): ``on_address(url)``; called when the address changes.
        on_loading (callable): ``on_loading(loading, can_back, can_forward)``; called when the loading state changes.
        on_ready (callable): ``on_ready()``; called when the browser exists.
    """

    def __init__(self, master, runtime, audio=None, **options):
        super().__init__(master, highlightthickness=0, background="white", takefocus=True, **options)
        self.runtime = runtime
        self.attach_view(TkAdapter(self, runtime.adapter), audio=audio)
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
        """Call ``on_title`` with the page title."""
        self.on_title(title)

    def browser_address(self, url):
        """Call ``on_address`` with the address of the page."""
        self.on_address(url)

    def browser_loading(self, loading, can_back, can_forward):
        """Call ``on_loading`` with the loading state."""
        self.on_loading(loading, can_back, can_forward)

    def browser_ready(self):
        """Give the view the focus state of the canvas and call ``on_ready``."""
        self.view.focus(self.focus_get() is self)
        self.on_ready()

    def _on_configure(self, event):
        if (event.width, event.height) != (self.view_width, self.view_height):
            self.view_width, self.view_height = event.width, event.height
            self.view.resized()

    # -- painting --------------------------------------------------------------------------------

    def present_frame(self, frame):
        """Draw a CEF frame (the view or a popup) as a canvas image, or hide the popup.

        Args:
            frame (cefweaver.ui.Frame): The frame to draw.
        """
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
