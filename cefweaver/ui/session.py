"""``Session``: CEF for a toolkit application, driven from the toolkit's event loop."""

import os
import sys

import cefweaver

from .view import BrowserView
from .widget import BrowserWidget


def view_of(target):
    """The ``BrowserView`` of what a toolkit application starts: the view, or the widget that has it."""
    if isinstance(target, BrowserView):
        return target
    if isinstance(target, BrowserWidget):
        return target.view
    raise TypeError("expected a BrowserView or a BrowserWidget, not %s" % type(target).__name__)


def default_ozone_platform(environ=None, platform=None, exists=os.path.exists):
    """``"wayland"`` where an offscreen browser should use it, else None (Chromium or ``CefApp`` decides).

    There has to be a Wayland compositor: ``WAYLAND_DISPLAY`` names a socket that exists. Offscreen CEF works on Wayland,
    and on X11 (XWayland) the GPU process of CEF dies on some machines and the video does not play, while Chrome plays
    it there. (A browser window of ``CefApp`` ends the process on Wayland: it stays on X11.)
    """
    environ = os.environ if environ is None else environ
    if (sys.platform if platform is None else platform) != "linux":
        return None
    display = environ.get("WAYLAND_DISPLAY")
    if not display:
        return None
    if os.path.isabs(display):
        path = display
    elif environ.get("XDG_RUNTIME_DIR"):
        path = os.path.join(environ["XDG_RUNTIME_DIR"], display)
    else:
        return None
    return "wayland" if exists(path) else None


class Session:
    """The ``CefApp``, the ``JavascriptBridge`` and the ``MessagePump`` of an application.

    CEF says (from any of its threads) when it wants to run; ``adapter.post`` brings that into the main thread
    and ``adapter.call_later`` carries the deadline, so there is no polling. One browser (one ``BrowserView``)
    per session for now::

        session = ui.Session(adapter, switches=[("disable-gpu", "")])
        view = ui.BrowserView(adapter)
        view.on_ready = lambda: view.load_url("https://example.org/")
        session.start(widget_or_view)
        ...
        session.shutdown(done=toolkit_quit)
    """

    def __init__(self, adapter, switches=(), cache_path=None):
        """``switches``: Chromium command line switches, ``(name, value)``. Where ``default_ozone_platform()`` says
        ``wayland`` and the application gave no ``ozone-platform`` (or ``ozone-platform-hint``), the session adds it;
        ``switches`` (a list, after this) tells what CEF was given."""
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
        """Start CEF and make the browser of ``target``, a ``BrowserView`` or a ``BrowserWidget`` (its ``on_ready``
        is called when the browser exists)."""
        view = view_of(target)
        self.views = [view]
        self.app.set_client(view.client)
        self.app.initialize(url)
        self.started = True
        self._schedule()

    def shutdown(self, done=None):
        """Close the browsers, wait until CEF has closed them, shut CEF down and call ``done()``."""
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
