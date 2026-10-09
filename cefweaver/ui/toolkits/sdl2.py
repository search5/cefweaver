"""An SDL2 window that shows a cefweaver offscreen browser (PySDL2), built on ``cefweaver.ui``.

SDL gives windows, events and textures but no widgets, so ``SdlBrowser`` is the toolkit side as a whole: the
adapter (size, place, drawing the frames to a texture, cursor, clipboard, candidate window) and the event
loop. ``step(timeout_ms)`` waits for an SDL event (or for the next timer), turns it into a call of
``BrowserView``, runs what ``post`` and ``call_later`` were given and draws what changed. CEF's request to
run (from any thread of CEF) comes through ``post``: a queue and an SDL user event pushed with
``SDL_PushEvent``, which is thread safe.

SDL tells the text an input method is composing (``SDL_TEXTEDITING``) and what it committed
(``SDL_TEXTINPUT``), so Hangul composition is real here. Drops of text and files from other programs
arrive (``SDL_DROPTEXT``, ``SDL_DROPFILE``); SDL cannot start a drag out of its window, so a drag inside the
page is carried out by the view.

Checked: Xvfb with SDL_VIDEODRIVER=x11 and xdotool: the 28 checks of examples/sdl2/smoke.py (PySDL2 0.9.17, SDL 2.32).
Not checked: drops of other programs (the checks feed SDL_DROPTEXT to the handler, no real XDND), a scale other than 1, a real input method.
"""

import collections
import ctypes
import heapq
import itertools
import os
import time
import warnings

warnings.filterwarnings("ignore", message="Using SDL2 binaries from pysdl2-dll")
os.environ.setdefault("SDL_VIDEODRIVER", "x11")                 # never the real Wayland session
os.environ.setdefault("SDL_HINT_RENDER_DRIVER", "software")

import sdl2                                                      # noqa: E402

from cefweaver import types, ui                                  # noqa: E402
from cefweaver.ui import audio, keys                              # noqa: E402

_KEYS = {
    sdl2.SDLK_BACKSPACE: keys.VK_BACK, sdl2.SDLK_TAB: keys.VK_TAB, sdl2.SDLK_RETURN: keys.VK_RETURN,
    sdl2.SDLK_KP_ENTER: keys.VK_RETURN, sdl2.SDLK_ESCAPE: keys.VK_ESCAPE, sdl2.SDLK_SPACE: keys.VK_SPACE,
    sdl2.SDLK_PAGEUP: keys.VK_PRIOR, sdl2.SDLK_PAGEDOWN: keys.VK_NEXT, sdl2.SDLK_END: keys.VK_END,
    sdl2.SDLK_HOME: keys.VK_HOME, sdl2.SDLK_LEFT: keys.VK_LEFT, sdl2.SDLK_UP: keys.VK_UP,
    sdl2.SDLK_RIGHT: keys.VK_RIGHT, sdl2.SDLK_DOWN: keys.VK_DOWN, sdl2.SDLK_INSERT: keys.VK_INSERT,
    sdl2.SDLK_DELETE: keys.VK_DELETE, sdl2.SDLK_LSHIFT: keys.VK_SHIFT, sdl2.SDLK_RSHIFT: keys.VK_SHIFT,
    sdl2.SDLK_LCTRL: keys.VK_CONTROL, sdl2.SDLK_RCTRL: keys.VK_CONTROL, sdl2.SDLK_LALT: keys.VK_ALT,
    sdl2.SDLK_RALT: keys.VK_ALT,
}
_CURSORS = {
    types.CursorType.POINTER: sdl2.SDL_SYSTEM_CURSOR_ARROW, types.CursorType.HAND: sdl2.SDL_SYSTEM_CURSOR_HAND,
    types.CursorType.IBEAM: sdl2.SDL_SYSTEM_CURSOR_IBEAM, types.CursorType.CROSS: sdl2.SDL_SYSTEM_CURSOR_CROSSHAIR,
    types.CursorType.WAIT: sdl2.SDL_SYSTEM_CURSOR_WAIT, types.CursorType.MOVE: sdl2.SDL_SYSTEM_CURSOR_SIZEALL,
    types.CursorType.NOTALLOWED: sdl2.SDL_SYSTEM_CURSOR_NO, types.CursorType.NODROP: sdl2.SDL_SYSTEM_CURSOR_NO,
    types.CursorType.COLUMNRESIZE: sdl2.SDL_SYSTEM_CURSOR_SIZEWE, types.CursorType.ROWRESIZE: sdl2.SDL_SYSTEM_CURSOR_SIZENS,
    types.CursorType.EASTWESTRESIZE: sdl2.SDL_SYSTEM_CURSOR_SIZEWE, types.CursorType.NORTHSOUTHRESIZE: sdl2.SDL_SYSTEM_CURSOR_SIZENS,
}


