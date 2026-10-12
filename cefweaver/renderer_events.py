"""Events of the renderer process, delivered to Python in the browser process.

The renderer is C++ and runs no Python. With ``CefApp.enable_renderer_events()`` it sends
process messages that :class:`RendererEvents` decodes and passes to a
:class:`RendererEventHandler`:

* An uncaught JavaScript error (``on_uncaught_exception``).
* A change of the focused node (``on_focused_node_changed``).
* The creation and release of a V8 context (``on_context_created``,
  ``on_context_released``).

The values delivered with an event are copies (named tuples), not live renderer objects.

Example::

    class MyClient(cefweaver.Client):
        def __init__(self):
            super().__init__()
            self.events = cefweaver.RendererEvents(MyEvents())

        def on_process_message_received(self, browser, frame, source_process, message):
            return self.events.on_process_message_received(browser, frame, source_process, message)

    app.enable_renderer_events()
    app.set_client(MyClient())
"""

from typing import NamedTuple

MESSAGE = "cefweaver-renderer-event"          # the name of the process message (native/cefwrapper/bridge.h)


class StackFrame(NamedTuple):
    """A frame of the stack of a JavaScript error.

    Attributes:
        function_name (str): The function name.
        script_name (str): The script name.
        line (int): The line number.
        column (int): The column number.
    """
    function_name: str
    script_name: str
    line: int
    column: int


class UncaughtException(NamedTuple):
    """A JavaScript error that nothing caught.

    Attributes:
        message (str): The error message.
        source_line (str): The source line of the error.
        script_name (str): The script name.
        line (int): The line number.
        start_column (int): The start column of the error in the line.
        end_column (int): The end column of the error in the line.
        stack (tuple of StackFrame): The stack trace. Empty unless
            ``CefApp.settings.uncaught_exception_stack_size`` is above 0, which
            ``enable_renderer_events()`` sets.
    """
    message: str
    source_line: str
    script_name: str
    line: int
    start_column: int
    end_column: int
    stack: tuple


class FocusedNode(NamedTuple):
    """The node of the page that has the focus.

    Attributes:
        editable (bool): Whether the node can be edited.
        tag (str): The tag name.
        bounds (tuple of int): ``(x, y, width, height)`` in the page.
    """
    editable: bool
    tag: str
    bounds: tuple


class RendererEventHandler:
    """Base class for the handlers of renderer events; override the methods needed.

    In every method ``browser`` is the :class:`~cefweaver.Browser` and ``frame`` the
    :class:`~cefweaver.Frame` that the event is about.

    Note:
        Called on the thread that runs the message loop of the browser process.
    """

    def on_uncaught_exception(self, browser, frame, exception):
        """Handle a JavaScript error that nothing caught.

        Args:
            browser (Browser): The browser.
            frame (cefweaver.Frame): The frame.
            exception (UncaughtException): The error.
        """

    def on_focused_node_changed(self, browser, frame, node):
        """Handle a change of the focused node.

        Args:
            browser (Browser): The browser.
            frame (cefweaver.Frame): The frame.
            node (FocusedNode or None): The focused node, or ``None`` if no node of the page
                has the focus.
        """

    def on_context_created(self, browser, frame, is_main, url):
        """Handle the creation of a V8 context.

        Args:
            browser (Browser): The browser.
            frame (cefweaver.Frame): The frame the context was created for.
            is_main (bool): Whether the frame is the main frame.
            url (str): The URL of the frame.
        """

    def on_context_released(self, browser, frame, is_main, url):
        """Handle the release of a V8 context (e.g. a removed iframe).

        Not sent when the main frame leaves its page.

        Args:
            browser (Browser): The browser.
            frame (cefweaver.Frame): The main frame of the browser, not the frame whose context was
                released.
            is_main (bool): Whether the frame whose context was released is a main frame.
            url (str): The URL of the frame whose context was released.
        """


class RendererEvents:
    """Decode renderer process messages and call a :class:`RendererEventHandler`.

    Args:
        handler (RendererEventHandler): The handler to call.

    Attributes:
        handler (RendererEventHandler): The handler to call.

    Raises:
        TypeError: If ``handler`` is not a :class:`RendererEventHandler`.
    """

    def __init__(self, handler):
        if not isinstance(handler, RendererEventHandler):
            raise TypeError("handler must be a RendererEventHandler, not %s" % type(handler).__name__)
        self.handler = handler

    def on_process_message_received(self, browser, frame, source_process, message):
        """Decode a process message; call it from ``Client.on_process_message_received``.

        Args:
            browser (Browser): The browser.
            frame (cefweaver.Frame): The frame.
            source_process (ProcessId): The process that sent the message.
            message (ProcessMessage): The message.

        Returns:
            bool: ``True`` if the message was a renderer event, which is then handled;
            ``False`` for any other message.
        """
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
