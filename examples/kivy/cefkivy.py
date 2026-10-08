"""A Kivy widget that shows a cefweaver offscreen browser.

``Runtime`` owns CEF and runs it from the Kivy clock with ``cefweaver.MessagePump``: CEF says (from any thread)
when it wants the loop, ``Clock.schedule_once`` (the same call ``@mainthread`` makes) carries that into the Kivy
thread and sets the deadline. ``CefView`` is a ``Widget``: the pixels of ``on_paint`` go into a ``Texture``
drawn by a ``Rectangle``, and the mouse, keys, text, composition and drops of the Kivy window become CEF events.

Kivy's window (SDL2) tells the text an input method is composing (``on_textedit``) and what it committed
(``on_textinput``), and where files and text are dropped (``on_drop_*``). It cannot start a drag, so a drag
inside the page is carried out by the widget itself (see ``begin_drag``).
"""

import os

from kivy.clock import Clock
from kivy.core.clipboard import Clipboard
from kivy.core.window import Keyboard, Window
from kivy.graphics import Color, Rectangle
from kivy.graphics.texture import Texture
from kivy.metrics import Metrics
from kivy.uix.widget import Widget

import cefweaver
from cefweaver import types

SHIFT, CONTROL, ALT = 1 << 1, 1 << 2, 1 << 3                       # EVENTFLAG_* of CEF
LEFT_BUTTON, MIDDLE_BUTTON, RIGHT_BUTTON = 1 << 4, 1 << 5, 1 << 6

_K = Keyboard.keycodes
_KEYS = {
    _K["backspace"]: 8, _K["tab"]: 9, _K["enter"]: 13, _K["escape"]: 27, _K["spacebar"]: 32, _K["pageup"]: 33,
    _K["pagedown"]: 34, _K["end"]: 35, _K["home"]: 36, _K["left"]: 37, _K["up"]: 38, _K["right"]: 39, _K["down"]: 40,
    _K["insert"]: 45, _K["delete"]: 46, _K["shift"]: 16, _K["lctrl"]: 17, _K["rctrl"]: 17, _K["alt"]: 18,
}
_CHAR_KEYS = {_K["enter"]: 13, _K["tab"]: 9, _K["backspace"]: 8}
_CURSORS = {
    types.CursorType.POINTER: "arrow", types.CursorType.HAND: "hand", types.CursorType.IBEAM: "ibeam",
    types.CursorType.CROSS: "crosshair", types.CursorType.WAIT: "wait", types.CursorType.MOVE: "size_all",
    types.CursorType.NOTALLOWED: "no", types.CursorType.NODROP: "no", types.CursorType.COLUMNRESIZE: "size_we",
    types.CursorType.ROWRESIZE: "size_ns", types.CursorType.EASTWESTRESIZE: "size_we",
    types.CursorType.NORTHSOUTHRESIZE: "size_ns",
}
_CTRL_KEYS = (_K["c"], _K["x"], _K["v"])


def windows_key_code(key):
    if key in _KEYS:
        return _KEYS[key]
    if _K["f1"] <= key <= _K["f1"] + 11:
        return 112 + key - _K["f1"]
    if 0x20 <= key < 0x7F:
        return ord(chr(key).upper())
    return 0


def modifier_flags(modifiers, buttons=()):
    flags = 0
    if "shift" in modifiers:
        flags |= SHIFT
    if "ctrl" in modifiers:
        flags |= CONTROL
    if "alt" in modifiers:
        flags |= ALT
    if "left" in buttons:
        flags |= LEFT_BUTTON
    if "middle" in buttons:
        flags |= MIDDLE_BUTTON
    if "right" in buttons:
        flags |= RIGHT_BUTTON
    return flags


class Runtime:
    """CEF for a Kivy application: ``Runtime(...)``, ``start(view, url)``, ``shutdown(done)``."""

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
        self._event = None
        self.started = False
        self.views = []

    def _wake(self, delay):                             # any thread of CEF
        Clock.schedule_once(lambda dt: self._schedule(), 0)

    def _schedule(self):
        if not self.started:
            return
        if self._event is not None:
            self._event.cancel()
        self._event = Clock.schedule_once(self._tick, max(0.0, self.pump.timeout()))

    def _tick(self, dt):
        self._event = None
        if self.started:
            self.pump.run()
            self._schedule()

    def start(self, view, url):
        self.views = [view]
        self.app.set_client(view.client)
        self.app.initialize(url)
        self.started = True
        self._schedule()

    def shutdown(self, done=None):
        for view in list(self.views):
            view.close_browser()

        def finish(dt):
            if self.app.is_running:
                Clock.schedule_once(finish, 0.02)
                return
            self.started = False
            if self._event is not None:
                self._event.cancel()
            self.app.shutdown()
            if done:
                done()
        Clock.schedule_once(finish, 0.02)


