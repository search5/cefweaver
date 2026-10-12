"""One offscreen browser and the rules of showing it in a toolkit.

A toolkit widget owns a :class:`BrowserView`, passes what the user does to its input methods
(:meth:`~BrowserView.mouse_move`, :meth:`~BrowserView.mouse_button`, :meth:`~BrowserView.key`,
:meth:`~BrowserView.text` and so on) and draws what ``present()`` of the adapter receives. The adapter
interface is :class:`~cefweaver.ui.ToolkitAdapter`.

Note:
    Everything here runs in the main thread of the toolkit.
"""

import os
import sys
import time

import cefweaver
from cefweaver import types

from . import audio as _audio
from . import menu as _menu
from . import permissions as _permissions
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

    Set the callables ``on_title``, ``on_address``, ``on_loading`` and ``on_ready`` as needed. ``client`` is
    what :meth:`Session.start <cefweaver.ui.Session.start>` gives to CEF.

    Args:
        adapter (ToolkitAdapter): The adapter of the toolkit.
        audio (object, optional): ``None`` (CEF plays the sound, the default), a sink (an object with
            ``start``, ``write`` and ``stop`` methods), or ``"auto"``: the sink of ``adapter.audio_sink()``,
            else a pygame sink if pygame is installed, else ``None``.
        pygame_sink (callable, optional): Returns the sink that ``"auto"`` falls back to. Defaults to the
            pygame sink of :mod:`cefweaver.ui.audio`.
        media_permissions (callable, optional): The policy for requests of the microphone and the camera
            (see :mod:`cefweaver.ui.permissions`). Without one CEF refuses them. Set it before the session
            starts.

    Raises:
        TypeError: If ``audio`` is neither ``None``, ``"auto"`` nor a sink.

    Attributes:
        adapter (ToolkitAdapter): The adapter of the toolkit.
        client (cefweaver.Client): The client for CEF.
        browser (cefweaver.Browser): The browser; ``None`` until it is created and after it closed.
        media_permissions (callable): The policy for media requests, or ``None``.
        on_context_menu (callable): ``hook(info, items)``, called before the context menu is shown; return
            the items to show or ``None`` to show no menu (see :mod:`cefweaver.ui.menu`). ``None`` by default.
            The menu is shown only if the adapter has ``show_menu``.
        audio_sink (object): The sink in use, or ``None``. Set to ``None`` if the sink raised.
        audio_muted (bool): If true, the sound is not passed to the sink.
        on_audio_error (callable): Called with a message when the sink or the audio stream failed.
        on_title (callable): ``on_title(title)``, called when the title changes.
        on_address (callable): ``on_address(url)``, called when the address of the main frame changes.
        on_loading (callable): ``on_loading(loading, can_back, can_forward)``, called when the loading state
            changes.
        on_ready (callable): ``on_ready()``, called when the browser exists.
        picture_size (tuple): ``(width, height)`` in pixels of the last painted picture of the view.
        store: The store of the pixels of the view and of the popup, which backs :meth:`snapshot`.
        popup_visible (bool): Whether a popup is shown.
        popup_rect: The rectangle of the popup in view coordinates, or ``None``.
        selected_text (str): The text selected in the page.
        drag_operation: The :class:`~cefweaver.types.DragOperationsMask` that CEF last answered to a drag
            over the view; ``COPY`` otherwise.
    """

    def __init__(self, adapter, audio=None, pygame_sink=None, media_permissions=None):
        self.adapter = adapter
        self.media_permissions = media_permissions      # a policy (see ``permissions``), set before the session starts
        self.on_context_menu = None                     # hook(info, items) -> items or None (see ``menu``)
        self.audio_sink = self._choose_sink(adapter, audio, pygame_sink)
        self.audio_muted = False
        self.on_audio_error = lambda message: None
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
        self._down_chars = {}                      # macOS: the key up repeats the character of the key down
        self._emulated = None                           # the DragData of a drag the view carries itself
        self._emulated_ops = types.DragOperationsMask.COPY
        self._outgoing = None                           # the DragData of a drag the toolkit carries
        self._pending = None                            # (payload, allowed) of a drag that waits for the pointer to move
        self._entered = False                           # CEF was told that a drag entered
        self._leaving = False
        self._over_answered = False

    def _run_context_menu(self, params, model, callback, frame=None):
        """Show the menu with the toolkit and answer CEF with what the user picks (once)."""
        answered = []

        def answer(pick):
            if answered:
                return
            answered.append(True)
            if pick is None:
                callback.cancel()
            elif pick in actions:
                callback.cancel()                       # a command of the application, CEF does not know it
                try:
                    actions[pick]()
                except Exception:
                    _menu.report()
            elif pick in _menu.CLIPBOARD_COMMANDS and self._does_clipboard():
                callback.cancel()                       # the clipboard of CEF is not the one of the toolkit
                try:
                    self._clipboard_command(_menu.CLIPBOARD_COMMANDS[pick], info.selection_text, refocus=True)
                except Exception:
                    _menu.report()
            elif (pick in _menu.SPELLING_SUGGESTIONS or pick == _menu.ADD_TO_DICTIONARY) and self.browser is not None:
                callback.cancel()                       # CEF would do it as the page was when the menu opened
                try:
                    self._spelling_command(pick, info)
                except Exception:
                    _menu.report()
            elif pick in _menu.FRAME_COMMANDS and (frame or self.browser) is not None:
                callback.cancel()                       # CEF would do it as the page was when the menu opened
                try:
                    getattr(frame or self.browser.get_main_frame(), _menu.FRAME_COMMANDS[pick])()
                except Exception:
                    _menu.report()
            else:
                callback.continue_(pick, 0)
        actions = {}
        try:
            info = _menu.ContextMenuInfo(params)
            items = _menu.items_from_model(model)
            if self.on_context_menu is not None:
                items = self.on_context_menu(info, items)
            if items is None:
                answer(None)
                return True
            items = _menu.tidy(items)
            actions.update(_menu.give_ids(items))
            self.adapter.show_menu(items, params.get_x_coord(), params.get_y_coord(), answer)
        except Exception:
            answer(None)
            _menu.report()
        return True

    @staticmethod
    def _choose_sink(adapter, audio, pygame_sink):
        """``audio``: None (CEF plays the sound), a sink, or ``"auto"``: the sink of the toolkit adapter
        (``adapter.audio_sink()``), else pygame if it is installed, else None (CEF plays the sound)."""
        if audio is None:
            return None
        if isinstance(audio, str):
            if audio != "auto":
                raise TypeError('audio must be a sink, "auto" or None, not %r' % (audio,))
            make = getattr(adapter, "audio_sink", None)
            sink = make() if make is not None else None
            if sink is not None:
                return sink
            return (pygame_sink or _audio.pygame_sink)()
        if not _audio.is_sink(audio):
            raise TypeError("audio must be a sink (start, write, stop), 'auto' or None, not %r" % (audio,))
        return audio

    @property
    def capabilities(self):
        """The ``capabilities`` of the adapter as a frozenset; empty if the adapter has none."""
        return frozenset(getattr(self.adapter, "capabilities", ()))

    # -- the sound of the page -------------------------------------------------------------------

    def _sink_call(self, name, *args):
        sink = self.audio_sink
        if sink is None:
            return
        try:
            getattr(sink, name)(*args)
        except Exception as error:                          # a failing sink must not go on failing 40 times a second
            self.audio_sink = None
            try:
                sink.stop()
            except Exception:
                pass
            self.on_audio_error("%s: %s" % (type(error).__name__, error))

    def _audio_started(self, sample_rate, channels):
        self._sink_call("start", sample_rate, channels)

    def _audio_packet(self, planes):
        if self.audio_muted or self.audio_sink is None:
            return
        samples, frames = _audio.interleave(planes)
        self._sink_call("write", samples, frames)

    def _audio_stopped(self):
        self._sink_call("stop")

    def _audio_error(self, message):
        self._sink_call("stop")
        self.on_audio_error(message)

    # -- the browser -----------------------------------------------------------------------------

    def host(self, function):
        """Call a function with the browser host if the browser exists.

        Args:
            function (callable): Called with the :class:`~cefweaver.BrowserHost` of the browser.

        Returns:
            object: What ``function`` returns, or ``None`` if the browser does not exist.
        """
        if self.browser is not None:
            return function(self.browser.get_host())

    def load_url(self, url):
        """Load a URL in the main frame; do nothing if the browser does not exist.

        Args:
            url (str): The URL.
        """
        if self.browser is not None:
            self.browser.get_main_frame().load_url(url)

    def go_back(self):
        """Go back in the history; do nothing if the browser does not exist."""
        if self.browser is not None:
            self.browser.go_back()

    def go_forward(self):
        """Go forward in the history; do nothing if the browser does not exist."""
        if self.browser is not None:
            self.browser.go_forward()

    def reload(self):
        """Reload the page; do nothing if the browser does not exist."""
        if self.browser is not None:
            self.browser.reload()

    def close_browser(self):
        """Close the browser, forcing the close; do nothing if it does not exist."""
        self.host(lambda h: h.close_browser(True))

    # -- state of the view -----------------------------------------------------------------------

    def snapshot(self, path):
        """Save the last picture of the view as a PNG file.

        Args:
            path (str): The file to write.

        Returns:
            bool: ``False`` if CEF has not painted yet.
        """
        return self.store.save_png(path)

    def resized(self):
        """Tell CEF that the view has another size, which ``view_size()`` of the adapter returns."""
        self.host(lambda h: h.was_resized())

    def focus(self, focused):
        """Give the page the focus or take it away.

        Args:
            focused (bool): Whether the view has the focus.
        """
        self.host(lambda h: h.set_focus(bool(focused)))

    def shown(self, visible):
        """Tell CEF whether the view is visible.

        Args:
            visible (bool): Whether the view is shown.
        """
        self.host(lambda h: h.was_hidden(not visible))

    # -- the mouse -------------------------------------------------------------------------------

    @property
    def dragging_out(self):
        """Whether a drag that the page started is going on, so that :meth:`drag_out_finished` is due."""
        return self._outgoing is not None

    def mouse_move(self, x, y, mods, leave=False):
        """Pass a movement of the pointer.

        Args:
            x (int): X coordinate in the view.
            y (int): Y coordinate in the view.
            mods (int): The modifier and mouse button flags of :mod:`cefweaver.ui.keys`.
            leave (bool, optional): Whether the pointer left the view.
        """
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
        """Pass a press or a release of a mouse button.

        A press gives the page the focus.

        Args:
            x (int): X coordinate in the view.
            y (int): Y coordinate in the view.
            button (str): ``"left"``, ``"middle"`` or ``"right"``. Others are ignored.
            pressed (bool): True for a press, False for a release.
            mods (int): The modifier and mouse button flags of :mod:`cefweaver.ui.keys`.
            clicks (int, optional): The count of clicks in a row that the toolkit gives. Without it the view
                counts clicks within 0.4 s and 4 pixels of each other, up to 3.
        """
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
        """Pass a scroll of the wheel.

        Args:
            x (int): X coordinate in the view.
            y (int): Y coordinate in the view.
            dx (int): Horizontal delta as CEF takes it, 120 for a notch.
            dy (int): Vertical delta as CEF takes it, 120 for a notch. A positive ``dy`` shows what is above.
            mods (int): The modifier flags of :mod:`cefweaver.ui.keys`.
        """
        mouse = types.MouseEvent(x, y, mods)
        self.host(lambda h: h.send_mouse_wheel_event(mouse, dx, dy))

    # -- the keyboard ------------------------------------------------------------------------------

    def key(self, down, windows_key_code, native_code, mods, char=None):
        """Pass a key press or release.

        Args:
            down (bool): True for a press, False for a release.
            windows_key_code (int): The Windows virtual-key code (see :mod:`cefweaver.ui.keys`).
            native_code (int): The native key code of the platform.
            mods (int): The modifier flags of :mod:`cefweaver.ui.keys`.
            char (str, optional): The character the key types, if the toolkit gives it with the key.

        Returns:
            bool: True if the view used the key itself (a clipboard key, or Select All, Undo and Redo on
            macOS), in which case the toolkit should not handle it further.
        """
        if self._clipboard_key(down, windows_key_code, mods):
            return True
        base = dict(modifiers=mods, windows_key_code=windows_key_code, native_key_code=native_code)
        if not down:
            character = 0
            if keys.IS_MAC:                        # a key up without its character is taken for a key down
                base["native_key_code"] = keys.native_code_for_key_down(windows_key_code, native_code)
                character = (keys.MAC_KEY_CHARS.get(windows_key_code, 0)
                             or self._down_chars.pop(windows_key_code, 0))
            self.host(lambda h: h.send_key_event(types.KeyEvent(
                types.KeyEventType.KEYUP, character=character, unmodified_character=character, **base)))
            return False
        base["native_key_code"] = keys.native_code_for_key_down(windows_key_code, native_code)
        self._last_key = base
        self.host(lambda h: h.send_key_event(types.KeyEvent(types.KeyEventType.RAWKEYDOWN, **base)))
        character = _CHAR_OF_KEY.get(windows_key_code) or (ord(char) if char else 0)
        if character:
            self._down_chars[windows_key_code] = character
        if character and not mods & (keys.CONTROL | keys.ALT | (keys.COMMAND if keys.IS_MAC else 0)):
            self._char(character, base)
        return False

    def _char(self, character, base):
        if sys.platform == "win32":                # a Windows WM_CHAR carries the character where the key code goes (CEF: windows_key_code)
            base = dict(base, windows_key_code=character)
        self.host(lambda h: h.send_key_event(types.KeyEvent(
            types.KeyEventType.CHAR, character=character, unmodified_character=character, **base)))

    def text(self, text):
        """Pass text that the toolkit commits, apart from key events.

        A single ASCII character is sent as a typed character, anything else as committed text.

        Args:
            text (str): The text, such as typed letters or the result of an input method.
        """
        if not text:
            return
        if len(text) == 1 and ord(text) < 0x80:
            base = self._last_key or dict(modifiers=0, windows_key_code=keys.vk_for_char(text), native_key_code=0)
            self._char(ord(text), base)
        else:
            self.commit_text(text)

    def commit_text(self, text):
        """Pass text that an input method committed, always as committed text.

        Unlike :meth:`text`, a single ASCII character is not sent as a typed character. Use this for a toolkit
        whose input method also handles the plain keys.

        Args:
            text (str): The committed text. An empty string is ignored.
        """
        if text:
            self.host(lambda h: h.ime_commit_text(text, cefweaver.Range(*_NOTHING), 0))

    def preedit(self, text, cursor):
        """Set the text an input method is composing.

        Args:
            text (str): The composition text. An empty string cancels the composition.
            cursor (int): The cursor position in ``text``.
        """
        if not text:
            self.host(lambda h: h.ime_cancel_composition())
            return
        underline = cefweaver.CompositionUnderline(cefweaver.Range(0, len(text)), 0xFF000000, 0, 0,
                                                   types.CompositionUnderlineStyle.SOLID)
        self.host(lambda h: h.ime_set_composition(text, [underline], cefweaver.Range(*_NOTHING),
                                                  cefweaver.Range(cursor, cursor)))

    def _clipboard_key(self, down, code, mods):
        """Ctrl+C, Ctrl+X and Ctrl+V (Command on macOS) with the toolkit's clipboard. CEF doing them would read the selection of
        this very process while the toolkit, in this thread, has to answer it: it hangs or comes back empty
        (Qt and Tk; GTK 3 could, hence the capability ``native_clipboard``)."""
        if not mods & keys.shortcut_modifier() or mods & keys.ALT:
            return False
        if keys.IS_MAC and code in (ord("A"), ord("Z")):
            # No Edit menu in this process, so CEF has no key equivalent for them: run the command.
            if down:
                self._edit_command("select_all" if code == ord("A") else "redo" if mods & keys.SHIFT else "undo")
            return True
        if code not in (ord("C"), ord("X"), ord("V")):
            return False
        if not self._does_clipboard():
            return False
        if down:
            self._clipboard_command({ord("C"): "copy", ord("X"): "cut", ord("V"): "paste"}[code])
        return True

    def _edit_command(self, name):
        """A command of the focused frame (``select_all``, ``undo``, ``redo``)."""
        if self.browser is None:
            return
        frame = self.browser.get_focused_frame() or self.browser.get_main_frame()
        getattr(frame, name)()

    def _spelling_command(self, command_id, info):
        """A suggestion of the spell checker replaces the misspelled word; Add to dictionary adds it."""
        if command_id == _menu.ADD_TO_DICTIONARY:
            if info.misspelled_word:
                self.host(lambda h: h.add_word_to_dictionary(info.misspelled_word))
            return
        index = command_id - _menu.SPELLING_SUGGESTIONS.start
        if index < len(info.dictionary_suggestions):
            self.host(lambda h: h.replace_misspelling(info.dictionary_suggestions[index]))

    def _does_clipboard(self):
        """Does the view do the clipboard commands with the clipboard of the toolkit (else CEF does them)?"""
        return "native_clipboard" not in self.capabilities and hasattr(self.adapter, "clipboard_get") and hasattr(
            self.adapter, "clipboard_set")

    def _clipboard_command(self, command, selection=None, refocus=False):
        """``"copy"``, ``"cut"`` or ``"paste"`` with the clipboard of the toolkit (the keys and the context menu).
        ``selection``: the text to copy, else the selection that CEF told. ``refocus``: give the page the focus first
        (a menu of the toolkit took it, and CEF does not edit a page that has none: cut and paste)."""
        if refocus and command != "copy":
            self.focus(True)
        if command == "paste":
            self.text(self.adapter.clipboard_get() or "")
            return
        text = self.selected_text if selection is None else selection
        if text:
            self.adapter.clipboard_set(text)
        if command == "cut" and self.browser is not None:
            self.browser.get_main_frame().delete()

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
        """Report that a drag from the toolkit entered the view.

        :meth:`drag_over`, :meth:`drag_leave` or :meth:`drag_drop` follow. Without data it is taken as the
        drag of the page itself over its own view, if one is going on; otherwise the call is ignored, as are
        the following steps, until :meth:`drag_drop` brings the data.

        Args:
            x (int): X coordinate in the view.
            y (int): Y coordinate in the view.
            operations: The allowed :class:`~cefweaver.types.DragOperationsMask`.
            text (str, optional): Dragged text.
            html (str, optional): Dragged HTML fragment.
            url (str, optional): Dragged link URL.
            files (list, optional): Paths of dragged files.
        """
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
        """Report that a drag moved over the view; ignored unless :meth:`drag_enter` started one.

        Args:
            x (int): X coordinate in the view.
            y (int): Y coordinate in the view.
            operations: The allowed :class:`~cefweaver.types.DragOperationsMask`.
        """
        if not self._entered:
            return
        mouse = types.MouseEvent(x, y, 0)
        self.host(lambda h: h.drag_target_drag_over(mouse, operations))

    def drag_leave(self):
        """Report that the drag left the view.

        CEF is told after the next turn of the toolkit loop, and not at all if :meth:`drag_drop` came in
        between. Ignored unless :meth:`drag_enter` started a drag.
        """
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
        """Report the drop of a drag.

        If :meth:`drag_enter` started the drag, this ends it. Otherwise, if data is given, it acts as
        :meth:`drop`; without data it is ignored.

        Args:
            x (int): X coordinate in the view.
            y (int): Y coordinate in the view.
            operations: The allowed :class:`~cefweaver.types.DragOperationsMask`.
            text (str, optional): Dropped text.
            html (str, optional): Dropped HTML fragment.
            url (str, optional): Dropped link URL.
            files (list, optional): Paths of dropped files.
        """
        self._leaving = False
        if self._entered:
            self._entered = False
            mouse = types.MouseEvent(x, y, 0)
            self.host(lambda h: (h.drag_target_drag_over(mouse, operations), h.drag_target_drop(mouse)))
        elif text or html or url or files:
            self.drop(x, y, text=text, html=html, url=url, files=files)

    def drop(self, x, y, text=None, html=None, url=None, files=None):
        """Drop data into the view as a whole drag: enter, over and drop.

        For a toolkit that reports only the drop, with its data. The drop is sent when CEF has answered the
        drag over, or after 0.5 s.

        Args:
            x (int): X coordinate in the view.
            y (int): Y coordinate in the view.
            text (str, optional): Dropped text.
            html (str, optional): Dropped HTML fragment.
            url (str, optional): Dropped link URL.
            files (list, optional): Paths of dropped files.
        """
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
        """Start a drag that the page began; called for ``start_dragging`` of CEF.

        Without the capability ``"drag_out"`` the view carries the drag itself, inside the page. With it, the
        adapter's ``start_drag_out`` starts the drag, at the time given by the adapter's ``drag_start``.

        Args:
            data (cefweaver.DragData): The dragged data.
            allowed: The allowed :class:`~cefweaver.types.DragOperationsMask`.
            x (int, optional): X coordinate in the view where the page started the drag.
            y (int, optional): Y coordinate in the view where the page started the drag.

        Returns:
            bool: Whether a drag is going on.
        """
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
        """Report that the drag started by ``start_drag_out`` of the adapter is over.

        Args:
            x (int): X coordinate in the view where the drag ended.
            y (int): Y coordinate in the view where the drag ended.
            operation: The resulting :class:`~cefweaver.types.DragOperationsMask`; ``NONE`` if the drag was
                cancelled.
        """
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
        self.audio, self.view = _Audio(view), view
        self.permission = _Permission(view)
        self.context_menu = _ContextMenu(view)

    def get_render_handler(self):
        return self.render

    def get_audio_handler(self):
        return self.audio if self.view.audio_sink is not None else None     # without a sink CEF plays the sound

    def get_context_menu_handler(self):
        return self.context_menu if hasattr(self.view.adapter, "show_menu") else None    # else CEF shows no menu

    def get_permission_handler(self):
        return self.permission if self.view.media_permissions is not None else None   # without a policy CEF refuses

    def get_life_span_handler(self):
        return self.life

    def get_display_handler(self):
        return self.display

    def get_load_handler(self):
        return self.load


class _ContextMenu(cefweaver.ContextMenuHandler):
    def __init__(self, view):
        self.v = view

    def run_context_menu(self, browser, frame, params, model, callback):
        return self.v._run_context_menu(params, model, callback, frame)


class _Permission(cefweaver.PermissionHandler):
    def __init__(self, view):
        self.v = view

    def on_request_media_access_permission(self, browser, frame, requesting_origin, requested_permissions, callback):
        policy = self.v.media_permissions
        if policy is None:
            return False
        request = _permissions.MediaRequest(requesting_origin, requested_permissions, frame.is_main(), callback)
        _permissions.ask(policy, request)
        return True


class _Audio(cefweaver.AudioHandler):
    def __init__(self, view):
        self.v = view

    def on_audio_stream_started(self, browser, params, channels):
        self.v._audio_started(params.sample_rate, channels)

    def on_audio_stream_packet(self, browser, data, pts):
        self.v._audio_packet(data)

    def on_audio_stream_stopped(self, browser):
        self.v._audio_stopped()

    def on_audio_stream_error(self, browser, message):
        self.v._audio_error(message)


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
