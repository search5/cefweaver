"""JSON calls between JavaScript and Python over the message router.

:class:`JavascriptBridge` exposes Python functions to pages as ``window.<name>(...)``, which
return a ``Promise``. Arguments and results are JSON values (``None``, ``bool``, numbers,
``str``, lists and dicts). A page function passed as an argument arrives as a
:class:`JsCallback`. In the other direction, :meth:`JavascriptBridge.execute_function` calls a
page function and :meth:`JavascriptBridge.evaluate` evaluates an expression.

Calls are answered on the thread that called ``CefApp.initialize()``, from
``do_message_loop_work()``.
"""

import json
import sys

from . import types
from ._cefweaver import ProcessMessage, QueryHandler, Task, post_delayed_task

_RESERVED = frozenset("""break case catch class const continue debugger default delete do else enum export
extends false finally for function if import in instanceof new null return super switch this throw true
try typeof var void while with yield let static await implements interface package private protected
public""".split())


class JsCallback:
    """A JavaScript function that a page passed to Python as an argument.

    Calling it after its frame is gone or after :meth:`release` does nothing.
    """

    __slots__ = ("_frame", "_id")

    def __init__(self, frame, callback_id):
        self._frame = frame
        self._id = callback_id

    def call(self, *args):
        """Call the page function in the frame it came from.

        Args:
            *args: The arguments; JSON-serializable values (``NaN`` and infinities are
                rejected).

        Raises:
            ValueError: If an argument is not JSON-serializable as strict JSON.
            TypeError: If an argument is not JSON-serializable.
        """
        if self._frame is None or not self._frame.is_valid():
            return
        self._frame.execute_java_script(
            "window.__cefweaverBridge && window.__cefweaverBridge.invoke(%s, %s)"
            % (json.dumps(self._id), json.dumps(list(args), allow_nan=False)), "", 0)

    def release(self):
        """Let the page forget the function. Later calls do nothing."""
        if self._frame is not None and self._frame.is_valid():
            self._frame.execute_java_script(
                "window.__cefweaverBridge && window.__cefweaverBridge.release(%s)" % json.dumps(self._id), "", 0)
        self._frame = None


class _BridgeHandler(QueryHandler):
    def __init__(self, bridge):
        self._bridge = bridge

    def on_query(self, browser, frame, query_id, request, persistent, callback):
        if not request.startswith('{"cefweaver":1'):
            return False  # not the bridge's: the application's handlers get it
        return self._bridge._handle(frame, request, callback)


class _Expire(Task):
    """The end of the wait of one ``evaluate()``: if the answer has not come, its callback gets the timeout."""

    def __init__(self, bridge, number, timeout):
        super().__init__()
        self._bridge, self._number, self._timeout = bridge, number, timeout

    def execute(self):
        function = self._bridge._pending.pop(self._number, None)
        if function is None:
            return                      # it was answered
        try:
            function(None, "TimeoutError: no answer in %g s" % self._timeout)
        except BaseException:
            sys.excepthook(*sys.exc_info())


