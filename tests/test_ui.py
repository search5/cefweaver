"""Tests of cefweaver.ui: the toolkit-independent browser view and its adapter interface.

The first part uses a fake browser and a fake adapter (no CEF process): what a toolkit hands to the view
must come out as the right CEF calls. The second part runs a real browser with the headless adapter.
"""

import os
import subprocess
import sys
import textwrap
import unittest

import cefweaver
from cefweaver import types
from cefweaver import ui
from cefweaver.ui import keys


class FakeFrame:
    def __init__(self, calls):
        self.calls = calls

    def delete(self):
        self.calls.append(("frame.delete",))

    def undo(self):
        self.calls.append(("frame.undo",))

    def redo(self):
        self.calls.append(("frame.redo",))

    def select_all(self):
        self.calls.append(("frame.select_all",))

    def is_main(self):
        return True

    def load_url(self, url):
        self.calls.append(("load_url", url))


class FakeHost:
    def __init__(self, calls):
        self.calls = calls

    def __getattr__(self, name):
        def record(*args):
            self.calls.append((name,) + args)
        return record


class FakeBrowser:
    def __init__(self, calls):
        self.calls = calls
        self.host = FakeHost(calls)
        self.frame = FakeFrame(calls)

    def get_host(self):
        return self.host

    def get_main_frame(self):
        return self.frame

    def get_focused_frame(self):
        return self.frame

    def go_back(self):
        self.calls.append(("go_back",))

    def reload(self):
        self.calls.append(("reload",))


class FakeAdapter:
    """The required methods only; tests add the optional ones."""

    capabilities = frozenset()

    def __init__(self):
        self.size, self.factor, self.origin, self.screen = (400, 300), 1.0, (50, 60), (1280, 1024)
        self.frames, self.posted, self.later = [], [], []

    def view_size(self):
        return self.size

    def scale(self):
        return self.factor

    def screen_origin(self):
        return self.origin

    def screen_size(self):
        return self.screen

    def present(self, frame):
        self.frames.append(frame)

    def post(self, function):
        self.posted.append(function)

    def call_later(self, seconds, function):
        self.later.append((seconds, function))

    def run_posted(self):
        queue, self.posted = self.posted, []
        for function in queue:
            function()

    def run_later(self):
        queue, self.later = self.later, []
        for _, function in queue:
            function()


def make_view(adapter=None):
    adapter = adapter or FakeAdapter()
    calls = []
    view = ui.BrowserView(adapter)
    view.browser = FakeBrowser(calls)
    return view, adapter, calls


def named(calls, name):
    return [c[1:] for c in calls if c[0] == name]


class Mouse(unittest.TestCase):
    def test_a_move_gives_cef_the_position_and_the_modifiers(self):
        view, _, calls = make_view()
        view.mouse_move(10, 20, keys.SHIFT | keys.LEFT_BUTTON)
        self.assertEqual(named(calls, "send_mouse_move_event"), [(types.MouseEvent(10, 20, keys.SHIFT | keys.LEFT_BUTTON), False)])

    def test_leaving_the_view_is_a_move_with_the_leave_flag(self):
        view, _, calls = make_view()
        view.mouse_move(5, 6, 0, leave=True)
        self.assertEqual(named(calls, "send_mouse_move_event"), [(types.MouseEvent(5, 6, 0), True)])

    def test_clicks_in_a_row_near_each_other_are_counted(self):
        view, _, calls = make_view()
        for _ in range(4):
            view.mouse_button(10, 10, "left", True, 0)
            view.mouse_button(10, 10, "left", False, 0)
        counts = [c[3] for c in named(calls, "send_mouse_click_event") if c[2] is False]
        self.assertEqual(counts, [1, 2, 3, 1])      # a fourth click starts again
        releases = [c[3] for c in named(calls, "send_mouse_click_event") if c[2] is True]
        self.assertEqual(releases, [1, 2, 3, 1])

    def test_a_click_far_away_or_late_starts_the_count_again(self):
        view, _, calls = make_view()
        now = [0.0]
        view._clock = lambda: now[0]
        view.mouse_button(10, 10, "left", True, 0)
        now[0] = 0.1
        view.mouse_button(200, 10, "left", True, 0)      # far away
        now[0] = 5.0
        view.mouse_button(200, 10, "left", True, 0)      # late
        counts = [c[3] for c in named(calls, "send_mouse_click_event")]
        self.assertEqual(counts, [1, 1, 1])

    def test_the_toolkits_own_count_wins(self):
        view, _, calls = make_view()
        view.mouse_button(10, 10, "right", True, 0, clicks=2)
        self.assertEqual(named(calls, "send_mouse_click_event"), [(types.MouseEvent(10, 10, 0), types.MouseButtonType.RIGHT, False, 2)])

    def test_a_button_cef_does_not_know_is_ignored(self):
        view, _, calls = make_view()
        view.mouse_button(1, 1, "back", True, 0)
        self.assertEqual(named(calls, "send_mouse_click_event"), [])

    def test_the_wheel_gives_the_deltas(self):
        view, _, calls = make_view()
        view.wheel(3, 4, 0, -120, keys.CONTROL)
        self.assertEqual(named(calls, "send_mouse_wheel_event"), [(types.MouseEvent(3, 4, keys.CONTROL), 0, -120)])

    def test_nothing_happens_before_the_browser_exists(self):
        view = ui.BrowserView(FakeAdapter())
        view.mouse_move(1, 1, 0)
        view.mouse_button(1, 1, "left", True, 0)
        view.key(True, 65, 0, 0)
        view.focus(True)


class Keyboard(unittest.TestCase):
    def events(self, calls):
        return [(e.type, e.windows_key_code, e.character) for (e,) in named(calls, "send_key_event")]

    def test_a_key_is_a_raw_key_down_and_a_key_up(self):
        view, _, calls = make_view()
        view.key(True, keys.vk_for_char("a"), 38, 0)
        view.key(False, keys.vk_for_char("a"), 38, 0)
        self.assertEqual(self.events(calls), [(types.KeyEventType.RAWKEYDOWN, 65, 0), (types.KeyEventType.KEYUP, 65, 0)])

    def test_on_macos_an_editing_key_goes_with_its_native_code_and_its_key_up_with_its_character(self):
        saved = keys.IS_MAC
        keys.IS_MAC = True
        try:
            view, _, calls = make_view()
            view.key(True, keys.VK_BACK, 0, 0)
            view.key(False, keys.VK_BACK, 0, 0)
            events = [e for (e,) in named(calls, "send_key_event")]
            # (Backspace also has a char event, as everywhere)
            self.assertEqual([(e.type, e.native_key_code) for e in events],
                             [(types.KeyEventType.RAWKEYDOWN, 51), (types.KeyEventType.CHAR, 51),
                              (types.KeyEventType.KEYUP, 51)])
            self.assertEqual(events[-1].character, 127)           # a key up without it is taken for a key down
            self.assertEqual(events[-1].unmodified_character, 127)
            view, _, calls = make_view()
            view.key(True, keys.VK_LEFT, 77, 0)                   # the toolkit's own code wins
            view.key(False, keys.VK_LEFT, 77, 0)
            events = [e for (e,) in named(calls, "send_key_event")]
            self.assertEqual([e.native_key_code for e in events], [77, 77])
            self.assertEqual(events[1].character, 0xF702)
            view, _, calls = make_view()
            view.key(True, 66, 11, 0, char="b")                   # a letter: the character of the key down
            view.key(False, 66, 11, 0)
            self.assertEqual(named(calls, "send_key_event")[-1][0].character, ord("b"))
        finally:
            keys.IS_MAC = saved

    def test_elsewhere_the_key_events_are_the_toolkits(self):
        saved = keys.IS_MAC
        keys.IS_MAC = False
        try:
            view, _, calls = make_view()
            view.key(True, keys.VK_BACK, 22, 0)
            view.key(False, keys.VK_BACK, 22, 0)
            events = [e for (e,) in named(calls, "send_key_event")]
            self.assertEqual([e.native_key_code for e in events], [22, 22, 22])
            self.assertEqual(events[-1].character, 0)
        finally:
            keys.IS_MAC = saved

    def test_the_character_of_a_key_follows_as_a_char_event(self):
        view, _, calls = make_view()
        view.key(True, 65, 38, 0, char="a")
        events = named(calls, "send_key_event")
        self.assertEqual([e.type for (e,) in events], [types.KeyEventType.RAWKEYDOWN, types.KeyEventType.CHAR])
        self.assertEqual((events[1][0].character, events[1][0].unmodified_character), (ord("a"), ord("a")))

    def test_no_char_event_while_control_or_alt_is_held(self):
        view, _, calls = make_view()
        view.key(True, 65, 38, keys.CONTROL, char="a")
        view.key(True, 65, 38, keys.ALT, char="a")
        self.assertEqual([t for t, _, _ in self.events(calls)], [types.KeyEventType.RAWKEYDOWN] * 2)

    def test_enter_tab_and_backspace_always_get_their_char_event(self):
        view, _, calls = make_view()
        for code in (keys.VK_RETURN, keys.VK_TAB, keys.VK_BACK):
            view.key(True, code, 0, 0)
        self.assertEqual([c for t, _, c in self.events(calls) if t == types.KeyEventType.CHAR], [13, 9, 8])

    def test_typed_text_of_one_ascii_letter_is_a_char_event_of_the_last_key(self):
        view, _, calls = make_view()
        view.key(True, 66, 56, 0)
        view.text("b")
        char = named(calls, "send_key_event")[-1][0]
        self.assertEqual((char.type, char.windows_key_code, char.native_key_code, char.character),
                         (types.KeyEventType.CHAR, 66, 56, ord("b")))

    def test_other_text_is_committed_as_input_method_text(self):
        view, _, calls = make_view()
        view.text("한")
        view.text("ab")
        self.assertEqual([c[0] for c in named(calls, "ime_commit_text")], ["한", "ab"])
        self.assertEqual(named(calls, "ime_commit_text")[0][1], cefweaver.Range(0xFFFFFFFF, 0xFFFFFFFF))

    def test_text_of_an_input_method_is_committed_even_when_it_is_one_ascii_letter(self):
        view, _, calls = make_view()
        view.commit_text("a")
        self.assertEqual([c[0] for c in calls], ["ime_commit_text"])

    def test_a_preedit_is_a_composition_and_an_empty_one_cancels_it(self):
        view, _, calls = make_view()
        view.preedit("하", 1)
        view.preedit("", 0)
        composition = named(calls, "ime_set_composition")
        self.assertEqual(len(composition), 1)
        self.assertEqual((composition[0][0], composition[0][3]), ("하", cefweaver.Range(1, 1)))
        self.assertEqual(named(calls, "ime_cancel_composition"), [()])

    def test_the_focus_the_size_and_the_visibility_reach_the_host(self):
        view, _, calls = make_view()
        view.focus(True)
        view.resized()
        view.shown(False)
        self.assertEqual([c[0] for c in calls], ["set_focus", "was_resized", "was_hidden"])
        self.assertEqual(calls[2], ("was_hidden", True))


class Clipboard(unittest.TestCase):
    def setUp(self):
        # These are the Control shortcuts; Command ones are tested below
        self._is_mac = keys.IS_MAC
        keys.IS_MAC = False

    def tearDown(self):
        keys.IS_MAC = self._is_mac

    def adapter(self, native=False):
        adapter = FakeAdapter()
        adapter.stored = {"text": "from clipboard"}
        adapter.clipboard_get = lambda: adapter.stored["text"]
        adapter.clipboard_set = lambda text: adapter.stored.update(text=text)
        adapter.capabilities = frozenset({"native_clipboard"} if native else ())
        return adapter

    def test_on_macos_command_c_x_v_use_the_toolkits_clipboard_and_control_does_not(self):
        keys.IS_MAC = True
        adapter = self.adapter()
        view, _, calls = make_view(adapter)
        view.selected_text = "cut me"
        self.assertTrue(view.key(True, ord("C"), 0, keys.COMMAND))
        self.assertEqual(adapter.stored["text"], "cut me")
        self.assertTrue(view.key(False, ord("C"), 0, keys.COMMAND))          # the key up is swallowed too
        self.assertFalse(view.key(True, ord("C"), 0, keys.CONTROL))          # Control+C is a plain key there
        self.assertEqual(named(calls, "send_key_event")[0][0].modifiers, keys.CONTROL)

    def test_on_macos_command_a_and_z_run_the_frame_commands(self):
        keys.IS_MAC = True
        view, _, calls = make_view()
        self.assertTrue(view.key(True, ord("A"), 0, keys.COMMAND))
        self.assertTrue(view.key(True, ord("Z"), 0, keys.COMMAND))
        self.assertTrue(view.key(True, ord("Z"), 0, keys.COMMAND | keys.SHIFT))
        self.assertEqual([c[0] for c in calls], ["frame.select_all", "frame.undo", "frame.redo"])
        self.assertEqual(named(calls, "send_key_event"), [])                  # not sent as keys
        keys.IS_MAC = False
        view, _, calls = make_view()
        self.assertFalse(view.key(True, ord("A"), 0, keys.CONTROL))           # elsewhere CEF has them

    def test_on_macos_command_does_not_type_the_letter(self):
        keys.IS_MAC = True
        view, _, calls = make_view()
        view.key(True, ord("F"), 0, keys.COMMAND, char="f")
        self.assertEqual([e.type for (e,) in named(calls, "send_key_event")], [types.KeyEventType.RAWKEYDOWN])

    def test_control_c_copies_the_selection_into_the_toolkits_clipboard(self):
        view, adapter, calls = make_view(self.adapter())
        view.selected_text = "chosen"
        self.assertTrue(view.key(True, ord("C"), 0, keys.CONTROL))
        self.assertTrue(view.key(False, ord("C"), 0, keys.CONTROL))       # the release is consumed too
        self.assertEqual(adapter.stored["text"], "chosen")
        self.assertEqual(named(calls, "send_key_event"), [])

    def test_control_x_cuts_and_control_v_pastes(self):
        view, adapter, calls = make_view(self.adapter())
        view.selected_text = "cut me"
        view.key(True, ord("X"), 0, keys.CONTROL)
        self.assertEqual((adapter.stored["text"], named(calls, "frame.delete")), ("cut me", [()]))
        view.key(True, ord("V"), 0, keys.CONTROL)
        self.assertEqual(named(calls, "ime_commit_text")[0][0], "cut me")

    def test_with_a_native_clipboard_the_keys_go_to_cef(self):
        view, adapter, calls = make_view(self.adapter(native=True))
        self.assertFalse(view.key(True, ord("C"), 0, keys.CONTROL))
        self.assertEqual(len(named(calls, "send_key_event")), 1)

    def test_without_clipboard_methods_the_keys_go_to_cef(self):
        view, _, calls = make_view()
        self.assertFalse(view.key(True, ord("V"), 0, keys.CONTROL))
        self.assertEqual(len(named(calls, "send_key_event")), 1)

    def test_other_control_keys_are_not_touched(self):
        view, _, calls = make_view(self.adapter())
        self.assertFalse(view.key(True, ord("A"), 0, keys.CONTROL))
        self.assertFalse(view.key(True, ord("C"), 0, keys.CONTROL | keys.ALT))


