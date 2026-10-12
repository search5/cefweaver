JavaScript bridge
=================

JavaScript in a page can call Python functions that you expose, and Python can call functions of a page and evaluate expressions in it. Both directions are on :class:`~cefweaver.JavascriptBridge`; a :class:`~cefweaver.ui.Session` has one as ``session.bridge``. Values travel as JSON. The examples of this page were run against the built wheel on a virtual X server (``xvfb-run python -P script.py``); each printed the same output in three runs in a row.

The bridge sits on the message router (``window.cefQuery``) and needs no Python in the renderer process. The older and simpler :meth:`~cefweaver.CefApp.add_javascript_binding` passes only ``int``, ``bool``, ``float`` and ``str`` arguments, it leaves out an argument of any other type (``bind(1, [1], 2)`` arrives as ``(1, 2)``, ``bind(null)`` as ``()``), and it returns nothing to the page. The bridge replaces it when you need a result, lists, dictionaries or callbacks.

JavaScript calls Python
-----------------------

:meth:`~cefweaver.JavascriptBridge.expose` defines ``window.<name>`` in every frame of every page, before the scripts of the page run. Call it **before** ``initialize()`` (with a session: before ``session.start()``), or it raises ``RuntimeError``. The name must be a JavaScript identifier that is not a reserved word and is not exposed already (``ValueError`` otherwise); the function must be callable (``TypeError``).

.. literalinclude:: recipes/bridge_calls.py
   :language: python

The page of the script calls the functions with ``await``. This is the first half of the output, what the page got:

.. code-block:: text

   page -> Python:
     add      5
     float    0.30000000000000004
     user     {"id": "42", "name": "Ada", "tags": ["admin"]}
     nothing  null
     where    "http://app.test/index.html"
     boom     "ValueError: no good"
     notjson  "TypeError: Object of type object is not JSON serializable"
     nan      "ValueError: Out of range float values are not JSON compliant: nan"
   JsCallback: JsCallback

What the lines show:

- ``window.add(2, 3)`` returns a ``Promise``. The arguments are encoded as JSON and arrive in Python as ``int``, ``float``, ``str``, ``bool``, ``None``, ``list`` and ``dict``. The result is encoded with ``json.dumps(..., allow_nan=False)``, so a function returning ``None`` resolves to ``null`` and a dictionary becomes an object.
- Floats keep their full precision (``0.1 + 0.2``). ``undefined`` as an argument arrives as ``None``.
- ``with_frame=True`` passes the calling :class:`~cefweaver.Frame` as the first argument (``where`` returned its URL).
- **A failure rejects the** ``Promise`` **with an** ``Error`` **whose** ``message`` **is** ``Type: message``: the exception of the function (``ValueError: no good``), or the error of encoding a result that is not JSON (``object()``, ``NaN``). The ``Error`` has no ``code`` property.
- Calls are answered on the thread that called ``initialize()``, from ``do_message_loop_work()``, so the functions run one after another and a slow function blocks the message loop (:doc:`message-loop`). Do slow work in a thread of your own and hand the result back to the thread of the loop with a task (:doc:`concepts`), where you can answer through a :class:`~cefweaver.JsCallback` (below).
- The bridge works in iframes and in every browser of the application, also in a frame of another site, which has a renderer process of its own (the test suite covers these cases).
- A name that is not exposed is not defined in the page at all: calling it is the page's own ``ReferenceError``.

Functions as arguments
~~~~~~~~~~~~~~~~~~~~~~

A function that the page passes as an argument arrives as a :class:`~cefweaver.JsCallback`. ``call(*args)`` runs it in the frame it came from with JSON arguments, and you may keep the object and call it later, after the exposed function has returned; ``release()`` lets the page forget it. A call after the frame is gone or after ``release()`` does nothing. In the script ``listen`` stored the callback, and ``callbacks[0].call("hello from Python")`` ran the page's function (the second half of the output below shows ``heard``).

Only a function that is itself an argument is converted. This second script shows what happens to a function inside a list or an object, and what ``evaluate`` makes of various results (next section):

.. literalinclude:: recipes/bridge_values.py
   :language: python

.. code-block:: text

   arguments: JsCallback [None] {}
   page heard: ['heard one']
   [1, 2.5, 1e21]           [1, 2.5, 1e+21] None
   NaN                      None None
   new Date(0)              '1970-01-01T00:00:00.000Z' None
   new Map([[1, 2]])        {} None
   var a = {}; a.a = a; a   None TypeError: Converting circular structure to JSON
   10n                      None TypeError: the result cannot be passed to the bridge
   Symbol('s')              None TypeError: the result cannot be passed to the bridge

