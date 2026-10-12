Embedding in a GUI toolkit
==========================

:mod:`cefweaver.ui` shows an **offscreen** browser inside a widget of a GUI toolkit. It does not embed a window into the widget: it takes the pixels CEF paints and draws them in the way of the toolkit. That is why it behaves the same on Wayland, and why the widget turns mouse, keys, the input method, the clipboard and drag and drop into CEF events.

Parts
-----

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Name
     - What it does
   * - :class:`~cefweaver.ui.Session`
     - Holds CEF, the JavaScript bridge and the message pump together. When CEF has work to do it wakes the loop of the toolkit, so there is no extra thread and no polling. A session holds one browser.
   * - :class:`~cefweaver.ui.BrowserView`
     - The CEF side: handlers, the record of events, click counts, the input method, clipboard keys and drag and drop. It also carries the options of features such as sound, permissions and menus.
   * - :class:`~cefweaver.ui.BrowserWidget`
     - The base class of the widgets. It gives ``load_url()``, ``go_back()``, ``reload()``, ``snapshot(path)`` and the hooks ``on_title``, ``on_address``, ``on_loading`` and ``on_ready``.
   * - Toolkit adapters
     - What a toolkit gives the view (size, drawing, cursor, clipboard, ...). Seven of them are in ``cefweaver.ui.toolkits`` (pywin32 on Windows only); see :doc:`toolkits`.

The basic flow
--------------

.. code-block:: python

   from cefweaver import ui

   session = ui.Session(loop, switches=[("autoplay-policy", "no-user-gesture-required")])
   widget = ToolkitWidget(...)                     # the widget of a toolkit module (for example CefCanvas)
   widget.on_ready = lambda: widget.load_url("https://example.org/")
   session.start(widget)                           # a widget or a BrowserView
   ...
   session.shutdown(done=function_that_ends_the_toolkit)   # closes the browser first, then calls done

- ``loop`` is the loop object of the toolkit (for example ``TkLoop(root)``). The session needs only two things from it: ``post(function)`` (run on the main thread, callable from any thread) and ``call_later(seconds, function)``.
- ``switches`` is a list of Chromium command-line switches as ``(name, value)``. An ``ozone-platform`` you do not give is filled with ``wayland`` when a Wayland compositor exists (see :doc:`wayland-gpu`). ``session.switches`` is the list that CEF actually got.
- Without ``cache_path`` CEF creates ``cache/`` in the working directory. A temporary folder is safer.

Calls between the page and Python
---------------------------------

``session.bridge`` exposes Python functions to the page. Expose them **before** ``session.start()``.

.. code-block:: python

   session.bridge.expose("add", lambda a, b: a + b)

.. code-block:: javascript

   add(2, 3).then(function (sum) { console.log(sum); });   // the page gets a Promise

To run JavaScript of the page from Python use ``session.bridge.evaluate(frame, "expression", callback)``. It works on pages that forbid ``eval`` (Trusted Types or a strict CSP, as on YouTube and GitHub), because the renderer runs the expression with the API of CEF and not with the ``eval`` of the page. Calling ``eval`` or ``new Function`` inside the expression raises ``EvalError``, as it does for the page. A top-level ``let`` or ``const`` of the expression lives only in that call (``var`` and function declarations stay). If no answer comes (a ``Promise`` that never ends, a frame without a context, a page that was left), the callback gets ``TimeoutError: ...`` after ``timeout`` seconds (30 by default, ``None`` for no limit).

Writing an adapter
------------------

To attach another toolkit, write an adapter. Seven methods are **required**:

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Method
     - Meaning
   * - ``view_size()``
     - The ``(width, height)`` of the view in logical pixels.
   * - ``scale()``
     - The device pixels per logical pixel.
   * - ``screen_origin()``
     - The screen coordinates of the top-left corner of the view.
   * - ``screen_size()``
     - The ``(width, height)`` of the screen.
   * - ``present(frame)``
     - Draw the :class:`~cefweaver.ui.Frame` that CEF painted. ``frame.buffer`` (BGRA) is valid only during this call.
   * - ``post(function)``
     - Run on the main thread.
   * - ``call_later(seconds, function)``
     - Run on the main thread later.

The **optional** methods switch a feature on when the adapter has them:

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Method
     - Feature
   * - ``set_cursor(cursor)``
     - Show the cursor CEF wants.
   * - ``clipboard_get()``, ``clipboard_set(text)``
     - Copy, cut and paste (from keys and from the context menu) through the clipboard of the toolkit.
   * - ``set_ime_rect(x, y, w, h)``
     - The position of the candidate window of the input method.
   * - ``start_drag_out(payload, allowed)``
     - Send what was dragged out of the page into the drag and drop of the toolkit.
   * - ``audio_sink()``
     - Give a sink that plays the sound of the page (:doc:`media`).
   * - ``show_menu(items, x, y, done)``
     - Show the context menu (:doc:`context-menu`).
   * - ``release()``
     - Let go of what the loop holds, when the session ends.

Without a screen you can test with :class:`cefweaver.ui.headless.HeadlessAdapter`. It keeps the pictures in memory, saves them with ``save_png(path)``, and runs its own event loop (``run_until``, ``run_for``). The ``snapshot(path)`` of a widget saves the picture the view holds as a PNG.