class Rendering(unittest.TestCase):
    def test_cef_asks_the_adapter_for_the_size_the_scale_and_the_position(self):
        view, adapter, _ = make_view()
        adapter.size, adapter.factor = (640, 480), 2.0
        render = view.client.get_render_handler()
        self.assertEqual(render.get_view_rect(None), cefweaver.Rect(0, 0, 640, 480))
        ok, info = render.get_screen_info(None)
        self.assertTrue(ok)
        self.assertEqual((info.device_scale_factor, info.rect.width, info.rect.height), (2.0, 1280, 1024))
        self.assertEqual(render.get_screen_point(None, 5, 7), (True, 55, 67))

    def test_a_paint_is_presented_to_the_adapter(self):
        view, adapter, _ = make_view()
        rects = [cefweaver.Rect(0, 0, 2, 1)]
        view.client.get_render_handler().on_paint(None, types.PaintElementType.VIEW, rects, memoryview(b"\0" * 8), 2, 1)
        frame = adapter.frames[0]
        self.assertEqual((frame.kind, frame.width, frame.height, frame.dirty_rects), (ui.Frame.VIEW, 2, 1, rects))
        self.assertEqual(view.picture_size, (2, 1))

    def test_a_popup_comes_with_its_place_and_goes_away_when_cef_hides_it(self):
        view, adapter, _ = make_view()
        render = view.client.get_render_handler()
        render.on_popup_show(None, True)
        render.on_popup_size(None, cefweaver.Rect(10, 20, 30, 40))
        render.on_paint(None, types.PaintElementType.POPUP, [], memoryview(b"\0" * 16), 2, 2)
        popup = adapter.frames[-1]
        self.assertEqual((popup.kind, popup.rect), (ui.Frame.POPUP, cefweaver.Rect(10, 20, 30, 40)))
        self.assertTrue(view.popup_visible)
        render.on_popup_show(None, False)
        self.assertEqual(adapter.frames[-1].kind, ui.Frame.POPUP_HIDDEN)
        self.assertFalse(view.popup_visible)

    def test_the_cursor_is_the_adapters_when_it_has_one(self):
        view, adapter, _ = make_view()
        render = view.client.get_render_handler()
        self.assertFalse(render.on_cursor_change(None, types.CursorType.HAND))     # CEF sets its own
        shown = []
        adapter.set_cursor = shown.append
        self.assertTrue(render.on_cursor_change(None, types.CursorType.HAND))
        self.assertEqual(shown, [types.CursorType.HAND])

    def test_the_selected_text_is_remembered(self):
        view, _, _ = make_view()
        view.client.get_render_handler().on_text_selection_changed(None, "abc", cefweaver.Range(0, 3))
        self.assertEqual(view.selected_text, "abc")

    def test_the_candidate_window_follows_the_composition(self):
        view, adapter, _ = make_view()
        places = []
        adapter.set_ime_rect = lambda *rect: places.append(rect)
        view.client.get_render_handler().on_ime_composition_range_changed(None, cefweaver.Range(0, 1), [cefweaver.Rect(1, 2, 3, 4)])
        self.assertEqual(places, [(1, 2, 3, 4)])

    def test_title_address_and_loading_reach_the_callbacks(self):
        view, _, calls = make_view()
        seen = []
        view.on_title = lambda title: seen.append(("title", title))
        view.on_address = lambda url: seen.append(("address", url))
        view.on_loading = lambda *state: seen.append(("loading",) + state)
        view.client.get_display_handler().on_title_change(None, "hello")
        view.client.get_display_handler().on_address_change(None, FakeFrame(calls), "http://a/")
        view.client.get_load_handler().on_loading_state_change(None, False, True, False)
        self.assertEqual(seen, [("title", "hello"), ("address", "http://a/"), ("loading", False, True, False)])
        self.assertEqual(named(calls, "notify_screen_info_changed"), [()])    # a page from the back-forward cache

    def test_a_frame_that_is_not_the_main_frame_does_not_change_the_address(self):
        view, _, _ = make_view()
        seen = []
        view.on_address = seen.append
        sub = FakeFrame([])
        sub.is_main = lambda: False
        view.client.get_display_handler().on_address_change(None, sub, "http://sub/")
        self.assertEqual(seen, [])

    def test_the_view_is_ready_when_cef_made_the_browser(self):
        view = ui.BrowserView(FakeAdapter())
        ready = []
        view.on_ready = lambda: ready.append(True)
        browser = FakeBrowser([])
        view.client.get_life_span_handler().on_after_created(browser)
        self.assertEqual((view.browser, ready), (browser, [True]))
        view.client.get_life_span_handler().on_before_close(browser)
        self.assertIsNone(view.browser)


class DragOut(unittest.TestCase):
    def data(self, text="dragged", url="", files=None):
        data = cefweaver.DragData.create()
        if text:
            data.set_fragment_text(text)
        if url:
            data.set_link_url(url)
        for name in files or []:
            data.add_file(name, os.path.basename(name))
        return data

    def test_without_a_drag_source_the_view_carries_the_drag_itself(self):
        view, _, calls = make_view()
        view.mouse_move(10, 10, 0)
        copy = types.DragOperationsMask.COPY
        self.assertTrue(view.client.get_render_handler().start_dragging(None, self.data(), copy, 10, 10))
        self.assertEqual([c[0] for c in calls if c[0].startswith("drag_")], ["drag_target_drag_enter"])
        view.mouse_move(40, 50, 0)                       # no plain move reaches the page meanwhile
        self.assertEqual(named(calls, "drag_target_drag_over"), [(types.MouseEvent(40, 50, 0), copy)])
        self.assertEqual(named(calls, "send_mouse_move_event"), [(types.MouseEvent(10, 10, 0), False)])
        view.mouse_button(40, 50, "left", False, 0)
        self.assertEqual(named(calls, "drag_target_drop"), [(types.MouseEvent(40, 50, 0),)])
        ended = named(calls, "drag_source_ended_at")
        self.assertEqual(ended, [(40, 50, types.DragOperationsMask.COPY)])
        self.assertEqual(named(calls, "drag_source_system_drag_ended"), [()])
        view.mouse_move(1, 1, 0)                         # moves are plain again
        self.assertEqual(len(named(calls, "send_mouse_move_event")), 2)

    def test_releasing_outside_the_view_cancels_the_drag(self):
        view, adapter, calls = make_view()
        view.mouse_move(10, 10, 0)
        view.client.get_render_handler().start_dragging(None, self.data(), types.DragOperationsMask.COPY, 10, 10)
        view.mouse_button(-5, 500, "left", False, 0)
        self.assertEqual(named(calls, "drag_target_drop"), [])
        self.assertEqual(named(calls, "drag_target_drag_leave"), [()])
        self.assertEqual(named(calls, "drag_source_ended_at"), [(-5, 500, types.DragOperationsMask.NONE)])

    def test_what_cef_answers_to_the_drag_is_the_result_of_the_drop(self):
        view, _, calls = make_view()
        view.mouse_move(1, 1, 0)
        render = view.client.get_render_handler()
        render.start_dragging(None, self.data(), types.DragOperationsMask.EVERY, 1, 1)
        render.update_drag_cursor(None, types.DragOperationsMask.MOVE)
        view.mouse_button(2, 2, "left", False, 0)
        self.assertEqual(named(calls, "drag_source_ended_at"), [(2, 2, types.DragOperationsMask.MOVE)])

    def test_an_adapter_with_a_drag_source_gets_what_the_page_drags(self):
        adapter = FakeAdapter()
        adapter.capabilities = frozenset({"drag_out"})
        started = []
        adapter.start_drag_out = lambda payload, allowed: started.append((payload, allowed)) or True
        view, _, calls = make_view(adapter)
        data = self.data(text="t", url="http://x/", files=["/tmp/a.txt"])
        copy = types.DragOperationsMask.COPY
        self.assertTrue(view.client.get_render_handler().start_dragging(None, data, copy, 3, 4))
        payload, allowed = started[0]
        self.assertEqual((payload.text, payload.url, payload.files, allowed), ("t", "http://x/", ["/tmp/a.txt"], copy))
        self.assertEqual((payload.x, payload.y), (3, 4))                         # where the page started the drag
        self.assertEqual(named(calls, "drag_target_drag_enter"), [])            # the toolkit's drag, not ours
        view.drag_out_finished(7, 8, types.DragOperationsMask.COPY)
        self.assertEqual(named(calls, "drag_source_ended_at"), [(7, 8, types.DragOperationsMask.COPY)])
        self.assertEqual(named(calls, "drag_source_system_drag_ended"), [()])

    def test_a_drag_the_adapter_cannot_start_is_refused(self):
        adapter = FakeAdapter()
        adapter.capabilities = frozenset({"drag_out"})
        adapter.start_drag_out = lambda payload, allowed: False
        view, _, _ = make_view(adapter)
        self.assertFalse(view.client.get_render_handler().start_dragging(None, self.data(), 1, 0, 0))

    def test_a_drag_with_nothing_to_carry_is_refused(self):
        adapter = FakeAdapter()
        adapter.capabilities = frozenset({"drag_out"})
        adapter.start_drag_out = lambda payload, allowed: True
        view, _, _ = make_view(adapter)
        self.assertFalse(view.client.get_render_handler().start_dragging(None, self.data(text=""), 1, 0, 0))


class DragOutStrategies(unittest.TestCase):
    """How a toolkit lets a drag start: at once, from the event loop, or at the next pointer move with the button down."""

    def setup(self, how):
        adapter = FakeAdapter()
        adapter.capabilities = frozenset({"drag_out"})
        adapter.drag_start = how
        adapter.started = []
        adapter.result = True
        adapter.start_drag_out = lambda payload, allowed: adapter.started.append((payload, allowed)) or adapter.result
        view, _, calls = make_view(adapter)
        data = cefweaver.DragData.create()
        data.set_fragment_text("t")
        return view, adapter, calls, data

    def start(self, view, data):
        return view.client.get_render_handler().start_dragging(None, data, types.DragOperationsMask.COPY, 5, 6)

    def test_an_immediate_drag_starts_in_the_call(self):
        view, adapter, _, data = self.setup("immediate")
        self.assertTrue(self.start(view, data))
        self.assertEqual(len(adapter.started), 1)

    def test_a_posted_drag_starts_from_the_loop_and_is_answered_for_cef_at_once(self):
        view, adapter, calls, data = self.setup("posted")
        self.assertTrue(self.start(view, data))
        self.assertEqual(adapter.started, [])
        adapter.run_posted()
        self.assertEqual(len(adapter.started), 1)
        self.assertTrue(view.dragging_out)

    def test_a_posted_drag_that_cannot_start_is_ended_for_cef(self):
        view, adapter, calls, data = self.setup("posted")
        adapter.result = False
        self.start(view, data)
        adapter.run_posted()
        self.assertFalse(view.dragging_out)
        self.assertEqual(named(calls, "drag_source_ended_at")[0][2], types.DragOperationsMask.NONE)
        self.assertEqual(named(calls, "drag_source_system_drag_ended"), [()])

    def test_a_drag_on_motion_waits_for_the_pointer_to_move_with_the_button_down(self):
        view, adapter, calls, data = self.setup("on_motion")
        self.assertTrue(self.start(view, data))
        view.mouse_move(8, 8, 0)                         # no button: not yet
        self.assertEqual(adapter.started, [])
        view.mouse_move(9, 9, keys.LEFT_BUTTON)
        self.assertEqual(len(adapter.started), 1)
        self.assertEqual(named(calls, "send_mouse_move_event")[-1][0], types.MouseEvent(8, 8, 0))   # that move did not reach the page

    def test_a_drag_on_motion_is_ended_when_the_button_goes_up_first(self):
        view, adapter, calls, data = self.setup("on_motion")
        self.start(view, data)
        view.mouse_button(7, 7, "left", False, 0)
        self.assertEqual(adapter.started, [])
        self.assertFalse(view.dragging_out)
        self.assertEqual(named(calls, "drag_source_ended_at"), [(7, 7, types.DragOperationsMask.NONE)])
        self.assertEqual(named(calls, "drag_target_drop"), [])

    def test_the_view_knows_when_its_own_drag_is_going_on(self):
        view, adapter, calls, data = self.setup("immediate")
        self.assertFalse(view.dragging_out)
        self.start(view, data)
        self.assertTrue(view.dragging_out)
        view.drag_out_finished(1, 1, types.DragOperationsMask.COPY)
        self.assertFalse(view.dragging_out)


