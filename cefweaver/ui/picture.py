"""Storage of the view and popup pixels between frames."""

import struct
import zlib

import cefweaver

from .adapter import Frame


def write_png(path, width, height, bgra):
    """Write BGRA pixels as an 8-bit RGBA PNG file.

    Args:
        path (str): The file to write.
        width (int): The width in pixels.
        height (int): The height in pixels.
        bgra (bytes): ``width * height * 4`` bytes, rows from the top.
    """
    rows = []
    for y in range(height):
        row = bytearray(bgra[y * width * 4:(y + 1) * width * 4])
        row[0::4], row[2::4] = row[2::4], row[0::4]             # BGRA to RGBA
        rows.append(b"\x00" + bytes(row))

    def chunk(kind, data):
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(b"".join(rows))) + chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)


class PictureChange:
    """The result of :meth:`PictureStore.apply`.

    Args:
        kind (str): The kind of change.
        rects (iterable of Rect, optional): The changed rectangles.

    Attributes:
        kind (str): ``PictureStore.NEW``, ``DIRTY``, ``POPUP`` or ``POPUP_HIDDEN``.
        rects (list of Rect): For ``DIRTY``, the changed rectangles in device pixels, clipped
            to the picture; for ``NEW``, the whole picture; otherwise empty.
    """

    def __init__(self, kind, rects=()):
        self.kind, self.rects = kind, list(rects)


class PictureStore:
    """A copy of the painted pixels, updated in place frame by frame.

    Meant for toolkits that wrap pixels without copying them (cairo, ``QImage``) and need to
    know what changed. CEF's buffer is valid only during ``present()``. A frame of the same
    size updates ``pixels`` in place, only in the dirty rows, so a surface wrapped around
    ``pixels`` stays valid. A frame of another size allocates new pixels and yields ``NEW``;
    the toolkit must then create a new surface.

    Attributes:
        pixels (bytearray or None): The view pixels in BGRA, ``width * height * 4`` bytes, or
            ``None`` before the first frame.
        size (tuple): ``(width, height)`` of ``pixels``.
        popup_pixels (bytearray or None): The popup pixels in BGRA, or ``None`` if no popup is
            shown.
        popup_size (tuple): ``(width, height)`` of the popup.
        popup_rect (Rect or None): The position of the popup in the view.
        NEW (str): Kind of change: new pixels were allocated.
        DIRTY (str): Kind of change: rectangles of ``pixels`` changed.
        POPUP (str): Kind of change: the popup was replaced.
        POPUP_HIDDEN (str): Kind of change: the popup was hidden.
    """

    NEW, DIRTY, POPUP, POPUP_HIDDEN = "new", "dirty", "popup", "popup-hidden"

    def __init__(self):
        self.pixels = None
        self.size = (0, 0)
        self.popup_pixels = None
        self.popup_size = (0, 0)
        self.popup_rect = None

    def save_png(self, path):
        """Save the view picture as a PNG file.

        Args:
            path (str): The file to write.

        Returns:
            bool: ``True`` if written, ``False`` if there is no picture yet.
        """
        if self.pixels is None:
            return False
        write_png(path, self.size[0], self.size[1], self.pixels)
        return True

    def apply(self, frame):
        """Apply a painted frame to the stored pixels.

        Args:
            frame (Frame): The frame, from ``ToolkitAdapter.present()``.

        Returns:
            PictureChange: What changed.
        """
        if frame.kind == Frame.POPUP_HIDDEN:
            self.popup_pixels = None
            return PictureChange(self.POPUP_HIDDEN)
        if frame.kind == Frame.POPUP:
            self.popup_pixels = bytearray(frame.buffer)
            self.popup_size = (frame.width, frame.height)
            self.popup_rect = frame.rect
            return PictureChange(self.POPUP)
        width, height = frame.width, frame.height
        if self.pixels is None or self.size != (width, height):
            self.pixels = bytearray(frame.buffer)
            self.size = (width, height)
            return PictureChange(self.NEW, [cefweaver.Rect(0, 0, width, height)])
        stride, cut = width * 4, []
        for rect in frame.dirty_rects:
            x0, x1 = max(0, rect.x), min(width, rect.x + rect.width)
            y0, y1 = max(0, rect.y), min(height, rect.y + rect.height)
            if x1 <= x0 or y1 <= y0:
                continue
            for y in range(y0, y1):
                start = y * stride + x0 * 4
                self.pixels[start:start + (x1 - x0) * 4] = frame.buffer[start:start + (x1 - x0) * 4]
            cut.append(cefweaver.Rect(x0, y0, x1 - x0, y1 - y0))
        return PictureChange(self.DIRTY, cut)

