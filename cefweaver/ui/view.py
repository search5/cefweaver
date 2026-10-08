"""``BrowserView``: one offscreen browser and the rules of showing it in a toolkit.

A toolkit widget owns a ``BrowserView(adapter)``, passes what the user does to the input methods
(``mouse_move``, ``mouse_button``, ``key``, ``text`` and so on) and draws what the adapter's ``present()``
gets. Everything CEF-specific that the toolkits of ``examples/`` had in common is here: the handlers, the
event records, the click count, the composition of an input method, the clipboard keys and the drag and
drop sequence. See ``adapter.py`` for what the toolkit supplies.

All of it runs in the main thread of the toolkit (CEF is driven by ``Session`` from the toolkit's loop).
"""

import os
import time

import cefweaver
from cefweaver import types

from . import keys
from .adapter import DragPayload, Frame
from .picture import PictureStore

_NOTHING = (0xFFFFFFFF, 0xFFFFFFFF)         # CefRange::kInvalid: the whole text, or no replacement
_CHAR_OF_KEY = {keys.VK_RETURN: 13, keys.VK_TAB: 9, keys.VK_BACK: 8}
_BUTTONS = {"left": types.MouseButtonType.LEFT, "middle": types.MouseButtonType.MIDDLE,
            "right": types.MouseButtonType.RIGHT}
_DROP_WAIT = 0.5                            # seconds: how long a drop waits for CEF's answer to dragover
_CLICK_TIME, _CLICK_DISTANCE = 0.4, 4