class _Handlers(cefweaver.Client):
    def __init__(self, view):
        super().__init__()
        self.render, self.life = _Render(view), _Life(view)
        self.display, self.load = _Display(view), _Load(view)

    def get_render_handler(self):
        return self.render

    def get_life_span_handler(self):
        return self.life

    def get_display_handler(self):
        return self.display

    def get_load_handler(self):
        return self.load


class _Render(cefweaver.RenderHandler):
    def __init__(self, view):
        self.v = view

    def get_view_rect(self, browser):
        return cefweaver.Rect(0, 0, max(1, int(self.v.width)), max(1, int(self.v.height)))

    def get_screen_info(self, browser):
        rect = cefweaver.Rect(0, 0, int(Window.system_size[0]), int(Window.system_size[1]))
        return True, cefweaver.ScreenInfo(float(Metrics.density), 24, 8, 0, rect, rect)

    def get_screen_point(self, browser, view_x, view_y):
        x, y = self.v.screen_origin()
        return True, x + view_x, y + view_y

    def on_paint(self, browser, type, dirty_rects, buffer, width, height):
        self.v.paint(type, buffer, width, height)

    def on_popup_show(self, browser, show):
        self.v.popup_show(show)

    def on_popup_size(self, browser, rect):
        self.v.popup_rect = rect

    def on_cursor_change(self, browser, cursor):
        Window.set_system_cursor(_CURSORS.get(cursor, "arrow"))
        return True

    def on_text_selection_changed(self, browser, selected_text, selected_range):
        self.v.selected_text = selected_text

    def start_dragging(self, browser, drag_data, allowed_ops, x, y):
        return self.v.begin_drag(drag_data, allowed_ops)

    def update_drag_cursor(self, browser, operation):
        self.v.drag_operation = operation
        self.v._over_answered = True


class _Life(cefweaver.LifeSpanHandler):
    def __init__(self, view):
        self.v = view

    def on_after_created(self, browser):
        self.v.browser = browser
        self.v.browser_ready()

    def on_before_close(self, browser):
        self.v.browser = None


class _Display(cefweaver.DisplayHandler):
    def __init__(self, view):
        self.v = view

    def on_title_change(self, browser, title):
        self.v.dispatch("on_title", title or "")

    def on_address_change(self, browser, frame, url):
        if frame.is_main():
            self.v.dispatch("on_address", url)


class _Load(cefweaver.LoadHandler):
    def __init__(self, view):
        self.v = view

    def on_loading_state_change(self, browser, is_loading, can_go_back, can_go_forward):
        if not is_loading:
            # a page restored by "back" from the back-forward cache ignores size changes until CEF is
            # told that the screen information changed (see the GTK example and the wiki, F67)
            self.v.host(lambda h: h.notify_screen_info_changed())
        self.v.dispatch("on_loading", is_loading, can_go_back, can_go_forward)


