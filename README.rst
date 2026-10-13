CEFWeaver
#########

Chromium for Python programs: embed a modern web browser in your application, show web pages in the windows of
your GUI toolkit, and let pages and Python call each other.

**Status: pre-release (0.1.0, classified as Alpha in pyproject.toml).** The API may still change. The automated tests run on
Linux x86_64, macOS arm64 and Windows 11 (in CI also on Linux aarch64 and macOS x86_64), and stability was tested on
Linux x86_64 with content you trust: 180 start-and-stop cycles without a failure and a 20-minute soak of 4,610 page
loads without an error (see `Production readiness`_). The Chromium sandbox is **not** enabled, so do not use it to open
untrusted web content, and it has not been tested for runs of days.

.. contents:: Table of contents
   :local:
   :depth: 1

Introduction
============

CEFWeaver is an open source project founded by Lee Ji-Ho in 2023 to provide python bindings for the Chromium Embedded Framework (CEF). The CEF API is generated from the CEF headers (``tools/gen``), and the descriptions of the generated classes in the reference are the comments of those headers. Examples of embedding the CEF browser are available for GTK 3 (PyGObject), Qt (PyQt6 and PySide6), Tk, SDL2 (PySDL2), wxPython, Kivy and, on Windows, PyWin32, as well as for CEF's own Views framework and, on macOS, Cocoa and SwiftUI.

There are many use cases for CEF. You can embed a web browser control based on Chromium with great HTML 5 support. You can use it to create a HTML 5 based GUI in an application, this can act as a replacement for standard GUI toolkits like wxWidgets, Qt or GTK. You can render web content off-screen in applications that use custom drawing frameworks. You can use it for automated testing of existing applications, and for scraping or automating sites you trust (the sandbox is not enabled yet, so do not point it at untrusted content on the open web).

Features
========

CEFWeaver is a broad binding, not a thin wrapper around a window. The numbers below come from the code of this
repository (CEF 154): the generated API covers 129 classes with 1,182 methods and functions (20 of them global
functions); ``cefweaver.types`` holds 100 enumeration classes (83 ``IntEnum`` and 17 ``IntFlag``) and 26 value types;
the type stub of the compiled module is about 14,300 lines; the guide has 19 pages, in English and Korean; the test
suite has 550 tests.

Browser and CEF API
-------------------

- The CEF API of the browser process, generated from the CEF 154 headers with PEP 8 names and the descriptions of the CEF
  headers as docstrings (``tools/gen``, type stubs and a ``py.typed`` marker included). The renderer-side V8 and DOM
  classes, about a dozen other classes (such as ``XmlReader``, ``TaskRunner``, ``WaitableEvent`` and ``ResourceBundle``)
  and 32 global functions (such as ``CefParseJSON`` and ``CefURIEncode``) are not generated yet
  (``llm-wiki/pages/reference/coverage-report.md`` lists what is covered).
- Handlers that a ``Client`` returns: load, life span, display, request, context menu, keyboard, focus, download,
  JavaScript and file dialogs, find, frame, command, print, permissions, drag and drop, audio, render and others. A
  handler that you do not override keeps the default behaviour of CEF. Python exceptions in a handler are reported to
  ``sys.excepthook`` and never reach CEF.
- Several browsers in one application (``create_browser()`` with its own offscreen or windowed mode, transparency,
  settings and request context), and separate profiles: a ``RequestContext`` gives a browser its own cache, cookies and
  preferences, with a ``RequestContextHandler`` that sees its requests.
- Typed CEF settings: ``app.settings`` (``cefweaver.Settings``) sets the user agent, the locale, the log file and
  severity, the remote debugging port, persistent session cookies, V8 flags and more as checked attributes, and
  ``AppHandler`` hooks change the command line of the browser and of child processes, register custom schemes and
  preferences, and run code when the CEF context is initialized, just before the first browser is created.