class BrowserView:
    """The browser in a toolkit view.

    Set the callables ``on_title(title)``, ``on_address(url)``, ``on_loading(loading, can_back, can_forward)``
    and ``on_ready()`` (the browser exists: load a page) as needed. ``client`` is what ``Session.start`` gives
    to CEF.
    """

    def __init__(self, adapter):
        self.adapter = adapter
        self.client = _Handlers(self)
        self.browser = None
        self.picture_size = (0, 0)
        self.store = PictureStore()                     # the pixels of the view and of the popup, kept for snapshots and for adapters
        self.popup_visible = False
        self.popup_rect = None
        self.selected_text = ""
        self.drag_operation = types.DragOperationsMask.COPY
        self.on_title = self.on_address = lambda value: None
        self.on_loading = lambda loading, can_back, can_forward: None
        self.on_ready = lambda: None
        self._clock = time.monotonic
        self._clicks = (float("-inf"), 0, 0, 0)         # time, x, y, count of the last press
        self._position = (0, 0)
        self._last_key = None
        self._emulated = None                           # the DragData of a drag the view carries itself
        self._emulated_ops = types.DragOperationsMask.COPY
        self._outgoing = None                           # the DragData of a drag the toolkit carries
        self._pending = None                            # (payload, allowed) of a drag that waits for the pointer to move
        self._entered = False                           # CEF was told that a drag entered
        self._leaving = False
        self._over_answered = False

    @property
    def capabilities(self):
        return frozenset(getattr(self.adapter, "capabilities", ()))

    # -- the browser -----------------------------------------------------------------------------

    def host(self, function):
        """Call ``function(browser host)`` if the browser exists."""
        if self.browser is not None:
            return function(self.browser.get_host())

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

    # -- state of the view -----------------------------------------------------------------------

    def snapshot(self, path):
        """Save the last picture of the view as a PNG file; False if CEF has not painted yet."""
        return self.store.save_png(path)

    def resized(self):
        """The view has another size (the adapter's ``view_size()`` tells which)."""
        self.host(lambda h: h.was_resized())

    def focus(self, focused):
        self.host(lambda h: h.set_focus(bool(focused)))

    def shown(self, visible):
        self.host(lambda h: h.was_hidden(not visible))

    # -- the mouse -------------------------------------------------------------------------------

    @property
    def dragging_out(self):
        """True while a drag that the page started goes on (CEF has been told, ``drag_out_finished`` is due)."""
        return self._outgoing is not None

    def mouse_move(self, x, y, mods, leave=False):
        self._position = (x, y)
        if self._pending is not None and mods & keys.LEFT_BUTTON:
            payload, allowed = self._pending
            self._pending = None
            self._start_outgoing(payload, allowed)      # the toolkit's drag runs from here, until it is over
            return
        if self._emulated is not None:
            mouse = types.MouseEvent(x, y, 0)
            self.host(lambda h: h.drag_target_drag_over(mouse, self._emulated_ops))
            return
        mouse = types.MouseEvent(x, y, mods)
        self.host(lambda h: h.send_mouse_move_event(mouse, bool(leave)))

    def mouse_button(self, x, y, button, pressed, mods, clicks=None):
        """``button``: ``"left"``, ``"middle"`` or ``"right"`` (others are ignored). ``clicks``: the toolkit's
        own count of clicks in a row; without it the view counts (within 0.4 s and 4 pixels, up to 3)."""
        kind = _BUTTONS.get(button)
        if kind is None:
            return
        self._position = (x, y)
        if self._pending is not None and not pressed:   # the button went up before the pointer moved
            self._pending = None
            self.drag_out_finished(x, y, types.DragOperationsMask.NONE)
            return
        if self._emulated is not None and button == "left" and not pressed:
            self._end_emulated(x, y)
            return
        if pressed:
            self.focus(True)                            # a click gives the page the focus
            self._count_click(x, y, clicks)
        elif clicks is not None:
            self._clicks = self._clicks[:3] + (clicks,)
        mouse = types.MouseEvent(x, y, mods)
        count = self._clicks[3] or 1
        self.host(lambda h: h.send_mouse_click_event(mouse, kind, not pressed, count))

    def _count_click(self, x, y, clicks):
        now = self._clock()
        last_time, last_x, last_y, count = self._clicks
        if clicks is None:
            near = abs(x - last_x) <= _CLICK_DISTANCE and abs(y - last_y) <= _CLICK_DISTANCE
            clicks = count + 1 if now - last_time < _CLICK_TIME and near and count < 3 else 1
        self._clicks = (now, x, y, clicks)

    def wheel(self, x, y, dx, dy, mods):
        """``dx`` and ``dy`` as CEF has them, 120 for a notch: a positive ``dy`` shows what is above the page."""
        mouse = types.MouseEvent(x, y, mods)
        self.host(lambda h: h.send_mouse_wheel_event(mouse, dx, dy))

    # -- the keyboard ------------------------------------------------------------------------------

    def key(self, down, windows_key_code, native_code, mods, char=None):
        """A key went down or up. ``char``: the character it types, if the toolkit tells it with the key.
        Returns True if the view used the key itself (the clipboard keys) and the toolkit should not go on."""
        if self._clipboard_key(down, windows_key_code, mods):
            return True
        base = dict(modifiers=mods, windows_key_code=windows_key_code, native_key_code=native_code)
        if not down:
            self.host(lambda h: h.send_key_event(types.KeyEvent(types.KeyEventType.KEYUP, **base)))
            return False
        self._last_key = base
        self.host(lambda h: h.send_key_event(types.KeyEvent(types.KeyEventType.RAWKEYDOWN, **base)))
        character = _CHAR_OF_KEY.get(windows_key_code) or (ord(char) if char else 0)
        if character and not mods & (keys.CONTROL | keys.ALT):
            self._char(character, base)
        return False

    def _char(self, character, base):
        self.host(lambda h: h.send_key_event(types.KeyEvent(
            types.KeyEventType.CHAR, character=character, unmodified_character=character, **base)))

    def text(self, text):
        """Text the toolkit commits (typed letters of a toolkit that gives them apart from the keys, or what
        an input method composed)."""
        if not text:
            return
        if len(text) == 1 and ord(text) < 0x80:
            base = self._last_key or dict(modifiers=0, windows_key_code=keys.vk_for_char(text), native_key_code=0)
            self._char(ord(text), base)
        else:
            self.commit_text(text)

    def commit_text(self, text):
        """Text an input method committed, always as such (``text()`` makes a key of a single ASCII letter).
        For a toolkit whose input method also handles the plain keys, like GTK."""
        if text:
            self.host(lambda h: h.ime_commit_text(text, cefweaver.Range(*_NOTHING), 0))

    def preedit(self, text, cursor):
        """The text an input method is composing; an empty one ends the composition."""
        if not text:
            self.host(lambda h: h.ime_cancel_composition())
            return
        underline = cefweaver.CompositionUnderline(cefweaver.Range(0, len(text)), 0xFF000000, 0, 0,
                                                   types.CompositionUnderlineStyle.SOLID)
        self.host(lambda h: h.ime_set_composition(text, [underline], cefweaver.Range(*_NOTHING),
                                                  cefweaver.Range(cursor, cursor)))

    def _clipboard_key(self, down, code, mods):
        """Ctrl+C, Ctrl+X and Ctrl+V with the toolkit's clipboard. CEF doing them would read the selection of
        this very process while the toolkit, in this thread, has to answer it: it hangs or comes back empty
        (Qt and Tk; GTK 3 could, hence the capability ``native_clipboard``)."""
        if code not in (ord("C"), ord("X"), ord("V")) or not mods & keys.CONTROL or mods & keys.ALT:
            return False
        if "native_clipboard" in self.capabilities or not (
                hasattr(self.adapter, "clipboard_get") and hasattr(self.adapter, "clipboard_set")):
            return False
        if not down:
            return True
        if code == ord("V"):
            self.text(self.adapter.clipboard_get() or "")
            return True
        if self.selected_text:
            self.adapter.clipboard_set(self.selected_text)
        if code == ord("X") and self.browser is not None:
            self.browser.get_main_frame().delete()
        return True

    # -- drag and drop: into the view ------------------------------------------------------------------

    @staticmethod
    def _drag_data(text=None, html=None, url=None, files=None):
        data = cefweaver.DragData.create()
        if text:
            data.set_fragment_text(text)
        if html:
            data.set_fragment_html(html)
        if url:
            data.set_link_url(url)
        for path in files or []:
            data.add_file(path, os.path.basename(path))
        return data

    def drag_enter(self, x, y, operations, text=None, html=None, url=None, files=None):
        """A drag from the toolkit entered the view, step by step (``drag_over``, ``drag_leave`` or
        ``drag_drop`` follow). Without data it is the drag of the page itself, over its own view; a toolkit
        that has the data only at the drop (wx) calls the steps without it and the view ignores them for a drag
        of another program, until ``drag_drop`` brings the data."""
        if self._outgoing is not None:
            data = self._outgoing
        elif text or html or url or files:
            data = self._drag_data(text, html, url, files)
        else:
            return
        self._entered = True
        self._leaving = False
        self.drag_operation = types.DragOperationsMask.COPY          # until CEF answers the dragover
        mouse = types.MouseEvent(x, y, 0)
        self.host(lambda h: h.drag_target_drag_enter(data, mouse, operations))

    def drag_over(self, x, y, operations):
        if not self._entered:
            return
        mouse = types.MouseEvent(x, y, 0)
        self.host(lambda h: h.drag_target_drag_over(mouse, operations))

    def drag_leave(self):
        """The drag left. Toolkits (GTK) say so just before a drop, so CEF is told after the next turn of the
        loop, if no ``drag_drop`` came."""
        if not self._entered:
            return
        self._leaving = True
        self.adapter.post(self._finish_leave)

    def _finish_leave(self):
        if self._leaving:
            self.host(lambda h: h.drag_target_drag_leave())
            self._entered = False
        self._leaving = False

    def drag_drop(self, x, y, operations, text=None, html=None, url=None, files=None):
        """The drop. If the drag was entered with its data, this ends it. Otherwise (data only now) it is a
        ``drop()`` with the data given here."""
        self._leaving = False
        if self._entered:
            self._entered = False
            mouse = types.MouseEvent(x, y, 0)
            self.host(lambda h: (h.drag_target_drag_over(mouse, operations), h.drag_target_drop(mouse)))
        elif text or html or url or files:
            self.drop(x, y, text=text, html=html, url=url, files=files)

    def drop(self, x, y, text=None, html=None, url=None, files=None):
        """A drop of a toolkit that tells only the drop itself, with its data: the view makes the whole drag
        of it. The drop waits for CEF's answer to the dragover, or the page would see a ``dragleave`` instead
        (observed with wx)."""
        data = self._drag_data(text, html, url, files)
        operations = types.DragOperationsMask.COPY
        mouse = types.MouseEvent(x, y, 0)
        self._over_answered = False
        self.host(lambda h: (h.drag_target_drag_enter(data, mouse, operations), h.drag_target_drag_over(mouse, operations)))
        self._drop_when_answered(mouse, self._clock() + _DROP_WAIT)

    def _drop_when_answered(self, mouse, deadline):
        if self._over_answered or self._clock() > deadline:
            self.host(lambda h: h.drag_target_drop(mouse))
        else:
            self.adapter.call_later(0.01, lambda: self._drop_when_answered(mouse, deadline))

    # -- drag and drop: out of the view ----------------------------------------------------------------

    def begin_drag(self, data, allowed, x=0, y=0):
        """CEF's ``start_dragging``: True if a drag is going on. ``x``, ``y``: where the page started it."""
        if "drag_out" not in self.capabilities:
            self._emulated, self._emulated_ops = data, allowed
            x, y = self._position
            mouse = types.MouseEvent(x, y, 0)
            self.host(lambda h: h.drag_target_drag_enter(data, mouse, allowed))
            return True
        ok, paths = data.get_file_paths() if data.is_file() else (False, [])
        payload = DragPayload(text=data.get_fragment_text(), html=data.get_fragment_html(),
                              url=data.get_link_url(), files=list(paths) if ok else [], x=x, y=y, raw=data)
        if not (payload.text or payload.html or payload.url or payload.files):
            return False
        self._outgoing = data
        how = getattr(self.adapter, "drag_start", "immediate")
        if how == "posted":                             # from the loop, not inside the callback of CEF
            self.adapter.post(lambda: self._start_outgoing(payload, allowed) if self._outgoing is data else None)
            return True
        if how == "on_motion":                          # with the next move of the pointer, button down
            self._pending = (payload, allowed)
            return True
        if not self.adapter.start_drag_out(payload, allowed):
            self._outgoing = None
            return False
        return True

    def _start_outgoing(self, payload, allowed):
        """Let the toolkit start the drag; CEF has been told it started, so a refusal is told as an end."""
        if not self.adapter.start_drag_out(payload, allowed):
            self.drag_out_finished(*self._position, types.DragOperationsMask.NONE)

    def drag_out_finished(self, x, y, operation):
        """The drag the toolkit started (``start_drag_out``) is over, where and with what result."""
        self._outgoing = None
        self._pending = None
        self.drag_operation = types.DragOperationsMask.COPY
        self.host(lambda h: (h.drag_source_ended_at(x, y, operation), h.drag_source_system_drag_ended()))

    def _end_emulated(self, x, y):
        width, height = self.adapter.view_size()
        inside = 0 <= x < width and 0 <= y < height
        mouse = types.MouseEvent(x, y, 0)
        operation = self.drag_operation if inside else types.DragOperationsMask.NONE
        if inside:
            self.host(lambda h: (h.drag_target_drag_over(mouse, self._emulated_ops), h.drag_target_drop(mouse)))
        else:
            self.host(lambda h: h.drag_target_drag_leave())
        self._emulated = None
        self.drag_operation = types.DragOperationsMask.COPY
        self.host(lambda h: (h.drag_source_ended_at(x, y, operation), h.drag_source_system_drag_ended()))


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
        width, height = self.v.adapter.view_size()
        return cefweaver.Rect(0, 0, max(1, width), max(1, height))

    def get_screen_info(self, browser):
        width, height = self.v.adapter.screen_size()
        rect = cefweaver.Rect(0, 0, width, height)
        return True, cefweaver.ScreenInfo(float(self.v.adapter.scale()), 24, 8, 0, rect, rect)

    def get_screen_point(self, browser, view_x, view_y):
        x, y = self.v.adapter.screen_origin()
        return True, x + view_x, y + view_y

    def on_paint(self, browser, type, dirty_rects, buffer, width, height):
        view = self.v
        if type == types.PaintElementType.POPUP:
            frame = Frame(Frame.POPUP, width, height, buffer, dirty_rects, view.popup_rect)
        else:
            view.picture_size = (width, height)
            frame = Frame(Frame.VIEW, width, height, buffer, dirty_rects)
        frame.change = view.store.apply(frame)
        view.adapter.present(frame)

    def on_popup_show(self, browser, show):
        self.v.popup_visible = show
        if not show:
            frame = Frame(Frame.POPUP_HIDDEN)
            frame.change = self.v.store.apply(frame)
            self.v.adapter.present(frame)

    def on_popup_size(self, browser, rect):
        self.v.popup_rect = rect

    def on_cursor_change(self, browser, cursor):
        if hasattr(self.v.adapter, "set_cursor"):
            self.v.adapter.set_cursor(cursor)
            return True
        return False

    def on_text_selection_changed(self, browser, selected_text, selected_range):
        self.v.selected_text = selected_text

    def on_ime_composition_range_changed(self, browser, selected_range, character_bounds):
        if character_bounds and hasattr(self.v.adapter, "set_ime_rect"):
            last = character_bounds[-1]
            self.v.adapter.set_ime_rect(last.x, last.y, last.width, last.height)

    def start_dragging(self, browser, drag_data, allowed_ops, x, y):
        return self.v.begin_drag(drag_data, allowed_ops, x, y)

    def update_drag_cursor(self, browser, operation):
        self.v.drag_operation = operation
        self.v._over_answered = True
        if hasattr(self.v.adapter, "drag_operation_changed"):
            self.v.adapter.drag_operation_changed(operation)


class _Life(cefweaver.LifeSpanHandler):
    def __init__(self, view):
        self.v = view

    def on_after_created(self, browser):
        self.v.browser = browser
        self.v.on_ready()

    def on_before_close(self, browser):
        self.v.browser = None


class _Display(cefweaver.DisplayHandler):
    def __init__(self, view):
        self.v = view

    def on_title_change(self, browser, title):
        self.v.on_title(title)

    def on_address_change(self, browser, frame, url):
        if frame.is_main():
            self.v.on_address(url)


class _Load(cefweaver.LoadHandler):
    def __init__(self, view):
        self.v = view

    def on_loading_state_change(self, browser, is_loading, can_go_back, can_go_forward):
        if not is_loading:
            # a page restored by "back" from the back-forward cache ignores size changes until CEF is
            # told that the screen information changed (wiki: F67)
            self.v.host(lambda h: h.notify_screen_info_changed())
        self.v.on_loading(is_loading, can_go_back, can_go_forward)
