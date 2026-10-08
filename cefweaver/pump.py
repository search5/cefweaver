"""A message pump for an application with an event loop of its own (a GUI toolkit).

With ``CefApp.settings.external_message_pump`` CEF tells the application through
``AppHandler.on_schedule_message_pump_work()``, on any of its threads, when
``CefApp.do_message_loop_work()`` should run. The protocol (as CEF's own cefclient does it):

* a request replaces the pending one (``delay_ms <= 0``: now);
* the application never waits longer than 1/30 s between two runs, because not every kind of
  work is announced.

``MessagePump`` keeps that protocol so that a toolkit only needs a timer::

    pump = cefweaver.MessagePump(app, wake=lambda delay: toolkit_call_later(delay, tick))
    app.initialize(url)
    def tick():
        pump.run()                         # on the thread that called initialize()
        toolkit_call_later(pump.timeout(), tick)
"""

import threading
import time

from ._cefweaver import AppHandler

# The longest wait between two runs, as cefclient's kMaxTimerDelay (30 fps).
MAX_DELAY = 1.0 / 30.0


class MessagePump(AppHandler):
    """Gives CEF the message loop when it asks for it. It is the ``AppHandler`` of ``app``, which
    must not be initialized yet; ``wake(delay)`` (optional) is called with the seconds until the
    next run each time CEF asks, from any thread, so that a sleeping event loop can adjust."""

    def __init__(self, app, wake=None):
        super().__init__()
        self._app = app
        self._wake = wake
        self._lock = threading.Lock()
        self._due = time.monotonic()      # the first run is due at once
        self._requests = 0                # counts what CEF asked, to see a request made during a run
        self._running = False
        app.settings.external_message_pump = True
        app.set_app_handler(self)

    def on_schedule_message_pump_work(self, delay_ms):
        delay = min(max(delay_ms, 0) / 1000.0, MAX_DELAY)
        with self._lock:
            self._due = time.monotonic() + delay
            self._requests += 1
        if self._wake is not None:
            self._wake(delay)

    def timeout(self):
        """Seconds until the next run is due (0.0: now). Never more than 1/30."""
        with self._lock:
            return max(0.0, self._due - time.monotonic())

    def run(self):
        """Run ``do_message_loop_work()`` if it is due and return True; otherwise do nothing and
        return False. Call it on the thread that called ``initialize()``."""
        with self._lock:
            if self._running or self._due > time.monotonic():
                return False
            self._running = True
            before = self._requests
        try:
            self._app.do_message_loop_work()
        finally:
            with self._lock:
                self._running = False
                if self._requests == before:   # CEF asked for nothing meanwhile: the fall-back timer
                    self._due = time.monotonic() + MAX_DELAY
        return True