A function inside a list arrives as ``None`` and one inside an object disappears (the JSON of the page drops it). After ``release()`` the call of the script did nothing: the page heard only ``one``.

Which pages may call
~~~~~~~~~~~~~~~~~~~~

**By default every frame of every page loaded in the application can call every exposed function**, whatever its origin. ``ui.Session`` makes its bridge this way. Expose only functions that are safe for all pages you load, validate their arguments, and do not load untrusted pages in a program that exposes functions with side effects.

To restrict the bridge, build it yourself with ``origins``, a list of URL prefixes, before ``initialize()``. Only frames whose URL starts with one of them are answered; the others get a rejected ``Promise``. A string instead of a list raises ``TypeError``.

.. literalinclude:: recipes/bridge_origins.py
   :language: python

.. code-block:: text

   http://trusted.test/ ('add', '5')
   http://other.test/ ('add failed', 'origin not allowed: http://other.test/')

The page of the second address could still use ``report``, a plain binding of :meth:`~cefweaver.CefApp.add_javascript_binding`: only the bridge is restricted. Queries that are not the bridge's go on to the handlers added with :meth:`~cefweaver.CefApp.add_query_handler`; the bridge hands them on.

Python calls JavaScript
-----------------------

Both methods need the :class:`~cefweaver.Frame` of the page: ``view.browser.get_main_frame()`` for a :class:`~cefweaver.ui.BrowserView` (as in the script), or ``browser.get_main_frame()`` from a handler such as ``LifeSpanHandler.on_after_created``. A bridge with nothing exposed works for these calls too.

:meth:`~cefweaver.JavascriptBridge.execute_function` ``(frame, path, *args)`` calls the function at a dotted path below ``window`` (``"api.greet"``) with JSON arguments and drops the result. It returns nothing and reports nothing back to Python; a path that is not made of identifiers raises ``ValueError``.

:meth:`~cefweaver.JavascriptBridge.evaluate` ``(frame, expression, callback, timeout=30.0)`` evaluates an expression and calls ``callback(value, error)`` later, from ``do_message_loop_work()``. This is the second half of the output of ``bridge_calls.py``:

.. code-block:: text

   Python -> page:
     report: {'greet': 'Ada{"k":[1,null]}'}
     report: {'heard': 'hello from Python'}
     evaluate double    (42, None)
     evaluate later     ({'done': [1, 2]}, None)
     evaluate object    ({'a': [1, 2], 'b': 'x'}, None)
     evaluate undefined (None, None)
     evaluate syntax    (None, "SyntaxError: Unexpected token '}'")
     evaluate thrown    (None, 'RangeError: r')
     evaluate nowhere   (None, 'ReferenceError: missing is not defined')
     evaluate never     (None, 'TimeoutError: no answer in 0.5 s')

- On success ``value`` is the JSON value of the result and ``error`` is ``None``. A ``Promise`` is awaited (``later``). ``undefined`` is ``None``. The conversions of the other script above apply: ``NaN`` is ``None``, a ``Date`` is its ISO string, a ``Map`` is ``{}``.
- On failure ``value`` is ``None`` and ``error`` is ``"Name: message"`` of the JavaScript error, for a syntax error or a thrown error. A result that cannot be sent (a cycle, a ``BigInt``, a ``Symbol``) comes as a ``TypeError`` string.
- If no answer comes, the callback gets ``TimeoutError: no answer in N s`` after ``timeout`` seconds, and a later answer is ignored. Typical causes are a ``Promise`` that never settles, a frame without a script context yet, and a page that was left. ``timeout=None`` waits without limit (the callback may then never be called). A ``timeout`` that is not a positive number raises ``ValueError``; a ``callback`` that is not callable raises ``TypeError``.
- The syntax error shows ``Unexpected token '}'`` for ``1 +``: the bridge puts the expression in a block before it runs, which is why a top-level ``let`` or ``const`` lives only in that call (see :doc:`embedding`).
- It works on pages that forbid ``eval``, as :doc:`embedding` explains.
- An exception in your callback goes to ``sys.excepthook`` (:doc:`concepts`).

Frames and navigation
~~~~~~~~~~~~~~~~~~~~~

Wait until the page can answer before you evaluate. In the script the page calls an exposed ``ready`` function at its end, and Python waits for it. An expression left unanswered because the page was left ends with the timeout (run: a ``Promise`` that never settles, the page replaced by another URL, ``TimeoutError: no answer in 1 s``). The renderer also ignores an expression that arrives before the script context of the frame exists, which ends the same way (source: ``cefweaver-eval`` in ``native/cefwrapper/cef_wrapper_render_process_handler.cc``); this was not reproduced, because an expression sent as soon as the view's ``on_ready`` was called was answered, by the context of ``about:blank``.
