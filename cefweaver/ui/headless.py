"""``HeadlessAdapter``: a ``ToolkitAdapter`` without a toolkit, for scripts, tests and screenshots.

It keeps the last picture of the view and runs its own loop (``run_until``): the calls ``post`` and
``call_later`` that CEF makes go into a queue and a timer list that the loop serves::

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
import struct
import time
import zlib

from .adapter import Frame


class HeadlessAdapter:
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
        return self.size

    def scale(self):
        return self.factor

    def screen_origin(self):
        return (0, 0)

    def screen_size(self):
        return self.screen

    def present(self, frame):
        if frame.kind == Frame.VIEW:
            self.picture = (frame.width, frame.height, bytes(frame.buffer))
            self.frames += 1
        elif frame.kind == Frame.POPUP:
            self.popup = (frame.width, frame.height, bytes(frame.buffer), frame.rect)
        else:
            self.popup = None

    def post(self, function):
        self._posted.put(function)

    def call_later(self, seconds, function):
        timer = _Timer(function)
        heapq.heappush(self._timers, (time.monotonic() + seconds, next(self._sequence), timer))
        return timer

    # -- the loop --------------------------------------------------------------------------------

    def step(self, wait=0.05):
        """Run what is due, waiting up to ``wait`` seconds for something to run."""
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
        """Run the loop until ``condition()``; a ``TimeoutError`` names what was awaited."""
        end = time.monotonic() + timeout
        while not condition():
            if time.monotonic() > end:
                raise TimeoutError("timed out waiting for " + what)
            self.step()

    def run_for(self, seconds):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            self.step(0.01)

    # -- pictures --------------------------------------------------------------------------------

    def save_png(self, path):
        """Write the last picture of the view as a PNG file (no dependencies)."""
        if self.picture is None:
            raise RuntimeError("no picture yet")
        width, height, bgra = self.picture
        rows = []
        for y in range(height):
            row = bytearray(bgra[y * width * 4:(y + 1) * width * 4])
            row[0::4], row[2::4] = row[2::4], row[0::4]         # BGRA to RGBA
            rows.append(b"\x00" + bytes(row))

        def chunk(kind, data):
            body = kind + data
            return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))
        png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        png += chunk(b"IDAT", zlib.compress(b"".join(rows))) + chunk(b"IEND", b"")
        with open(path, "wb") as f:
            f.write(png)

    def pixel(self, x, y):
        """(red, green, blue, alpha) of a pixel of the last picture."""
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
