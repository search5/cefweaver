"""The session that runs CEF for a toolkit application from the toolkit's event loop."""

import os
import posixpath
import sys

import cefweaver

from .view import BrowserView
from .widget import BrowserWidget


def view_of(target):
    """Return the view of a view or of a widget.

    Args:
        target (BrowserView or BrowserWidget): A view, or a widget that has one.

    Returns:
        BrowserView: ``target`` itself, or ``target.view``.

    Raises:
        TypeError: If ``target`` is neither.
    """
    if isinstance(target, BrowserView):
        return target
    if isinstance(target, BrowserWidget):
        return target.view
    raise TypeError("expected a BrowserView or a BrowserWidget, not %s" % type(target).__name__)


def default_ozone_platform(environ=None, platform=None, exists=os.path.exists):
    """Return the Ozone platform an offscreen browser should use.

    A Wayland compositor must be present: ``WAYLAND_DISPLAY`` names a socket that exists, either as an absolute
    path or relative to ``XDG_RUNTIME_DIR``.

    Args:
        environ (dict, optional): The environment to read. Defaults to ``os.environ``.
        platform (str, optional): The platform name. Defaults to ``sys.platform``.
        exists (callable, optional): Tells whether a path exists. Defaults to ``os.path.exists``.

    Returns:
        str: ``"wayland"`` on Linux where a compositor is present; otherwise ``None``, which leaves the choice
        to Chromium or :class:`~cefweaver.CefApp`.
    """
    environ = os.environ if environ is None else environ
    if (sys.platform if platform is None else platform) != "linux":
        return None
    display = environ.get("WAYLAND_DISPLAY")
    if not display:
        return None
    if posixpath.isabs(display):                        # (Wayland is Linux: POSIX paths, wherever this runs)
        path = display
    elif environ.get("XDG_RUNTIME_DIR"):
        path = posixpath.join(environ["XDG_RUNTIME_DIR"], display)
    else:
        return None
    return "wayland" if exists(path) else None


class Session:
    """The :class:`~cefweaver.CefApp`, the :class:`~cefweaver.JavascriptBridge` and the :class:`~cefweaver.MessagePump` of an application.

    CEF reports from any of its threads when it wants to run; ``adapter.post`` brings that into the main
    thread and ``adapter.call_later`` carries the deadline, so nothing polls. A session holds one browser
    (one :class:`~cefweaver.ui.BrowserView`).

    Example:
        ::

            session = ui.Session(adapter, switches=[("disable-gpu", "")])
            view = ui.BrowserView(adapter)
            view.on_ready = lambda: view.load_url("https://example.org/")
            session.start(widget_or_view)
            ...
            session.shutdown(done=toolkit_quit)

    Args:
        adapter (ToolkitAdapter): The toolkit adapter; only ``post`` and ``call_later`` are needed (and
            ``release``, if it has one).
        switches (iterable, optional): Chromium command line switches as ``(name, value)`` pairs. If
            :func:`default_ozone_platform` returns a platform and neither ``ozone-platform`` nor
            ``ozone-platform-hint`` is given, ``("ozone-platform", platform)`` is added.
        cache_path (str, optional): The cache directory, passed to :meth:`~cefweaver.CefApp.set_cache_path`.

    Attributes:
        adapter (ToolkitAdapter): The toolkit adapter.
        switches (list): The switches given to CEF, including one added by the session.
        app (CefApp): The offscreen, non-transparent application.
        bridge (JavascriptBridge): The JavaScript bridge of ``app``.
        pump (MessagePump): The message pump of ``app``.
        started (bool): Whether :meth:`start` has been called and :meth:`shutdown` has not finished.
        views (list): The views of the session.
    """

    def __init__(self, adapter, switches=(), cache_path=None):
        self.adapter = adapter
        self.switches = list(switches)
        names = {str(name).lstrip("-") for name, _ in self.switches}
        if "ozone-platform" not in names and "ozone-platform-hint" not in names:
            platform = default_ozone_platform()
            if platform:
                self.switches.append(("ozone-platform", platform))
        self.app = cefweaver.CefApp()
        self.app.offscreen = True
        self.app.transparent = False
        if cache_path:
            self.app.set_cache_path(cache_path)
        for name, value in self.switches:
            self.app.add_command_line_switch(name, value)
        self.bridge = cefweaver.JavascriptBridge(self.app)
        self.pump = cefweaver.MessagePump(self.app, wake=self._wake)
        self.started = False
        self.views = []
        self._timer = None

    def _wake(self, delay):                             # any thread of CEF
        self.adapter.post(self._schedule)

    def _schedule(self):
        if not self.started:
            return
        if self._timer is not None and hasattr(self._timer, "cancel"):
            self._timer.cancel()
        self._timer = self.adapter.call_later(max(0.0, self.pump.timeout()), self._tick)

    def _tick(self):
        self._timer = None
        if self.started:
            self.pump.run()
            self._schedule()

    def start(self, target, url="about:blank"):
        """Start CEF and create the browser of a view.

        ``on_ready`` of the view is called when the browser exists.

        Args:
            target (BrowserView or BrowserWidget): The view, or the widget that has it.
            url (str, optional): The first URL. Defaults to ``"about:blank"``.

        Raises:
            TypeError: If ``target`` is neither a view nor a widget.
        """
        view = view_of(target)
        self.views = [view]
        self.app.set_client(view.client)
        self.app.initialize(url)
        self.started = True
        self._schedule()

    def shutdown(self, done=None):
        """Close the browsers, wait until CEF has closed them, shut CEF down and call ``done``.

        Returns at once; the rest runs from the loop of the toolkit. Calls ``adapter.release()`` if the
        adapter has it, before ``done``.

        Args:
            done (callable, optional): Called without arguments when the shutdown is complete.
        """
        for view in list(self.views):
            view.close_browser()

        def finish():
            if self.app.is_running:
                self.adapter.call_later(0.02, finish)
                return
            self.started = False
            if self._timer is not None and hasattr(self._timer, "cancel"):
                self._timer.cancel()
            self.app.shutdown()
            if hasattr(self.adapter, "release"):        # the loop may have something to let go of (a pipe)
                self.adapter.release()
            if done:
                done()
        self.adapter.call_later(0.02, finish)
