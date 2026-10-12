"""A Kivy widget that shows a cefweaver offscreen browser, built on :mod:`cefweaver.ui`.

:mod:`cefweaver.ui` has the CEF side (:class:`~cefweaver.ui.BrowserView`,
:class:`~cefweaver.ui.Session`). This module adds the Kivy side:

* :class:`KivyLoop`: runs functions in the Kivy thread from any thread, at once or later.
* :class:`KivyAdapter`: the :class:`~cefweaver.ui.ToolkitAdapter` for a :class:`CefView` (size,
  scale and position, drawing frames into a ``Texture``, cursor and clipboard).
* :class:`CefView`: a ``Widget`` that passes the mouse, keys, text, composition and drops of the
  Kivy window (SDL2) to the view.

Note:
    The Kivy window reports composition text (``on_textedit``), committed text (``on_textinput``)
    and drops (``on_drop_*``). It cannot start a drag, so a drag inside the page is carried out by
    the view.

Checked: Xvfb with SDL_VIDEODRIVER=x11 and xdotool: the 27 checks of examples/kivy/smoke.py, and closing the window of the app (Kivy 2.3.1).
Not checked: drops of other programs (the checks hand the events of the window to the handlers), a scale other than 1, a real input method.
"""

import os

from kivy.clock import Clock
from kivy.core.clipboard import Clipboard
from kivy.core.window import Keyboard, Window
from kivy.graphics import Color, Rectangle
from kivy.graphics.texture import Texture
from kivy.metrics import Metrics
from kivy.uix.widget import Widget

from cefweaver import types, ui
from cefweaver.ui import keys

_K = Keyboard.keycodes
_KEYS = {
    _K["backspace"]: keys.VK_BACK, _K["tab"]: keys.VK_TAB, _K["enter"]: keys.VK_RETURN, _K["escape"]: keys.VK_ESCAPE,
    _K["spacebar"]: keys.VK_SPACE, _K["pageup"]: keys.VK_PRIOR, _K["pagedown"]: keys.VK_NEXT, _K["end"]: keys.VK_END,
    _K["home"]: keys.VK_HOME, _K["left"]: keys.VK_LEFT, _K["up"]: keys.VK_UP, _K["right"]: keys.VK_RIGHT,
    _K["down"]: keys.VK_DOWN, _K["insert"]: keys.VK_INSERT, _K["delete"]: keys.VK_DELETE, _K["shift"]: keys.VK_SHIFT,
    _K["lctrl"]: keys.VK_CONTROL, _K["rctrl"]: keys.VK_CONTROL, _K["alt"]: keys.VK_ALT,
}
_CURSORS = {
    types.CursorType.POINTER: "arrow", types.CursorType.HAND: "hand", types.CursorType.IBEAM: "ibeam",
    types.CursorType.CROSS: "crosshair", types.CursorType.WAIT: "wait", types.CursorType.MOVE: "size_all",
    types.CursorType.NOTALLOWED: "no", types.CursorType.NODROP: "no", types.CursorType.COLUMNRESIZE: "size_we",
    types.CursorType.ROWRESIZE: "size_ns", types.CursorType.EASTWESTRESIZE: "size_we",
    types.CursorType.NORTHSOUTHRESIZE: "size_ns",
}
_KEYTABLE = ui.KeyTable(_KEYS, function=ui.function_range(_K["f1"]),
                        char=lambda key: chr(key) if 0x20 <= key < 0x7F else None)
_MODIFIERS = ui.NamedModifiers()
_CURSOR_NAMES = ui.CursorTable(_CURSORS, default="arrow")


def windows_key_code(key):
    """Return the Windows virtual key code of a Kivy key code.

    Args:
        key (int): The key code of a Kivy ``on_key_down`` or ``on_key_up`` event.

    Returns:
        int: The virtual key code CEF expects. Printable ASCII letters and digits map to their
        capitals; unmapped keys map to 0.
    """
    return _KEYTABLE.code(key)