class DragInWithoutEarlyData(unittest.TestCase):
    """A toolkit that gives the data only at the drop (wx) calls the steps without data, then drag_drop with it."""

    ops = types.DragOperationsMask.COPY

    def test_the_steps_without_data_of_another_program_do_not_reach_cef(self):
        view, adapter, calls = make_view()
        view.drag_enter(1, 1, self.ops)
        view.drag_over(2, 2, self.ops)
        view.drag_leave()
        adapter.run_posted()
        self.assertEqual([c for c in calls if c[0].startswith("drag_target")], [])

    def test_a_drop_with_data_that_was_not_entered_is_a_one_shot_drop(self):
        view, adapter, calls = make_view()
        view.drag_enter(1, 1, self.ops)
        view.drag_drop(3, 3, self.ops, text="dropped")
        self.assertEqual([c[0] for c in calls if c[0].startswith("drag_target")], ["drag_target_drag_enter", "drag_target_drag_over"])
        view.client.get_render_handler().update_drag_cursor(None, self.ops)
        adapter.run_later()
        self.assertEqual(len(named(calls, "drag_target_drop")), 1)

    def test_the_own_drag_of_the_page_goes_step_by_step_without_data(self):
        adapter = FakeAdapter()
        adapter.capabilities = frozenset({"drag_out"})
        adapter.start_drag_out = lambda payload, allowed: True
        view, _, calls = make_view(adapter)
        data = cefweaver.DragData.create()
        data.set_fragment_text("own")
        view.client.get_render_handler().start_dragging(None, data, self.ops, 0, 0)
        view.drag_enter(1, 1, self.ops)
        view.drag_over(2, 2, self.ops)
        view.drag_drop(3, 3, self.ops)
        self.assertEqual([c[0] for c in calls if c[0].startswith("drag_target")],
                         ["drag_target_drag_enter", "drag_target_drag_over", "drag_target_drag_over", "drag_target_drop"])

    def test_after_a_drop_the_next_drag_starts_again(self):
        view, adapter, calls = make_view()
        view.drag_enter(0, 0, self.ops, text="a")
        view.drag_drop(1, 1, self.ops)
        view.drag_enter(0, 0, self.ops)                  # another program, no data yet
        view.drag_over(1, 1, self.ops)
        self.assertEqual(len(named(calls, "drag_target_drag_enter")), 1)
        self.assertEqual(len(named(calls, "drag_target_drag_over")), 1)    # only the one of the first drop


class DragIn(unittest.TestCase):
    ops = types.DragOperationsMask.COPY

    def test_the_steps_of_a_toolkit_drag_reach_cef_in_order(self):
        view, adapter, calls = make_view()
        view.drag_enter(5, 6, self.ops, text="hello")
        view.drag_over(7, 8, self.ops)
        view.drag_drop(7, 8, self.ops)
        self.assertEqual([c[0] for c in calls if c[0].startswith("drag_target")],
                         ["drag_target_drag_enter", "drag_target_drag_over", "drag_target_drag_over", "drag_target_drop"])
        data = named(calls, "drag_target_drag_enter")[0][0]
        self.assertEqual(data.get_fragment_text(), "hello")

    def test_files_html_and_links_become_drag_data(self):
        view, _, calls = make_view()
        view.drag_enter(0, 0, self.ops, files=["/tmp/x/a.txt"], html="<b>x</b>", url="http://l/")
        data = named(calls, "drag_target_drag_enter")[0][0]
        self.assertEqual((data.get_file_paths(), data.get_fragment_html(), data.get_link_url()),
                         ((True, ["/tmp/x/a.txt"]), "<b>x</b>", "http://l/"))

    def test_leaving_is_told_after_the_next_turn_so_that_a_drop_can_follow(self):
        view, adapter, calls = make_view()
        view.drag_enter(0, 0, self.ops, text="t")
        view.drag_leave()
        self.assertEqual(named(calls, "drag_target_drag_leave"), [])
        adapter.run_posted()
        self.assertEqual(named(calls, "drag_target_drag_leave"), [()])

    def test_a_drop_right_after_the_leave_is_a_drop(self):
        view, adapter, calls = make_view()
        view.drag_enter(0, 0, self.ops, text="t")
        view.drag_leave()
        view.drag_drop(1, 1, self.ops)
        adapter.run_posted()
        self.assertEqual(named(calls, "drag_target_drag_leave"), [])
        self.assertEqual(len(named(calls, "drag_target_drop")), 1)

    def test_a_one_shot_drop_waits_for_the_answer_to_dragover(self):
        view, adapter, calls = make_view()
        view.drop(9, 9, text="dropped")
        self.assertEqual([c[0] for c in calls if c[0].startswith("drag_target")], ["drag_target_drag_enter", "drag_target_drag_over"])
        adapter.run_later()                              # CEF has not answered yet
        self.assertEqual(named(calls, "drag_target_drop"), [])
        view.client.get_render_handler().update_drag_cursor(None, self.ops)
        adapter.run_later()
        self.assertEqual(named(calls, "drag_target_drop"), [(types.MouseEvent(9, 9, 0),)])

    def test_a_one_shot_drop_does_not_wait_for_ever(self):
        view, adapter, calls = make_view()
        now = [0.0]
        view._clock = lambda: now[0]
        view.drop(1, 1, text="x")
        now[0] = 10.0
        adapter.run_later()
        self.assertEqual(len(named(calls, "drag_target_drop")), 1)

    def test_a_new_drag_starts_with_the_copy_operation(self):
        view, _, _ = make_view()
        view.drag_operation = types.DragOperationsMask.MOVE         # what the last drag ended with
        view.drag_enter(0, 0, self.ops, text="t")
        self.assertEqual(view.drag_operation, types.DragOperationsMask.COPY)

    def test_the_operation_cef_answers_is_visible_to_the_adapter(self):
        view, adapter, _ = make_view()
        answers = []
        adapter.drag_operation_changed = answers.append
        view.client.get_render_handler().update_drag_cursor(None, types.DragOperationsMask.MOVE)
        self.assertEqual((view.drag_operation, answers), (types.DragOperationsMask.MOVE, [types.DragOperationsMask.MOVE]))

    def test_the_toolkit_drag_over_its_own_widget_uses_the_data_cef_knows(self):
        adapter = FakeAdapter()
        adapter.capabilities = frozenset({"drag_out"})
        adapter.start_drag_out = lambda payload, allowed: True
        view, _, calls = make_view(adapter)
        data = cefweaver.DragData.create()
        data.set_fragment_text("own")
        view.client.get_render_handler().start_dragging(None, data, self.ops, 0, 0)
        view.drag_enter(3, 3, self.ops)                  # the toolkit has no data to give: it is our own drag
        self.assertIs(named(calls, "drag_target_drag_enter")[0][0], data)


class Keys(unittest.TestCase):
    def test_virtual_key_codes_of_characters_and_function_keys(self):
        self.assertEqual((keys.vk_for_char("a"), keys.vk_for_char("A"), keys.vk_for_char("5")), (65, 65, 53))
        self.assertEqual((keys.vk_for_function(1), keys.vk_for_function(12)), (112, 123))
        self.assertEqual(keys.vk_for_char("한"), 0)      # no virtual key: the text comes by text()
        self.assertEqual((keys.VK_LEFT, keys.VK_DELETE), (37, 46))
        self.assertEqual(keys.VK_CAPITAL, 20)                       # Caps Lock

    def test_the_modifier_flags_are_the_event_flags_of_cef(self):
        self.assertEqual((keys.SHIFT, keys.CONTROL, keys.ALT), (types.EventFlags.SHIFT_DOWN, types.EventFlags.CONTROL_DOWN, types.EventFlags.ALT_DOWN))
        self.assertEqual((keys.LEFT_BUTTON, keys.MIDDLE_BUTTON, keys.RIGHT_BUTTON),
                         (types.EventFlags.LEFT_MOUSE_BUTTON, types.EventFlags.MIDDLE_MOUSE_BUTTON, types.EventFlags.RIGHT_MOUSE_BUTTON))


class Tables(unittest.TestCase):
    def test_a_key_table_gives_the_virtual_key_code_of_a_toolkit_key(self):
        table = ui.KeyTable({"Left": keys.VK_LEFT, "Return": keys.VK_RETURN},
                            function=lambda name: int(name[1:]) if name[0] == "F" and name[1:].isdigit() else None,
                            char=lambda name: name if len(name) == 1 else None)
        self.assertEqual(table.code("Left"), keys.VK_LEFT)       # a special key
        self.assertEqual(table.code("F5"), keys.vk_for_function(5))
        self.assertEqual((table.code("a"), table.code("5")), (65, 53))   # the key of a character
        self.assertEqual(table.code("Menu"), 0)                  # unknown
        self.assertEqual(table.code("F13"), 0)                   # not a function key CEF knows

    def test_a_key_table_can_give_the_code_point_of_a_letter_that_has_no_virtual_key(self):
        table = ui.KeyTable({}, char=lambda key: key, others_as_code_point=True)
        self.assertEqual((table.code("a"), table.code("한")), (65, ord("한")))
        self.assertEqual(ui.KeyTable({}, char=lambda key: key).code("한"), 0)

    def test_a_function_key_range_is_a_function(self):
        function = ui.function_range(100)                    # the key code of F1 in some toolkit
        self.assertEqual((function(100), function(111), function(99), function(112)), (1, 12, None, None))

    def test_modifiers_from_masks(self):
        table = ui.MaskModifiers(shift=1, control=4, alt=8, left=0x100, right=0x400)
        self.assertEqual(table.flags(1 | 4), keys.SHIFT | keys.CONTROL)
        self.assertEqual(table.flags(8 | 0x100 | 0x400), keys.ALT | keys.LEFT_BUTTON | keys.RIGHT_BUTTON)
        self.assertEqual(table.flags(0), 0)
        self.assertEqual(ui.MaskModifiers(shift=1).flags(4), 0)                       # a modifier the toolkit does not have

    def test_modifiers_and_buttons_from_two_sources(self):
        table = ui.MaskModifiers(shift=1, control=4, left=0x1)
        self.assertEqual(table.flags(4, buttons=0x1), keys.CONTROL | keys.LEFT_BUTTON)

    def test_modifiers_from_names(self):
        table = ui.NamedModifiers()
        self.assertEqual(table.flags(["ctrl", "shift"], buttons={"left"}), keys.CONTROL | keys.SHIFT | keys.LEFT_BUTTON)

    def test_modifiers_from_an_event(self):
        class Event:
            def ShiftDown(self): return True
            def ControlDown(self): return False
            def AltDown(self): return True
            def LeftIsDown(self): return False
            def MiddleIsDown(self): return True
            def RightIsDown(self): return False
        self.assertEqual(ui.EventModifiers().flags(Event()), keys.SHIFT | keys.ALT | keys.MIDDLE_BUTTON)

    def test_a_cursor_table_has_a_default(self):
        table = ui.CursorTable({types.CursorType.HAND: "hand2"}, default="arrow")
        self.assertEqual((table.get(types.CursorType.HAND), table.get(types.CursorType.WAIT)), ("hand2", "arrow"))


class WidgetBase(unittest.TestCase):
    """``ui.BrowserWidget``: what every toolkit widget of a browser does the same way."""

    def make(self):
        calls = []

        class Widget(ui.BrowserWidget):
            def __init__(self, adapter):
                self.attach_view(adapter)
                self.events = []

            def browser_title(self, title):
                self.events.append(("title", title))

            def browser_address(self, url):
                self.events.append(("address", url))

            def browser_loading(self, loading, back, forward):
                self.events.append(("loading", loading, back, forward))

            def browser_ready(self):
                self.events.append(("ready",))

        widget = Widget(FakeAdapter())
        widget.view.browser = FakeBrowser(calls)
        return widget, calls

    def test_the_widget_has_a_view_and_forwards_its_state(self):
        widget, _ = self.make()
        self.assertIsInstance(widget.view, ui.BrowserView)
        self.assertIs(widget.browser, widget.view.browser)
        self.assertFalse(widget.popup_visible)
        self.assertIsNone(widget.popup_rect)

    def test_navigation_and_text_go_to_the_view(self):
        widget, calls = self.make()
        widget.load_url("http://a/")
        widget.go_back()
        widget.reload()
        widget.commit_text("한")
        widget.set_preedit("하", 1)
        widget.close_browser()
        self.assertEqual([c[0] for c in calls], ["load_url", "go_back", "reload", "ime_commit_text", "ime_set_composition", "close_browser"])

    def test_the_notifications_of_the_view_call_the_hooks_of_the_widget(self):
        widget, calls = self.make()
        view = widget.view
        view.client.get_display_handler().on_title_change(None, "t")
        view.client.get_display_handler().on_address_change(None, FakeFrame(calls), "http://a/")
        view.client.get_load_handler().on_loading_state_change(None, True, False, False)
        view.client.get_life_span_handler().on_after_created(FakeBrowser(calls))
        self.assertEqual(widget.events, [("title", "t"), ("address", "http://a/"), ("loading", True, False, False), ("ready",)])

    def test_the_options_of_the_view_can_be_given_by_the_widget(self):
        sink = FakeSink()
        widget = ui.BrowserWidget()
        view = widget.attach_view(FakeAdapter(), audio=sink)
        self.assertIs(view.audio_sink, sink)

    def test_a_widget_without_hooks_works_too(self):
        class Plain(ui.BrowserWidget):
            def __init__(self):
                self.attach_view(FakeAdapter())
        widget = Plain()
        widget.view.client.get_display_handler().on_title_change(None, "t")      # nothing to call: no error
        widget.view.client.get_life_span_handler().on_after_created(FakeBrowser([]))


