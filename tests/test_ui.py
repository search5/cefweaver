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
    def adapter(self, native=False):
        adapter = FakeAdapter()
        adapter.stored = {"text": "from clipboard"}
        adapter.clipboard_get = lambda: adapter.stored["text"]
        adapter.clipboard_set = lambda text: adapter.stored.update(text=text)
        adapter.capabilities = frozenset({"native_clipboard"} if native else ())
        return adapter

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

    def test_a_widget_without_hooks_works_too(self):
        class Plain(ui.BrowserWidget):
            def __init__(self):
                self.attach_view(FakeAdapter())
        widget = Plain()
        widget.view.client.get_display_handler().on_title_change(None, "t")      # nothing to call: no error
        widget.view.client.get_life_span_handler().on_after_created(FakeBrowser([]))


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

PAGE = \"\"\"<!doctype html><meta charset=utf-8><title>start</title>
<body style="margin:0;background:#00ff00">
<button id=b style="position:fixed;left:0;top:0;width:100px;height:50px" onclick="document.title='clicked'">go</button>
<input id=i style="position:fixed;left:0;top:100px;width:200px" oninput="document.title='typed:' + this.value">
<div id=z style="position:fixed;left:0;top:150px;width:100px;height:40px;background:#ccf"
     ondragenter="event.preventDefault()" ondragover="event.preventDefault()"
     ondrop="event.preventDefault(); document.title='dropped:' + event.dataTransfer.getData('text/plain')">zone</div>
\"\"\"
adapter = HeadlessAdapter(size=(300, 220))
session = ui.Session(adapter, switches=[("ozone-platform", "x11")], cache_path=tempfile.mkdtemp(prefix="cefweaver-ui-"))
view = ui.BrowserView(adapter)
titles, loading = [], []
view.on_title = titles.append
view.on_loading = lambda *state: loading.append(state)

def ready():
    session.app.add_resource("http://ui.test/", PAGE)
    view.load_url("http://ui.test/")
view.on_ready = ready

def wait_title(text, what):
    adapter.run_until(lambda: titles and titles[-1] == text, what + " (titles: %r)" % titles[-5:])

session.start(view)
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

done = []
session.shutdown(lambda: done.append(True))
adapter.run_until(lambda: done, "CEF to shut down", 20)
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


if __name__ == "__main__":
    unittest.main()
