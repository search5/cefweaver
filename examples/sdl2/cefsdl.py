"""An SDL2 window that shows a cefweaver offscreen browser (PySDL2).

SDL gives windows, events and textures but no widgets, so ``SdlBrowser`` is both the view and the
event loop: ``step(timeout_ms)`` waits for an SDL event (or for the time CEF asked for), handles it,
runs ``cefweaver.MessagePump`` when it is due and draws what changed. CEF's request to run (from any
thread of CEF) is an SDL user event pushed with ``SDL_PushEvent``, which is thread safe.

SDL tells the text an input method is composing (``SDL_TEXTEDITING``) and what it committed
(``SDL_TEXTINPUT``), so Hangul composition is real here. Drops of text and files from other programs
arrive (``SDL_DROPTEXT``, ``SDL_DROPFILE``); SDL cannot start a drag out of its window.
"""

import ctypes
import os
import time
import warnings

warnings.filterwarnings("ignore", message="Using SDL2 binaries from pysdl2-dll")
os.environ.setdefault("SDL_VIDEODRIVER", "x11")                 # never the real Wayland session
os.environ.setdefault("SDL_HINT_RENDER_DRIVER", "software")

import sdl2                                                      # noqa: E402
from sdl2 import sdlimage                                        # noqa: E402

import cefweaver                                                 # noqa: E402
from cefweaver import types                                      # noqa: E402

SHIFT, CONTROL, ALT = 1 << 1, 1 << 2, 1 << 3                     # EVENTFLAG_* of CEF
LEFT_BUTTON, MIDDLE_BUTTON, RIGHT_BUTTON = 1 << 4, 1 << 5, 1 << 6

_KEYS = {
    sdl2.SDLK_BACKSPACE: 8, sdl2.SDLK_TAB: 9, sdl2.SDLK_RETURN: 13, sdl2.SDLK_KP_ENTER: 13, sdl2.SDLK_ESCAPE: 27,
    sdl2.SDLK_SPACE: 32, sdl2.SDLK_PAGEUP: 33, sdl2.SDLK_PAGEDOWN: 34, sdl2.SDLK_END: 35, sdl2.SDLK_HOME: 36,
    sdl2.SDLK_LEFT: 37, sdl2.SDLK_UP: 38, sdl2.SDLK_RIGHT: 39, sdl2.SDLK_DOWN: 40, sdl2.SDLK_INSERT: 45,
    sdl2.SDLK_DELETE: 46, sdl2.SDLK_LSHIFT: 16, sdl2.SDLK_RSHIFT: 16, sdl2.SDLK_LCTRL: 17, sdl2.SDLK_RCTRL: 17,
    sdl2.SDLK_LALT: 18, sdl2.SDLK_RALT: 18,
}
_CHAR_KEYS = {sdl2.SDLK_RETURN: 13, sdl2.SDLK_KP_ENTER: 13, sdl2.SDLK_TAB: 9, sdl2.SDLK_BACKSPACE: 8}
_CURSORS = {
    types.CursorType.POINTER: sdl2.SDL_SYSTEM_CURSOR_ARROW, types.CursorType.HAND: sdl2.SDL_SYSTEM_CURSOR_HAND,
    types.CursorType.IBEAM: sdl2.SDL_SYSTEM_CURSOR_IBEAM, types.CursorType.CROSS: sdl2.SDL_SYSTEM_CURSOR_CROSSHAIR,
    types.CursorType.WAIT: sdl2.SDL_SYSTEM_CURSOR_WAIT, types.CursorType.MOVE: sdl2.SDL_SYSTEM_CURSOR_SIZEALL,
    types.CursorType.NOTALLOWED: sdl2.SDL_SYSTEM_CURSOR_NO, types.CursorType.NODROP: sdl2.SDL_SYSTEM_CURSOR_NO,
    types.CursorType.COLUMNRESIZE: sdl2.SDL_SYSTEM_CURSOR_SIZEWE, types.CursorType.ROWRESIZE: sdl2.SDL_SYSTEM_CURSOR_SIZENS,
    types.CursorType.EASTWESTRESIZE: sdl2.SDL_SYSTEM_CURSOR_SIZEWE, types.CursorType.NORTHSOUTHRESIZE: sdl2.SDL_SYSTEM_CURSOR_SIZENS,
}


