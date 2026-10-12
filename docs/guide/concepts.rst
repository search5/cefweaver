Concepts
========

What to know before writing handlers: which thread runs your code, which processes exist, what kinds of classes the package has, what a handler method receives and returns, how a program ends and what happens to an error. The examples on this page come from one script, which was run against the built wheel on a virtual X server (``xvfb-run python -P concepts.py``):

.. literalinclude:: recipes/concepts.py
   :language: python

It prints:

.. code-block:: text

   Request(): TypeError
   resource handler on the initialize() thread: {False}
   ('binding on the initialize() thread', True)
   ('binding on the initialize() thread', True)
   reported by sys.excepthook: ['ValueError: raised in a handler']
   ('IO task', False, False, True)
   ('UI task', True, True, False)
   ('UI task from a Python thread', True, True, False)
   is_running after shutdown(): False
   RuntimeError: CEF has been shut down
   RuntimeError: this must be done before initialize()
   RuntimeError: CEF can be initialized only once per process, and it was shut down already

Three runs in a row printed the same lines. For the first steps see :doc:`quickstart` and :doc:`cookbook`.

Threads and where code runs
---------------------------

**The thread that calls** :meth:`~cefweaver.CefApp.initialize` **is the UI thread of CEF.** Python calls CEF from it, and the callbacks that CEF makes on the UI thread run on it, inside :meth:`~cefweaver.CefApp.do_message_loop_work`. This covers the handlers of the ``Client`` given to :meth:`~cefweaver.CefApp.set_client`, the functions of :meth:`~cefweaver.CefApp.add_javascript_binding` and :meth:`~cefweaver.JavascriptBridge.expose`, the :class:`~cefweaver.QueryHandler` methods and the :class:`~cefweaver.AppHandler` methods other than :meth:`~cefweaver.AppHandler.on_schedule_message_pump_work`. In the script above the JavaScript binding ``hello`` ran on that thread (the two ``True`` lines).

Because a callback runs inside ``do_message_loop_work()``, that call returns only when the callback has returned. A callback that takes long delays everything else CEF has to do, and the exposed functions of the bridge run synchronously in the same way (see :doc:`javascript-bridge`).

**Some callbacks come on other threads of CEF.** The docstring of each handler class names the thread. For example ``ResourceHandler`` says its methods are called on the IO thread unless indicated otherwise, and ``SchemeHandlerFactory`` says its methods are always called on the IO thread. In the script the ``open`` method of the resource handler ran on a thread that is not the one that called ``initialize()``. Such a method runs Python on a thread that Python did not create. The objects of a toolkit belong to its main thread, so pass results there instead of touching them (the ``post`` method of the toolkit adapter, see :doc:`embedding`).

Two other places where the thread matters:

- :meth:`~cefweaver.AppHandler.on_schedule_message_pump_work` is called on any thread of CEF, unlike the other methods of :class:`~cefweaver.AppHandler`. :class:`~cefweaver.QueryCallback` can be used from any thread.
- :meth:`~cefweaver.CefApp.create_browser` and :meth:`~cefweaver.CefApp.cancel_pending_queries` say in their docstrings that they are called on the thread that called ``initialize()``. The docstrings of the other :class:`~cefweaver.CefApp` methods do not name a thread, so call them from that thread too.

Tasks
~~~~~

:func:`~cefweaver.post_task` queues a :class:`~cefweaver.Task` for a thread of CEF (``cefweaver.types.ThreadId.UI``, ``IO``, ...), :func:`~cefweaver.post_delayed_task` adds a delay in milliseconds, and :func:`~cefweaver.currently_on` tells whether the calling thread is the named one. The script posted three tasks and each one recorded where it ran:

- A task for ``ThreadId.UI`` runs on the thread that called ``initialize()``, inside ``do_message_loop_work()``, never inside ``post_task()`` itself. It does so also when it is posted from a Python thread of your own (the second line of the group).
- A task for ``ThreadId.IO`` runs on another thread, where ``currently_on(ThreadId.IO)`` is true.
- ``post_task`` returns ``True`` when the task was queued. Before :meth:`~cefweaver.CefApp.initialize` it returned ``False`` and CEF printed a warning (``No task runner for threadId 0``).

