"""What a toolkit gives ``BrowserView``: the adapter interface and the values that cross it."""

from dataclasses import dataclass, field
from typing import ClassVar, Protocol, runtime_checkable


@dataclass
class Frame:
    """A picture CEF painted: the whole view, or the popup of a ``<select>`` and the like.

    ``buffer`` holds BGRA pixels (``width * height * 4`` bytes, rows from the top) and is valid during the
    ``present()`` call only: copy what is kept. ``dirty_rects`` are the parts that changed since the last
    frame of the same kind (the first frame is all of it). A popup frame has the place of the popup in
    ``rect`` (view coordinates); ``POPUP_HIDDEN`` has no pixels and tells that the popup is gone.
    """

    VIEW: ClassVar[str] = "view"
    POPUP: ClassVar[str] = "popup"
    POPUP_HIDDEN: ClassVar[str] = "popup-hidden"

    kind: str
    width: int = 0
    height: int = 0
    buffer: object = None
    dirty_rects: list = field(default_factory=list)
    rect: object = None
    change: object = None       # a PictureChange: what the view's PictureStore did with the frame (for adapters that wrap its pixels)


@dataclass
class DragPayload:
    """What the page drags out, for a toolkit that starts a drag of its own (``start_drag_out``)."""

    text: str = ""
    html: str = ""
    url: str = ""
    files: list = field(default_factory=list)
    x: int = 0                  # where in the view the page started the drag
    y: int = 0
    raw: object = None          # the cefweaver.DragData


@runtime_checkable
class ToolkitAdapter(Protocol):
    """The required part. A toolkit implements these and calls the input methods of ``BrowserView``.

    Everything else is optional; an adapter that has the method (and, for the ones that change how the view
    behaves, names the capability in ``capabilities``) gets the feature:

    ``ui.Session`` needs of the toolkit only ``post`` and ``call_later``, so a loop object with these two can
    start CEF before any widget (and its adapter) exists.

    ``set_cursor(cursor_type)``      show the cursor CEF wants (a ``types.CursorType``)
    ``clipboard_get()``, ``clipboard_set(text)``   the toolkit's text clipboard; ``Ctrl+C``, ``Ctrl+X`` and
                                     ``Ctrl+V`` are done by the view with them. Name ``"native_clipboard"``
                                     in ``capabilities`` if CEF can do them itself (it could on GTK 3)
    ``set_ime_rect(x, y, w, h)``     where the input method puts its candidate window
    ``start_drag_out(payload, allowed)``   start a drag of the toolkit (capability ``"drag_out"``); without
                                     it the view carries the drag out itself, inside the page only
    ``drag_start``                   an attribute: when the toolkit can start its drag. ``"immediate"`` (the
                                     default; ``start_drag_out`` returns whether it started), ``"posted"``
                                     (from the loop, once CEF's callback is over: Qt) or ``"on_motion"`` (with
                                     the next move of the pointer, button down: wx on GTK). The call may
                                     run until the drag is over; then ``view.drag_out_finished`` follows
    ``drag_operation_changed(operation)``  CEF's answer to a drag over the view arrives later
    """

    def view_size(self) -> tuple: ...       # (width, height) of the view, in logical pixels
    def scale(self) -> float: ...           # device pixels per logical pixel
    def screen_origin(self) -> tuple: ...   # (x, y) of the view's top left corner on the screen
    def screen_size(self) -> tuple: ...     # (width, height) of the screen
    def present(self, frame: Frame) -> None: ...
    def post(self, function) -> None: ...   # run function in the toolkit's main thread; callable from any thread
    def call_later(self, seconds: float, function) -> object: ...   # in the main thread; may return an object with cancel()