class JavascriptBridge:
    """The JavaScript bridge of an application.

    Args:
        app (CefApp): The application; it must not be initialized yet.
        origins (list of str, optional): URL prefixes such as ``["https://example.org/"]``.
            Only calls from frames whose URL starts with one of them are answered. The
            default, ``None``, answers every frame.

    Raises:
        TypeError: If ``origins`` is neither ``None`` nor a list of ``str``.
    """

    def __init__(self, app, origins=None):
        if origins is not None and (isinstance(origins, str) or
                                    not all(isinstance(origin, str) for origin in origins)):
            raise TypeError("origins must be a list of str (URL prefixes) or None")
        self._app = app
        self._origins = None if origins is None else tuple(origins)
        self._functions = {}
        self._pending = {}
        self._next = 1
        app.add_query_handler(_BridgeHandler(self), first=True)
        # The pages get window.__cefweaverBridge when this is set, even if nothing is exposed: evaluate()
        # and execute_function() need it, and a program may only want to read the state of a page.
        app._set_bridge_names("[]")

    def expose(self, name, function, with_frame=False):
        """Expose a Python function to pages as ``window.<name>``.

        An exception raised by the function rejects the ``Promise`` with its type and message.

        Args:
            name (str): A JavaScript identifier that is not a reserved word.
            function (callable): Called with the JSON arguments of the page call.
            with_frame (bool, optional): If true, ``function`` receives the calling
                :class:`~cefweaver.Frame` as its first argument. Defaults to ``False``.

        Raises:
            ValueError: If ``name`` is not a valid name or is exposed already.
            TypeError: If ``function`` is not callable.

        Note:
            Call before ``initialize()``.
        """
        if not isinstance(name, str) or not name.isidentifier() or name in _RESERVED:
            raise ValueError("%r is not a name for a JavaScript function" % (name,))
        if not callable(function):
            raise TypeError("function must be callable")
        if name in self._functions:
            raise ValueError("%r is exposed already" % (name,))
        self._functions[name] = (function, bool(with_frame))
        self._app._set_bridge_names(json.dumps(sorted(self._functions)))

    def execute_function(self, frame, path, *args):
        """Call a function of the page, discarding its result.

        Use :meth:`evaluate` to obtain a result.

        Args:
            frame (cefweaver.Frame): The frame whose page defines the function.
            path (str): The dotted path from ``window``, e.g. ``"api.greet"``.
            *args: The arguments; JSON-serializable values.

        Raises:
            ValueError: If ``path`` is not a dotted path of identifiers.
        """
        parts = path.split(".") if isinstance(path, str) else []
        if not parts or not all(part.isidentifier() for part in parts):
            raise ValueError("%r is not the path of a function" % (path,))
        frame.execute_java_script("window.__cefweaverBridge.call(%s, %s)"
                                  % (json.dumps(path), json.dumps(list(args), allow_nan=False)), "", 0)

    def evaluate(self, frame, expression, callback, timeout=30.0):
        """Evaluate a JavaScript expression in a frame.

        ``callback`` is called later from ``do_message_loop_work()``. A ``Promise`` result is
        awaited. If no answer arrives within ``timeout`` seconds, ``callback`` gets the error
        ``"TimeoutError: ..."`` and a later answer is ignored.

        Args:
            frame (cefweaver.Frame): The frame to evaluate in.
            expression (str): The JavaScript expression.
            callback (callable): Called as ``callback(value, error)``. On success ``value`` is
                the JSON value of the result and ``error`` is ``None``; on failure ``value`` is
                ``None`` and ``error`` is the message of the exception.
            timeout (float, optional): Seconds to wait for the answer, or ``None`` to wait
                without limit. Defaults to 30.0.

        Raises:
            TypeError: If ``callback`` is not callable.
            ValueError: If ``timeout`` is neither a positive number nor ``None``.
        """
        if not callable(callback):
            raise TypeError("callback must be callable")
        if timeout is not None and (isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or timeout <= 0):
            raise ValueError("timeout must be a positive number of seconds or None")
        number = self._next
        self._next += 1
        self._pending[number] = callback
        # The renderer runs it with CefV8Context::Eval: a page that forbids eval (CSP, Trusted Types) does not stop it.
        message = ProcessMessage.create("cefweaver-eval")
        arguments = message.get_argument_list()
        arguments.set_size(2)
        arguments.set_int(0, number)
        arguments.set_string(1, expression)
        frame.send_process_message(types.ProcessId.RENDERER, message)
        if timeout is not None:
            post_delayed_task(types.ThreadId.UI, _Expire(self, number, timeout), max(1, int(timeout * 1000)))

    # -- the queries of the pages ----------------------------------------------------------

    def _allowed(self, frame):
        if self._origins is None:
            return True
        url = frame.get_url()
        return any(url.startswith(origin) for origin in self._origins)

    def _handle(self, frame, request, callback):
        try:
            message = json.loads(request)
        except ValueError:
            return False
        if not isinstance(message, dict) or message.get("cefweaver") != 1:
            return False
        if not self._allowed(frame):
            callback.failure(403, "origin not allowed: %s" % frame.get_url())
            return True
        kind = message.get("t")
        if kind == "call":
            self._call(frame, message, callback)
        elif kind == "result":
            self._result(message, callback)
        else:
            callback.failure(400, "unknown message %r" % (kind,))
        return True

    def _call(self, frame, message, callback):
        entry = self._functions.get(message.get("n"))
        if entry is None:
            callback.failure(404, "%r is not exposed" % (message.get("n"),))
            return
        function, with_frame = entry
        try:
            args = [JsCallback(frame, a["__cb"]) if isinstance(a, dict) and "__cb" in a and len(a) == 1 else a
                    for a in message.get("a", [])]
            value = function(frame, *args) if with_frame else function(*args)
            answer = json.dumps(value, allow_nan=False)
        except BaseException as error:  # reported to the page, which asked
            callback.failure(500, "%s: %s" % (type(error).__name__, error))
            return
        callback.success(answer)

    def _result(self, message, callback):
        function = self._pending.pop(message.get("id"), None)
        callback.success("")
        if function is None:
            return
        try:
            if message.get("ok"):
                function(message.get("v"), None)
            else:
                function(None, message.get("e") or "error")
        except BaseException:
            sys.excepthook(*sys.exc_info())