def windows_key_code(sym):
    if sym in _KEYS:
        return _KEYS[sym]
    if sdl2.SDLK_F1 <= sym <= sdl2.SDLK_F12:
        return 112 + sym - sdl2.SDLK_F1
    if 0x20 <= sym < 0x7F:
        return ord(chr(sym).upper())
    return 0


def modifier_flags(mod, buttons=0):
    flags = 0
    if mod & sdl2.KMOD_SHIFT:
        flags |= SHIFT
    if mod & sdl2.KMOD_CTRL:
        flags |= CONTROL
    if mod & sdl2.KMOD_ALT:
        flags |= ALT
    if buttons & sdl2.SDL_BUTTON_LMASK:
        flags |= LEFT_BUTTON
    if buttons & sdl2.SDL_BUTTON_MMASK:
        flags |= MIDDLE_BUTTON
    if buttons & sdl2.SDL_BUTTON_RMASK:
        flags |= RIGHT_BUTTON
    return flags


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
        return cefweaver.Rect(0, 0, max(1, self.v.width), max(1, self.v.height))

    def get_screen_info(self, browser):
        rect = cefweaver.Rect(0, 0, self.v.screen_size[0], self.v.screen_size[1])
        return True, cefweaver.ScreenInfo(float(self.v.scale), 24, 8, 0, rect, rect)

    def get_screen_point(self, browser, view_x, view_y):
        x, y = ctypes.c_int(), ctypes.c_int()
        sdl2.SDL_GetWindowPosition(self.v.window, ctypes.byref(x), ctypes.byref(y))
        return True, x.value + view_x, y.value + view_y

    def on_paint(self, browser, type, dirty_rects, buffer, width, height):
        self.v.paint(type, dirty_rects, buffer, width, height)

    def on_popup_show(self, browser, show):
        self.v.popup_show(show)

    def on_popup_size(self, browser, rect):
        self.v.popup_rect = rect

    def on_cursor_change(self, browser, cursor):
        self.v.set_cursor(cursor)
        return True

    def on_text_selection_changed(self, browser, selected_text, selected_range):
        self.v.selected_text = selected_text

    def start_dragging(self, browser, drag_data, allowed_ops, x, y):
        return self.v.begin_drag(drag_data, allowed_ops)

    def update_drag_cursor(self, browser, operation):
        self.v.drag_operation = operation

    def on_ime_composition_range_changed(self, browser, selected_range, character_bounds):
        if character_bounds:                            # where the candidate window goes
            last = character_bounds[-1]
            rect = sdl2.SDL_Rect(last.x, last.y, last.width, last.height)
            sdl2.SDL_SetTextInputRect(ctypes.byref(rect))


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
        self.v.title = title or "cefweaver SDL2"
        sdl2.SDL_SetWindowTitle(self.v.window, self.v.title.encode("utf-8"))

    def on_address_change(self, browser, frame, url):
        if frame.is_main():
            self.v.url = url


class _Load(cefweaver.LoadHandler):
    def __init__(self, view):
        self.v = view

    def on_loading_state_change(self, browser, is_loading, can_go_back, can_go_forward):
        self.v.can_back, self.v.can_forward = can_go_back, can_go_forward
        if not is_loading:
            # a page restored by "back" from the back-forward cache ignores size changes until CEF is
            # told that the screen information changed (see the GTK example and the wiki, F67)
            self.v.host(lambda h: h.notify_screen_info_changed())