class SessionTargets(unittest.TestCase):
    def test_a_session_starts_a_view_or_a_widget_of_a_view(self):
        view = ui.BrowserView(FakeAdapter())

        class Widget(ui.BrowserWidget):
            def __init__(self):
                self.view = view
        self.assertIs(ui.session.view_of(view), view)
        self.assertIs(ui.session.view_of(Widget()), view)
        with self.assertRaises(TypeError):
            ui.session.view_of(object())


class AskingFrame:
    def __init__(self, main=True):
        self.main = main

    def is_main(self):
        return self.main


class FakeAnswer:
    """What CEF gives for a media access request: ``continue_(permissions)`` or ``cancel()``."""

    def __init__(self):
        self.calls = []

    def continue_(self, permissions):
        self.calls.append(("allow", int(permissions)))

    def cancel(self):
        self.calls.append(("deny",))


AUDIO = types.MediaAccessPermissionTypes.DEVICE_AUDIO_CAPTURE
VIDEO = types.MediaAccessPermissionTypes.DEVICE_VIDEO_CAPTURE
SCREEN = types.MediaAccessPermissionTypes.DESKTOP_VIDEO_CAPTURE


class MediaPermissions(unittest.TestCase):
    """The microphone and the camera: the application decides (``BrowserView(media_permissions=policy)``)."""

    def ask(self, policy, permissions=AUDIO, origin="https://example.org/", main=True):
        view = ui.BrowserView(FakeAdapter(), media_permissions=policy)
        handler = view.client.get_permission_handler()
        answer = FakeAnswer()
        handled = handler.on_request_media_access_permission(FakeBrowser([]), AskingFrame(main), origin, permissions, answer)
        return handled, answer.calls

    def test_without_a_policy_cef_keeps_its_own_answer(self):
        self.assertIsNone(ui.BrowserView(FakeAdapter()).client.get_permission_handler())

    def test_a_policy_is_told_who_asks_for_what(self):
        seen = []
        self.ask(lambda request: seen.append((request.origin, request.permissions, request.is_main_frame)),
                 AUDIO | VIDEO, "https://meet.test/", main=False)
        self.assertEqual(seen, [("https://meet.test/", AUDIO | VIDEO, False)])

    def test_allow_gives_what_was_asked(self):
        handled, calls = self.ask(lambda request: request.allow(), AUDIO | VIDEO)
        self.assertTrue(handled)
        self.assertEqual(calls, [("allow", int(AUDIO | VIDEO))])

    def test_allow_can_give_less_than_was_asked(self):
        _, calls = self.ask(lambda request: request.allow(AUDIO), AUDIO | VIDEO)
        self.assertEqual(calls, [("allow", int(AUDIO))])

    def test_allow_never_gives_more_than_was_asked(self):
        _, calls = self.ask(lambda request: request.allow(AUDIO | SCREEN), AUDIO)
        self.assertEqual(calls, [("allow", int(AUDIO))])

    def test_deny_refuses(self):
        handled, calls = self.ask(lambda request: request.deny())
        self.assertTrue(handled)
        self.assertEqual(calls, [("deny",)])

    def test_the_answer_may_come_later_for_instance_after_asking_the_user(self):
        held = []
        view = ui.BrowserView(FakeAdapter(), media_permissions=held.append)
        answer = FakeAnswer()
        view.client.get_permission_handler().on_request_media_access_permission(FakeBrowser([]), AskingFrame(), "https://a.test/", AUDIO, answer)
        self.assertEqual(answer.calls, [])                            # nothing yet: the page waits
        held[0].allow()
        held[0].deny()                                                # a second answer is ignored
        held[0].allow()
        self.assertEqual(answer.calls, [("allow", int(AUDIO))])

    def test_a_policy_that_fails_denies_and_the_error_is_reported(self):
        reported = []
        original, sys.excepthook = sys.excepthook, lambda *info: reported.append(info[1])
        try:
            def policy(request):
                raise ValueError("no")
            handled, calls = self.ask(policy)
        finally:
            sys.excepthook = original
        self.assertTrue(handled)
        self.assertEqual(calls, [("deny",)])
        self.assertEqual([str(error) for error in reported], ["no"])

    def test_allow_origins_gives_the_devices_to_the_listed_origins_only(self):
        policy = ui.permissions.allow_origins("https://meet.test", "http://localhost")
        self.assertEqual(self.ask(policy, AUDIO | VIDEO, "https://meet.test/")[1], [("allow", int(AUDIO | VIDEO))])
        self.assertEqual(self.ask(policy, AUDIO, "http://localhost/")[1], [("allow", int(AUDIO))])
        self.assertEqual(self.ask(policy, AUDIO, "https://evil.test/")[1], [("deny",)])
        self.assertEqual(self.ask(policy, AUDIO, "https://meet.test.evil.test/")[1], [("deny",)])

    def test_allow_origins_does_not_give_the_screen(self):
        policy = ui.permissions.allow_origins("https://meet.test")
        self.assertEqual(self.ask(policy, AUDIO | SCREEN, "https://meet.test/")[1], [("allow", int(AUDIO))])
        self.assertEqual(self.ask(policy, SCREEN, "https://meet.test/")[1], [("deny",)])


class FakeMenuModel:
    """The reading side of CEF's ``MenuModel``: rows of (type, id, label, enabled, checked, visible, submenu)."""

    def __init__(self, rows):
        self.rows = rows

    def get_count(self):
        return len(self.rows)

    def get_type_at(self, i):
        return self.rows[i][0]

    def get_command_id_at(self, i):
        return self.rows[i][1]

    def get_label_at(self, i):
        return self.rows[i][2]

    def is_enabled_at(self, i):
        return self.rows[i][3]

    def is_checked_at(self, i):
        return self.rows[i][4]

    def is_visible_at(self, i):
        return self.rows[i][5]

    def get_sub_menu_at(self, i):
        return self.rows[i][6]


COMMAND, CHECK, RADIO, SEPARATOR, SUBMENU = (types.MenuItemType.COMMAND, types.MenuItemType.CHECK, types.MenuItemType.RADIO,
                                             types.MenuItemType.SEPARATOR, types.MenuItemType.SUBMENU)


def row(kind, command_id, label="", enabled=True, checked=False, visible=True, sub=None):
    return (kind, command_id, label, enabled, checked, visible, sub)


class FakeMenuParams:
    def __init__(self, x=30, y=40, link="", selection="", editable=False, word="", suggestions=()):
        self.values = dict(x=x, y=y, link=link, selection=selection, editable=editable, word=word, suggestions=suggestions)

    def get_x_coord(self):
        return self.values["x"]

    def get_y_coord(self):
        return self.values["y"]

    def get_link_url(self):
        return self.values["link"]

    def get_source_url(self):
        return ""

    def get_page_url(self):
        return "https://example.org/"

    def get_selection_text(self):
        return self.values["selection"]

    def get_misspelled_word(self):
        return self.values.get("word", "")

    def get_dictionary_suggestions(self):
        suggestions = self.values.get("suggestions", [])
        return (bool(suggestions), list(suggestions))

    def is_editable(self):
        return self.values["editable"]


class MenuAnswer:
    def __init__(self):
        self.calls = []

    def continue_(self, command_id, flags):
        self.calls.append(("pick", command_id, flags))

    def cancel(self):
        self.calls.append(("cancel",))


class ContextMenuItems(unittest.TestCase):
    def test_the_model_becomes_a_list_of_items(self):
        sub = FakeMenuModel([row(COMMAND, 300, "Inner")])
        model = FakeMenuModel([row(COMMAND, 100, "&Back"), row(COMMAND, 101, "Forward", enabled=False), row(SEPARATOR, -1),
                               row(CHECK, 200, "Spell check", checked=True), row(RADIO, 201, "Left"), row(SUBMENU, 400, "More", sub=sub)])
        items = ui.menu.items_from_model(model)
        self.assertEqual([(i.kind, i.command_id, i.label, i.enabled, i.checked) for i in items],
                         [("command", 100, "Back", True, False), ("command", 101, "Forward", False, False), ("separator", None, "", False, False),
                          ("check", 200, "Spell check", True, True), ("radio", 201, "Left", True, False), ("submenu", 400, "More", True, False)])
        self.assertEqual([(i.kind, i.command_id, i.label) for i in items[-1].children], [("command", 300, "Inner")])

    def test_a_mnemonic_mark_is_dropped_and_a_double_one_is_an_ampersand(self):
        items = ui.menu.items_from_model(FakeMenuModel([row(COMMAND, 1, "&Save && close")]))
        self.assertEqual(items[0].label, "Save & close")

    def test_hidden_items_are_left_out_and_the_separators_are_tidied(self):
        model = FakeMenuModel([row(SEPARATOR, -1), row(COMMAND, 1, "A"), row(SEPARATOR, -1), row(COMMAND, 2, "Hidden", visible=False),
                               row(SEPARATOR, -1), row(COMMAND, 3, "B"), row(SEPARATOR, -1)])
        self.assertEqual([(i.kind, i.label) for i in ui.menu.items_from_model(model)], [("command", "A"), ("separator", ""), ("command", "B")])


class MenuAdapter(FakeAdapter):
    """An adapter that can show a menu: it records the request and the test answers through ``done``."""

    def __init__(self):
        super().__init__()
        self.menus = []

    def show_menu(self, items, x, y, done):
        self.menus.append((items, x, y, done))


class ContextMenuHandling(unittest.TestCase):
    MODEL = [row(COMMAND, 113, "&Copy"), row(SEPARATOR, -1), row(COMMAND, 117, "Select &all")]

    def setUp(self):
        self.adapter = MenuAdapter()
        self.view = ui.BrowserView(self.adapter)
        self.answer = MenuAnswer()

    def open(self, params=None, rows=None):
        handler = self.view.client.get_context_menu_handler()
        return handler.run_context_menu(FakeBrowser([]), None, params or FakeMenuParams(), FakeMenuModel(rows or self.MODEL), self.answer)

    def test_without_a_menu_in_the_toolkit_cef_keeps_its_own_way(self):
        self.assertIsNone(ui.BrowserView(FakeAdapter()).client.get_context_menu_handler())

    def test_the_toolkit_is_asked_to_show_the_menu_where_the_page_was_clicked(self):
        self.assertTrue(self.open(FakeMenuParams(x=12, y=34)))
        items, x, y, _ = self.adapter.menus[0]
        self.assertEqual((x, y), (12, 34))
        self.assertEqual([i.label for i in items if i.kind == "command"], ["Copy", "Select all"])
        self.assertEqual(self.answer.calls, [])                       # nothing is answered until the user picks

    def test_a_pick_goes_to_cef_as_a_command(self):
        self.open()
        self.adapter.menus[0][3](117)
        self.assertEqual(self.answer.calls, [("pick", 117, 0)])

    def test_leaving_the_menu_cancels_it(self):
        self.open()
        self.adapter.menus[0][3](None)
        self.assertEqual(self.answer.calls, [("cancel",)])

    def test_the_menu_is_answered_once(self):
        self.open()
        done = self.adapter.menus[0][3]
        done(113)
        done(None)
        done(117)
        self.assertEqual(self.answer.calls, [("pick", 113, 0)])

    def test_a_hook_sees_where_and_on_what_the_page_was_clicked(self):
        seen = []
        self.view.on_context_menu = lambda info, items: seen.append((info.x, info.y, info.link_url, info.selection_text, info.is_editable)) or items
        self.open(FakeMenuParams(link="https://a.test/", selection="chosen", editable=True))
        self.assertEqual(seen, [(30, 40, "https://a.test/", "chosen", True)])

    def test_a_hook_can_change_the_items(self):
        mine = []
        self.view.on_context_menu = lambda info, items: [i for i in items if i.command_id != 117] + [ui.menu.MenuItem("Mine", action=lambda: mine.append(1))]
        self.open()
        items = self.adapter.menus[0][0]
        self.assertEqual([i.label for i in items if i.kind == "command"], ["Copy", "Mine"])

    def test_a_hook_that_returns_none_shows_no_menu(self):
        self.view.on_context_menu = lambda info, items: None
        self.assertTrue(self.open())
        self.assertEqual(self.adapter.menus, [])
        self.assertEqual(self.answer.calls, [("cancel",)])

    def test_an_item_of_the_application_runs_its_action_and_cef_is_not_told_the_pick(self):
        mine = []
        item = ui.menu.MenuItem("Mine", action=lambda: mine.append("run"))
        self.view.on_context_menu = lambda info, items: items + [item]
        self.open()
        shown = self.adapter.menus[0][0][-1]
        self.adapter.menus[0][3](shown.command_id)
        self.assertEqual(mine, ["run"])
        self.assertEqual(self.answer.calls, [("cancel",)])

    def test_a_hook_that_fails_cancels_and_the_error_is_reported(self):
        reported = []
        original, sys.excepthook = sys.excepthook, lambda *info: reported.append(info[1])
        try:
            def hook(info, items):
                raise ValueError("no")
            self.view.on_context_menu = hook
            self.assertTrue(self.open())
        finally:
            sys.excepthook = original
        self.assertEqual(self.answer.calls, [("cancel",)])
        self.assertEqual([str(e) for e in reported], ["no"])

    def test_a_toolkit_that_fails_to_show_the_menu_cancels_and_the_error_is_reported(self):
        reported = []
        original, sys.excepthook = sys.excepthook, lambda *info: reported.append(info[1])
        self.adapter.show_menu = lambda *args: (_ for _ in ()).throw(RuntimeError("no menu"))
        try:
            self.assertTrue(self.open())
        finally:
            sys.excepthook = original
        self.assertEqual(self.answer.calls, [("cancel",)])
        self.assertEqual([str(e) for e in reported], ["no menu"])