This is the way to hand work to the UI thread from a thread of your own.

Processes
---------

CEF runs several processes. In cefweaver the Python process is the **browser process**: it calls ``initialize()``, owns the windows and the browsers, and runs all your Python. The renderer, GPU and utility processes are started from the executable ``cefsubprocess`` that is installed with the package (:meth:`~cefweaver.CefApp.set_subprocess_path` changes the path). They run no Python.

The page's JavaScript runs in a renderer process. So :doc:`javascript-bridge` sends JSON messages over the message router and defines the exposed functions with a fixed piece of JavaScript in the renderer, and the renderer events of :doc:`events` report to Python instead of running Python there.

CEF can be initialized **once per process**. After :meth:`~cefweaver.CefApp.shutdown` a new ``CefApp().initialize()`` raises ``RuntimeError`` (the last line of the output above), so a test suite or a job that needs CEF several times uses one Python process for each.

Classes you use
---------------

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Kind
     - What it is
   * - The application
     - :class:`~cefweaver.CefApp`, written by hand: configure it, call ``initialize()``, run the message loop, call ``shutdown()``. :class:`~cefweaver.Settings` (``app.settings``), :class:`~cefweaver.MessagePump` and :class:`~cefweaver.JavascriptBridge` are plain Python helpers around it.
   * - Library classes
     - Implemented by CEF and given to you: :class:`~cefweaver.Browser`, :class:`~cefweaver.Frame`, :class:`~cefweaver.Request`, :class:`~cefweaver.Response`, :class:`~cefweaver.ListValue` and so on. You do not construct them: ``cefweaver.Request()`` and ``cefweaver.Browser()`` raise ``TypeError`` (``Browser objects are created by CEF or by a create() function``). You get them as arguments of handler methods or from a ``create()`` function such as ``Request.create()``, which also works before ``initialize()``. A method of such a class calls CEF.
   * - Handler classes
     - The ones you subclass to answer CEF: :class:`~cefweaver.Client`, :class:`~cefweaver.LoadHandler`, :class:`~cefweaver.LifeSpanHandler`, :class:`~cefweaver.ResourceHandler`, :class:`~cefweaver.SchemeHandlerFactory`, :class:`~cefweaver.Task`, :class:`~cefweaver.QueryHandler`, :class:`~cefweaver.AppHandler` and so on. Override the methods you need. A method you do not override keeps the behavior CEF has without a handler.
   * - Value types and enumerations
     - In :mod:`cefweaver.types`. The value types are named tuples (``Rect(x=1, y=2, width=3, height=4)``) and the enumerations are ``IntEnum`` or ``IntFlag`` classes (``ThreadId.UI`` is ``0``). A plain integer or a tuple with the same fields is accepted where one is expected.

The names follow PEP 8: the ``Cef`` prefix of the C++ classes is dropped, methods and arguments are in snake_case (``GetURL`` is ``get_url``), and a name that is a Python keyword gets an underscore (``Callback.continue_``).

What a handler method receives and returns
------------------------------------------

A handler method gets the inputs of the C++ method in order. The C++ output parameters become **return values**: if the method also returns a value, that value comes first.

.. list-table::
   :header-rows: 1
   :widths: 50 50

   * - The C++ method
     - The Python method returns
   * - Returns nothing, has no output parameters
     - Nothing (``None``).
   * - Returns a value, no output parameters
     - The value.
   * - Has one output parameter and returns nothing
     - The output value.
   * - Returns a value and outputs, or has several outputs
     - A tuple, the return value first.

