"""A message pump for applications with their own event loop, such as a GUI toolkit.

With ``CefApp.settings.external_message_pump`` set, CEF reports through
``AppHandler.on_schedule_message_pump_work()``, on any thread, when
``CefApp.do_message_loop_work()`` should run. :class:`MessagePump` implements the scheduling
protocol, so that a toolkit only needs a timer:

* A request replaces the pending one (``delay_ms <= 0`` means now).
* The interval between two runs never exceeds 1/30 s.

Example::

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
#: float: The longest wait between two message loop runs, in seconds (1/30).
MAX_DELAY = 1.0 / 30.0


class MessagePump(AppHandler):
    """An ``AppHandler`` that schedules ``do_message_loop_work()`` as CEF requests.

    Construction sets ``app.settings.external_message_pump`` and installs the pump as the app
    handler of ``app``.

    Args:
        app (CefApp): The application; it must not be initialized yet.
        wake (callable, optional): Called as ``wake(delay)`` each time CEF requests work, with
            the seconds until the next run. It may be called from any thread.
    """

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
        """Record CEF's request for a message loop run.

        Args:
            delay_ms (int): Milliseconds until the run; zero or less means now.
        """
        delay = min(max(delay_ms, 0) / 1000.0, MAX_DELAY)
        with self._lock:
            self._due = time.monotonic() + delay
            self._requests += 1
        if self._wake is not None:
            self._wake(delay)

    def timeout(self):
        """Return the seconds until the next run is due.

        Returns:
            float: The wait, from 0.0 (due now) to ``MAX_DELAY``.
        """
        with self._lock:
            return max(0.0, self._due - time.monotonic())

    def run(self):
        """Run ``do_message_loop_work()`` if it is due.

        Returns:
            bool: ``True`` if the message loop ran, ``False`` if nothing was due.

        Note:
            Call on the thread that called ``initialize()``.
        """
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