- Version information before ``initialize()``: ``cefweaver.get_version()`` returns the versions of cefweaver, CEF and
  Chromium.

Pages, network and data
-----------------------

- Pages served from memory with ``add_resource()`` (``str`` or ``bytes``, with a MIME type, response headers and a status)
  or from a custom scheme, without a network.
- Cookies from Python: ``CookieManager`` sets, lists and deletes them, and a ``CookieAccessFilter`` decides per resource
  which cookies are sent and saved.
- HTTP requests made from Python through the network stack of Chromium (``URLRequest`` with a ``URLRequestClient`` that
  gets progress, data and credentials), response filters that rewrite a response body, and an HTTP server
  (``Server`` and ``ServerHandler``).
- Security and authentication decisions in Python: certificate errors, HTTP and proxy authentication, client
  certificates, and the SSL certificate of a page.
- Reading and controlling a page from Python: the HTML or text of a frame, finding text, zoom, downloading a file or an
  image, the navigation history, and loading a ``Request`` with POST data.

Python and JavaScript
---------------------

- ``session.bridge.expose(name, function)`` makes a Python function a ``Promise``-returning function of the page with JSON
  values, a page function can be passed to Python and called back (``JsCallback``), ``execute_function()`` calls a page
  function, and ``bridge.evaluate(frame, expression, callback)`` runs JavaScript from Python and passes its value (a ``Promise`` is
  awaited) to ``callback(value, error)``, also on pages whose CSP or Trusted Types forbid ``eval``. An 8 MB string went from the page to Python and back in 0.22 seconds in the Linux stability tests.
- ``add_javascript_binding()`` for simple functions, and the java-cef style message router (``window.cefQuery`` and a
  ``QueryHandler``) that exchanges strings and ``bytes``, with persistent queries, several handlers in order,
  cancellation and other function names than ``cefQuery`` (``set_query_functions()``).
- Process messages between the browser and the renderer, and events of the renderer process (uncaught JavaScript errors,
  the focused node, V8 contexts) that reach Python. The DevTools window (``show_dev_tools()``), and the DevTools Protocol:
  ``BrowserHost.execute_dev_tools_method()`` and a ``DevToolsMessageObserver``.

GUI toolkits
------------

- ``cefweaver.ui`` shows an offscreen browser in a widget of GTK 3, Qt (PyQt6 and PySide6), Tk, SDL2, wxPython, Kivy
  or, on Windows, a Win32 window (pywin32). Mouse, keyboard, the clipboard and popup widgets (such as the list of a ``<select>``) are handled for you; drags inside
  the page work everywhere, while drops from other programs, dragging out of the page (GTK 3, Qt and wxPython), input
  methods, HiDPI scaling and the context menu depend on the toolkit (each toolkit module says what it supports
  and what was checked; SDL2 and Kivy show no context menu, and Tk has no scaling). The adapter of a new toolkit is
  seven methods, and ``cefweaver.ui.tables`` has the key, cursor and modifier tables for writing one.
- ``ui.Session`` takes Chromium switches and the profile directory, runs CEF from the loop of the toolkit without a
  thread (``MessagePump``), and shuts down in order. ``view.snapshot(path)`` saves any embedded browser as a PNG.
- The right-click menu is drawn by the toolkit; ``view.on_context_menu`` can remove items and add items whose ``action``
  is a Python function, and spelling suggestions and "Add to dictionary" work.
- The offscreen browser of ``cefweaver.ui.Session`` works on either window system of Linux: it uses Wayland where a
  compositor is present and otherwise X11 when ``DISPLAY`` is set (a plain offscreen ``CefApp`` uses X11 when ``DISPLAY``
  is set). On Linux the toolkit windows themselves were checked on X11 only (the pywin32
  one on Windows 11).
- Without a toolkit: windows, panels, buttons, text fields, box and fill layouts, scroll views and overlays of CEF's own
  Views framework (the Views example builds a toolbar from them), and ``cefweaver.ui.headless.HeadlessAdapter``
  (``run_until()``, ``save_png()``, ``pixel(x, y)``) for tests and screenshots.