The script's resource handler shows it. ``ResourceHandler.open(request, callback)`` returns ``(result, handle_request)``, ``get_response_headers(response)`` returns ``(response_length, redirect_url)`` and ``read(data_out, callback)`` returns ``(result, bytes_read)``: the first item is the C++ return value and the names of the others are those of the C++ parameters in the docstrings. In ``read`` the C++ pointer and size pair is one writable ``memoryview`` named ``data_out``; copy into it with a slice. The exact signature and the return annotation of every method are in ``cefweaver/_cefweaver.pyi`` and in the reference.

The library classes follow the same rule for their output parameters: ``MenuModel.get_accelerator(command_id)`` returns ``(ok, key_code, shift, ctrl, alt)``.

``None`` is accepted as an argument or a return value only where the CEF header marks the parameter optional; elsewhere it is a ``TypeError``.

Lifetime and shutdown
---------------------

The order is: create :class:`~cefweaver.CefApp`, configure it, ``initialize()``, run the message loop (:doc:`message-loop`), ``shutdown()``.

- The configuration methods and the settings work **before** ``initialize()`` only. Afterwards :meth:`~cefweaver.CefApp.add_javascript_binding`, :meth:`~cefweaver.JavascriptBridge.expose`, :meth:`~cefweaver.CefApp.set_client` and the others raise ``RuntimeError("this must be done before initialize()")``, and a change to ``app.settings`` raises ``RuntimeError("the settings cannot change after initialize()")``. Before ``initialize()``, ``load_url()`` and ``do_message_loop_work()`` raise ``RuntimeError("initialize() has not been called")``.
- :attr:`~cefweaver.CefApp.is_running` is true from ``initialize()`` until every browser is closed or ``shutdown()`` is called. A popup closing alone leaves it true. ``initialize(None)`` starts without a first browser, and then ``is_running`` stays true until ``shutdown()``.
- :meth:`~cefweaver.CefApp.shutdown` does nothing if CEF is not running, so a second call is harmless (the last line of the script). It closes browsers that are still open before it stops CEF, waiting at most about 5 seconds for the browsers of the application and then at most about 5 seconds for any others that are still open, such as a Views window (source: ``ShutdownCefSimple`` in ``native/cefwrapper/library.cpp``; with the window of ``CefApp`` open it returned in under 0.1 s in three runs). It is called from the thread that called ``initialize()``. Under a toolkit, :meth:`~cefweaver.ui.Session.shutdown` does it for you after closing the view.
- After ``shutdown()``, calls that need CEF raise ``RuntimeError("CEF has been shut down")``, and ``is_running`` is ``False``.
- A script with the window of ``CefApp`` that ends without ``shutdown()`` ended with exit status 0 and wrote nothing to standard error in three runs. (A GPU error line, ``ContextResult::kTransientFailure``, appeared in one of three runs of the same script with ``shutdown()``, so such a line is not a sign of the missing call.) Call ``shutdown()`` anyway: the wrapper closes the browsers in it in the order CEF needs.

Errors
------

- **An exception in a handler is not passed to CEF.** It goes to ``sys.excepthook`` and the callbacks that follow keep running. In the script ``fail()`` raised ``ValueError`` in a binding; ``sys.excepthook`` received it once and the second ``hello()`` after it still ran. The same holds for the callbacks of :meth:`~cefweaver.JavascriptBridge.evaluate` and the methods of :class:`~cefweaver.QueryHandler`. In a query handler an exception counts as "not handled".
- **Wrong state raises** ``RuntimeError`` (see the previous section). A value of the wrong type raises ``TypeError``, an invalid value ``ValueError``; the docstring of each method lists them under ``Raises``.
- **Calls that cannot work yet return** ``False``: :meth:`~cefweaver.CefApp.load_url` when the first browser does not exist, :meth:`~cefweaver.CefApp.execute_javascript` when there is no browser or the page is still loading.
- **Errors in the page** are not Python exceptions. An uncaught JavaScript error can be reported with ``enable_renderer_events()`` (:doc:`events`), and :meth:`~cefweaver.JavascriptBridge.evaluate` returns the error of its expression as a string (:doc:`javascript-bridge`).
