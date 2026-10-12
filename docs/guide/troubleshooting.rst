Troubleshooting
===============

Messages you may see, what CEFWeaver does in some situations, and where the known problems are listed. A message is on this page because it was produced on purpose and the condition is given. The runs used the installed wheel (CEF 154, Python 3.13) on Linux x86_64 on a virtual X server (``xvfb-run -a``, ``WAYLAND_DISPLAY`` unset), and each result was the same in three runs in a row. The scripts are in ``docs/guide/recipes/``. Where a message could not be reproduced the line of the source that prints it is the evidence, and it says so.

Messages
--------

Exceptions of the Python side
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. literalinclude:: recipes/api_errors.py
   :language: python

It prints:

.. code-block:: text

   load_url() before initialize()         RuntimeError: initialize() has not been called
   add_resource() before initialize()     RuntimeError: initialize() has not been called
   Settings(foo=1)                        TypeError: unknown setting 'foo'
   settings.foo = 1                       AttributeError: unknown setting 'foo'
   settings.log_file = 5                  TypeError: log_file must be a str
   settings.persist_session_cookies = 1   TypeError: persist_session_cookies must be a bool
   settings.remote_debugging_port = 70000 ValueError: remote_debugging_port must be a port number
   initialize() twice                     RuntimeError: initialize() was already called
   set_cache_path() after initialize()    RuntimeError: this must be done before initialize()
   add_command_line_switch() after it     RuntimeError: this must be done before initialize()
   settings.user_agent = ... after it     RuntimeError: the settings cannot change after initialize()
   offscreen = False after it             RuntimeError: this must be done before initialize()
   add_resource() with an ftp URL         ValueError: expected an absolute http or https URL, not 'ftp://x/'
   do_message_loop_work() after shutdown  RuntimeError: CEF has been shut down
   CefApp().initialize() after shutdown   RuntimeError: CEF can be initialized only once per process, and it was shut down already

.. list-table::
   :header-rows: 1
   :widths: 38 62

   * - Message
     - What to do
   * - ``initialize() has not been called``
     - The call needs a running CEF. ``add_resource()`` and ``load_url()`` work after ``initialize()``; with :class:`~cefweaver.ui.Session` that is :meth:`~cefweaver.ui.Session.start`, and the browser exists when the view's ``on_ready`` is called (:doc:`cookbook`).
   * - ``this must be done before initialize()``
     - Move the call before ``initialize()`` / ``session.start()``: switches, cache and resource paths, the app handler, JavaScript bindings, ``offscreen`` and the other properties. The same for the settings: ``the settings cannot change after initialize()``. See :doc:`configuration`.
   * - ``initialize() was already called``
     - One ``CefApp`` starts once.
   * - ``CEF can be initialized only once per process, and it was shut down already``
     - CEF cannot start again in a process after ``shutdown()``, not even with a new ``CefApp``. Start a new process.
   * - ``CEF has been shut down``
     - The call came after ``shutdown()``.
   * - ``expected an absolute http or https URL``
     - ``add_resource()`` serves ``http`` and ``https`` URLs only. For another scheme see "Custom schemes" in :doc:`configuration`.

The wheel and the source use the same texts for the lines above. The port check allows 0 to 65535 in both, while the docstring of ``remote_debugging_port`` in the source says 1024 to 65535.

``RuntimeError: CefInitialize() failed``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A second process started CEF with the cache folder that a running process uses:

.. literalinclude:: recipes/second_process.py
   :language: python

With ``LANGUAGE=en LANG=en_US.UTF-8`` it prints:

.. code-block:: text

   second: RuntimeError: CefInitialize() failed
   Opening in existing browser session.
   first: on_already_running_app_relaunch(second='yes', same directory=True)

The second process hands its command line to the first and fails with this error; the first gets :meth:`~cefweaver.AppHandler.on_already_running_app_relaunch` with the switches and the working directory of the second. The hook is not required: without an app handler the second process failed the same way. But when the hook is missing or returns ``False`` (the default; the docstring says CEF then opens a new window), ``is_running`` of the first process stayed true and :meth:`~cefweaver.ui.Session.shutdown` did not finish within the 30 seconds of the script's wait in three runs, because it closes the views only; ``app.shutdown()`` closed everything in about 0.06 s. Give each process its own ``cache_path``, or use the hook to pass the work to the first process. ``CefInitialize() failed`` is also what the source raises when CEF does not start for another reason (``_cefweaver.pyx``, in ``initialize()``); the reasons other than this one were not reproduced.