- Offscreen rendering directly on ``CefApp`` too: ``app.offscreen`` sends the pixels to ``RenderHandler.on_paint()``
  (transparent unless ``app.transparent = False``, up to ``app.windowless_frame_rate`` frames per second), and
  ``app.shared_texture`` hands GPU textures to ``on_accelerated_paint()`` (dmabuf planes on Linux; a linear one can be
  copied with ``cefweaver.read_plane()``). It needs a GPU (without one CEF falls back to ``on_paint()``), and the tests
  that check real textures are opt-in.

Media and devices
-----------------

- Page sound through the sink of the toolkit (Qt, SDL2), pygame, or a sink of your own (any object with ``start``,
  ``write`` and ``stop``), with ``view.audio_muted``.
- A policy for the microphone and the camera (``ui.permissions.allow_origins()`` or your own function, answered now or
  later); without a policy CEF refuses them.
- Chromecast: finding devices and playing, pausing, seeking and setting the volume.
- Printing on Linux through a ``PrintHandler`` that shows your own dialog (``examples/print`` draws it with Tk and sends the
  job to CUPS), and ``print_to_pdf()``. On macOS ``print()`` opens the system print panel (printing from it was not tried).
- Media router and component updater, tracing, and shared-memory process messages.

Packaging and quality
---------------------

- One wheel per platform for every Python from 3.11 (``abi3``), with the CEF runtime inside; one wheel was started with
  Python 3.11 to 3.14 on Linux and with 3.13 and 3.14 on Windows. The wheels built by the ``build-test`` workflow are
  tagged ``manylinux_2_28`` on Linux (x86_64 and aarch64); a wheel built with ``uv build --wheel`` on your own Linux
  machine is tagged ``linux_x86_64``. Apps can be frozen with PyInstaller and cx_Freeze on Linux and Windows, and with
  py2exe on Windows (py2exe needs the CEF runtime files copied next to the executable by hand).
- A test suite that runs against the installed wheel, stability scripts (``tools/stability``), a generated coverage
  report, and docstrings for every public name (a test enforces it).

Not included
------------

- Python code that runs inside the renderer process (the renderer is C++; it reports events to Python instead).
- The renderer-side V8 and DOM classes, and a few other CEF classes that are not generated yet.
- A browser window as a native child of the window of another toolkit on Windows and Linux (the offscreen adapters are
  the way to embed there; ``CefApp.parent_view`` is macOS only).
- The Chromium sandbox (see `Production readiness`_), a PyPI release and signed macOS helper apps (see `Install`_).

Documentation
=============

The guide, the cookbook and the API reference are published on GitHub Pages, in English and Korean:

- English: https://search5.github.io/cefweaver/en/index.html
- Korean: https://search5.github.io/cefweaver/ko/index.html

The same text is in ``docs/`` (Sphinx, Read the Docs theme; ``make -C docs site`` builds both languages, see ``docs/Makefile``). The reference is generated from the docstrings of the installed package.

Supported platforms
===================

=============================  ======================  ===============================================================
OS                             Architecture            Status
=============================  ======================  ===============================================================
Linux                          x86_64                  Supported (under development)
Linux                          aarch64                 Built and tested in CI only (``manylinux_2_28``)
macOS                          arm64 (Apple Silicon)   Supported (under development)
macOS                          x86_64                  Built and tested in CI (one shared-texture test fails there because the GPU process of the runner does not start); earlier also run under Rosetta; not tried on a real Intel Mac
Windows 11                     x86_64                  Supported (under development)
=============================  ======================  ===============================================================