class ContextMenuClipboard(unittest.TestCase):
    """Copy, Cut and Paste of the context menu go through the clipboard of the toolkit, as the keys do (the clipboard of
    CEF is another one where CEF runs on Wayland), and the other commands are CEF's."""
    ROWS = [row(COMMAND, 112, "Cut"), row(COMMAND, 113, "Copy"), row(COMMAND, 114, "Paste"), row(COMMAND, 115, "Paste as text"),
            row(COMMAND, 117, "Select all")]

    def start(self, native=False, clipboard=True):
        adapter = MenuAdapter()
        adapter.stored = {"text": "from clipboard"}
        if clipboard:
            adapter.clipboard_get = lambda: adapter.stored["text"]
            adapter.clipboard_set = lambda text: adapter.stored.update(text=text)
        adapter.capabilities = frozenset({"native_clipboard"} if native else ())
        self.view, self.adapter, self.calls = make_view(adapter)
        self.answer = MenuAnswer()

    def choose(self, command_id, selection="chosen"):
        handler = self.view.client.get_context_menu_handler()
        handler.run_context_menu(FakeBrowser([]), None, FakeMenuParams(selection=selection), FakeMenuModel(self.ROWS), self.answer)
        self.adapter.menus[0][3](command_id)

    def test_copy_puts_the_selection_into_the_clipboard_of_the_toolkit(self):
        self.start()
        self.choose(int(types.MenuId.COPY))
        self.assertEqual(self.adapter.stored["text"], "chosen")
        self.assertEqual(self.answer.calls, [("cancel",)])                 # CEF does not copy into its own clipboard

    def test_copy_without_a_selection_leaves_the_clipboard_alone(self):
        self.start()
        self.choose(int(types.MenuId.COPY), selection="")
        self.assertEqual(self.adapter.stored["text"], "from clipboard")
        self.assertEqual(self.answer.calls, [("cancel",)])

    def test_cut_copies_and_deletes_the_selection(self):
        self.start()
        self.choose(int(types.MenuId.CUT))
        self.assertEqual(self.adapter.stored["text"], "chosen")
        self.assertEqual(named(self.calls, "frame.delete"), [()])
        self.assertEqual(self.answer.calls, [("cancel",)])

    def test_paste_types_the_clipboard_of_the_toolkit(self):
        for command in (types.MenuId.PASTE, types.MenuId.PASTE_MATCH_STYLE):
            self.start()
            self.choose(int(command))
            self.assertEqual(named(self.calls, "ime_commit_text")[0][0], "from clipboard", command)
            self.assertEqual(self.answer.calls, [("cancel",)])

    def test_cut_and_paste_give_the_page_the_focus_first(self):
        # the menu of the toolkit took the focus; CEF does not edit a page that has none
        for command, then in ((types.MenuId.CUT, "frame.delete"), (types.MenuId.PASTE, "ime_commit_text"),
                              (types.MenuId.PASTE_MATCH_STYLE, "ime_commit_text")):
            self.start()
            self.choose(int(command))
            names = [call[0] for call in self.calls]
            self.assertIn(then, names, command)
            self.assertLess(names.index("set_focus"), names.index(then), command)
            self.assertEqual(named(self.calls, "set_focus")[0], (True,), command)

    def test_the_edit_commands_run_in_the_frame_not_through_cef(self):
        # CEF runs them as the page was when the menu opened: after the menu of the toolkit took the focus they do nothing
        for command, method in ((types.MenuId.UNDO, "frame.undo"), (types.MenuId.REDO, "frame.redo"),
                                (types.MenuId.DELETE, "frame.delete"), (types.MenuId.SELECT_ALL, "frame.select_all")):
            self.start()
            self.choose(int(command))
            self.assertEqual(named(self.calls, method), [()], command)
            self.assertEqual(self.answer.calls, [("cancel",)], command)

    def test_the_edit_commands_run_in_the_frame_that_was_clicked(self):
        self.start()
        clicked = FakeFrame(self.calls)
        handler = self.view.client.get_context_menu_handler()
        handler.run_context_menu(FakeBrowser([]), clicked, FakeMenuParams(), FakeMenuModel(self.ROWS), self.answer)
        clicked.calls = []
        self.adapter.menus[0][3](int(types.MenuId.SELECT_ALL))
        self.assertEqual(named(clicked.calls, "frame.select_all"), [()])

    def spelling(self, command_id):
        self.start()
        handler = self.view.client.get_context_menu_handler()
        params = FakeMenuParams(word="teh", suggestions=["the", "eh", "tech"])
        handler.run_context_menu(FakeBrowser([]), None, params, FakeMenuModel(self.ROWS), self.answer)
        self.adapter.menus[0][3](command_id)

    def test_a_suggestion_replaces_the_misspelled_word_through_the_host(self):
        # CEF would do it as the page was when the menu opened: after the menu of the toolkit took the focus, nothing
        for index, word in enumerate(["the", "eh", "tech"]):
            self.spelling(int(types.MenuId.SPELLCHECK_SUGGESTION_0) + index)
            self.assertEqual(named(self.calls, "replace_misspelling"), [(word,)])
            self.assertEqual(self.answer.calls, [("cancel",)])

    def test_add_to_dictionary_adds_the_misspelled_word_through_the_host(self):
        self.spelling(int(types.MenuId.ADD_TO_DICTIONARY))
        self.assertEqual(named(self.calls, "add_word_to_dictionary"), [("teh",)])
        self.assertEqual(self.answer.calls, [("cancel",)])

    def test_a_suggestion_that_is_not_there_does_nothing(self):
        self.spelling(int(types.MenuId.SPELLCHECK_SUGGESTION_4))
        self.assertEqual(named(self.calls, "replace_misspelling"), [])

    def test_copy_does_not_need_the_focus(self):
        self.start()
        self.choose(int(types.MenuId.COPY))
        self.assertEqual(named(self.calls, "set_focus"), [])

    def test_the_other_commands_are_cefs(self):
        self.start()
        self.choose(int(types.MenuId.RELOAD))
        self.assertEqual(self.answer.calls, [("pick", 102, 0)])
        self.assertEqual(self.adapter.stored["text"], "from clipboard")

    def test_with_a_native_clipboard_cef_does_them(self):
        self.start(native=True)
        self.choose(int(types.MenuId.COPY))
        self.assertEqual(self.answer.calls, [("pick", 113, 0)])

    def test_without_clipboard_methods_cef_does_them(self):
        self.start(clipboard=False)
        self.choose(int(types.MenuId.PASTE))
        self.assertEqual(self.answer.calls, [("pick", 114, 0)])


class OzonePlatform(unittest.TestCase):
    """An offscreen session lets CEF use Wayland when there is a Wayland compositor: on X11 (XWayland) the GPU process of
    CEF dies on some machines and the video does not play (the same Chrome plays), and offscreen Wayland works."""

    SOCKET = "/run/user/1000/wayland-0"

    def env(self, **given):
        return dict({"WAYLAND_DISPLAY": "wayland-0", "XDG_RUNTIME_DIR": "/run/user/1000"}, **given)

    def test_wayland_is_the_default_where_there_is_a_compositor(self):
        self.assertEqual(ui.session.default_ozone_platform(self.env(), "linux", lambda path: path == self.SOCKET), "wayland")

    def test_a_socket_given_by_its_full_path_counts_too(self):
        env = self.env(WAYLAND_DISPLAY="/tmp/compositor.sock")
        self.assertEqual(ui.session.default_ozone_platform(env, "linux", lambda path: path == "/tmp/compositor.sock"), "wayland")

    def test_there_is_no_default_without_a_compositor(self):
        for env in ({}, {"WAYLAND_DISPLAY": ""}, {"WAYLAND_DISPLAY": "wayland-0"}):      # none, empty, no runtime directory
            self.assertIsNone(ui.session.default_ozone_platform(env, "linux", lambda path: True), env)
        self.assertIsNone(ui.session.default_ozone_platform(self.env(), "linux", lambda path: False))   # a stale variable
        self.assertIsNone(ui.session.default_ozone_platform(self.env(), "win32", lambda path: True))

    def session(self, switches, platform="wayland"):
        original, ui.session.default_ozone_platform = ui.session.default_ozone_platform, lambda *a, **k: platform
        try:
            return ui.Session(FakeAdapter(), switches=switches)
        finally:
            ui.session.default_ozone_platform = original

    def test_the_session_adds_the_platform_when_the_application_gave_none(self):
        self.assertEqual(self.session([("disable-gpu", "")]).switches, [("disable-gpu", ""), ("ozone-platform", "wayland")])

    def test_the_session_follows_what_the_application_gave(self):
        for given in ([("ozone-platform", "x11")], [("--ozone-platform", "x11")], [("ozone-platform-hint", "auto")]):
            self.assertEqual(self.session(given).switches, given)

    def test_the_session_adds_nothing_where_there_is_no_default(self):
        self.assertEqual(self.session([("disable-gpu", "")], platform=None).switches, [("disable-gpu", "")])


def read_png(path):
    """(width, height, RGBA bytes) of a PNG written by cefweaver.ui (8 bit RGBA, no interlace)."""
    import struct
    import zlib
    with open(path, "rb") as f:
        data = f.read()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", data[:8]
    position, width, height, idat = 8, 0, 0, b""
    while position < len(data):
        (length,) = struct.unpack(">I", data[position:position + 4])
        kind, body = data[position + 4:position + 8], data[position + 8:position + 8 + length]
        if kind == b"IHDR":
            width, height = struct.unpack(">II", body[:8])
        elif kind == b"IDAT":
            idat += body
        position += 12 + length
    raw = zlib.decompress(idat)
    rows = [raw[y * (1 + width * 4) + 1:(y + 1) * (1 + width * 4)] for y in range(height)]
    return width, height, b"".join(rows)


class Snapshots(unittest.TestCase):
    def paint(self, view, pixels, width, height, rects=None):
        view.client.get_render_handler().on_paint(None, types.PaintElementType.VIEW,
                                                  rects if rects is not None else [cefweaver.Rect(0, 0, width, height)],
                                                  memoryview(bytes(pixels)), width, height)

    def test_a_png_is_written_without_a_toolkit(self):
        import tempfile
        path = os.path.join(tempfile.mkdtemp(), "x.png")
        ui.write_png(path, 2, 1, bytes([1, 2, 3, 255, 4, 5, 6, 128]))          # BGRA
        self.assertEqual(read_png(path), (2, 1, bytes([3, 2, 1, 255, 6, 5, 4, 128])))   # RGBA

    def test_the_view_keeps_the_last_picture_and_saves_it(self):
        import tempfile
        view, adapter, _ = make_view()
        path = os.path.join(tempfile.mkdtemp(), "shot.png")
        self.assertFalse(view.snapshot(path))                      # nothing painted yet
        self.paint(view, [10, 20, 30, 255] * 4, 2, 2)
        self.assertTrue(view.snapshot(path))
        self.assertEqual(read_png(path), (2, 2, bytes([30, 20, 10, 255] * 4)))

    def test_the_picture_follows_the_dirty_rows(self):
        import tempfile
        view, _, _ = make_view()
        self.paint(view, [0, 0, 0, 255] * 4, 2, 2)
        self.paint(view, [9, 9, 9, 255] * 4, 2, 2, rects=[cefweaver.Rect(0, 1, 2, 1)])
        path = os.path.join(tempfile.mkdtemp(), "shot.png")
        view.snapshot(path)
        self.assertEqual(read_png(path)[2], bytes([0, 0, 0, 255] * 2 + [9, 9, 9, 255] * 2))

    def test_the_frame_tells_the_adapter_what_changed(self):
        view, adapter, _ = make_view()
        self.paint(view, [0] * 16, 2, 2)
        self.paint(view, [1] * 16, 2, 2, rects=[cefweaver.Rect(0, 0, 1, 1)])
        self.assertEqual([f.change.kind for f in adapter.frames], [ui.PictureStore.NEW, ui.PictureStore.DIRTY])
        self.assertEqual(adapter.frames[1].change.rects, [cefweaver.Rect(0, 0, 1, 1)])
        render = view.client.get_render_handler()
        render.on_popup_show(None, True)
        render.on_popup_size(None, cefweaver.Rect(1, 1, 1, 1))
        render.on_paint(None, types.PaintElementType.POPUP, [], memoryview(bytes(4)), 1, 1)
        render.on_popup_show(None, False)
        self.assertEqual([f.change.kind for f in adapter.frames[2:]], [ui.PictureStore.POPUP, ui.PictureStore.POPUP_HIDDEN])
        self.assertEqual(view.store.popup_rect, cefweaver.Rect(1, 1, 1, 1))