The process stops at start
~~~~~~~~~~~~~~~~~~~~~~~~~~

If the files of the runtime are not where CEF looks, the failure depends on the file. This was tried by removing one file at a time from a copy of the package made of links (``start_only.py`` starts CEF and shuts down; its argument is the folder to import from):

.. code-block:: sh

   SITE=$(python -P -c 'import cefweaver, os; print(os.path.dirname(os.path.dirname(cefweaver.__file__)))')
   mkdir farm && cp -rs "$SITE/cefweaver" farm/cefweaver
   rm farm/cefweaver/icudtl.dat
   xvfb-run -a python -P start_only.py "$PWD/farm"

.. literalinclude:: recipes/start_only.py
   :language: python

.. list-table::
   :header-rows: 1
   :widths: 24 76

   * - Removed
     - Result
   * - ``libcef.so``
     - ``import cefweaver`` fails: ``ImportError: libcef.so: cannot open shared object file: No such file or directory`` (exit status 1).
   * - ``icudtl.dat``
     - Exit status 133 (``Trace/breakpoint trap (core dumped)``); before it ``Invalid file descriptor to ICU data received.``
   * - ``locales/``
     - Exit status 133 with no message before it.
   * - ``cefsubprocess``
     - Exit status 133. Standard error has many ``LaunchProcess: failed to execvp:`` lines with the path, ``GPU process launch failed: error_code=1002``, ``Network service crashed or was terminated, restarting service.`` and finally ``GPU process isn't usable. Goodbye.``
   * - ``resources.pak``
     - The browser started and shut down (exit status 0). Standard error had ``Failed to load .../resources.pak``, ``Some features may not be available.`` and ``Failed to parse extension manifest.``
   * - ``v8_context_snapshot.bin``
     - The browser started and shut down; no message.

With nothing removed the script prints ``browser ready`` and ``shut down; log file in the cache folder: True`` and writes nothing to standard error. Other missing files were not tried. Status 133 is the shell's 128 plus signal 5 (SIGTRAP). Reinstall the wheel, and check the layout in :doc:`installation` if you copied the files yourself.

No display
~~~~~~~~~~

With ``DISPLAY`` and ``WAYLAND_DISPLAY`` both unset:

- An offscreen browser (:class:`~cefweaver.ui.Session`, ``start_only.py``) started and shut down. Standard error had one line: ``GLib-GObject: g_object_set_is_valid_property: object class 'GtkSettings' has no property named 'gtk-modules'``.
- The window of :class:`~cefweaver.CefApp` (``window_mode.py``) ended the process in ``initialize()`` with exit status 133, after that same line. There was no ``Missing X server`` message. Run it on a virtual display (``xvfb-run -a``) or in a graphical session. On a Wayland desktop the window mode uses X11 unless you say otherwise (:doc:`wayland-gpu`).

.. literalinclude:: recipes/window_mode.py
   :language: python

On a virtual X server the script prints ``initialize() returned`` and ``shut down`` and exits with status 0.

Printing
~~~~~~~~

All from ``print_handler.py`` and ``print_pdf.py``; the conditions are on :doc:`printing`:

- ``The selected printer is not available or not installed correctly. Check your printer or try selecting another printer.``: the handler did not fill the settings in ``on_print_settings(get_defaults=True)``. The text is in the language of the process.
- ``Error rendering printed document via service for document N: kFailed`` followed by ``Something went wrong when trying to print.  Please check your printer and try again.``: CEF was not started with ``disable-features=EnableOopPrintDrivers``.
- ``PrintToPDF failed with error: Page range exceeds page count`` and ``... Page range is invalid (start > end)``: the ``page_ranges`` of :meth:`~cefweaver.BrowserHost.print_to_pdf`; ``on_pdf_print_finished`` gets ``ok=False``.
- Nothing at all after ``host.print()``: no print handler is found; set it on the class of the client.

