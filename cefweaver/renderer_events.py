"""The events of the renderer process, for a Python program that has no Python in the renderer.

The renderer of cefweaver is C++: Python code cannot run there, and V8 values cannot be held. What can be done
is to tell the browser process what happens in the renderer and to let Python react to it. With
``CefApp.enable_renderer_events()`` the renderer sends a process message for

* a JavaScript error that nothing caught (``on_uncaught_exception``: the message, the line of the source, the place
  and the stack),
* the node that has the focus (``on_focused_node_changed``: whether it can be edited, the tag and the bounds, or
  ``None`` when the focus left every node: where an input method or a virtual keyboard should appear),
* a V8 context made or released (``on_context_created``, ``on_context_released``: each frame of a page has one;
  the release of the context of a page that the main frame **leaves** is not told: the renderer is taken down
  and its messages are lost, only the context of the next page comes).

``RendererEvents`` decodes those messages for the ``Client.on_process_message_received`` of the program::

    class MyClient(cefweaver.Client):
        def __init__(self):
            super().__init__()
            self.events = cefweaver.RendererEvents(MyEvents())

        def on_process_message_received(self, browser, frame, source_process, message):
            return self.events.on_process_message_received(browser, frame, source_process, message)

    app.enable_renderer_events()
    app.set_client(MyClient())

The values that come with an event are copies (named tuples), not live objects of the renderer.
"""

from typing import NamedTuple

MESSAGE = "cefweaver-renderer-event"          # the name of the process message (native/cefwrapper/bridge.h)


class StackFrame(NamedTuple):
    """A frame of the stack of a JavaScript error."""
    function_name: str
    script_name: str
    line: int
    column: int


class UncaughtException(NamedTuple):
    """A JavaScript error that nothing caught. ``stack`` is empty unless
    ``CefApp.settings.uncaught_exception_stack_size`` is above 0 (``enable_renderer_events()`` sets it)."""
    message: str
    source_line: str
    script_name: str
    line: int
    start_column: int
    end_column: int
    stack: tuple


class FocusedNode(NamedTuple):
    """The node of the page that has the focus: ``bounds`` is ``(x, y, width, height)`` in the page."""
    editable: bool
    tag: str
    bounds: tuple


class RendererEventHandler:
    """The events of the renderer: override what the program needs. ``browser`` is a ``Browser`` and ``frame`` the
    ``Frame`` the event is about. Called on the thread that runs the message loop of the browser process."""

    def on_uncaught_exception(self, browser, frame, exception):
        """A JavaScript error that nothing caught; ``exception`` is an ``UncaughtException``."""

    def on_focused_node_changed(self, browser, frame, node):
        """The focus is on ``node`` (a ``FocusedNode``) or on no node of the page (``None``)."""

    def on_context_created(self, browser, frame, is_main, url):
        """A V8 context was made for ``frame`` (``is_main``: of the main frame; ``url`` of the frame then)."""

    def on_context_released(self, browser, frame, is_main, url):
        """The V8 context of a frame is gone (an iframe was removed). ``frame`` is the main frame of the browser
        (the message goes through it: the frame itself is already replaced); ``is_main`` and ``url`` are those of
        the frame whose context was released. Not sent when the main frame leaves its page."""


class RendererEvents:
    """Decodes the process messages of the renderer and calls a ``RendererEventHandler``."""

    def __init__(self, handler):
        if not isinstance(handler, RendererEventHandler):
            raise TypeError("handler must be a RendererEventHandler, not %s" % type(handler).__name__)
        self.handler = handler

    def on_process_message_received(self, browser, frame, source_process, message):
        """For ``Client.on_process_message_received``: True if the message was an event of the renderer (it is
        then not for anyone else), False for any other message."""
        if message.get_name() != MESSAGE:
            return False
        args = message.get_argument_list()
        kind = args.get_string(0)
        handler = self.handler
        if kind == "uncaught-exception":
            frames = args.get_list(7)
            stack = tuple(StackFrame(item.get_string(0), item.get_string(1), item.get_int(2), item.get_int(3))
                          for item in (frames.get_list(i) for i in range(frames.get_size())))
            handler.on_uncaught_exception(browser, frame, UncaughtException(
                args.get_string(1), args.get_string(2), args.get_string(3), args.get_int(4), args.get_int(5),
                args.get_int(6), stack))
        elif kind == "focused-node":
            node = None
            if args.get_bool(1):
                node = FocusedNode(args.get_bool(2), args.get_string(3),
                                   (args.get_int(4), args.get_int(5), args.get_int(6), args.get_int(7)))
            handler.on_focused_node_changed(browser, frame, node)
        elif kind == "context-created":
            handler.on_context_created(browser, frame, args.get_bool(1), args.get_string(2))
        elif kind == "context-released":
            handler.on_context_released(browser, frame, args.get_bool(1), args.get_string(2))
        else:
            return False
        return True
