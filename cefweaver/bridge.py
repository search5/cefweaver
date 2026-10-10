"""JSON calls between JavaScript and Python, over the message router (cefpython's
``JavascriptBindings``).

``JavascriptBridge`` exposes Python functions to pages: ``window.<name>(...)`` returns a
``Promise``; its arguments and the result are JSON values (``None``, ``bool``, numbers, ``str``,
lists and dicts). A function of the page given as an argument arrives as a ``JsCallback``. The
other way, ``execute_function()`` calls a function of the page and ``evaluate()`` runs an
expression and gives its value (a ``Promise`` is awaited) to a callback.

Nothing runs in the renderer process but a fixed piece of JavaScript that defines the
functions; the calls are queries of the message router (``window.cefQuery``), answered on the
thread that called ``CefApp.initialize()`` in ``do_message_loop_work()``.
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
    """A function of the page that was given to Python as an argument. ``call(*args)`` runs it in
    the frame it came from with JSON arguments; ``release()`` lets the page forget it. A call after
    the frame is gone or the function released does nothing."""

    __slots__ = ("_frame", "_id")

    def __init__(self, frame, callback_id):
        self._frame = frame
        self._id = callback_id

    def call(self, *args):
        if self._frame is None or not self._frame.is_valid():
            return
        self._frame.execute_java_script(
            "window.__cefweaverBridge && window.__cefweaverBridge.invoke(%s, %s)"
            % (json.dumps(self._id), json.dumps(list(args), allow_nan=False)), "", 0)

    def release(self):
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
    """The bridge of ``app`` (a ``CefApp`` that is not initialized yet). ``origins``, a list of URL
    prefixes (``["https://example.org/"]``), limits the frames whose calls are answered; the
    default is every frame, so set it when pages from outside can be loaded."""

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
        """Make ``window.<name>`` call ``function`` (before ``initialize()``). With ``with_frame``
        the function gets the ``Frame`` of the caller first. An exception in it rejects the
        ``Promise`` with its type and message."""
        if not isinstance(name, str) or not name.isidentifier() or name in _RESERVED:
            raise ValueError("%r is not a name for a JavaScript function" % (name,))
        if not callable(function):
            raise TypeError("function must be callable")
        if name in self._functions:
            raise ValueError("%r is exposed already" % (name,))
        self._functions[name] = (function, bool(with_frame))
        self._app._set_bridge_names(json.dumps(sorted(self._functions)))

    def execute_function(self, frame, path, *args):
        """Call the function ``path`` (``"api.greet"``, from ``window``) of the page in ``frame`` with
        JSON arguments. The result is not wanted; ``evaluate()`` gives it."""
        parts = path.split(".") if isinstance(path, str) else []
        if not parts or not all(part.isidentifier() for part in parts):
            raise ValueError("%r is not the path of a function" % (path,))
        frame.execute_java_script("window.__cefweaverBridge.call(%s, %s)"
                                  % (json.dumps(path), json.dumps(list(args), allow_nan=False)), "", 0)

    def evaluate(self, frame, expression, callback, timeout=30.0):
        """Run the JavaScript ``expression`` in ``frame`` and call ``callback(value, error)`` later,
        in ``do_message_loop_work()``: ``value`` is its JSON value (a ``Promise`` is awaited) and
        ``error`` is ``None``, or the message of the exception and then ``value`` is ``None``.

        An expression that gets no answer (a ``Promise`` that stays pending, a frame that has no
        context yet, a page that was left) ends after ``timeout`` seconds with the error
        ``"TimeoutError: ..."``; a later answer is ignored. ``timeout=None`` waits without limit."""
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
