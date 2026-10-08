"""``PictureStore``: the pixels of the view and of the popup, kept between frames."""

import struct
import zlib

import cefweaver

from .adapter import Frame


def write_png(path, width, height, bgra):
    """Write BGRA pixels (``width * height * 4`` bytes, rows from the top) as an 8 bit RGBA PNG file. Needs no
    imaging library."""
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
    """What ``PictureStore.apply`` did: ``kind`` (``NEW``, ``DIRTY``, ``POPUP``, ``POPUP_HIDDEN``) and, for
    ``DIRTY``, the rectangles that changed (device pixels, cut to the picture)."""

    def __init__(self, kind, rects=()):
        self.kind, self.rects = kind, list(rects)


class PictureStore:
    """For a toolkit that wraps the pixels without copying them (cairo, ``QImage``) and wants to know what changed.

    CEF's buffer is valid during ``present()`` only. The store keeps its own copy as ``pixels`` (BGRA,
    ``width * height * 4`` bytes) and changes it in place for a frame of the same size, only in the dirty
    rows, so that a surface made around ``pixels`` stays valid. A frame of another size makes new pixels:
    ``NEW``, and the toolkit makes a new surface. The popup is kept the same way (``popup_pixels``,
    ``popup_size``, ``popup_rect``), whole.
    """

    NEW, DIRTY, POPUP, POPUP_HIDDEN = "new", "dirty", "popup", "popup-hidden"

    def __init__(self):
        self.pixels = None
        self.size = (0, 0)
        self.popup_pixels = None
        self.popup_size = (0, 0)
        self.popup_rect = None

    def save_png(self, path):
        """Save the picture as a PNG file; False if there is none yet."""
        if self.pixels is None:
            return False
        write_png(path, self.size[0], self.size[1], self.pixels)
        return True

    def apply(self, frame):
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