_KEYTABLE = ui.KeyTable(_KEYS, function=ui.function_range(sdl2.SDLK_F1),
                        char=lambda sym: chr(sym) if 0x20 <= sym < 0x7F else None)
_MODIFIERS = ui.MaskModifiers(shift=sdl2.KMOD_SHIFT, control=sdl2.KMOD_CTRL, alt=sdl2.KMOD_ALT,
                              left=sdl2.SDL_BUTTON_LMASK, middle=sdl2.SDL_BUTTON_MMASK, right=sdl2.SDL_BUTTON_RMASK)
_CURSOR_SHAPES = ui.CursorTable(_CURSORS, default=sdl2.SDL_SYSTEM_CURSOR_ARROW)


def windows_key_code(sym):
    return _KEYTABLE.code(sym)


def modifier_flags(mod, buttons=0):
    return _MODIFIERS.flags(mod, buttons)


class SdlSink:
    """An audio sink of SDL: the device is opened in queue mode (``SDL_QueueAudio``, no Python callback in SDL's audio
    thread), at most ``max_latency`` seconds are queued (older sound is dropped) and a little sound (``prebuffer``) is
    collected before it plays, and again after the queue ran empty. ``volume`` (0.0 to 1.0) is applied to the samples.
    ``stats()`` tells what happened."""

    def __init__(self, volume=1.0, max_latency=0.5, prebuffer=0.1):
        self.volume, self.max_latency, self.prebuffer = volume, max_latency, prebuffer
        self._device = 0
        self._rate = self._channels = 0
        self._playing = False
        self._counters = dict(written=0, dropped=0, underruns=0)

    def start(self, sample_rate, channels):
        self.stop()
        if sdl2.SDL_InitSubSystem(sdl2.SDL_INIT_AUDIO) != 0:
            raise RuntimeError("SDL audio: %s" % sdl2.SDL_GetError().decode())
        wanted = sdl2.SDL_AudioSpec(sample_rate, sdl2.AUDIO_F32SYS, channels, 1024)       # no callback: a queue
        obtained = sdl2.SDL_AudioSpec(0, 0, 0, 0)
        device = sdl2.SDL_OpenAudioDevice(None, 0, wanted, obtained, 0)           # 0: SDL converts to what the device has
        if device == 0:
            raise RuntimeError("no audio device: %s" % sdl2.SDL_GetError().decode())
        self._device, self._rate, self._channels, self._playing = device, sample_rate, channels, False

    def write(self, samples, frames):
        device = self._device
        if not device:
            return
        samples = audio.apply_volume(samples, self.volume)
        queued = sdl2.SDL_GetQueuedAudioSize(device)
        if self._playing and queued == 0:                                       # it ran empty: collect again
            sdl2.SDL_PauseAudioDevice(device, 1)
            self._playing = False
            self._counters["underruns"] += 1
        limit = int(self._rate * self.max_latency) * self._channels * 4
        if queued > limit:                                                      # the application cannot keep up
            sdl2.SDL_ClearQueuedAudio(device)
            self._counters["dropped"] += queued // (4 * self._channels)
            queued = 0
        sdl2.SDL_QueueAudio(device, samples, len(samples))
        self._counters["written"] += frames
        if not self._playing and queued + len(samples) >= int(self._rate * self.prebuffer) * self._channels * 4:
            sdl2.SDL_PauseAudioDevice(device, 0)
            self._playing = True

    def stop(self):
        device, self._device = self._device, 0
        if device:
            sdl2.SDL_CloseAudioDevice(device)
        self._playing = False

    def stats(self):
        queued = (sdl2.SDL_GetQueuedAudioSize(self._device) // (4 * self._channels)) if self._device else 0
        counters = dict(self._counters)
        counters["queued"] = queued
        counters["consumed"] = counters["written"] - counters["dropped"] - queued
        return counters


class _Timer:
    def __init__(self, function):
        self.function = function

    def cancel(self):
        self.function = None


class SdlBrowser(ui.BrowserWidget):
    """The window, the browser and the event loop. It is the ``ui.ToolkitAdapter`` of its own ``BrowserView``."""

    capabilities = frozenset()      # no drag source and no clipboard CEF could use: the view does both

    def __init__(self, switches=(), cache_path=None, width=900, height=640, title="cefweaver SDL2", audio=None):
        if sdl2.SDL_Init(sdl2.SDL_INIT_VIDEO) != 0:
            raise RuntimeError("SDL_Init: %s" % sdl2.SDL_GetError().decode())
        sdl2.SDL_SetHint(b"SDL_IME_SHOW_UI", b"1")
        self.window = sdl2.SDL_CreateWindow(title.encode("utf-8"), sdl2.SDL_WINDOWPOS_UNDEFINED, sdl2.SDL_WINDOWPOS_UNDEFINED,
                                            width, height, sdl2.SDL_WINDOW_SHOWN | sdl2.SDL_WINDOW_RESIZABLE | sdl2.SDL_WINDOW_ALLOW_HIGHDPI)
        self.renderer = sdl2.SDL_CreateRenderer(self.window, -1, sdl2.SDL_RENDERER_SOFTWARE)
        self.driver = sdl2.SDL_GetCurrentVideoDriver().decode()
        self.width, self.height = width, height
        self.scale_factor = 1
        display = sdl2.SDL_DisplayMode()
        sdl2.SDL_GetDesktopDisplayMode(0, ctypes.byref(display))
        self.screen = (display.w or 1280, display.h or 1024)
        self.title, self.url = title, ""
        self.can_back = self.can_forward = False
        self.texture = self.popup_texture = None
        self.picture = (0, 0)
        self.popup_size = (0, 0)
        self._dirty = True
        self._cursors = {}
        self._wake_event = sdl2.SDL_RegisterEvents(1)
        self._posted = collections.deque()
        self._timers = []
        self._sequence = itertools.count()
        self.quit = False
        self._closing = False
        # CEF
        self.attach_view(self, audio=audio)
        self.on_ready = lambda: None                    # set by the application: the browser exists, load a page
        self.session = ui.Session(self, switches, cache_path)
        self.app, self.bridge = self.session.app, self.session.bridge
        self._update_size()
        sdl2.SDL_StartTextInput()

    # -- the toolkit side of ui.ToolkitAdapter ---------------------------------------------------------

    def post(self, function):                           # any thread of CEF
        self._posted.append(function)
        event = sdl2.SDL_Event()
        event.type = self._wake_event
        sdl2.SDL_PushEvent(ctypes.byref(event))

    def call_later(self, seconds, function):
        timer = _Timer(function)
        heapq.heappush(self._timers, (time.monotonic() + seconds, next(self._sequence), timer))
        return timer

    def audio_sink(self):
        """``BrowserView(audio="auto")`` plays the sound of the page with the audio of SDL."""
        return SdlSink()

    def view_size(self):
        return self.width, self.height

    def scale(self):
        return float(self.scale_factor)

    def screen_origin(self):
        x, y = ctypes.c_int(), ctypes.c_int()
        sdl2.SDL_GetWindowPosition(self.window, ctypes.byref(x), ctypes.byref(y))
        return x.value, y.value

    def screen_size(self):
        return self.screen

    def present(self, frame):
        if frame.kind == ui.Frame.POPUP_HIDDEN:
            self.popup_texture = None
            self._dirty = True
            return
        data = bytes(frame.buffer)                       # the memoryview is valid during this call only
        width, height, pitch = frame.width, frame.height, frame.width * 4
        if frame.kind == ui.Frame.POPUP:
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
            for rect in frame.dirty_rects:               # only what changed
                x0, y0 = max(0, rect.x), max(0, rect.y)
                w, h = min(width, rect.x + rect.width) - x0, min(height, rect.y + rect.height) - y0
                if w > 0 and h > 0:
                    area = sdl2.SDL_Rect(x0, y0, w, h)
                    sdl2.SDL_UpdateTexture(self.texture, ctypes.byref(area), data[y0 * pitch + x0 * 4:], pitch)
        self._dirty = True

    def set_cursor(self, cursor):
        shape = _CURSOR_SHAPES.get(cursor)
        if shape not in self._cursors:
            self._cursors[shape] = sdl2.SDL_CreateSystemCursor(shape)
        sdl2.SDL_SetCursor(self._cursors[shape])

    def set_ime_rect(self, x, y, width, height):         # where the candidate window goes
        rect = sdl2.SDL_Rect(x, y, width, height)
        sdl2.SDL_SetTextInputRect(ctypes.byref(rect))

    def clipboard_get(self):
        text = sdl2.SDL_GetClipboardText()
        return text.decode("utf-8", "replace") if text else None

    def clipboard_set(self, text):
        sdl2.SDL_SetClipboardText(text.encode("utf-8"))

    # -- the application ---------------------------------------------------------------------------------

    @property
    def started(self):
        return self.session.started

    def browser_title(self, title):
        self.title = title or "cefweaver SDL2"
        sdl2.SDL_SetWindowTitle(self.window, self.title.encode("utf-8"))

    def browser_address(self, url):
        self.url = url

    def browser_loading(self, loading, can_back, can_forward):
        self.can_back, self.can_forward = can_back, can_forward

    def browser_ready(self):
        self.on_ready()

    def start(self, url):
        self.session.start(self.view, url)

    def close(self):
        """Close the browser and shut CEF down; ``step()`` goes on until that is done."""
        if not self._closing:
            self._closing = True
            self.session.shutdown()

    # -- the loop ------------------------------------------------------------------------------------

    def step(self, timeout_ms=None):
        """One turn: wait for an event (at most until the next timer), handle all there are, run what was
        posted and what is due, draw."""
        wait = 50 if timeout_ms is None else timeout_ms
        if self._timers:
            wait = min(wait, max(0, int((self._timers[0][0] - time.monotonic()) * 1000)))
        event = sdl2.SDL_Event()
        if not self._posted and sdl2.SDL_WaitEventTimeout(ctypes.byref(event), max(0, wait)):
            self._handle(event)
        while sdl2.SDL_PollEvent(ctypes.byref(event)):
            self._handle(event)
        while self._posted:
            self._posted.popleft()()
        now = time.monotonic()
        while self._timers and self._timers[0][0] <= now:
            timer = heapq.heappop(self._timers)[2]
            if timer.function is not None:
                timer.function()
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
        self.scale_factor = max(1, round(ow.value / max(1, w.value)))

    @staticmethod
    def _pointer():
        x, y = ctypes.c_int(), ctypes.c_int()
        buttons = sdl2.SDL_GetMouseState(ctypes.byref(x), ctypes.byref(y))
        return x.value, y.value, modifier_flags(sdl2.SDL_GetModState(), buttons)

    def _handle(self, event):
        kind = event.type
        view = self.view
        if kind == sdl2.SDL_QUIT:
            self.close()
        elif kind == self._wake_event:
            pass                                         # step() runs what was posted
        elif kind == sdl2.SDL_WINDOWEVENT:
            what = event.window.event
            if what in (sdl2.SDL_WINDOWEVENT_SIZE_CHANGED, sdl2.SDL_WINDOWEVENT_RESIZED):
                self._update_size()
                view.resized()
                self._dirty = True
            elif what == sdl2.SDL_WINDOWEVENT_FOCUS_GAINED:
                view.focus(True)
            elif what == sdl2.SDL_WINDOWEVENT_FOCUS_LOST:
                view.focus(False)
            elif what in (sdl2.SDL_WINDOWEVENT_HIDDEN, sdl2.SDL_WINDOWEVENT_MINIMIZED):
                view.shown(False)
            elif what in (sdl2.SDL_WINDOWEVENT_SHOWN, sdl2.SDL_WINDOWEVENT_RESTORED):
                view.shown(True)
            elif what == sdl2.SDL_WINDOWEVENT_EXPOSED:
                self._dirty = True
            elif what == sdl2.SDL_WINDOWEVENT_LEAVE:
                view.mouse_move(0, 0, 0, leave=True)
        elif kind == sdl2.SDL_MOUSEMOTION:
            view.mouse_move(event.motion.x, event.motion.y, self._pointer()[2])
        elif kind in (sdl2.SDL_MOUSEBUTTONDOWN, sdl2.SDL_MOUSEBUTTONUP):
            button = event.button
            name = {sdl2.SDL_BUTTON_LEFT: "left", sdl2.SDL_BUTTON_MIDDLE: "middle", sdl2.SDL_BUTTON_RIGHT: "right"}.get(button.button)
            view.mouse_button(button.x, button.y, name, kind == sdl2.SDL_MOUSEBUTTONDOWN, self._pointer()[2],
                              clicks=max(1, button.clicks))
        elif kind == sdl2.SDL_MOUSEWHEEL:
            x, y, mods = self._pointer()
            sign = -1 if event.wheel.direction == sdl2.SDL_MOUSEWHEEL_FLIPPED else 1
            view.wheel(x, y, sign * event.wheel.x * 120, sign * event.wheel.y * 120, mods)
        elif kind in (sdl2.SDL_KEYDOWN, sdl2.SDL_KEYUP):
            self._key(event.key, kind == sdl2.SDL_KEYDOWN)
        elif kind == sdl2.SDL_TEXTINPUT:
            view.text(event.text.text.decode("utf-8", "replace"))
        elif kind == sdl2.SDL_TEXTEDITING:
            text = event.edit.text.decode("utf-8", "replace")
            view.preedit(text, event.edit.start + event.edit.length if text else 0)
        elif kind == sdl2.SDL_DROPFILE:
            self.handle_drop(files=[event.drop.file.decode("utf-8", "replace")])
        elif kind == sdl2.SDL_DROPTEXT:
            self.handle_drop(text=event.drop.file.decode("utf-8", "replace"))

    def _key(self, key, down):
        sym, mod = key.keysym.sym, key.keysym.mod
        if down and mod & sdl2.KMOD_ALT and sym in (sdl2.SDLK_LEFT, sdl2.SDLK_RIGHT):
            (self.go_back if sym == sdl2.SDLK_LEFT else self.go_forward)()
            return
        if down and sym == sdl2.SDLK_F5:
            self.reload()
            return
        self.view.key(down, windows_key_code(sym), key.keysym.scancode, modifier_flags(mod))

    def handle_drop(self, text=None, files=None):
        """A drop from another program: SDL tells what was dropped, not where; the pointer is where."""
        x, y, _ = self._pointer()
        self.view.drop(x, y, text=text, files=files)

    # -- painting --------------------------------------------------------------------------------------

    def _draw(self):
        if not self._dirty:
            return
        self._dirty = False
        sdl2.SDL_SetRenderDrawColor(self.renderer, 255, 255, 255, 255)
        sdl2.SDL_RenderClear(self.renderer)
        if self.texture:
            sdl2.SDL_RenderCopy(self.renderer, self.texture, None, None)
        rect = self.view.popup_rect
        if self.view.popup_visible and self.popup_texture and rect is not None:
            target = sdl2.SDL_Rect(rect.x * self.scale_factor, rect.y * self.scale_factor,
                                   self.popup_size[0], self.popup_size[1])
            sdl2.SDL_RenderCopy(self.renderer, self.popup_texture, None, ctypes.byref(target))
        sdl2.SDL_RenderPresent(self.renderer)