Python 3.11 or later is required (``requires-python`` in ``pyproject.toml``). The differences between the platforms are in ``llm-wiki/pages/reference/known-constraints.md`` and in the guide (Limitations). On macOS the browser builds and runs offscreen and with a native window, also as a child ``NSView`` of a Cocoa window (``CefApp.parent_view``), and the Tk, Qt, wxPython and SDL2 examples run (Kivy does not shut down cleanly; GTK 3 was not tried). On Windows it builds and runs offscreen and in a Win32 window (``cefweaver.ui.toolkits.pywin32``), and it can be frozen with PyInstaller, cx_Freeze and py2exe. Not done: a native browser window as the child of a window of the application on Windows and Linux (``CefApp.parent_view`` is macOS only).

Install
=======

CEFWeaver is not on PyPI (the project page returns 404) and has no GitHub release yet, so the wheel is built from source (see `Building from source`_) and installed from ``dist/``. A ``build-test`` run also keeps each platform's wheel as a workflow artifact::

    uv pip install dist/cefweaver-*.whl
    uv pip install "cefweaver[qt]"      # the toolkit you use, see below

The wheel carries the CEF runtime (the Linux wheel built here is 156 MB). The toolkits are optional extras: ``cefweaver[qt]`` (PyQt6; PySide6 you install yourself), ``[gtk3]``, ``[tk]``, ``[sdl2]``, ``[kivy]``, ``[pywin32]``; wxPython: see ``examples/wx``. ``[pygame]`` plays the sound of a page for the toolkits that have no audio sink of their own. The wheel declares ``numpy`` as a dependency, although no module of the package imports it.

The Linux wheel does not carry the system libraries that ``libcef.so`` links against (GLib and GIO, NSS and NSPR, ATK and AT-SPI, CUPS, GBM, xkbcommon, X11 and its Xext, composite, damage, fixes and randr libraries, Pango, Cairo, ALSA, D-Bus, udev, expat and xcb). Install them from your distribution; the ``build-test`` workflow installs ``libnss3 libatk1.0-0t64 libatk-bridge2.0-0t64 libcups2t64 libdrm2 libgbm1 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libpango-1.0-0 libasound2t64 libgtk-3-0t64`` on Ubuntu 24.04. macOS wheels are built for macOS 12 or later, and their helper apps carry only ad hoc signatures (signing and notarization are left to the application that ships them).

Showing a page in a GUI toolkit
===============================

``cefweaver.ui`` shows an offscreen browser in a window of a GUI toolkit. Adapters for GTK 3, Qt (PyQt6 and PySide6),
Tk, SDL2, wxPython, Kivy and, on Windows, pywin32 are in ``cefweaver.ui.toolkits``; install the extra of the toolkit you use, which adds the Python packages its adapter needs
(``cefweaver[qt]`` for PyQt6, ``[gtk3]``, ``[tk]``, ``[sdl2]``, ``[kivy]``, ``[pywin32]``; PySide6 you install yourself;
wxPython: see ``examples/wx``). The smallest program, with Tk::

    import sys
    import tkinter

    from cefweaver import ui
    from cefweaver.ui.toolkits.tk import CefCanvas, TkLoop

    URL = sys.argv[1] if len(sys.argv) > 1 else "https://example.org/"

    root = tkinter.Tk()
    session = ui.Session(TkLoop(root))                    # CEF, run by the Tk loop
    canvas = CefCanvas(root, session, width=900, height=640)   # the browser, a Canvas (the size of the window)
    canvas.pack(fill="both", expand=True)
    canvas.on_ready = lambda: canvas.load_url(URL)        # the browser exists
    canvas.on_title = lambda title: print("title:", title, flush=True)
    root.protocol("WM_DELETE_WINDOW", lambda: session.shutdown(root.destroy))   # close the browser, then the window
    root.after(0, lambda: session.start(canvas))
    root.mainloop()