Lines on standard error that are not errors of your program
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Chromium writes its log to ``chrome_debug.log`` in the cache folder, and standard error stays quiet unless something prints there (see "Behavior"). These were seen and the program went on, with exit status 0:

.. list-table::
   :header-rows: 1
   :widths: 46 54

   * - Line
     - Seen when
   * - ``DevTools listening on ws://127.0.0.1:PORT/devtools/browser/ID``
     - ``remote_debugging_port`` is set (three runs of a script that sets only the port).
   * - ``Message 6 rejected by interface blink.mojom.WidgetHost`` and the same for ``Message 7``
     - Printed in ``configuration.py`` (custom scheme, evaluate, user agent and the other settings); not printed by ``start_only.py`` or the cookbook script. Which setting causes it was not found.
   * - ``Check failed: observers_.empty().`` (``base/observer_list.h:330``)
     - At the end of a run in which a print cycle failed (``empty`` and ``no-switch`` of ``print_handler.py``); not in the run that succeeded. The cause was not investigated.
   * - ``GLib-GObject: ... 'gtk-modules'``
     - No display (above).
   * - In ``chrome_debug.log``: ``dri3 extension not supported.``, ``InitializeSandbox() called with multiple threads in process gpu-process.``, ``Failed to register with org.freedesktop.host.portal.Registry``, ``Desktop Identity Consistency cannot be enabled as no OAuth client ID and client secret have been configured.``
     - In each of three starts on this machine under ``xvfb-run`` with the default log level (WARNING lines).

Messages that are not on this page were not produced. In particular the errors of the ``bridge.evaluate`` timeout and of ``DragData.get_file_name()`` are in :doc:`limitations`.

Behavior
--------

- **Exceptions in your callbacks do not stop CEF.** An exception raised in a hook of the view (``on_title`` here) was passed to ``sys.excepthook`` and the loop went on; the hook was called twice for one page and both exceptions arrived (``hook_errors.py``). The docstring of :class:`~cefweaver.AppHandler` says the same for its methods (source).

  .. literalinclude:: recipes/hook_errors.py
     :language: python

  Output:

  .. code-block:: text

     titles: ['first', 'first']
     caught: ['ValueError: raised in on_title', 'ValueError: raised in on_title']
     shut down

- **Callbacks run inside the message loop.** CEF's UI-thread callbacks are called from ``do_message_loop_work()`` on the thread that called ``initialize()`` (docstring of :class:`~cefweaver.CefApp`, source). If the loop does not run, no callback arrives; see :doc:`message-loop`. The print and PDF callbacks above arrived inside ``run_until`` of the headless adapter.
- **Standard error is quiet.** The log goes to ``chrome_debug.log`` in the cache folder unless ``log_file`` is set; the cookbook script and ``start_only.py`` wrote nothing to standard error. For a log on standard error Chromium has the switch ``enable-logging=stderr``; with it the four ``chrome_debug.log`` lines of the table above appeared on standard error in three runs of a script that only starts and shuts down (not kept as a script); other scripts were not tried with it. The log level is ``Settings.log_severity``.
- **The cache folder is** ``cache/`` **in the working directory** when no ``cache_path`` is given (:doc:`configuration`). Two processes cannot share a cache folder (above).
- **The language of the pages follows** ``LANGUAGE`` / ``LANG``, not ``Settings.locale``, on Linux (:doc:`configuration`).
- **Offscreen runs without a display, window mode does not** (above).

Known problems
--------------

They are kept in two places, with their causes where the cause was found:

- :doc:`limitations`: platforms, Windows and macOS differences, features that are not there, the API restrictions (``bridge.evaluate`` before the context exists, ``DragData.get_file_name()``, ``Image`` before initialization, views with an external message pump), and the scope of the tests.
- :doc:`wayland-gpu`: the window mode on Wayland that cannot be closed from code, and the GPU process on X11.

Not tried for this page: a real Wayland session, Windows and macOS, window-mode printing, a printer, and the many Chromium switches not named here.
