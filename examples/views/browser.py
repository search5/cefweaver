"""A browser window made only with CEF's Views: no GUI toolkit. The window, the toolbar (buttons and an address
field) and the browser are views that the program puts together; CEF draws them and handles their input.

``ViewsBrowser`` is what quickstart.py shows and what smoke.py drives with real X events.
"""

import tempfile
import time

import cefweaver as cef
from cefweaver import types

BACK, FORWARD, RELOAD, ADDRESS = 1, 2, 3, 4          # the ids of the views the delegates look at


class ViewsBrowser:
    def __init__(self, url, title_changed=print):
        self.url = url
        self.title_changed = title_changed               # called with each title of the page
        self.window = self.browser_view = self.address = None
        self.done = False                                # the window was destroyed
        self.app = cef.CefApp()
        self.app.set_cache_path(tempfile.mkdtemp(prefix="cefweaver-views-"))

    # -- the pieces CEF calls --------------------------------------------------------------------------------------

    def start(self):
        self.app.initialize(None)                        # no first browser: the BrowserView below is the browser
        self.browser_view = cef.BrowserView.create_browser_view(
            _Client(self), self.url, types.BrowserSettings(), None, None, cef.BrowserViewDelegate())
        cef.Window.create_top_level_window(_Window(self))

    def step(self, timeout=0.005):
        """Let CEF run, then wait `timeout` seconds. CEF owns the window here, so it has to see the events of the
        window system itself: the loop calls ``do_message_loop_work()`` often (polling). With a ``MessagePump``
        (``external_message_pump``) CEF only does the work it announced, and the X11 events of its own windows
        are not processed: a click on a button never arrives."""
        self.app.do_message_loop_work()
        time.sleep(timeout)

    def run(self):
        while not self.done:
            self.step()
        self.app.shutdown()

    def browser(self):
        return self.browser_view.get_browser()

    # -- the toolbar -----------------------------------------------------------------------------------------------

    def build(self, window):
        """Put the toolbar and the browser into the window (CEF has made it)."""
        self.window = window
        column = window.set_to_box_layout(types.BoxLayoutSettings(horizontal=False))
        toolbar = cef.Panel.create_panel(None)
        row = toolbar.set_to_box_layout(types.BoxLayoutSettings(
            horizontal=True, between_child_spacing=4, inside_border_insets=types.Insets(4, 4, 4, 4)))
        buttons = _Buttons(self)
        for number, text in ((BACK, "Back"), (FORWARD, "Forward"), (RELOAD, "Reload")):
            button = cef.LabelButton.create_label_button(buttons, text)
            button.set_id(number)
            toolbar.add_child_view(button)
        self.address = cef.Textfield.create_textfield(_Address(self))
        self.address.set_id(ADDRESS)
        toolbar.add_child_view(self.address)
        row.set_flex_for_view(self.address, 1)           # the address field takes the width that is left
        window.add_child_view(toolbar)
        window.add_child_view(self.browser_view)
        column.set_flex_for_view(self.browser_view, 1)   # the browser takes the height that is left
        window.set_title("cefweaver Views")
        window.show()


class _Buttons(cef.ButtonDelegate):
    """The buttons are told apart by their id: the Python objects of one CEF view are not the same object."""

    def __init__(self, owner):
        super().__init__()
        self.owner = owner

    def on_button_pressed(self, button):
        browser = self.owner.browser()
        if browser is None:
            return
        which = button.get_id()
        if which == BACK:
            browser.go_back()
        elif which == FORWARD:
            browser.go_forward()
        elif which == RELOAD:
            browser.reload()


class _Address(cef.TextfieldDelegate):
    """Return in the address field loads the address."""

    def __init__(self, owner):
        super().__init__()
        self.owner = owner

    def on_key_event(self, textfield, event):
        if event.windows_key_code == 13 and event.type == types.KeyEventType.RAWKEYDOWN:
            self.owner.browser().get_main_frame().load_url(textfield.get_text())
            return True
        return False


class _Display(cef.DisplayHandler):
    def __init__(self, owner):
        super().__init__()
        self.owner = owner

    def on_title_change(self, browser, title):
        self.owner.window.set_title(title)
        self.owner.title_changed(title)

    def on_address_change(self, browser, frame, url):
        if frame.is_main():
            self.owner.address.set_text(url)


class _Client(cef.Client):
    def __init__(self, owner):
        super().__init__()
        self.display = _Display(owner)

    def get_display_handler(self):
        return self.display


class _Window(cef.WindowDelegate):
    def __init__(self, owner):
        super().__init__()
        self.owner = owner

    def on_window_created(self, window):
        self.owner.build(window)

    def on_window_destroyed(self, window):
        self.owner.done = True

    def can_close(self, window):
        return True

    def get_initial_bounds(self, window):
        return (100, 100, 900, 640)