Each ``examples/<toolkit>/quickstart.py`` is the same for its toolkit. This is experimental: the adapters have been
checked with real input events (on a virtual X server with ``xdotool``; the pywin32 one on Windows 11 with
``SendInput``). The sound of a page was heard on a real desktop with every Linux toolkit, the clipboard was tried on a
real desktop with GTK 3, and the context menu with GTK 3, Qt (PyQt6 and PySide6), wxPython and Tk. A real input method
(Korean) was tried by hand on a real screen with GTK 3 only; the automated checks call the composition methods
directly (each module says what it was checked on).

Examples
========

Each example folder (all but ``common``) has a ``README.md`` and, for the toolkits, a ``quickstart.py`` (the smallest program), a ``browser.py`` and a ``smoke.py``.

=============  ==========================================================================
Folder         What it shows
=============  ==========================================================================
``gtk3``       GTK 3
``qt``         Qt (PyQt6; PySide6 with ``CEFQT_BINDING=pyside6``)
``tk``         Tk
``sdl2``       SDL2
``wx``         wxPython
``kivy``       Kivy
``pywin32``    A Win32 window (Windows)
``views``      A window made by CEF's own Views framework, without a toolkit
``print``      Printing a page: on Linux with CUPS and a dialog drawn with Tk, on macOS with the system print panel and a PDF
``cocoa``      A browser as a child ``NSView`` of a Cocoa window (macOS)
``swiftui``    A Swift app that embeds Python and gives a SwiftUI view to ``CefApp.parent_view`` (macOS)
``common``     Code shared by the examples
=============  ==========================================================================

Building from source
====================

``uv build --wheel`` alone builds everything on Linux, macOS and Windows (scikit-build-core and CMake; CEF is taken
from ``$CEF_ROOT`` or downloaded, and the download is checked against the SHA1 published with it; Windows needs the
Visual Studio C++ build tools). Building needs a C++20 compiler, CMake 3.28.1 or later and Cython 3, which ``uv build``
installs as build requirements. ``tools/prepare.py`` resolves CEF in advance and builds the native libraries in
``build/native`` (on macOS also the helper apps); it links the CEF it used at ``build/native/cef``, and the wheel build
does not read its result, so pass that CEF with ``CEF_ROOT``. ``cefsubprocess.app`` on macOS is assembled by the wheel
build::

    python tools/prepare.py                        # download the prebuilt CEF
    python tools/prepare.py --cef-root /path/cef   # use a self-built or extracted CEF
    python tools/prepare.py --build-cef            # build CEF (libcef) from source
    CEF_ROOT=$PWD/build/native/cef uv build --wheel

Available prebuilt versions (full names) can be listed with
``python tools/prepare.py --list-versions [FILTER]``, and one is selected for ``prepare.py`` with
``--cef-version "154.0.34+g14c5a08+chromium-154.0.8037.98"`` (the default); build the wheel with the ``CEF_ROOT`` above
so that it uses the same CEF.

Building CEF from source
------------------------

``--build-cef`` runs CEF's ``automate-git.py`` for the branch and commit taken
from the full CEF version name, then continues with the usual steps using the
resulting ``cef_binary_*`` distribution. It needs about 120 GB of free disk space,
16 GB of RAM or more, and several hours; Linux x86_64 only. Review the plan first
(``--dry-run`` prints the version, the branch, the commit and the ``automate-git.py`` command; if a distribution already
exists it is reused and the build continues)::

    python tools/prepare.py --build-cef --dry-run
    python tools/prepare.py --build-cef --cef-build-dir /data/cef_src --proprietary-codecs

Sources and the build go to ``build/cef_src`` unless ``--cef-build-dir`` is given
(no spaces in the path). A distribution that already exists there is reused
unless ``--rebuild`` is passed.

Python API
==========

::

    import cefweaver

    app = cefweaver.CefApp()
    app.add_javascript_binding("hello", print)    # window.hello(...) in pages
    app.initialize("https://example.com")
    while app.is_running:                         # becomes False when the window is closed
        app.do_message_loop_work()
    app.shutdown()