class Pictures(unittest.TestCase):
    """``ui.PictureStore``: the pixels of the view and of the popup, kept between frames."""

    def frame(self, pixels, width, height, rects=None, kind=ui.Frame.VIEW, rect=None):
        return ui.Frame(kind, width, height, memoryview(bytes(pixels)), rects if rects is not None else [cefweaver.Rect(0, 0, width, height)], rect)

    def test_the_first_frame_is_stored_whole_and_is_new(self):
        store = ui.PictureStore()
        change = store.apply(self.frame(range(16), 2, 2))
        self.assertEqual((change.kind, bytes(store.pixels), store.size), (ui.PictureStore.NEW, bytes(range(16)), (2, 2)))

    def test_a_frame_of_the_same_size_changes_only_the_dirty_rows(self):
        store = ui.PictureStore()
        store.apply(self.frame([1] * 32, 2, 4))                          # 2 x 4 pixels, 8 bytes a row
        change = store.apply(self.frame([9] * 32, 2, 4, rects=[cefweaver.Rect(1, 1, 1, 2)]))
        self.assertEqual(change.kind, ui.PictureStore.DIRTY)
        self.assertEqual(change.rects, [cefweaver.Rect(1, 1, 1, 2)])
        pixels = bytes(store.pixels)
        for y in range(4):
            row = pixels[y * 8:(y + 1) * 8]
            expected = bytes([1] * 4 + ([9] * 4 if y in (1, 2) else [1] * 4))
            self.assertEqual(row, expected, "row %d" % y)

    def test_dirty_rects_outside_the_picture_are_cut(self):
        store = ui.PictureStore()
        store.apply(self.frame([0] * 16, 2, 2))
        change = store.apply(self.frame([5] * 16, 2, 2, rects=[cefweaver.Rect(1, 1, 10, 10), cefweaver.Rect(5, 5, 1, 1)]))
        self.assertEqual(change.rects, [cefweaver.Rect(1, 1, 1, 1)])
        self.assertEqual(bytes(store.pixels)[12:16], bytes([5] * 4))

    def test_another_size_is_new_again_with_new_pixels(self):
        store = ui.PictureStore()
        store.apply(self.frame([0] * 16, 2, 2))
        first = store.pixels
        change = store.apply(self.frame([7] * 24, 3, 2))
        self.assertEqual((change.kind, store.size), (ui.PictureStore.NEW, (3, 2)))
        self.assertIsNot(store.pixels, first)

    def test_the_store_does_not_depend_on_the_buffer_of_the_frame(self):
        store = ui.PictureStore()
        data = bytearray(16)
        store.apply(ui.Frame(ui.Frame.VIEW, 2, 2, memoryview(data), []))
        data[0] = 99
        self.assertEqual(store.pixels[0], 0)

    def test_the_popup_is_kept_with_its_place_until_it_is_hidden(self):
        store = ui.PictureStore()
        place = cefweaver.Rect(3, 4, 2, 2)
        change = store.apply(self.frame([2] * 16, 2, 2, kind=ui.Frame.POPUP, rect=place))
        self.assertEqual((change.kind, bytes(store.popup_pixels), store.popup_size, store.popup_rect), (ui.PictureStore.POPUP, bytes([2] * 16), (2, 2), place))
        change = store.apply(ui.Frame(ui.Frame.POPUP_HIDDEN))
        self.assertEqual((change.kind, store.popup_pixels), (ui.PictureStore.POPUP_HIDDEN, None))


TOOLKITS = ("gtk3", "qt", "tk", "sdl2", "wx", "kivy")


class ToolkitModules(unittest.TestCase):
    """The adapters live in the package, one module a toolkit, so that they can be split off later (wiki: ui-api)."""

    def source(self, name):
        import importlib.util
        spec = importlib.util.find_spec("cefweaver.ui.toolkits." + name)
        self.assertIsNotNone(spec, "cefweaver.ui.toolkits.%s does not exist" % name)
        with open(spec.origin, encoding="utf-8") as f:
            return f.read()

    def test_there_is_a_module_for_each_toolkit(self):
        for name in TOOLKITS:
            self.source(name)

    def test_importing_the_ui_package_imports_no_toolkit(self):
        code = ("import sys, cefweaver, cefweaver.ui, cefweaver.ui.toolkits\n"
                "bad = [n for n in ('PyQt6', 'PySide6', 'gi', 'tkinter', 'sdl2', 'wx', 'kivy', 'PIL') if n in sys.modules]\n"
                "assert not bad, bad\nprint('OK')")
        result = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, timeout=60)
        self.assertEqual((result.returncode, result.stdout.strip()), (0, "OK"), result.stderr[-1500:])

    def test_a_module_says_what_it_was_checked_on_and_what_not(self):
        import ast
        for name in TOOLKITS:
            doc = ast.get_docstring(ast.parse(self.source(name))) or ""
            self.assertIn("Checked:", doc, name)
            self.assertIn("Not checked:", doc, name)

    def test_the_modules_do_not_import_each_other(self):
        import ast
        for name in TOOLKITS:
            for node in ast.walk(ast.parse(self.source(name))):
                modules = []
                if isinstance(node, ast.Import):
                    modules = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    modules = [("." * node.level) + (node.module or "")]
                for module in modules:
                    self.assertNotIn("toolkits", module, "%s imports %s" % (name, module))

    def test_the_modules_keep_no_aliases_of_the_library_constants(self):
        import re
        for name in TOOLKITS:
            found = re.findall(r"(?<![\w.])(SHIFT|CONTROL|ALT|LEFT_BUTTON|MIDDLE_BUTTON|RIGHT_BUTTON)\b", self.source(name))
            self.assertEqual(found, [], "%s keeps aliases (write keys.SHIFT and so on)" % name)

    def test_every_toolkit_does_the_clipboard_itself(self):
        # CEF's own clipboard is the compositor's on Wayland and the X server's on X11: the toolkit's may be another one
        for name in ("gtk3", "qt", "tk", "sdl2", "wx", "kivy"):
            source = self.source(name)
            self.assertNotRegex(source, r"capabilities\s*=[^\n]*native_clipboard", name)
            self.assertIn("def clipboard_get", source, name)
            self.assertIn("def clipboard_set", source, name)

    def test_the_modules_have_no_bare_virtual_key_numbers(self):
        import re
        for name in TOOLKITS:
            self.assertEqual(re.findall(r'"\w+":\s*\d+,', self.source(name)), [], name)    # a key table entry with a bare number

    def test_the_modules_use_only_the_public_side_of_the_view(self):
        import re
        for name in TOOLKITS:
            self.assertEqual(re.findall(r"\bview\._\w+", self.source(name)), [], name)


class FakeSink:
    """An audio sink that writes down what it is given."""

    def __init__(self):
        self.calls = []

    def start(self, sample_rate, channels):
        self.calls.append(("start", sample_rate, channels))

    def write(self, samples, frames):
        self.calls.append(("write", samples, frames))

    def stop(self):
        self.calls.append(("stop",))


def floats(*values):
    import array
    return memoryview(array.array("f", values))


class AudioOutput(unittest.TestCase):
    """The sound of the page goes to a sink the application (or the toolkit) gives; without one CEF plays it."""

    PARAMS = types.AudioParameters(types.ChannelLayout.LAYOUT_STEREO, 44100, 1024)

    def test_without_a_sink_cef_plays_the_sound_itself(self):
        view, _, _ = make_view()
        self.assertIsNone(view.client.get_audio_handler())

    def test_a_sink_gets_the_stream_as_interleaved_samples(self):
        import array
        sink = FakeSink()
        view = ui.BrowserView(FakeAdapter(), audio=sink)
        handler = view.client.get_audio_handler()
        self.assertIsNotNone(handler)
        handler.on_audio_stream_started(None, self.PARAMS, 2)
        handler.on_audio_stream_packet(None, [floats(1, 2, 3), floats(10, 20, 30)], 1234)
        handler.on_audio_stream_stopped(None)
        self.assertEqual(sink.calls[0], ("start", 44100, 2))
        kind, samples, frames = sink.calls[1]
        self.assertEqual((kind, frames), ("write", 3))
        self.assertEqual(list(array.array("f", samples)), [1, 10, 2, 20, 3, 30])      # left, right, left, right ...
        self.assertEqual(sink.calls[2], ("stop",))

    def test_a_mono_stream_is_the_samples_as_they_are(self):
        import array
        sink = FakeSink()
        view = ui.BrowserView(FakeAdapter(), audio=sink)
        handler = view.client.get_audio_handler()
        handler.on_audio_stream_started(None, self.PARAMS, 1)
        handler.on_audio_stream_packet(None, [floats(0.5, -0.5)], 0)
        self.assertEqual(list(array.array("f", sink.calls[1][1])), [0.5, -0.5])

    def test_a_muted_view_drops_the_packets_but_keeps_the_stream(self):
        sink = FakeSink()
        view = ui.BrowserView(FakeAdapter(), audio=sink)
        handler = view.client.get_audio_handler()
        handler.on_audio_stream_started(None, self.PARAMS, 1)
        view.audio_muted = True
        handler.on_audio_stream_packet(None, [floats(1, 2)], 0)
        view.audio_muted = False
        handler.on_audio_stream_packet(None, [floats(3, 4)], 0)
        self.assertEqual([c[0] for c in sink.calls], ["start", "write"])
        self.assertEqual(sink.calls[1][2], 2)

    def test_an_error_of_the_stream_stops_the_sink_and_is_told(self):
        sink = FakeSink()
        view = ui.BrowserView(FakeAdapter(), audio=sink)
        told = []
        view.on_audio_error = told.append
        handler = view.client.get_audio_handler()
        handler.on_audio_stream_started(None, self.PARAMS, 2)
        handler.on_audio_stream_error(None, "device lost")
        self.assertEqual((sink.calls[-1], told), (("stop",), ["device lost"]))

    def test_a_sink_that_fails_is_dropped_once_and_told_not_every_packet(self):
        class Broken(FakeSink):
            def write(self, samples, frames):
                raise OSError("no device")
        sink, told = Broken(), []
        view = ui.BrowserView(FakeAdapter(), audio=sink)
        view.on_audio_error = told.append
        handler = view.client.get_audio_handler()
        handler.on_audio_stream_started(None, self.PARAMS, 1)
        for _ in range(5):
            handler.on_audio_stream_packet(None, [floats(1, 2)], 0)
        self.assertEqual(len(told), 1)
        self.assertIn("no device", told[0])
        self.assertEqual(sink.calls[-1], ("stop",))                  # the sink is let go of

    def test_auto_takes_the_sink_of_the_adapter(self):
        adapter = FakeAdapter()
        mine = FakeSink()
        adapter.audio_sink = lambda: mine
        view = ui.BrowserView(adapter, audio="auto")
        self.assertIs(view.audio_sink, mine)

    def test_auto_without_a_sink_of_the_toolkit_takes_pygame_if_it_is_there(self):
        view_with = ui.BrowserView(FakeAdapter(), audio="auto", pygame_sink=lambda: "pygame")
        self.assertEqual(view_with.audio_sink, "pygame")
        view_without = ui.BrowserView(FakeAdapter(), audio="auto", pygame_sink=lambda: None)   # pygame is not installed
        self.assertIsNone(view_without.audio_sink)
        self.assertIsNone(view_without.client.get_audio_handler())             # then CEF plays it itself

    def test_a_toolkit_sink_wins_over_pygame(self):
        adapter = FakeAdapter()
        adapter.audio_sink = lambda: "toolkit"
        view = ui.BrowserView(adapter, audio="auto", pygame_sink=lambda: "pygame")
        self.assertEqual(view.audio_sink, "toolkit")

    def test_audio_must_be_a_sink_auto_or_none(self):
        with self.assertRaises(TypeError):
            ui.BrowserView(FakeAdapter(), audio=42)


class Interleaving(unittest.TestCase):
    def test_planes_become_one_buffer_of_frames(self):
        import array
        samples, frames = ui.audio.interleave([floats(1, 2), floats(3, 4), floats(5, 6)])
        self.assertEqual(frames, 2)
        self.assertEqual(list(array.array("f", samples)), [1, 3, 5, 2, 4, 6])

    def test_no_planes_are_no_frames(self):
        self.assertEqual(ui.audio.interleave([]), (b"", 0))


