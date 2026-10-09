"""Showing a cefweaver browser in a GUI toolkit (experimental: the interface may change).

A toolkit implements ``ToolkitAdapter`` (what it can draw, where it is, how to run something in its loop)
and calls the input methods of ``BrowserView`` from its events; ``Session`` runs CEF in the toolkit's loop.
``cefweaver.ui.headless`` has an adapter without a toolkit.
"""

from .adapter import DragPayload, Frame, ToolkitAdapter
from .picture import PictureChange, PictureStore, write_png
from .session import Session
from .tables import CursorTable, EventModifiers, KeyTable, MaskModifiers, NamedModifiers, function_range
from .view import BrowserView
from .widget import BrowserWidget
from . import audio, keys, permissions

__all__ = ["BrowserView", "BrowserWidget", "CursorTable", "DragPayload", "EventModifiers", "Frame", "KeyTable", "MaskModifiers", "permissions",
           "NamedModifiers", "PictureChange", "PictureStore", "Session", "write_png", "ToolkitAdapter", "audio", "function_range", "keys"]