Pages can also be served from memory, without network access. Call ``add_resource()`` after ``initialize()`` and before
the page is loaded; it takes absolute ``http`` or ``https`` URLs only (a MIME type, response headers and a status can be
given)::

    app.add_resource("http://app.test/index.html", "<h1>hello</h1>")
    app.load_url("http://app.test/index.html")

Browser events go to the handlers that a ``Client`` returns (``get_load_handler()``, ``get_life_span_handler()``,
``get_display_handler()``, ``get_request_handler()`` and the other ``get_*_handler()`` methods); the client is given
before ``initialize()``::

    class Load(cefweaver.LoadHandler):
        def on_load_end(self, browser, frame, http_status_code):
            print("loaded", frame.get_url())

    class MyClient(cefweaver.Client):
        def __init__(self):
            self.load = Load()

        def get_load_handler(self):
            return self.load

    app.set_client(MyClient())

The CEF classes are available as generated, PEP 8 style wrappers
(``cefweaver.Request``, ``cefweaver.ResourceHandler``,
``cefweaver.SchemeHandlerFactory``, ``cefweaver.register_scheme_handler_factory()``,
...). They are generated from the CEF headers by ``tools/gen``; the part of the CEF
API covered so far is listed in the generated wiki page
``llm-wiki/pages/reference/coverage-report.md``.

The CEF enumerations and value types are in ``cefweaver.types``: ``IntEnum``/``IntFlag``
classes (``types.MouseButtonType.LEFT``, ``types.EventFlags.SHIFT_DOWN | types.EventFlags.CONTROL_DOWN``)
and named tuples (``types.Rect(0, 0, 640, 480)``). Plain integers and tuples are accepted
wherever they are expected.

On Linux, when ``DISPLAY`` is set, the browser window of ``CefApp`` uses X11 (XWayland on a Wayland desktop) unless
``ozone-platform`` or ``ozone-platform-hint`` is given with ``add_command_line_switch()``; without ``DISPLAY`` Chromium
chooses. On native Wayland such a window cannot be closed from code and ``shutdown()`` ends the process abnormally inside
CEF (a limit of CEF, recorded in ``llm-wiki/pages/reference/known-constraints.md``). The offscreen ``cefweaver.ui.Session``
uses Wayland by default where a Wayland compositor is found (``WAYLAND_DISPLAY`` names an existing socket); otherwise it
leaves the choice to ``CefApp`` (X11 when ``DISPLAY`` is set).

The context menu can be changed and driven from code (``ContextMenuHandler``;
``run_context_menu`` can pick an item with ``callback.continue_()``). The wrapper's own
"Show DevTools" items are off by default: ``app.devtools_menu = True``.

Pages and Python can talk in three ways (see the guide for each):

- ``app.add_javascript_binding(name, callback)`` makes ``window.<name>(...)`` call a Python function. Only ``int``,
  ``bool``, ``float`` and ``str`` arguments are passed on and there is no return value. Call it before ``initialize()``.
- ``JavascriptBridge`` (``session.bridge`` in ``cefweaver.ui``): ``expose(name, function)`` gives the page a function that
  returns a ``Promise`` and passes JSON values, a page function can be passed as an argument and called back from
  Python (``JsCallback``), ``execute_function()`` calls a function of the page, and ``evaluate(frame, expression,
  callback)`` runs JavaScript and passes its value (a ``Promise`` is awaited) to the callback, also on pages whose CSP or Trusted Types forbid ``eval``. By
  default every frame may call every exposed function; ``JavascriptBridge(app, origins=[...])`` (URL prefixes) refuses
  calls from other pages.
- The message router, as in java-cef: ``window.cefQuery`` in the page and a ``QueryHandler`` (``app.add_query_handler()``)
  in Python. It exchanges strings and, unlike java-cef, also ``bytes`` (an ``ArrayBuffer`` in the page).