class PygameSinkOnADevice(unittest.TestCase):
    """The pygame sink on the real audio device, with silence (volume 0) so that nothing is heard. Skipped without
    pygame or without an audio device."""

    def make(self):
        try:
            sink = ui.audio.PygameSink(volume=0.0)
        except ImportError:
            self.skipTest("pygame is not installed")
        return sink

    def feed(self, sink, seconds, rate=44100, channels=2):
        import array
        import time
        packet = array.array("f", bytes(4 * 1024 * channels)).tobytes()
        end = time.monotonic() + seconds
        fed = 0
        while time.monotonic() < end:
            sink.write(packet, 1024)
            fed += 1024
            time.sleep(1024 / rate)
        return fed

    def test_a_stream_is_played_as_fast_as_it_comes_and_ends_cleanly(self):
        sink = self.make()
        try:
            sink.start(44100, 2)
        except Exception as error:
            self.skipTest("no audio device to open: %s" % error)
        fed = self.feed(sink, 1.0)
        import time
        time.sleep(0.2)
        stats = sink.stats()
        sink.stop()
        self.assertEqual(stats["written"], fed)
        self.assertGreaterEqual(stats["consumed"], fed - 3 * 1024)           # the device took what was written
        self.assertLessEqual(stats["queued"], 3 * 1024, stats)               # and no big pile is left: the latency is small
        self.assertEqual(stats["dropped"], 0)
        self.assertLessEqual(stats["underruns"], 3, stats)

    def test_a_stream_can_start_again(self):
        sink = self.make()
        try:
            sink.start(48000, 1)
        except Exception as error:
            self.skipTest("no audio device to open: %s" % error)
        self.feed(sink, 0.2, rate=48000, channels=1)
        sink.stop()
        sink.start(44100, 2)                                                 # another page, another stream
        self.feed(sink, 0.2)
        sink.stop()

    def test_what_the_application_cannot_keep_up_with_is_dropped_not_piled_up(self):
        sink = self.make()
        try:
            sink.start(44100, 2)
        except Exception as error:
            self.skipTest("no audio device to open: %s" % error)
        sink.device_paused = True
        import array
        big = array.array("f", bytes(4 * 44100 * 2)).tobytes()               # a second of sound at once, three times
        for _ in range(3):
            sink.write(big, 44100)
        self.assertLessEqual(sink.stats()["queued"], int(44100 * sink.max_latency) + 1024)
        self.assertGreater(sink.stats()["dropped"], 0)
        sink.stop()


class Navigation(unittest.TestCase):
    def test_navigation_goes_to_the_browser(self):
        view, _, calls = make_view()
        view.load_url("http://a/")
        view.go_back()
        view.reload()
        view.close_browser()
        self.assertEqual([c[0] for c in calls], ["load_url", "go_back", "reload", "close_browser"])


SCRIPT = """
import sys, tempfile
from cefweaver import types, ui
from cefweaver.ui import keys
from cefweaver.ui.headless import HeadlessAdapter

class Loop(HeadlessAdapter):
    closed = False
    def release(self):
        self.closed = True

PAGE = \"\"\"<!doctype html><meta charset=utf-8><title>start</title>
<body style="margin:0;background:#00ff00">
<button id=b style="position:fixed;left:0;top:0;width:100px;height:50px" onclick="document.title='clicked'">go</button>
<input id=i style="position:fixed;left:0;top:100px;width:200px" oninput="document.title='typed:' + this.value">
<div id=z style="position:fixed;left:0;top:150px;width:100px;height:40px;background:#ccf"
     ondragenter="event.preventDefault()" ondragover="event.preventDefault()"
     ondrop="event.preventDefault(); document.title='dropped:' + event.dataTransfer.getData('text/plain')">zone</div>
\"\"\"
adapter = Loop(size=(300, 220))
session = ui.Session(adapter, switches=[("ozone-platform", "x11")], cache_path=tempfile.mkdtemp(prefix="cefweaver-ui-"))
class Widget(ui.BrowserWidget):
    pass
widget = Widget()
view = widget.attach_view(adapter)
titles, loading = [], []
view.on_title = titles.append
view.on_loading = lambda *state: loading.append(state)

def ready():
    session.app.add_resource("http://ui.test/", PAGE)
    view.load_url("http://ui.test/")
view.on_ready = ready

def wait_title(text, what):
    adapter.run_until(lambda: titles and titles[-1] == text, what + " (titles: %r)" % titles[-5:])

session.start(widget)
adapter.run_until(lambda: adapter.picture and "start" in titles, "the page")
adapter.run_for(0.3)
width, height, _ = adapter.picture
assert (width, height) == (300, 220), (width, height)
assert adapter.pixel(250, 10)[:3] == (0, 255, 0), adapter.pixel(250, 10)         # the green of the page
assert any(state[0] is False for state in loading), loading

# a click on the button, with the toolkit's coordinates
view.focus(True)
view.mouse_move(20, 20, 0)
view.mouse_button(20, 20, "left", True, keys.LEFT_BUTTON)
view.mouse_button(20, 20, "left", False, 0)
wait_title("clicked", "the click")

# typing: a key with its character, then the text of an input method
view.mouse_button(50, 110, "left", True, keys.LEFT_BUTTON)
view.mouse_button(50, 110, "left", False, 0)
adapter.run_for(0.2)
view.key(True, keys.vk_for_char("a"), 38, 0, char="a")
view.key(False, keys.vk_for_char("a"), 38, 0)
wait_title("typed:a", "the typed letter")
view.preedit("하", 1)
view.text("한")
wait_title("typed:a한", "the Hangul")

# a drop from another program, as a toolkit that tells only the drop reports it
view.drop(30, 160, text="from-outside")
wait_title("dropped:from-outside", "the drop")

# the view follows the size the adapter reports
adapter.size = (260, 180)
view.resized()
adapter.run_until(lambda: adapter.picture[:2] == (260, 180), "the picture of the new size")

shot = tempfile.mktemp(suffix=".png")
assert widget.snapshot(shot), "no picture to save"
assert open(shot, "rb").read(8) == b"\\x89PNG\\r\\n\\x1a\\n"
done = []
session.shutdown(lambda: done.append(True))
adapter.run_until(lambda: done, "CEF to shut down", 20)
assert adapter.closed, "the loop was not closed"
print("OK")
"""


class WithCef(unittest.TestCase):
    def test_a_browser_runs_in_the_headless_adapter(self):
        env = dict(os.environ)
        env.pop("WAYLAND_DISPLAY", None)
        result = subprocess.run([sys.executable, "-I", "-c", textwrap.dedent(SCRIPT)], capture_output=True, text=True,
                                timeout=120, env=env)
        self.assertEqual(result.returncode, 0, (result.stdout + result.stderr)[-3000:])
        self.assertNotIn("stack smashing", result.stderr)
        self.assertIn("OK", result.stdout)


PERMISSION_SCRIPT = """
import sys, tempfile
from cefweaver import ui
from cefweaver.ui.headless import HeadlessAdapter

PAGE = \"\"\"<!doctype html><meta charset=utf-8><title>asking</title><script>
navigator.mediaDevices.getUserMedia({audio: true}).then(
  function (s) { document.title = "granted:" + s.getAudioTracks().length; },
  function (e) { document.title = "denied:" + e.name; });
</script>\"\"\"
adapter = HeadlessAdapter(size=(200, 100))
# fake devices: the answer of the page is what is checked, not a real microphone
session = ui.Session(adapter, switches=[("ozone-platform", "x11"), ("use-fake-device-for-media-stream", "")],
                     cache_path=tempfile.mkdtemp(prefix="cefweaver-ui-"))
asked = []
def policy(request):
    asked.append(request.origin)
    ui.permissions.allow_origins("http://localhost")(request)
class Widget(ui.BrowserWidget):
    pass
widget = Widget()
view = widget.attach_view(adapter, media_permissions=policy)
titles = []
view.on_title = titles.append
def ready():
    session.app.add_resource("http://localhost/", PAGE)
    session.app.add_resource("http://127.0.0.1/", PAGE)             # a secure context too, but not in the policy
    view.load_url("http://localhost/")
view.on_ready = ready
session.start(widget)
adapter.run_until(lambda: any(t.startswith(("granted", "denied")) for t in titles), "the answer for localhost (titles %r)" % titles)
first = [t for t in titles if t.startswith(("granted", "denied"))][-1]
del titles[:]
view.load_url("http://127.0.0.1/")
adapter.run_until(lambda: any(t.startswith(("granted", "denied")) for t in titles), "the answer for 127.0.0.1 (titles %r)" % titles)
second = [t for t in titles if t.startswith(("granted", "denied"))][-1]
print("ANSWERS", first, second, asked)
done = []
session.shutdown(lambda: done.append(True))
adapter.run_until(lambda: done, "CEF to shut down", 20)
print("OK")
"""


MENU_SCRIPT = """
import sys, tempfile
from cefweaver import types, ui
from cefweaver.ui import keys
from cefweaver.ui.headless import HeadlessAdapter

class Menus(HeadlessAdapter):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.menus = []
    def show_menu(self, items, x, y, done):
        self.menus.append((items, x, y, done))

PAGE = \"\"\"<!doctype html><meta charset=utf-8><title>start</title><body style="margin:0;font:20px sans-serif">
<p id=t style="margin:0;padding:20px">hello menu</p>
<script>document.addEventListener("selectionchange", function () { var s = String(getSelection());
  if (s) document.title = "selected:" + s; });</script>\"\"\"
adapter = Menus(size=(300, 200))
session = ui.Session(adapter, switches=[("ozone-platform", "x11")], cache_path=tempfile.mkdtemp(prefix="cefweaver-ui-"))
class Widget(ui.BrowserWidget):
    pass
widget = Widget()
view = widget.attach_view(adapter)
titles = []
view.on_title = titles.append
hooked = []
view.on_context_menu = lambda info, items: hooked.append((info.x, info.y)) or items
def ready():
    session.app.add_resource("http://ui.test/", PAGE)
    view.load_url("http://ui.test/")
view.on_ready = ready
session.start(widget)
adapter.run_until(lambda: adapter.picture and "start" in titles, "the page")
adapter.run_for(0.3)
view.focus(True)
def right_click():
    view.mouse_move(40, 30, 0)
    view.mouse_button(40, 30, "right", True, keys.RIGHT_BUTTON)
    view.mouse_button(40, 30, "right", False, 0)
for _ in range(10):                                   # the page may need a moment to take the click
    right_click()
    adapter.run_for(0.3)
    if adapter.menus:
        break
assert adapter.menus, "the toolkit was not asked to show the menu"
items, x, y, done = adapter.menus[0]
ids = [i.command_id for i in items if i.kind != "separator"]
assert (x, y) == (40, 30), (x, y)
assert hooked and hooked[0] == (40, 30), hooked
if sys.platform != "darwin":      # the menu of CEF on macOS has no Back and Forward (only 113, view source, here)
    assert int(types.MenuId.BACK) in ids and int(types.MenuId.FORWARD) in ids, ids   # the standard items, by the ids CEF knows
assert ids, ids
assert all(i.label for i in items if i.kind != "separator"), items
# Select all is not in the menu of a plain click, but CEF runs any standard command it is given (F32)
done(int(types.MenuId.SELECT_ALL))
adapter.run_until(lambda: any(t == "selected:hello menu" for t in titles), "the selection made by the menu (titles %r)" % titles[-4:])
print("ITEMS", len(items), "OK-PICK")
done_shutdown = []
session.shutdown(lambda: done_shutdown.append(True))
adapter.run_until(lambda: done_shutdown, "CEF to shut down", 20)
print("OK")
"""


class WithCefContextMenu(unittest.TestCase):
    def test_a_right_click_asks_the_toolkit_for_a_menu_and_a_pick_is_run_by_cef(self):
        env = dict(os.environ)
        env.pop("WAYLAND_DISPLAY", None)
        result = subprocess.run([sys.executable, "-I", "-c", textwrap.dedent(MENU_SCRIPT)], capture_output=True, text=True,
                                timeout=120, env=env)
        self.assertEqual(result.returncode, 0, (result.stdout + result.stderr)[-3000:])
        self.assertNotIn("stack smashing", result.stderr)
        self.assertIn("OK-PICK", result.stdout)
        self.assertIn("OK", result.stdout.splitlines()[-1])


KEYS_SCRIPT = """
import tempfile
from cefweaver import types, ui
from cefweaver.ui import keys
from cefweaver.ui.headless import HeadlessAdapter

PAGE = \"\"\"<!doctype html><meta charset=utf-8><title>start</title><body style="margin:0">
<input id=i autofocus style="width:200px"><script>var i = document.getElementById("i");
["keyup", "input", "compositionupdate"].forEach(function (n) { i.addEventListener(n, function () { document.title = "v:" + i.value + ":" + i.selectionStart; }); });</script>\"\"\"
adapter = HeadlessAdapter(size=(300, 100))
session = ui.Session(adapter, cache_path=tempfile.mkdtemp(prefix="cefweaver-ui-"))
class Widget(ui.BrowserWidget):
    pass
widget = Widget()
view = widget.attach_view(adapter)
titles = []
view.on_title = titles.append
def ready():
    session.app.add_resource("http://ui.test/", PAGE)
    view.load_url("http://ui.test/")
view.on_ready = ready
session.start(widget)
adapter.run_until(lambda: adapter.picture and "start" in titles, "the page")
adapter.run_for(0.3)
view.focus(True)
def press(code, char=None):
    view.key(True, code, 0, 0, char=char)           # the toolkit gives no native code
    view.key(False, code, 0, 0)
def value(expected):
    adapter.run_until(lambda: titles and titles[-1] == "v:" + expected, "the value " + expected + " (titles %r)" % titles[-3:], 20)
for _ in range(10):                                 # the page may need a moment to take the focus
    view.mouse_button(20, 10, "left", True, keys.LEFT_BUTTON)       # into the field
    view.mouse_button(20, 10, "left", False, 0)
    press(88, "x")
    adapter.run_for(0.3)
    if "v:x:1" in titles:
        break
view.key(True, keys.VK_BACK, 0, 0); view.key(False, keys.VK_BACK, 0, 0)    # clear the x
value(":0")
for code, char in ((65, "a"), (66, "b"), (67, "c")):
    press(code, char)
value("abc:3")
press(keys.VK_BACK)
value("ab:2")
press(keys.VK_LEFT)
value("ab:1")
press(keys.VK_DELETE)
value("a:1")
# An input method: the composition of Hangul shows in the field, the commit makes it text
view.preedit("\ud55c", 1)
adapter.run_until(lambda: titles[-1].startswith("v:a\ud55c"), "the composition (titles %r)" % titles[-2:], 20)
view.commit_text("\ud55c\uae00")
adapter.run_until(lambda: titles and titles[-1].startswith("v:a\ud55c\uae00") or any(t.startswith("v:a\ud55c\uae00") for t in titles), "the committed text (titles %r)" % titles[-3:], 20)
view.preedit("", 0)
if keys.IS_MAC:                                     # Command+A selects all (a frame command: no Edit menu), then a letter replaces it
    view.key(True, 65, 0, keys.COMMAND); view.key(False, 65, 0, keys.COMMAND)
    press(81, "q")
    value("q:1")
done = []
session.shutdown(lambda: done.append(True))
adapter.run_until(lambda: done, "CEF to shut down", 20)
print("OK")
"""


