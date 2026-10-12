"""A toolkit-free adapter for scripts, tests and screenshots.

:class:`HeadlessAdapter` keeps the last picture of a view and runs its own event loop.

Example::

    adapter = HeadlessAdapter(size=(800, 600))
    session = ui.Session(adapter)
    view = ui.BrowserView(adapter)
    view.on_ready = lambda: view.load_url("https://example.org/")
    session.start(view)
    adapter.run_until(lambda: adapter.picture is not None, "the first picture")
    adapter.save_png("page.png")
"""

import heapq
import itertools
import queue
import time

from .adapter import Frame
from .picture import write_png


class HeadlessAdapter:
    """A :class:`~cefweaver.ui.ToolkitAdapter` without a toolkit.

    Functions passed to :meth:`post` and :meth:`call_later` run in :meth:`step`, :meth:`run_until`
    and :meth:`run_for`, on the thread that calls them.

    Args:
        size (tuple, optional): The ``(width, height)`` of the view in logical pixels. Defaults
            to ``(800, 600)``.
        scale (float, optional): The device pixels per logical pixel. Defaults to 1.0.
        screen_size (tuple, optional): The ``(width, height)`` of the screen. Defaults to
            ``(1920, 1080)``.

    Attributes:
        capabilities (frozenset): The adapter's capabilities; empty.
        size (tuple): The ``(width, height)`` of the view.
        picture (tuple or None): ``(width, height, bytes)`` of the last view frame in BGRA, or
            ``None`` before the first.
        popup (tuple or None): ``(width, height, bytes, rect)`` of the shown popup in BGRA, or
            ``None`` if no popup is shown.
        frames (int): The number of view frames presented.
    """

    capabilities = frozenset()

    def __init__(self, size=(800, 600), scale=1.0, screen_size=(1920, 1080)):
        self.size, self.factor, self.screen = tuple(size), float(scale), tuple(screen_size)
        self.picture = None             # (width, height, bytes) of the last frame of the view, BGRA
        self.popup = None               # the same for the popup that is shown, with its rect: (w, h, bytes, rect)
        self.frames = 0
        self._posted = queue.Queue()
        self._timers = []
        self._sequence = itertools.count()

    # -- the interface ---------------------------------------------------------------------------

    def view_size(self):
        """Return the size of the view as ``(width, height)``."""
        return self.size

    def scale(self):
        """Return the device pixels per logical pixel."""
        return self.factor

    def screen_origin(self):
        """Return the position of the view on the screen, always ``(0, 0)``."""
        return (0, 0)

    def screen_size(self):
        """Return the size of the screen as ``(width, height)``."""
        return self.screen

    def present(self, frame):
        """Store a painted picture in ``picture`` or ``popup``.

        Args:
            frame (Frame): The picture; a ``POPUP_HIDDEN`` frame clears ``popup``.
        """
        if frame.kind == Frame.VIEW:
            self.picture = (frame.width, frame.height, bytes(frame.buffer))
            self.frames += 1
        elif frame.kind == Frame.POPUP:
            self.popup = (frame.width, frame.height, bytes(frame.buffer), frame.rect)
        else:
            self.popup = None

    def post(self, function):
        """Queue a function to run in the loop; may be called from any thread.

        Args:
            function (callable): Called without arguments.
        """
        self._posted.put(function)

    def call_later(self, seconds, function):
        """Run a function in the loop after a delay.

        Args:
            seconds (float): The delay in seconds.
            function (callable): Called without arguments.

        Returns:
            object: A timer with a ``cancel()`` method.
        """
        timer = _Timer(function)
        heapq.heappush(self._timers, (time.monotonic() + seconds, next(self._sequence), timer))
        return timer

    # -- the loop --------------------------------------------------------------------------------

    def step(self, wait=0.05):
        """Run the timers that are due and the queued functions.

        Args:
            wait (float, optional): The longest time to wait for something to run, in
                seconds. Defaults to 0.05.
        """
        now = time.monotonic()
        while self._timers and self._timers[0][0] <= now:
            _, _, timer = heapq.heappop(self._timers)
            timer.run()
        until = self._timers[0][0] - time.monotonic() if self._timers else wait
        try:
            function = self._posted.get(timeout=max(0.0, min(wait, until)))
        except queue.Empty:
            return
        function()
        while True:
            try:
                self._posted.get_nowait()()
            except queue.Empty:
                return

    def run_until(self, condition, what, timeout=30):
        """Run the loop until a condition is true.

        Args:
            condition (callable): Called without arguments; the loop ends when it returns true.
            what (str): A description of the awaited event, used in the error message.
            timeout (float, optional): The limit in seconds. Defaults to 30.

        Raises:
            TimeoutError: If the condition is not true within ``timeout``.
        """
        end = time.monotonic() + timeout
        while not condition():
            if time.monotonic() > end:
                raise TimeoutError("timed out waiting for " + what)
            self.step()

    def run_for(self, seconds):
        """Run the loop for a fixed time.

        Args:
            seconds (float): The duration in seconds.
        """
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            self.step(0.01)

    # -- pictures --------------------------------------------------------------------------------

    def save_png(self, path):
        """Write the last picture of the view as a PNG file.

        Args:
            path (str): The file to write.

        Raises:
            RuntimeError: If no picture has been presented yet.
        """
        if self.picture is None:
            raise RuntimeError("no picture yet")
        width, height, bgra = self.picture
        write_png(path, width, height, bgra)

    def pixel(self, x, y):
        """Return a pixel of the last picture.

        Args:
            x (int): The column.
            y (int): The row.

        Returns:
            tuple: ``(red, green, blue, alpha)``.

        Raises:
            TypeError: If no picture has been presented yet.
        """
        width, _, bgra = self.picture[0], self.picture[1], self.picture[2]
        b, g, r, a = bgra[(y * width + x) * 4:(y * width + x) * 4 + 4]
        return r, g, b, a


class _Timer:
    def __init__(self, function):
        self.function = function

    def cancel(self):
        self.function = None

    def run(self):
        if self.function is not None:
            self.function()