Process messages are available too (``Client.on_process_message_received``, ``Frame.send_process_message``,
``ProcessMessage``, ``ListValue`` ...). The renderer is C++, so no Python runs in it; instead it speaks a few messages of
its own: ``cefweaver-ping`` is answered with ``cefweaver-pong``, ``cefweaver-eval`` carries the expression of
``evaluate()`` into the renderer, and after ``app.enable_renderer_events()`` the renderer reports uncaught JavaScript
errors, the focused node and the creation and release of V8 contexts as ``cefweaver-renderer-event`` messages, which
``RendererEvents`` decodes into the methods of a ``RendererEventHandler``.

The browsers that ``CefApp`` creates (``initialize()``, ``create_browser()``, offscreen browsers) use the Alloy runtime
style (as java-cef does); a Views ``BrowserView`` made by the application uses the style its
``BrowserViewDelegate.get_browser_runtime_style()`` returns. CEF can be initialized only once per process, also after
``shutdown()``.

The application runs CEF's message loop by calling ``do_message_loop_work()`` (CEF's ``external_message_pump`` setting is
off unless set or ``MessagePump`` is used): the thread that calls ``initialize()`` is the CEF UI thread, and JavaScript
bindings and the UI-thread handlers are called inside ``do_message_loop_work()`` (those of the first browser already
inside ``initialize()``); some handlers, such as ``ResourceHandler`` and ``SchemeHandlerFactory``, are called on CEF's IO
thread. ``cefweaver.MessagePump`` sets
``external_message_pump`` and runs ``do_message_loop_work()`` when CEF asks for it (and at least every 1/30 second), so a
toolkit loop can drive CEF with a timer instead of a busy loop (``cefweaver.ui.Session`` does this).

On Linux the wheel puts the CEF runtime (``libcef.so``, ``icudtl.dat``, ``v8_context_snapshot.bin``, the ``.pak`` files,
``locales/``, the SwiftShader and Vulkan files) and the ``cefsubprocess`` executable next to the extension module, where
they must stay; ``set_subprocess_path()`` and ``set_resources_path()`` can point to another ``cefsubprocess`` or resource
folder. Unless ``set_cache_path()`` (or ``ui.Session(cache_path=...)``) is called or ``Settings.root_cache_path`` is set, CEF writes its cache and profile data
to a ``cache`` folder in the current working directory.

Production readiness
====================

The automated tests run on all three platforms; on macOS and Windows the tests that need Linux (X11 windows, the Linux print handler; on Windows also dmabuf
descriptors) are skipped, and a few are skipped where the platform behaves differently and the cause was not examined. The
stability tests below ran on Linux x86_64 (offscreen browser, CEF 154, virtual X server); their scripts are in
``tools/stability/`` and the details in ``llm-wiki/pages/reference/production-readiness.md``.

==========================================  ===================================================================
Test                                        Result
==========================================  ===================================================================
Automated tests (Linux)                     549 ran, OK (144 seconds; 537 passed, 9 skipped, 3 expected
                                            failures); the suite has 550 tests now
Start, call Python from a page, shut down   180 runs, each in a new process: no failure (no
                                            leftover process in the last 100)
Soak, 20 minutes                            4,610 page loads, 4,610 calls into Python, no error, clean exit;
                                            file descriptors and threads stay flat
A renderer that crashes                     the application keeps running and loads the next page
Exceptions in Python code                   an exception in a bridge function rejects the page's ``Promise``;
                                            one in a handler or hook goes to ``sys.excepthook``; the
                                            application keeps running
Unreachable hosts, shutdown while loading   no hang (shutdown in 0.05 seconds)
Parent killed with ``SIGKILL``              no process is left behind
Idle                                        about 0.7 percent of one CPU
==========================================  ===================================================================

What to know before you ship:

- **No sandbox.** The renderer runs without the Chromium sandbox (``no_sandbox``), and an application cannot turn it on:
  the setting is fixed in the native wrapper, the Windows sandbox library is not linked and the Linux ``chrome-sandbox``
  helper is not in the wheel. Use CEFWeaver for content you control, not for browsing the open web.
