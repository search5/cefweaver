"""``BrowserWidget``: what every toolkit widget of a browser does the same way."""

from .view import BrowserView


class BrowserWidget:
    """A base class (put it first) for a toolkit widget that shows a browser through a ``BrowserView``.

    The widget calls ``self.attach_view(adapter)`` once it can (its ``__init__``, after the toolkit's base
    class) and then has the ``view``, the navigation methods and the state of the view. It says what happens
    on the notifications of the browser by overriding the hooks, which do nothing here:

    ``browser_title(title)``, ``browser_address(url)``, ``browser_loading(loading, can_back, can_forward)``,
    ``browser_ready()``.
    """

    view = None

    def attach_view(self, adapter):
        self.view = BrowserView(adapter)
        self.view.on_title = self.browser_title
        self.view.on_address = self.browser_address
        self.view.on_loading = self.browser_loading
        self.view.on_ready = self.browser_ready
        return self.view

    # -- the hooks ---------------------------------------------------------------------------------

    def browser_title(self, title):
        pass

    def browser_address(self, url):
        pass

    def browser_loading(self, loading, can_back, can_forward):
        pass

    def browser_ready(self):
        pass

    # -- state and navigation of the view ------------------------------------------------------------

    @property
    def browser(self):
        return self.view.browser

    @property
    def popup_visible(self):
        return self.view.popup_visible

    @property
    def popup_rect(self):
        return self.view.popup_rect

    def load_url(self, url):
        self.view.load_url(url)

    def go_back(self):
        self.view.go_back()

    def go_forward(self):
        self.view.go_forward()

    def reload(self):
        self.view.reload()

    def close_browser(self):
        self.view.close_browser()

    def commit_text(self, text):
        """Text an input method committed (also for tests and for applications that have an input method)."""
        self.view.commit_text(text)

    def set_preedit(self, text, cursor):
        """The text an input method is composing."""
        self.view.preedit(text, cursor)
