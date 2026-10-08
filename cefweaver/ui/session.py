"""``Session``: CEF for a toolkit application, driven from the toolkit's event loop."""

import cefweaver


class Session:
    """The ``CefApp``, the ``JavascriptBridge`` and the ``MessagePump`` of an application.

    CEF says (from any of its threads) when it wants to run; ``adapter.post`` brings that into the main thread
    and ``adapter.call_later`` carries the deadline, so there is no polling. One browser (one ``BrowserView``)
    per session for now::

        session = ui.Session(adapter, switches=[("disable-gpu", "")])
        view = ui.BrowserView(adapter)
        view.on_ready = lambda: view.load_url("https://example.org/")
        session.start(view)
        ...
        session.shutdown(done=toolkit_quit)
    """

    def __init__(self, adapter, switches=(), cache_path=None):
        self.adapter = adapter
        self.app = cefweaver.CefApp()
        self.app.offscreen = True
        self.app.transparent = False
        if cache_path:
            self.app.set_cache_path(cache_path)
        for name, value in switches:
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

    def start(self, view, url="about:blank"):
        """Start CEF and make the browser of ``view`` (``view.on_ready`` is called when it exists)."""
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
            if done:
                done()
        self.adapter.call_later(0.02, finish)
