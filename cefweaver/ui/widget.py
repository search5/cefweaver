"""A base class with what every toolkit widget of a browser has in common."""

from .view import BrowserView


class BrowserWidget:
    """A base class for a toolkit widget that shows a browser through a :class:`~cefweaver.ui.BrowserView`.

    List it first among the base classes. Call ``self.attach_view(adapter)`` once, in ``__init__`` after the
    toolkit's base class. Then the widget has ``view``, the navigation methods and the state of the view.
    Override the hooks ``browser_title``, ``browser_address``, ``browser_loading`` and ``browser_ready`` to
    handle the notifications of the browser; they do nothing here.

    Attributes:
        view (BrowserView): The view; ``None`` until :meth:`attach_view` is called.
    """

    view = None

    def attach_view(self, adapter, **options):
        """Create the view and connect the hooks to it.

        Args:
            adapter (ToolkitAdapter): The adapter of the toolkit.
            **options: Keyword arguments of :class:`~cefweaver.ui.BrowserView`, such as ``audio``.

        Returns:
            BrowserView: The new view, also stored as ``view``.
        """
        self.view = BrowserView(adapter, **options)
        self.view.on_title = self.browser_title
        self.view.on_address = self.browser_address
        self.view.on_loading = self.browser_loading
        self.view.on_ready = self.browser_ready
        return self.view

    # -- the hooks ---------------------------------------------------------------------------------

    def browser_title(self, title):
        """Handle a change of the page title.

        Args:
            title (str): The new title.
        """
        pass

    def browser_address(self, url):
        """Handle a change of the address of the main frame.

        Args:
            url (str): The new URL.
        """
        pass

    def browser_loading(self, loading, can_back, can_forward):
        """Handle a change of the loading state.

        Args:
            loading (bool): Whether a page is loading.
            can_back (bool): Whether the browser can go back.
            can_forward (bool): Whether the browser can go forward.
        """
        pass

    def browser_ready(self):
        """Handle the creation of the browser, after which pages can be loaded."""
        pass

    # -- state and navigation of the view ------------------------------------------------------------

    @property
    def browser(self):
        """The CEF browser of the view, or ``None`` before it exists and after it closed."""
        return self.view.browser

    @property
    def popup_visible(self):
        """Whether a popup (such as the list of a ``<select>``) is shown."""
        return self.view.popup_visible

    @property
    def popup_rect(self):
        """The rectangle of the popup in view coordinates, or ``None`` if CEF has not told one."""
        return self.view.popup_rect

    def load_url(self, url):
        """Load a URL in the main frame; see :meth:`~cefweaver.ui.BrowserView.load_url`.

        Args:
            url (str): The URL.
        """
        self.view.load_url(url)

    def go_back(self):
        """Go back in the history; see :meth:`~cefweaver.ui.BrowserView.go_back`."""
        self.view.go_back()

    def go_forward(self):
        """Go forward in the history; see :meth:`~cefweaver.ui.BrowserView.go_forward`."""
        self.view.go_forward()

    def reload(self):
        """Reload the page; see :meth:`~cefweaver.ui.BrowserView.reload`."""
        self.view.reload()

    def close_browser(self):
        """Close the browser; see :meth:`~cefweaver.ui.BrowserView.close_browser`."""
        self.view.close_browser()

    def snapshot(self, path):
        """Save the last picture of the view as a PNG file.

        Args:
            path (str): The file to write.

        Returns:
            bool: ``False`` if CEF has not painted yet.
        """
        return self.view.snapshot(path)

    def commit_text(self, text):
        """Send text that an input method committed; see :meth:`~cefweaver.ui.BrowserView.commit_text`.

        Args:
            text (str): The committed text.
        """
        self.view.commit_text(text)

    def set_preedit(self, text, cursor):
        """Set the text an input method is composing; see :meth:`~cefweaver.ui.BrowserView.preedit`.

        Args:
            text (str): The composition text. An empty string ends the composition.
            cursor (int): The cursor position in the text.
        """
        self.view.preedit(text, cursor)
