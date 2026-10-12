"""Show a cefweaver browser in a GUI toolkit (experimental; the interface may change).

A toolkit implements :class:`ToolkitAdapter` and calls the input methods of
:class:`BrowserView` from its events. :class:`Session` runs CEF in the toolkit's event loop.
:mod:`cefweaver.ui.headless` provides an adapter that needs no toolkit.
"""

from .adapter import DragPayload, Frame, ToolkitAdapter
from .picture import PictureChange, PictureStore, write_png
from .session import Session
from .tables import CursorTable, EventModifiers, KeyTable, MaskModifiers, NamedModifiers, function_range
from .view import BrowserView
from .widget import BrowserWidget
from . import audio, keys, menu, permissions

__all__ = ["BrowserView", "BrowserWidget", "CursorTable", "DragPayload", "EventModifiers", "Frame", "KeyTable", "MaskModifiers", "menu", "permissions",
           "NamedModifiers", "PictureChange", "PictureStore", "Session", "write_png", "ToolkitAdapter", "audio", "function_range", "keys"]