class SdlBrowser:
    """The window, the browser and the event loop."""

    def __init__(self, switches=(), cache_path=None, width=900, height=640, title="cefweaver SDL2"):
        if sdl2.SDL_Init(sdl2.SDL_INIT_VIDEO) != 0:
            raise RuntimeError("SDL_Init: %s" % sdl2.SDL_GetError().decode())
        sdl2.SDL_SetHint(b"SDL_IME_SHOW_UI", b"1")
        self.window = sdl2.SDL_CreateWindow(title.encode("utf-8"), sdl2.SDL_WINDOWPOS_UNDEFINED, sdl2.SDL_WINDOWPOS_UNDEFINED,
                                            width, height, sdl2.SDL_WINDOW_SHOWN | sdl2.SDL_WINDOW_RESIZABLE | sdl2.SDL_WINDOW_ALLOW_HIGHDPI)
        self.renderer = sdl2.SDL_CreateRenderer(self.window, -1, sdl2.SDL_RENDERER_SOFTWARE)
        self.driver = sdl2.SDL_GetCurrentVideoDriver().decode()
        self.width, self.height = width, height
        self.scale = 1
        display = sdl2.SDL_DisplayMode()
        sdl2.SDL_GetDesktopDisplayMode(0, ctypes.byref(display))
        self.screen_size = (display.w or 1280, display.h or 1024)
        self.title, self.url = title, ""
        self.can_back = self.can_forward = False
        self.browser = None
        self.texture = self.popup_texture = None
        self.picture = (0, 0)
        self.popup_rect, self.popup_visible, self.popup_size = None, False, (0, 0)
        self.selected_text = ""
        self.drag_operation = types.DragOperationsMask.COPY
        self._drag_emulated = None
        self._drag_allowed = types.DragOperationsMask.COPY
        self._dirty = True
        self._cursors = {}
        self._wake_event = sdl2.SDL_RegisterEvents(1)
        self.quit = False
        self.on_ready = lambda: None
        # CEF
        self.app = cefweaver.CefApp()
        self.app.offscreen = True
        self.app.transparent = False
        if cache_path:
            self.app.set_cache_path(cache_path)
        for name, value in switches:
            self.app.add_command_line_switch(name, value)
        self.bridge = cefweaver.JavascriptBridge(self.app)
        self.pump = cefweaver.MessagePump(self.app, wake=self._wake)
        self.client = _Handlers(self)
        self.started = False
        self._closing = False
        self._update_size()
        sdl2.SDL_StartTextInput()

    # -- CEF -------------------------------------------------------------------------------------

    def _wake(self, delay):                             # any thread of CEF
        event = sdl2.SDL_Event()
        event.type = self._wake_event
        sdl2.SDL_PushEvent(ctypes.byref(event))

    def start(self, url):
        self.app.set_client(self.client)
        self.app.initialize(url)
        self.started = True

    def host(self, function):
        if self.browser is not None:
            return function(self.browser.get_host())

    def browser_ready(self):
        self.host(lambda h: h.set_focus(True))
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

    def close(self):
        """Close the browser; ``step()`` goes on until CEF is shut down."""
        if not self._closing:
            self._closing = True
            self.host(lambda h: h.close_browser(True))

    # -- the loop ------------------------------------------------------------------------------------

    def step(self, timeout_ms=None):
        """One turn: wait for an event (at most until CEF is due), handle all there are, run CEF, draw."""
        if timeout_ms is None:
            timeout_ms = int(self.pump.timeout() * 1000) if self.started else 50
        else:
            timeout_ms = min(timeout_ms, int(self.pump.timeout() * 1000)) if self.started else timeout_ms
        event = sdl2.SDL_Event()
        if sdl2.SDL_WaitEventTimeout(ctypes.byref(event), max(0, timeout_ms)):
            self._handle(event)
            while sdl2.SDL_PollEvent(ctypes.byref(event)):
                self._handle(event)
        if self.started:
            self.pump.run()
            if self._closing and not self.app.is_running:
                self.started = False
                self.app.shutdown()
        self._draw()

    def run(self):
        while not self.quit and not (self._closing and not self.started):
            self.step()
        self.destroy()

    def destroy(self):
        sdl2.SDL_StopTextInput()
        for texture in (self.texture, self.popup_texture):
            if texture:
                sdl2.SDL_DestroyTexture(texture)
        sdl2.SDL_DestroyRenderer(self.renderer)
        sdl2.SDL_DestroyWindow(self.window)
        sdl2.SDL_Quit()

    # -- events --------------------------------------------------------------------------------------

    def _update_size(self):
        w, h = ctypes.c_int(), ctypes.c_int()
        sdl2.SDL_GetWindowSize(self.window, ctypes.byref(w), ctypes.byref(h))
        ow, oh = ctypes.c_int(), ctypes.c_int()
        sdl2.SDL_GetRendererOutputSize(self.renderer, ctypes.byref(ow), ctypes.byref(oh))
        self.width, self.height = w.value, h.value
        self.scale = max(1, round(ow.value / max(1, w.value)))

    def _handle(self, event):
        kind = event.type
        if kind == sdl2.SDL_QUIT:
            self.close()
        elif kind == self._wake_event:
            pass                                         # step() runs the pump when it is due
        elif kind == sdl2.SDL_WINDOWEVENT:
            what = event.window.event
            if what in (sdl2.SDL_WINDOWEVENT_SIZE_CHANGED, sdl2.SDL_WINDOWEVENT_RESIZED):
                self._update_size()
                self.host(lambda h: h.was_resized())
                self._dirty = True
            elif what == sdl2.SDL_WINDOWEVENT_FOCUS_GAINED:
                self.host(lambda h: h.set_focus(True))
            elif what == sdl2.SDL_WINDOWEVENT_FOCUS_LOST:
                self.host(lambda h: h.set_focus(False))
            elif what in (sdl2.SDL_WINDOWEVENT_HIDDEN, sdl2.SDL_WINDOWEVENT_MINIMIZED):
                self.host(lambda h: h.was_hidden(True))
            elif what in (sdl2.SDL_WINDOWEVENT_SHOWN, sdl2.SDL_WINDOWEVENT_RESTORED):
                self.host(lambda h: h.was_hidden(False))
            elif what == sdl2.SDL_WINDOWEVENT_EXPOSED:
                self._dirty = True
            elif what == sdl2.SDL_WINDOWEVENT_LEAVE:
                self.host(lambda h: h.send_mouse_move_event(types.MouseEvent(0, 0, 0), True))
        elif kind == sdl2.SDL_MOUSEMOTION:
            self._motion(event.motion.x, event.motion.y)
        elif kind == sdl2.SDL_MOUSEBUTTONDOWN:
            self._button(event.button, False)
        elif kind == sdl2.SDL_MOUSEBUTTONUP:
            self._button(event.button, True)
        elif kind == sdl2.SDL_MOUSEWHEEL:
            x, y = ctypes.c_int(), ctypes.c_int()
            buttons = sdl2.SDL_GetMouseState(ctypes.byref(x), ctypes.byref(y))
            mouse = types.MouseEvent(x.value, y.value, modifier_flags(sdl2.SDL_GetModState(), buttons))
            sign = -1 if event.wheel.direction == sdl2.SDL_MOUSEWHEEL_FLIPPED else 1
            dx, dy = sign * event.wheel.x * 120, sign * event.wheel.y * 120
            self.host(lambda h: h.send_mouse_wheel_event(mouse, dx, dy))
        elif kind in (sdl2.SDL_KEYDOWN, sdl2.SDL_KEYUP):
            self._key(event.key, kind == sdl2.SDL_KEYUP)
        elif kind == sdl2.SDL_TEXTINPUT:
            self._text(event.text.text.decode("utf-8", "replace"))
        elif kind == sdl2.SDL_TEXTEDITING:
            text = event.edit.text.decode("utf-8", "replace")
            self.set_preedit(text, event.edit.start + event.edit.length if text else 0)
        elif kind == sdl2.SDL_DROPFILE:
            self._drop(files=[event.drop.file.decode("utf-8", "replace")])
        elif kind == sdl2.SDL_DROPTEXT:
            self._drop(text=event.drop.file.decode("utf-8", "replace"))

    def _mouse_event(self, x, y):
        buttons = sdl2.SDL_GetMouseState(None, None)
        return types.MouseEvent(int(x), int(y), modifier_flags(sdl2.SDL_GetModState(), buttons))

    def _motion(self, x, y):
        if self._drag_emulated is not None:
            mouse = types.MouseEvent(int(x), int(y), 0)
            self.host(lambda h: h.drag_target_drag_over(mouse, self._drag_allowed))
            return
        mouse = self._mouse_event(x, y)
        self.host(lambda h: h.send_mouse_move_event(mouse, False))

    def _button(self, button, release):
        if not release:
            self.host(lambda h: h.set_focus(True))      # a click gives the page the focus (IME and popups need it)
        mouse = self._mouse_event(button.x, button.y)
        kind = {sdl2.SDL_BUTTON_LEFT: types.MouseButtonType.LEFT, sdl2.SDL_BUTTON_MIDDLE: types.MouseButtonType.MIDDLE,
                sdl2.SDL_BUTTON_RIGHT: types.MouseButtonType.RIGHT}.get(button.button)
        if kind is None:
            return
        if release and self._drag_emulated is not None and button.button == sdl2.SDL_BUTTON_LEFT:
            self._end_drag(button.x, button.y)
            return
        self.host(lambda h: h.send_mouse_click_event(mouse, kind, release, max(1, button.clicks)))

    def _key(self, key, release):
        sym = key.keysym.sym
        mod = key.keysym.mod
        if not release and mod & sdl2.KMOD_ALT and sym in (sdl2.SDLK_LEFT, sdl2.SDLK_RIGHT):
            (self.go_back if sym == sdl2.SDLK_LEFT else self.go_forward)()
            return
        if not release and sym == sdl2.SDLK_F5:
            self.reload()
            return
        if mod & sdl2.KMOD_CTRL and sym in (sdl2.SDLK_c, sdl2.SDLK_x, sdl2.SDLK_v):
            # Done here: SDL answers selection requests in this thread, so CEF reading the selection of
            # this very process (or SDL reading CEF's) would wait for an answer nobody can give.
            if not release:
                self._clipboard_key(sym)
            return
        base = dict(modifiers=modifier_flags(mod), windows_key_code=windows_key_code(sym), native_key_code=key.keysym.scancode)
        if release:
            self.host(lambda h: h.send_key_event(types.KeyEvent(types.KeyEventType.KEYUP, **base)))
            return
        self.host(lambda h: h.send_key_event(types.KeyEvent(types.KeyEventType.RAWKEYDOWN, **base)))
        character = _CHAR_KEYS.get(sym)
        if character and not mod & (sdl2.KMOD_CTRL | sdl2.KMOD_ALT):
            self.host(lambda h: h.send_key_event(types.KeyEvent(
                types.KeyEventType.CHAR, character=character, unmodified_character=character, **base)))
        self._last_key = base

    def _text(self, text):
        """What SDL commits (typed letters, or text an input method composed)."""
        if not text:
            return
        if all(ord(c) < 0x80 for c in text) and len(text) == 1:
            base = getattr(self, "_last_key", dict(modifiers=0, windows_key_code=ord(text.upper()), native_key_code=0))
            self.host(lambda h: h.send_key_event(types.KeyEvent(
                types.KeyEventType.CHAR, character=ord(text), unmodified_character=ord(text), **base)))
        else:
            self.commit_text(text)

    def _clipboard_key(self, sym):
        if sym == sdl2.SDLK_v:
            text = sdl2.SDL_GetClipboardText()
            text = text.decode("utf-8", "replace") if text else ""
            if text:
                self.commit_text(text)
            return
        if self.selected_text:
            sdl2.SDL_SetClipboardText(self.selected_text.encode("utf-8"))
        if sym == sdl2.SDLK_x and self.browser is not None:
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

    # -- drag and drop -------------------------------------------------------------------------------

    def begin_drag(self, data, allowed_ops):
        """CEF's start_dragging(): SDL cannot start a drag, so the loop carries it out (see the Tk example)."""
        x, y = ctypes.c_int(), ctypes.c_int()
        sdl2.SDL_GetMouseState(ctypes.byref(x), ctypes.byref(y))
        self._drag_emulated, self._drag_allowed = data, allowed_ops
        mouse = types.MouseEvent(x.value, y.value, 0)
        self.host(lambda h: h.drag_target_drag_enter(data, mouse, allowed_ops))
        return True

    def _end_drag(self, x, y):
        mouse = types.MouseEvent(int(x), int(y), 0)
        inside = 0 <= x < self.width and 0 <= y < self.height
        operation = self.drag_operation if inside else types.DragOperationsMask.NONE
        if inside:
            self.host(lambda h: (h.drag_target_drag_over(mouse, self._drag_allowed), h.drag_target_drop(mouse)))
        else:
            self.host(lambda h: h.drag_target_drag_leave())
        self.host(lambda h: (h.drag_source_ended_at(int(x), int(y), operation), h.drag_source_system_drag_ended()))
        self._drag_emulated = None
        self.drag_operation = types.DragOperationsMask.COPY

    def _drop(self, text=None, files=None):
        """A drop from another program: SDL tells what was dropped, not where; the pointer is where."""
        data = cefweaver.DragData.create()
        if files:
            for name in files:
                data.add_file(name, os.path.basename(name))
        else:
            data.set_fragment_text(text)
        x, y = ctypes.c_int(), ctypes.c_int()
        sdl2.SDL_GetMouseState(ctypes.byref(x), ctypes.byref(y))
        mouse = types.MouseEvent(x.value, y.value, 0)
        ops = types.DragOperationsMask.COPY
        self.host(lambda h: (h.drag_target_drag_enter(data, mouse, ops), h.drag_target_drag_over(mouse, ops),
                             h.drag_target_drop(mouse)))

    # -- painting --------------------------------------------------------------------------------------

    def paint(self, type, dirty_rects, buffer, width, height):
        data = bytes(buffer)                             # the memoryview is valid during this call only
        pitch = width * 4
        if type == types.PaintElementType.POPUP:
            if self.popup_texture and self.popup_size != (width, height):
                sdl2.SDL_DestroyTexture(self.popup_texture)
                self.popup_texture = None
            if self.popup_texture is None:
                self.popup_texture = sdl2.SDL_CreateTexture(self.renderer, sdl2.SDL_PIXELFORMAT_ARGB8888,
                                                            sdl2.SDL_TEXTUREACCESS_STREAMING, width, height)
                self.popup_size = (width, height)
            sdl2.SDL_UpdateTexture(self.popup_texture, None, data, pitch)
            self._dirty = True
            return
        if self.texture is None or self.picture != (width, height):
            if self.texture:
                sdl2.SDL_DestroyTexture(self.texture)
            self.texture = sdl2.SDL_CreateTexture(self.renderer, sdl2.SDL_PIXELFORMAT_ARGB8888,
                                                  sdl2.SDL_TEXTUREACCESS_STREAMING, width, height)
            self.picture = (width, height)
            sdl2.SDL_UpdateTexture(self.texture, None, data, pitch)
        else:
            for rect in dirty_rects:                     # only what changed
                x0, y0 = max(0, rect.x), max(0, rect.y)
                w, h = min(width, rect.x + rect.width) - x0, min(height, rect.y + rect.height) - y0
                if w > 0 and h > 0:
                    area = sdl2.SDL_Rect(x0, y0, w, h)
                    sdl2.SDL_UpdateTexture(self.texture, ctypes.byref(area), data[y0 * pitch + x0 * 4:], pitch)
        self._pixels = data
        self._dirty = True

    def popup_show(self, show):
        self.popup_visible = show
        self._dirty = True

    def _draw(self):
        if not self._dirty:
            return
        self._dirty = False
        sdl2.SDL_SetRenderDrawColor(self.renderer, 255, 255, 255, 255)
        sdl2.SDL_RenderClear(self.renderer)
        if self.texture:
            sdl2.SDL_RenderCopy(self.renderer, self.texture, None, None)
        if self.popup_visible and self.popup_texture and self.popup_rect is not None:
            target = sdl2.SDL_Rect(self.popup_rect.x * self.scale, self.popup_rect.y * self.scale,
                                   self.popup_size[0], self.popup_size[1])
            sdl2.SDL_RenderCopy(self.renderer, self.popup_texture, None, ctypes.byref(target))
        sdl2.SDL_RenderPresent(self.renderer)

    def set_cursor(self, cursor):
        shape = _CURSORS.get(cursor, sdl2.SDL_SYSTEM_CURSOR_ARROW)
        if shape not in self._cursors:
            self._cursors[shape] = sdl2.SDL_CreateSystemCursor(shape)
        sdl2.SDL_SetCursor(self._cursors[shape])

    def snapshot(self, path):
        if not getattr(self, "_pixels", None):
            return False
        width, height = self.picture
        surface = sdl2.SDL_CreateRGBSurfaceWithFormatFrom(self._pixels, width, height, 32, width * 4, sdl2.SDL_PIXELFORMAT_ARGB8888)
        result = sdlimage.IMG_SavePNG(surface, path.encode("utf-8"))
        sdl2.SDL_FreeSurface(surface)
        return result == 0
