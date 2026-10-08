"""Showing a cefweaver browser in a GUI toolkit (experimental: the interface may change).

A toolkit implements ``ToolkitAdapter`` (what it can draw, where it is, how to run something in its loop)
and calls the input methods of ``BrowserView`` from its events; ``Session`` runs CEF in the toolkit's loop.
``cefweaver.ui.headless`` has an adapter without a toolkit.
"""

from .adapter import DragPayload, Frame, ToolkitAdapter
from .session import Session
from .view import BrowserView
from . import keys

__all__ = ["BrowserView", "DragPayload", "Frame", "Session", "ToolkitAdapter", "keys"]