class CefView(Widget):
    """The browser. Events: ``on_title(title)``, ``on_address(url)``, ``on_loading(loading, back, forward)``,
    ``on_ready()``."""

    __events__ = ("on_title", "on_address", "on_loading", "on_ready")

    def __init__(self, runtime, **kwargs):
        super().__init__(**kwargs)
        self.runtime = runtime
        self.client = _Handlers(self)
        self.browser = None
        self.texture = self.popup_texture = None
        self.picture = (0, 0)
        self.popup_rect, self.popup_visible = None, False
        self.selected_text = ""
        self.drag_operation = types.DragOperationsMask.COPY
        self._over_answered = False
        self._buttons = set()
        self._modifiers = []
        self._drag_emulated = None                      # the DragData of a drag inside the page
        self._drag_allowed = types.DragOperationsMask.COPY
        self._last_key = None
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
                    on_minimize=lambda *a: self.host(lambda h: h.was_hidden(True)),
                    on_restore=lambda *a: self.host(lambda h: h.was_hidden(False)))

    def on_title(self, title):
        pass

    def on_address(self, url):
        pass

    def on_loading(self, loading, can_back, can_forward):
        pass

    def on_ready(self):
        pass

    # -- the browser -----------------------------------------------------------------------------

    def host(self, function):
        if self.browser is not None:
            return function(self.browser.get_host())

    def browser_ready(self):
        self.host(lambda h: h.set_focus(True))
        self.dispatch("on_ready")

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

    def screen_origin(self):
        """The top-left corner of the widget on the screen (Kivy's y runs upwards: the window's height turns it)."""
        return int(Window.left + self.x), int(Window.top + Window.height - self.top)

    def _on_geometry(self, *args):
        self._rect.pos, self._rect.size = self.pos, self.size
        self.host(lambda h: h.was_resized())
        self._place_popup()

    # -- painting --------------------------------------------------------------------------------

    def _texture(self, current, buffer, width, height):
        if current is None or current.size != (width, height):
            current = Texture.create(size=(width, height), colorfmt="bgra")
            current.flip_vertical()                     # CEF's rows run downwards, OpenGL's upwards
        current.blit_buffer(bytes(buffer), colorfmt="bgra", bufferfmt="ubyte")   # valid during this call only
        return current

    def paint(self, type, buffer, width, height):
        if type == types.PaintElementType.POPUP:
            self.popup_texture = self._texture(self.popup_texture, buffer, width, height)
            self._popup_rect_graphic.texture = self.popup_texture
            self._place_popup()
        else:
            self.texture = self._texture(self.texture, buffer, width, height)
            self.picture = (width, height)
            self._rect.texture = self.texture
        self.canvas.ask_update()

    def popup_show(self, show):
        self.popup_visible = show
        if not show:
            self.popup_texture = None
            self._popup_rect_graphic.texture = None
        self._place_popup()

    def _place_popup(self):
        rect = self.popup_rect
        if not self.popup_visible or self.popup_texture is None or rect is None:
            self._popup_rect_graphic.size = (0, 0)
            return
        width, height = self.popup_texture.size
        self._popup_rect_graphic.size = (width, height)
        self._popup_rect_graphic.pos = (self.x + rect.x, self.top - rect.y - height)
        self.canvas.ask_update()

    def snapshot(self, path):
        if self.texture is None:
            return False
        self.texture.save(path, flipped=True)
        return True

    # -- the mouse -------------------------------------------------------------------------------

    def _local(self, pos):
        return int(pos[0] - self.x), int(self.top - pos[1])

    def _mouse(self, pos):
        x, y = self._local(pos)
        return types.MouseEvent(x, y, modifier_flags(self._modifiers, self._buttons))

    def _on_mouse_pos(self, window, pos):
        if self._drag_emulated is not None:
            x, y = self._local(pos)
            mouse = types.MouseEvent(x, y, 0)
            self.host(lambda h: h.drag_target_drag_over(mouse, self._drag_allowed))
            return
        inside = self.collide_point(*pos)
        if inside or self._inside:
            self.host(lambda h: h.send_mouse_move_event(self._mouse(pos), not inside))
        self._inside = inside

    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return super().on_touch_down(touch)
        button = getattr(touch, "button", "left")
        self.host(lambda h: h.set_focus(True))
        if button in ("scrollup", "scrolldown", "scrollleft", "scrollright"):
            # Kivy names the direction the other way round: its "scrollup" is the X button 5 (the wheel turned
            # towards the user, the page goes down), checked with xdotool
            dx = {"scrollleft": -120, "scrollright": 120}.get(button, 0)
            dy = {"scrollup": -120, "scrolldown": 120}.get(button, 0)
            self.host(lambda h: h.send_mouse_wheel_event(self._mouse(touch.pos), dx, dy))
            return True
        kind = {"left": types.MouseButtonType.LEFT, "middle": types.MouseButtonType.MIDDLE,
                "right": types.MouseButtonType.RIGHT}.get(button)
        if kind is None:
            return False
        self._buttons.add(button)
        touch.grab(self)
        count = 3 if touch.is_triple_tap else 2 if touch.is_double_tap else 1
        touch.ud["cef_clicks"] = count
        self.host(lambda h: h.send_mouse_click_event(self._mouse(touch.pos), kind, False, count))
        return True

    def on_touch_up(self, touch):
        if touch.grab_current is not self:
            return super().on_touch_up(touch)
        touch.ungrab(self)
        button = getattr(touch, "button", "left")
        self._buttons.discard(button)
        if self._drag_emulated is not None and button == "left":
            self._end_drag(touch.pos)
            return True
        kind = {"left": types.MouseButtonType.LEFT, "middle": types.MouseButtonType.MIDDLE,
                "right": types.MouseButtonType.RIGHT}[button]
        self.host(lambda h: h.send_mouse_click_event(self._mouse(touch.pos), kind, True, touch.ud.get("cef_clicks", 1)))
        return True

    # -- the keyboard --------------------------------------------------------------------------------

    def _on_key_down(self, window, key, scancode, codepoint, modifiers):
        self._modifiers = modifiers
        if "ctrl" in modifiers and key in _CTRL_KEYS:
            self._clipboard_key(key)        # not CEF: the selection of this very process (see README)
            return True
        base = dict(modifiers=modifier_flags(modifiers), windows_key_code=windows_key_code(key), native_key_code=scancode)
        self._last_key = base
        self.host(lambda h: h.send_key_event(types.KeyEvent(types.KeyEventType.RAWKEYDOWN, **base)))
        character = _CHAR_KEYS.get(key)
        if character and not ("ctrl" in modifiers or "alt" in modifiers):
            self.host(lambda h: h.send_key_event(types.KeyEvent(
                types.KeyEventType.CHAR, character=character, unmodified_character=character, **base)))
        return False

    def _on_key_up(self, window, key, scancode, *args):
        modifiers = args[-1] if args and isinstance(args[-1], list) else self._modifiers
        self._modifiers = modifiers
        if "ctrl" in modifiers and key in _CTRL_KEYS:
            return True
        base = dict(modifiers=modifier_flags(modifiers), windows_key_code=windows_key_code(key), native_key_code=scancode)
        self.host(lambda h: h.send_key_event(types.KeyEvent(types.KeyEventType.KEYUP, **base)))
        return False

    def _on_textinput(self, window, text):
        """What the window commits (typed letters, or text an input method composed)."""
        if not text:
            return
        if len(text) == 1 and ord(text) < 0x80:
            base = self._last_key or dict(modifiers=0, windows_key_code=windows_key_code(ord(text)), native_key_code=0)
            self.host(lambda h: h.send_key_event(types.KeyEvent(
                types.KeyEventType.CHAR, character=ord(text), unmodified_character=ord(text), **base)))
        else:
            self.commit_text(text)

    def _on_textedit(self, window, text):
        self.set_preedit(text, len(text))

    def _clipboard_key(self, key):
        if key == _K["v"]:
            text = Clipboard.paste()
            if text:
                self.commit_text(text)
            return
        if self.selected_text:
            Clipboard.copy(self.selected_text)
        if key == _K["x"] and self.browser is not None:
            self.browser.get_main_frame().delete()

    def commit_text(self, text):
        nothing = cefweaver.Range(0xFFFFFFFF, 0xFFFFFFFF)
        self.host(lambda h: h.ime_commit_text(text, nothing, 0))

    def set_preedit(self, text, cursor):
        if not text:
            self.host(lambda h: h.ime_cancel_composition())
            return
        underline = cefweaver.CompositionUnderline(cefweaver.Range(0, len(text)), 0xFF000000, 0, 0, types.CompositionUnderlineStyle.SOLID)
        nothing = cefweaver.Range(0xFFFFFFFF, 0xFFFFFFFF)
        self.host(lambda h: h.ime_set_composition(text, [underline], nothing, cefweaver.Range(cursor, cursor)))

    # -- drag and drop -----------------------------------------------------------------------------

    def begin_drag(self, data, allowed_ops):
        """CEF's start_dragging(): Kivy cannot start a drag, so the widget carries it out: the pointer moves
        are handed to CEF as drag_target_drag_over() and the release as the drop (drags inside the page)."""
        self._drag_emulated, self._drag_allowed = data, allowed_ops
        x, y = self._local(Window.mouse_pos)
        mouse = types.MouseEvent(x, y, 0)
        self.host(lambda h: h.drag_target_drag_enter(data, mouse, allowed_ops))
        return True

    def _end_drag(self, pos):
        x, y = self._local(pos)
        mouse = types.MouseEvent(x, y, 0)
        inside = self.collide_point(*pos)
        operation = self.drag_operation if inside else types.DragOperationsMask.NONE
        if inside:
            self.host(lambda h: (h.drag_target_drag_over(mouse, self._drag_allowed), h.drag_target_drop(mouse)))
        else:
            self.host(lambda h: h.drag_target_drag_leave())
        self.host(lambda h: (h.drag_source_ended_at(x, y, operation), h.drag_source_system_drag_ended()))
        self._drag_emulated = None
        self.drag_operation = types.DragOperationsMask.COPY

    def _drop_position(self, x, y):
        """Drop events come in window pixels with y downwards."""
        return int(x - self.x), int(y - (Window.height - self.top))

    def _on_drop_begin(self, window, x, y, *args):
        self._drop_at = self._drop_position(x, y)

    def _on_drop_file(self, window, filename, x, y, *args):
        self._drop(os.fsdecode(filename), (x, y), files=True)

    def _on_drop_text(self, window, text, x, y, *args):
        self._drop(text, (x, y), files=False)

    def _on_drop_end(self, window, *args):
        pass

    def _drop(self, what, position, files):
        """A drop from another program: enter and over first, the drop when CEF has answered the over."""
        data = cefweaver.DragData.create()
        if files:
            data.add_file(what, os.path.basename(what))
        else:
            data.set_fragment_text(what)
        mouse = types.MouseEvent(*self._drop_position(*position), 0)
        ops = types.DragOperationsMask.COPY
        self._over_answered = False
        self.host(lambda h: (h.drag_target_drag_enter(data, mouse, ops), h.drag_target_drag_over(mouse, ops)))
        deadline = Clock.get_time() + 0.5

        def drop(dt):
            if self._over_answered or Clock.get_time() > deadline:
                self.host(lambda h: h.drag_target_drop(mouse))
            else:
                Clock.schedule_once(drop, 0.01)
        drop(0)