- **Memory grows slowly under load** (about 15 percent in 20 minutes; the cause is not known). For services that run for
  days, plan to restart the process. One browser uses about 1 GB of resident memory summed over its processes (shared
  pages are counted more than once).
- **One initialization per process.** CEF cannot be started again after ``shutdown()``.
- **The bridge answers every frame by default.** If pages that you do not control can be loaded, build the bridge
  yourself with ``JavascriptBridge(app, origins=[...])`` before ``initialize()``; the ``session.bridge`` of
  ``cefweaver.ui.Session`` takes no ``origins`` and answers every frame.
- **Licenses.** The wheel bundles the CEF and Chromium binaries, which come under their own licenses; only the license of
  CEFWeaver itself is inside the wheel, so an application that redistributes it must add the license files of the CEF
  distribution (``LICENSE.txt``, ``CREDITS.html``).
- Windows and macOS build and run, and the automated tests pass on the developer's machines (in the one Windows CI run 8
  of them failed, 7 by timing out and one find test without a result; the cause, possibly the runner having no real
  desktop or GPU, was not found), but the
  start-and-stop, soak and fault tests above were run on Linux only. The differences between the platforms are listed in
  ``llm-wiki/pages/reference/known-constraints.md``.

Testing
=======

The tests run against the installed wheel, on a virtual X server on Linux::

    env -u WAYLAND_DISPLAY xvfb-run -a python -P -m unittest discover -s tests -v

The suite is run on Linux, macOS and Windows. It covers the CEF integration (each test that starts CEF runs in a new
process), the generator (the generated files must be up to date), the ``ui`` layer with a fake and a headless adapter,
each toolkit quickstart whose example environment exists, on an X server (shown, then closed with a window-manager close
event; on Windows the pywin32 one), Cast against a fake
router, the docstrings and the documentation, and the wiki. The toolkit adapters are driven with real input by
``examples/<toolkit>/smoke.py`` (X events through ``xdotool``; the pywin32 one with ``SendInput`` on Windows). Tests that need a real GPU, a Wayland desktop or a Cocoa window are skipped unless
``CEFWEAVER_TEST_GPU`` (and ``CEFWEAVER_TEST_GPU_PIXELS`` for the pixel check), ``CEFWEAVER_TEST_WAYLAND`` or
``CEFWEAVER_TEST_COCOA`` is set to 1.

Nothing runs automatically on a push: the ``build-test`` workflow (run by hand from the Actions tab) builds the wheel on
the platforms chosen when it is started (Linux x86_64 and aarch64, macOS arm64 and x86_64, Windows; all five with
``all``, Linux x86_64 and macOS arm64 by default) and runs the tests (``llm-wiki/pages/components/packaging.md`` lists
the results per platform). On Windows it also starts the same ``abi3`` wheel with other Python versions; that step has
not run in Actions yet. ``tools/stability/cycle.sh [N]`` repeats start, a call from the page into Python and shutdown
in new processes and reports failures and leftover ``cefsubprocess`` processes; ``soak.py`` and ``scenarios.py`` in the
same folder are the soak and fault tests of the table above.

Related projects
================

- `cefloom <https://github.com/search5/cefloom>`_: the same CEF binding for PHP, with documentation at https://search5.github.io/cefloom/. Its guide covers the same topics as this one.
- `cefpython <https://github.com/cztomczak/cefpython>`_: an earlier CEF binding for Python with the same purpose; this project's structure and build were compared with it (``llm-wiki/pages/reference/related-projects.md``).

License
=======

BSD 3-Clause License, see ``LICENSE``. The generator uses CEF's own header parser, copied unmodified into
``tools/gen/vendor/`` under CEF's BSD-style license; it is a build tool and is not part of the wheel.

Project website:
https://github.com/search5/cefweaver