class WithCefKeys(unittest.TestCase):
    """The keys of a toolkit that gives no native key code edit a field (macOS needs the code)."""

    def test_editing_keys_edit_a_field_without_native_codes_from_the_toolkit(self):
        env = dict(os.environ)
        env.pop("WAYLAND_DISPLAY", None)
        result = subprocess.run([sys.executable, "-I", "-c", textwrap.dedent(KEYS_SCRIPT)], capture_output=True,
                                text=True, timeout=120, env=env)
        self.assertEqual(result.returncode, 0, (result.stdout + result.stderr)[-3000:])
        self.assertIn("OK", result.stdout.splitlines()[-1])


SPELL_SCRIPT = """
import tempfile
from cefweaver import types, ui
from cefweaver.ui import keys
from cefweaver.ui.headless import HeadlessAdapter

class Menus(HeadlessAdapter):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.menus = []
    def show_menu(self, items, x, y, done):
        self.menus.append((items, x, y, done))

PAGE = \"\"\"<!doctype html><meta charset=utf-8><title>start</title><body style="margin:0">
<textarea id=a rows=3 cols=30 spellcheck=true style="font:20px sans-serif"></textarea>\"\"\"
adapter = Menus(size=(500, 200))
session = ui.Session(adapter, switches=[("ozone-platform", "x11")], cache_path=tempfile.mkdtemp(prefix="cefweaver-ui-"))
class Widget(ui.BrowserWidget):
    pass
widget = Widget()
view = widget.attach_view(adapter)
titles, seen = [], []
view.on_title = titles.append
view.on_context_menu = lambda info, items: seen.append((info.misspelled_word, info.dictionary_suggestions)) or items
def ready():
    session.app.add_resource("http://ui.test/", PAGE)
    view.load_url("http://ui.test/")
view.on_ready = ready
session.start(widget)
adapter.run_until(lambda: adapter.picture and "start" in titles, "the page")
adapter.run_for(0.3)

def js(code):
    box = []
    session.bridge.evaluate(view.browser.get_main_frame(), code, lambda v, e: box.append((v, e)))
    adapter.run_until(lambda: box, "the value of " + code)
    return box[0][0]

view.focus(True)
view.mouse_move(100, 30, 0)
view.mouse_button(100, 30, "left", True, keys.LEFT_BUTTON)
view.mouse_button(100, 30, "left", False, 0)
adapter.run_for(0.4)
for letter in "teh wrold ":                           # typed, so that the checker looks at the words
    view.text(letter)
    adapter.run_for(0.05)
adapter.run_for(1.5)
for attempt in range(20):                              # the checker is asynchronous: try until it knows the word
    before = len(adapter.menus)
    view.mouse_move(12, 14, 0)
    view.mouse_button(12, 14, "right", True, keys.RIGHT_BUTTON)
    view.mouse_button(12, 14, "right", False, 0)
    adapter.run_for(0.5)
    if len(adapter.menus) > before:
        if seen and seen[-1][0] == "teh" and seen[-1][1]:
            break
        adapter.menus[-1][3](None)
        adapter.run_for(0.5)
items, x, y, done = adapter.menus[-1]
assert seen[-1][0] == "teh" and seen[-1][1], seen[-1:]
ids = [i.command_id for i in items if i.kind != "separator"]
assert int(types.MenuId.SPELLCHECK_SUGGESTION_0) in ids and int(types.MenuId.ADD_TO_DICTIONARY) in ids, ids
view.focus(False)                                      # the menu of the toolkit took the focus
adapter.run_for(0.3)
done(int(types.MenuId.SPELLCHECK_SUGGESTION_0))        # the user picks the first suggestion
adapter.run_for(0.8)
value = js("document.getElementById('a').value")
print("VALUE", repr(value), "SUGGESTION", seen[-1][1][0])
assert value == seen[-1][1][0] + " wrold ", value
d = []
session.shutdown(lambda: d.append(True))
adapter.run_until(lambda: d, "CEF to shut down", 20)
print("OK")
"""


class WithCefSpelling(unittest.TestCase):
    @unittest.skipIf(sys.platform == "darwin", "macOS checks the spelling with NSSpellChecker: no suggestions came here; not examined")
    def test_a_suggestion_of_the_menu_replaces_the_misspelled_word_on_a_page_that_lost_the_focus(self):
        env = dict(os.environ)
        env.pop("WAYLAND_DISPLAY", None)
        result = subprocess.run([sys.executable, "-I", "-c", textwrap.dedent(SPELL_SCRIPT)], capture_output=True, text=True,
                                timeout=120, env=env)
        self.assertEqual(result.returncode, 0, (result.stdout + result.stderr)[-3000:])
        self.assertNotIn("stack smashing", result.stderr)
        self.assertIn("OK", result.stdout.splitlines()[-1])


class WithCefPermissions(unittest.TestCase):
    def test_a_policy_decides_what_a_real_page_gets_for_the_microphone(self):
        env = dict(os.environ)
        env.pop("WAYLAND_DISPLAY", None)
        result = subprocess.run([sys.executable, "-I", "-c", textwrap.dedent(PERMISSION_SCRIPT)], capture_output=True, text=True,
                                timeout=120, env=env)
        self.assertEqual(result.returncode, 0, (result.stdout + result.stderr)[-3000:])
        self.assertNotIn("stack smashing", result.stderr)
        self.assertIn("OK", result.stdout)
        line = [l for l in result.stdout.splitlines() if l.startswith("ANSWERS")][0]
        self.assertEqual(line, "ANSWERS granted:1 denied:NotAllowedError ['http://localhost/', 'http://127.0.0.1/']")


# -- the quickstarts of the examples run for real -----------------------------------------------------------------

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUICKSTARTS = (          # (example, its uv environment, what keeps the toolkit on X11)
    ("gtk3", ".venv", {"GDK_BACKEND": "x11"}),
    ("qt", ".venv", {"QT_QPA_PLATFORM": "xcb"}),
    ("qt", ".venv-pyside", {"QT_QPA_PLATFORM": "xcb"}),
    ("tk", ".venv", {}),
    ("sdl2", ".venv", {"SDL_VIDEODRIVER": "x11"}),
    ("wx", ".venv", {"GDK_BACKEND": "x11"}),
    ("kivy", ".venv", {"SDL_VIDEODRIVER": "x11", "KIVY_NO_CONSOLELOG": "1"}),
)


def send_delete_window(window):
    """Ask a window to close, as the close button does (WM_DELETE_WINDOW), without a window manager."""
    import ctypes
    x = ctypes.CDLL("libX11.so.6")
    x.XOpenDisplay.restype = ctypes.c_void_p
    x.XInternAtom.restype = ctypes.c_ulong
    x.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
    x.XSendEvent.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_long, ctypes.c_void_p]

    class Message(ctypes.Structure):
        _fields_ = [("type", ctypes.c_int), ("serial", ctypes.c_ulong), ("send_event", ctypes.c_int),
                    ("display", ctypes.c_void_p), ("window", ctypes.c_ulong), ("message_type", ctypes.c_ulong),
                    ("format", ctypes.c_int), ("data", ctypes.c_long * 5)]

    class Event(ctypes.Union):
        _fields_ = [("message", Message), ("pad", ctypes.c_long * 24)]
    display = x.XOpenDisplay(None)
    event = Event()
    event.message.type, event.message.window, event.message.format = 33, window, 32      # ClientMessage
    event.message.message_type = x.XInternAtom(display, b"WM_PROTOCOLS", 0)
    event.message.data[0] = x.XInternAtom(display, b"WM_DELETE_WINDOW", 0)
    x.XSendEvent(display, window, 0, 0, ctypes.byref(event))
    x.XFlush(display)


def code_after_the_docstring(path):
    import ast
    with open(path, encoding="utf-8") as f:
        text = f.read()
    first = ast.parse(text).body[0]
    return "\n".join(text.split("\n")[first.end_lineno:]).strip("\n") + "\n"


class QuickstartDocs(unittest.TestCase):
    """The documentation shows the code of the quickstart files, not a copy that can drift away from them."""

    def test_each_example_readme_shows_the_code_of_its_quickstart(self):
        for example in ("gtk3", "qt", "tk", "sdl2", "wx", "kivy"):
            code = code_after_the_docstring(os.path.join(ROOT, "examples", example, "quickstart.py"))
            with open(os.path.join(ROOT, "examples", example, "README.md"), encoding="utf-8") as f:
                self.assertIn(code, f.read(), "examples/%s/README.md does not show quickstart.py" % example)

    def test_the_readme_of_the_project_shows_the_tk_quickstart(self):
        code = code_after_the_docstring(os.path.join(ROOT, "examples", "tk", "quickstart.py"))
        indented = "".join(("    " + line if line else line) + "\n" for line in code.rstrip("\n").split("\n"))
        with open(os.path.join(ROOT, "README.rst"), encoding="utf-8") as f:
            self.assertIn(indented, f.read())

    def test_a_quickstart_is_short(self):
        for example in ("gtk3", "qt", "tk", "sdl2", "wx", "kivy"):
            code = code_after_the_docstring(os.path.join(ROOT, "examples", example, "quickstart.py"))
            self.assertLessEqual(len(code.splitlines()), 40, example)     # it is what a user reads first


class Quickstarts(unittest.TestCase):
    """examples/<toolkit>/quickstart.py is the program the documentation shows: it must show a page and, when its window
    is closed, end cleanly. Runs where the example has its uv environment (examples/<toolkit>/README.md) and an X
    server, else it is skipped."""

    def window_of(self, pid):
        import time
        end = time.time() + 15
        while time.time() < end:
            found = subprocess.run(["xdotool", "search", "--onlyvisible", "--pid", str(pid)], capture_output=True, text=True).stdout.split()
            if not found:                  # Tk does not tell the process: the window of class Tk (on a real screen there are other windows)
                found = subprocess.run(["xdotool", "search", "--onlyvisible", "--class", "Tk"],
                                       capture_output=True, text=True).stdout.split()
            if found:
                return int(found[0])
            time.sleep(0.3)
        self.fail("the window of the quickstart did not appear")

    def run_quickstart(self, example, venv, pins):
        import shutil
        import tempfile
        import threading
        import time
        python = os.path.join(ROOT, "examples", example, venv, "bin", "python")
        env = {k: v for k, v in os.environ.items() if k not in ("WAYLAND_DISPLAY", "XDG_SESSION_TYPE")}
        env.update(pins)
        # in a directory of its own: without a cache path CEF makes "cache" in the working directory
        scratch = tempfile.mkdtemp(prefix="cefweaver-quickstart-")
        self.addCleanup(shutil.rmtree, scratch, True)
        process = subprocess.Popen([python, os.path.join(ROOT, "examples", example, "quickstart.py"),
                                    "data:text/html,<title>quickstart</title><p>hi"],
                                   cwd=scratch, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        lines, errors = [], []
        threading.Thread(target=lambda: lines.extend(iter(process.stdout.readline, "")), daemon=True).start()
        threading.Thread(target=lambda: errors.extend(iter(process.stderr.readline, "")), daemon=True).start()
        try:
            end = time.time() + 60
            while "title: quickstart\n" not in lines:
                self.assertIsNone(process.poll(), "ended before the page was shown: " + "".join(errors)[-1500:])
                self.assertLess(time.time(), end, "no title in 60 s: " + "".join(errors)[-1500:])
                time.sleep(0.2)
            send_delete_window(self.window_of(process.pid))
            self.assertEqual(process.wait(timeout=40), 0, "".join(errors)[-1500:])
        finally:
            if process.poll() is None:
                process.kill()
        self.assertNotIn("stack smashing", "".join(errors))

    def test_each_quickstart_shows_a_page_and_ends_cleanly_when_its_window_is_closed(self):
        import shutil
        if not os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY") or not shutil.which("xdotool"):
            self.skipTest("needs an X server (not a Wayland session) and xdotool")
        ran = 0
        for example, venv, pins in QUICKSTARTS:
            if not os.path.isfile(os.path.join(ROOT, "examples", example, venv, "bin", "python")):
                continue
            with self.subTest(example=example, environment=venv):
                self.run_quickstart(example, venv, pins)
                ran += 1
        if not ran:
            self.skipTest("no example has its uv environment")


if __name__ == "__main__":
    unittest.main()