def modifier_flags(modifiers, buttons=()):
    """Convert Kivy modifier and button names to CEF event flags.

    Args:
        modifiers (list): The modifier names that are down (for example ``["ctrl", "shift"]``).
        buttons (collection, optional): The names of the mouse buttons that are down
            (``"left"``, ``"middle"``, ``"right"``). Default: none.

    Returns:
        int: The combined CEF flags.
    """
    return _MODIFIERS.flags(modifiers, buttons)


class KivyLoop:
    """The loop object :class:`~cefweaver.ui.Session` needs, on the Kivy clock."""

    def post(self, function):                           # any thread
        """Run ``function`` once in the Kivy thread on the next clock tick; callable from any thread."""
        Clock.schedule_once(lambda dt: function(), 0)

    def call_later(self, seconds, function):
        """Run ``function`` in the Kivy thread after ``seconds`` and return a ``ClockEvent`` (it has ``cancel()``)."""
        return Clock.schedule_once(lambda dt: function(), seconds)   # a ClockEvent: it has cancel()


class KivyAdapter(KivyLoop):
    """The :class:`~cefweaver.ui.ToolkitAdapter` for a :class:`CefView`.

    Declares no capabilities: the view carries out drags from the page itself.

    Args:
        widget (CefView): The widget this adapter serves.

    Attributes:
        capabilities (frozenset): The empty set.
    """

    capabilities = frozenset()

    def __init__(self, widget):
        self.w = widget

    def view_size(self):
        """Return the size of the widget as ``(width, height)`` in Kivy pixels."""
        return int(self.w.width), int(self.w.height)

    def scale(self):
        """Return Kivy's ``Metrics.density`` as the scale factor."""
        return float(Metrics.density)

    def screen_origin(self):
        """Return the screen position of the widget's top-left corner as ``(x, y)``.

        The window position is taken as ``(0, 0)`` where SDL2 cannot report it (macOS).
        """
        try:
            left, top = Window.left, Window.top
        except TypeError:                   # macOS: Kivy's SDL2 window cannot tell where it is
            left, top = 0, 0
        return int(left + self.w.x), int(top + Window.height - self.w.top)

    def screen_size(self):
        """Return the system size of the Kivy window's screen as ``(width, height)``."""
        return int(Window.system_size[0]), int(Window.system_size[1])

    def present(self, frame):
        """Hand a painted frame to the widget, which uploads it into a texture."""
        self.w.present_frame(frame)

    def set_cursor(self, cursor):
        """Set the system cursor of the Kivy window for a ``types.CursorType`` (``"arrow"`` if unmapped)."""
        Window.set_system_cursor(_CURSOR_NAMES.get(cursor))

    def clipboard_get(self):
        """Return the text of the Kivy clipboard."""
        return Clipboard.paste()

    def clipboard_set(self, text):
        """Put ``text`` on the Kivy clipboard."""
        Clipboard.copy(text)


