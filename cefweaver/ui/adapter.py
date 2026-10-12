"""The adapter interface a toolkit implements for :class:`~cefweaver.ui.BrowserView`, and the values that cross it."""

from dataclasses import dataclass, field
from typing import ClassVar, Protocol, runtime_checkable


@dataclass
class Frame:
    """A picture CEF painted: the whole view, or a popup such as the list of a ``<select>``.

    ``buffer`` is valid only during the :meth:`~cefweaver.ui.ToolkitAdapter.present` call; copy the pixels
    that are kept. A frame of kind ``POPUP_HIDDEN`` has no pixels and signals that the popup is gone.

    Attributes:
        VIEW (str): Value of ``kind`` for a frame of the whole view.
        POPUP (str): Value of ``kind`` for a frame of a popup.
        POPUP_HIDDEN (str): Value of ``kind`` for the end of a popup.
        kind (str): One of ``VIEW``, ``POPUP`` and ``POPUP_HIDDEN``.
        width (int): Width of the picture in pixels.
        height (int): Height of the picture in pixels.
        buffer (object): BGRA pixels, ``width * height * 4`` bytes, rows from the top.
        dirty_rects (list): The rectangles that changed since the last frame of the same kind. The first
            frame is all of it.
        rect (object): For a popup frame, the place of the popup in view coordinates; otherwise ``None``.
        change (object): The ``PictureChange`` that the view's picture store made of this frame, for adapters
            that wrap its pixels.
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
    change: object = None


@dataclass
class DragPayload:
    """What the page drags out, passed to ``start_drag_out`` of a toolkit that starts the drag itself.

    Attributes:
        text (str): The dragged text, or ``""``.
        html (str): The dragged HTML fragment, or ``""``.
        url (str): The dragged link URL, or ``""``.
        files (list): Paths of the dragged files.
        x (int): X coordinate in the view where the page started the drag.
        y (int): Y coordinate in the view where the page started the drag.
        raw (object): The :class:`~cefweaver.DragData` of the drag.
    """

    text: str = ""
    html: str = ""
    url: str = ""
    files: list = field(default_factory=list)
    x: int = 0                  # where in the view the page started the drag
    y: int = 0
    raw: object = None          # the cefweaver.DragData


@runtime_checkable
class ToolkitAdapter(Protocol):
    """The methods a toolkit adapter must have.

    A toolkit implements these structurally (no inheritance) and calls the input methods of
    :class:`~cefweaver.ui.BrowserView`. The optional members below are used if the adapter has them. Those
    that change how the view behaves must also be named in the ``capabilities`` attribute (a collection of
    strings) of the adapter.

    :class:`~cefweaver.ui.Session` needs only ``post`` and ``call_later``, so an object with these two can
    start CEF before any widget exists.

    Optional members:

    * ``set_cursor(cursor_type)``: show the cursor CEF wants (a :class:`~cefweaver.types.CursorType`).
    * ``clipboard_get()`` and ``clipboard_set(text)``: the text clipboard of the toolkit. The view uses them
      for Ctrl+C, Ctrl+X and Ctrl+V (Command on macOS). Name ``"native_clipboard"`` in ``capabilities`` if
      CEF can do these itself.
    * ``set_ime_rect(x, y, w, h)``: where the input method puts its candidate window.
    * ``start_drag_out(payload, allowed)``: start a drag of the toolkit for a drag from the page (capability
      ``"drag_out"``). ``payload`` is a :class:`~cefweaver.ui.DragPayload`. Return whether the drag started.
      The call may run until the drag is over; then call
      :meth:`~cefweaver.ui.BrowserView.drag_out_finished`. Without the capability the view carries the
      drag out itself, inside the page only.
    * ``drag_start``: an attribute telling when the toolkit can start its drag. ``"immediate"`` (the
      default), ``"posted"`` (from the loop, after the callback of CEF is over) or ``"on_motion"`` (with the
      next pointer move, button down).
    * ``drag_operation_changed(operation)``: CEF's answer to a drag over the view.
    * ``show_menu(items, x, y, answer)``: show a context menu; without it CEF shows none.
    * ``audio_sink()``: return a sink for ``audio="auto"`` or ``None``.
    * ``release()``: let go of resources; called by :meth:`~cefweaver.ui.Session.shutdown`.
    """

    def view_size(self) -> tuple:
        """Return the size of the view.

        Returns:
            tuple: ``(width, height)`` in logical pixels.
        """
        ...

    def scale(self) -> float:
        """Return the device pixels per logical pixel.

        Returns:
            float: The scale factor.
        """
        ...

    def screen_origin(self) -> tuple:
        """Return the position of the view's top left corner on the screen.

        Returns:
            tuple: ``(x, y)`` in screen coordinates.
        """
        ...

    def screen_size(self) -> tuple:
        """Return the size of the screen.

        Returns:
            tuple: ``(width, height)``.
        """
        ...

    def present(self, frame: Frame) -> None:
        """Show a picture that CEF painted.

        Args:
            frame (Frame): The picture. Its ``buffer`` is valid only during this call.
        """
        ...

    def post(self, function) -> None:
        """Run a function in the main thread of the toolkit.

        Args:
            function (callable): Called without arguments.

        Note:
            Callable from any thread.
        """
        ...

    def call_later(self, seconds: float, function) -> object:
        """Run a function in the main thread of the toolkit after a delay.

        Args:
            seconds (float): The delay in seconds.
            function (callable): Called without arguments.

        Returns:
            object: May be an object with a ``cancel()`` method, which cancels the call.

        Note:
            Called in the main thread.
        """
        ...