class CefView(ui.BrowserWidget, Widget):
    """A Kivy widget that shows a browser.

    Args:
        runtime: The runtime (as returned by ``initialize()``) that makes the browser; stored as
            :attr:`runtime`.
        audio (optional): The audio handler options passed to the :class:`~cefweaver.ui.BrowserView`.
            Default None.
        **kwargs: Passed to ``Widget``.

    Attributes:
        runtime: The runtime given to the constructor.
        texture (Texture | None): The texture of the current view frame.
        popup_texture (Texture | None): The texture of the current popup, if any.
        picture (tuple): The ``(width, height)`` of the last view frame in pixels.

    Events:
        on_title(title): The page title changed.
        on_address(url): The page address changed.
        on_loading(loading, can_back, can_forward): The loading state or the navigation flags changed.
        on_ready(): The browser was created.
    """

    __events__ = ("on_title", "on_address", "on_loading", "on_ready")

    def __init__(self, runtime, audio=None, **kwargs):
        super().__init__(**kwargs)
        self.runtime = runtime
        self.attach_view(KivyAdapter(self), audio=audio)
        self.texture = self.popup_texture = None
        self.picture = (0, 0)
        self._buttons = set()
        self._modifiers = []
        self._inside = False
        with self.canvas:
            Color(1, 1, 1, 1)
            self._rect = Rectangle(pos=self.pos, size=self.size)
        with self.canvas.after:
            Color(1, 1, 1, 1)
            self._popup_rect_graphic = Rectangle(pos=(0, 0), size=(0, 0))
        self.bind(pos=self._on_geometry, size=self._on_geometry)
        Window.bind(mouse_pos=self._on_mouse_pos, on_key_down=self._on_key_down, on_key_up=self._on_key_up,
                    on_textinput=self._on_textinput, on_textedit=self._on_textedit, on_drop_begin=self._on_drop_begin,
                    on_drop_file=self._on_drop_file, on_drop_text=self._on_drop_text, on_drop_end=self._on_drop_end,
                    on_minimize=lambda *a: self.view.shown(False), on_restore=lambda *a: self.view.shown(True))

    def on_title(self, title):
        """Handle the ``on_title`` event; does nothing by default."""
        pass

    def on_address(self, url):
        """Handle the ``on_address`` event; does nothing by default."""
        pass

    def on_loading(self, loading, can_back, can_forward):
        """Handle the ``on_loading`` event; does nothing by default."""
        pass

    def on_ready(self):
        """Handle the ``on_ready`` event; does nothing by default."""
        pass

    # -- the browser -----------------------------------------------------------------------------

    def browser_title(self, title):
        """Dispatch ``on_title`` with the page title (an empty string for None)."""
        self.dispatch("on_title", title or "")

    def browser_address(self, url):
        """Dispatch ``on_address`` with the page address."""
        self.dispatch("on_address", url)

    def browser_loading(self, loading, can_back, can_forward):
        """Dispatch ``on_loading`` with the loading state and the navigation flags."""
        self.dispatch("on_loading", loading, can_back, can_forward)

    def browser_ready(self):
        """Focus the browser and dispatch ``on_ready``."""
        self.view.focus(True)
        self.dispatch("on_ready")

    def screen_origin(self):
        """Return the screen position of the widget's top-left corner as ``(x, y)``."""
        return self.view.adapter.screen_origin()

    def _on_geometry(self, *args):
        self._rect.pos, self._rect.size = self.pos, self.size
        self.view.resized()
        self._place_popup()

    # -- painting --------------------------------------------------------------------------------

    @staticmethod
    def _texture(current, buffer, width, height):
        if current is None or current.size != (width, height):
            current = Texture.create(size=(width, height), colorfmt="bgra")
            current.flip_vertical()                     # CEF's rows run downwards, OpenGL's upwards
        current.blit_buffer(bytes(buffer), colorfmt="bgra", bufferfmt="ubyte")   # valid during this call only
        return current

    def present_frame(self, frame):
        """Upload a painted frame (view or popup) into its texture and redraw."""
        if frame.kind == ui.Frame.POPUP_HIDDEN:
            self.popup_texture = None
            self._popup_rect_graphic.texture = None
        elif frame.kind == ui.Frame.POPUP:
            self.popup_texture = self._texture(self.popup_texture, frame.buffer, frame.width, frame.height)
            self._popup_rect_graphic.texture = self.popup_texture
        else:
            self.texture = self._texture(self.texture, frame.buffer, frame.width, frame.height)
            self.picture = (frame.width, frame.height)
            self._rect.texture = self.texture
        self._place_popup()
        self.canvas.ask_update()

    def _place_popup(self):
        rect = self.view.popup_rect
        if not self.view.popup_visible or self.popup_texture is None or rect is None:
            self._popup_rect_graphic.size = (0, 0)
            return
        width, height = self.popup_texture.size
        self._popup_rect_graphic.size = (width, height)
        self._popup_rect_graphic.pos = (self.x + rect.x, self.top - rect.y - height)
        self.canvas.ask_update()

    # -- the mouse -------------------------------------------------------------------------------

    def _local(self, pos):
        return int(pos[0] - self.x), int(self.top - pos[1])

    def _mods(self):
        return modifier_flags(self._modifiers, self._buttons)

    def _on_mouse_pos(self, window, pos):
        inside = self.collide_point(*pos)
        if inside or self._inside:
            x, y = self._local(pos)
            self.view.mouse_move(x, y, self._mods(), leave=not inside)
        self._inside = inside

    def on_touch_down(self, touch):
        """Pass a mouse button press or wheel step inside the widget to the view.

        Returns:
            bool: True if the view got the event; otherwise the result of the parent handler, or
            False for an unsupported button.
        """
        if not self.collide_point(*touch.pos):
            return super().on_touch_down(touch)
        button = getattr(touch, "button", "left")
        x, y = self._local(touch.pos)
        if button in ("scrollup", "scrolldown", "scrollleft", "scrollright"):
            # Kivy names the direction the other way round: its "scrollup" is the X button 5 (the wheel turned
            # towards the user, the page goes down), checked with xdotool
            dx = {"scrollleft": -120, "scrollright": 120}.get(button, 0)
            dy = {"scrollup": -120, "scrolldown": 120}.get(button, 0)
            self.view.wheel(x, y, dx, dy, self._mods())
            return True
        if button not in ("left", "middle", "right"):
            return False
        self._buttons.add(button)
        touch.grab(self)
        touch.ud["cef_clicks"] = 3 if touch.is_triple_tap else 2 if touch.is_double_tap else 1
        self.view.mouse_button(x, y, button, True, self._mods(), clicks=touch.ud["cef_clicks"])
        return True

    def on_touch_up(self, touch):
        """Pass the release of a button pressed in this widget to the view.

        Returns:
            bool: True if the touch was grabbed by this widget; otherwise the result of the parent
            handler.
        """
        if touch.grab_current is not self:
            return super().on_touch_up(touch)
        touch.ungrab(self)
        button = getattr(touch, "button", "left")
        self._buttons.discard(button)
        x, y = self._local(touch.pos)
        self.view.mouse_button(x, y, button, False, self._mods(), clicks=touch.ud.get("cef_clicks", 1))
        return True

    # -- the keyboard --------------------------------------------------------------------------------

    def _on_key_down(self, window, key, scancode, codepoint, modifiers):
        self._modifiers = modifiers
        return self.view.key(True, windows_key_code(key), scancode, modifier_flags(modifiers))

    def _on_key_up(self, window, key, scancode, *args):
        modifiers = args[-1] if args and isinstance(args[-1], list) else self._modifiers
        self._modifiers = modifiers
        return self.view.key(False, windows_key_code(key), scancode, modifier_flags(modifiers))

    def _on_textinput(self, window, text):
        """What the window commits (typed letters, or text an input method composed)."""
        self.view.text(text)

    def _on_textedit(self, window, text):
        self.view.preedit(text, len(text))

    # -- drops from other programs ---------------------------------------------------------------------

    def _drop_position(self, x, y):
        """Drop events come in window pixels with y downwards."""
        return int(x - self.x), int(y - (Window.height - self.top))

    def _on_drop_begin(self, window, x, y, *args):
        pass

    def _on_drop_file(self, window, filename, x, y, *args):
        self.view.drop(*self._drop_position(x, y), files=[os.fsdecode(filename)])

    def _on_drop_text(self, window, text, x, y, *args):
        self.view.drop(*self._drop_position(x, y), text=text)

    def _on_drop_end(self, window, *args):
        pass
