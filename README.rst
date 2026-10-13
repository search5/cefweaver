CEFWeaver
#########

Chromium for Python programs: embed a modern web browser in your application, show web pages in the windows of
your GUI toolkit, and let pages and Python call each other.

**Status: pre-release (0.1.0).** The API may still change. The automated tests run on Linux x86_64, macOS arm64 and
Windows 11, and stability was tested on Linux x86_64 with content you trust: 180 start-and-stop cycles without a
failure and a 20-minute soak of 4,610 page loads without an error (see `Production readiness`_). It does **not** yet run the Chromium sandbox, so do not use
it to open untrusted web content, and it has not been tested for runs of days.

.. contents:: Table of contents
   :local:
   :depth: 1

Introduction
============

CEFWeaver is an open source project founded by Lee Ji-Ho in 2023 to provide python bindings for the Chromium Embedded Framework (CEF). The CEF API is generated from the CEF headers (``tools/gen``), and the descriptions in the reference are the comments of those headers. Examples of embedding CEF browser are available for many popular GUI toolkits including: wxPython, PyQt, PySide, Kivy, PyGObject, PyGame/PyOpenGL and PyWin32. (not ready: Panda3D)

There are many use cases for CEF. You can embed a web browser control based on Chromium with great HTML 5 support. You can use it to create a HTML 5 based GUI in an application, this can act as a replacement for standard GUI toolkits like wxWidgets, Qt or GTK. You can render web content off-screen in application that use custom drawing frameworks. You can use it for automated testing of existing applications. You can use it for web scraping or as a web crawler, or other kind of internet bots.

Features
========

**Browser**

- The full CEF API, generated from the CEF 154 headers: 129 classes, 1,182 methods and functions, and 20 global functions,
  with PEP 8 names and the descriptions of the CEF headers as docstrings (``tools/gen``, type stubs included).
- Handlers for load, life span, display, requests and resources, downloads, dialogs, keyboard, focus, find, printing,
  permissions, drag and drop, audio and accessibility. Python exceptions in a handler never reach CEF.
- Pages served from memory or from a custom scheme without a network, cookies, an HTTP server, response filters,
  DevTools (``show_dev_tools()``) and tracing.

**Python and JavaScript**

- ``session.bridge.expose(name, function)`` makes a Python function a ``Promise``-returning function of the page, and
  ``bridge.evaluate(frame, expression, callback)`` runs JavaScript from Python (also on pages that forbid ``eval``).
  Values are JSON; a payload of 8 MB goes round in a fifth of a second.
- Events of the renderer process (uncaught JavaScript errors, the focused node, V8 contexts) reach Python.

**GUI toolkits**

- ``cefweaver.ui`` shows an offscreen browser in a widget of GTK 3, Qt (PyQt6 and PySide6), Tk, SDL2, wxPython, Kivy
  or, on Windows, a Win32 window (pywin32). Mouse, keyboard, input methods, the clipboard, drag and drop, HiDPI scaling,
  popups and the context menu are handled for you; the adapter of a new toolkit is seven methods.
- It does not depend on the window system: the same code runs on X11 and on Wayland.
- Without a toolkit: windows, toolbars, buttons and text fields of CEF's own Views framework, and a headless adapter
  for tests and screenshots.

**Media and devices**

- Page sound through the sink of the toolkit (Qt, SDL2) or pygame, a policy for the microphone and the camera, and
  Chromecast: finding devices and playing, pausing, seeking and setting the volume.
- Printing on Linux with your own dialog and CUPS, and ``print_to_pdf()``. On macOS ``print()`` opens the system print
  panel (printing from it was not tried).

**Packaging**

- One wheel per platform for every Python from 3.11 (``abi3``), with the CEF runtime inside; one wheel was started with
  Python 3.11 to 3.14 on Linux and with 3.13 and 3.14 on Windows. Linux wheels are tagged ``manylinux_2_28`` (x86_64 and
  aarch64). On Windows the apps can be frozen with PyInstaller, cx_Freeze and py2exe.

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
macOS                          arm64 (Apple Silicon)   Supported (under development); x86_64 is not built yet
Windows 11                     x86_64                  Supported (under development)
=============================  ======================  ===============================================================

Python 3.11 or later is required (``requires-python`` in ``pyproject.toml``). The differences between the platforms are in ``llm-wiki/pages/reference/known-constraints.md``. On macOS the browser builds and runs offscreen and with a native window, and works in Tk; on Windows it builds and runs offscreen and in a Win32 window (``cefweaver.ui.toolkits.pywin32``), and it is frozen with PyInstaller, cx_Freeze and py2exe. Not done: a browser window as the child of another program's window on Windows.

Install
=======

CEFWeaver is not on PyPI (the project page returns 404) and has no GitHub release yet, so the wheel is built from source (next section) and installed from ``dist/``::

    uv pip install dist/cefweaver-*.whl
    uv pip install "cefweaver[qt]"      # the toolkit you use, see below

The wheel carries the CEF runtime (the Linux wheel built here is 156 MB). The toolkits are optional extras: ``cefweaver[qt]``, ``[gtk3]``, ``[tk]``, ``[sdl2]``, ``[kivy]``, ``[pywin32]``, ``[pygame]``; wxPython: see ``examples/wx``.

Showing a page in a GUI toolkit
===============================

``cefweaver.ui`` shows an offscreen browser in a window of a GUI toolkit. Adapters for GTK 3, Qt (PyQt6 and PySide6),
Tk, SDL2, wxPython, Kivy and, on Windows, pywin32 are in ``cefweaver.ui.toolkits``; install the toolkit you use
(``cefweaver[qt]``, ``[gtk3]``, ``[tk]``, ``[sdl2]``, ``[kivy]``, ``[pywin32]``; wxPython: see ``examples/wx``). The smallest program, with Tk::

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
checked on a virtual X server with real X events, and the menus, clipboard and sound on a real desktop for most of
them; a real input method (Korean) only with GTK 3 (each module says what it was checked on).

Examples
========

Each folder of ``examples/`` has a ``README.md`` and, for the toolkits, a ``quickstart.py`` (the smallest program), a ``browser.py`` and a ``smoke.py``.

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
``print``      Printing a page on Linux with CUPS (the dialog is drawn with Tk)
``cocoa``      A browser as a child ``NSView`` of a Cocoa window (macOS)
``swiftui``    A Swift app that embeds Python and gives a SwiftUI view to ``CefApp.parent_view`` (macOS)
``common``     Code shared by the examples
=============  ==========================================================================

Building from source
====================

On Linux ``uv build --wheel`` alone builds everything (scikit-build-core and CMake; CEF is taken from ``$CEF_ROOT``
or downloaded). ``tools/prepare.py`` prepares CEF and the native libraries in advance (and, on macOS, assembles
``cefsubprocess.app``)::

    python tools/prepare.py                        # download the prebuilt CEF
    python tools/prepare.py --cef-root /path/cef   # use a self-built or extracted CEF
    python tools/prepare.py --build-cef            # build CEF (libcef) from source
    uv build --wheel

Available prebuilt versions (full names) can be listed with
``python tools/prepare.py --list-versions [FILTER]``, and one is selected with
``--cef-version "154.0.34+g14c5a08+chromium-154.0.8037.98"``.

Building CEF from source
------------------------

``--build-cef`` runs CEF's ``automate-git.py`` for the branch and commit taken
from the full CEF version name, then continues with the usual steps using the
resulting ``cef_binary_*`` distribution. It needs about 120 GB of free disk space,
16 GB of RAM or more, and several hours; Linux x86_64 only. Review the plan first::

    python tools/prepare.py --build-cef --dry-run
    python tools/prepare.py --build-cef --cef-build-dir /data/cef_src --proprietary-codecs

Sources and the build go to ``build/cef_src`` unless ``--cef-build-dir`` is given
(no spaces in the path). A distribution that already exists there is reused
unless ``--rebuild`` is passed.

Python API (Linux, early preview)
=================================

::

    import cefweaver

    app = cefweaver.CefApp()
    app.add_javascript_binding("hello", print)    # window.hello(...) in pages
    app.initialize("https://example.com")
    while app.is_running:                         # becomes False when the window is closed
        app.do_message_loop_work()
    app.shutdown()

Pages can also be served from memory, without a network access::

    app.add_resource("http://app.test/index.html", "<h1>hello</h1>")
    app.load_url("http://app.test/index.html")

Browser events (load, life span and display handlers) go to the handlers of a
``Client``, which is given before ``initialize()``::

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

On Linux the browser window of ``CefApp`` uses X11 (XWayland on a Wayland desktop) unless ``ozone-platform`` is
given with ``add_command_line_switch()``: on native Wayland such a window cannot be closed from code and
``shutdown()`` ends the process inside CEF (a limit of CEF). The offscreen ``cefweaver.ui.Session`` uses Wayland by
default where there is a Wayland compositor, and X11 otherwise.

The context menu can be changed and driven from code (``ContextMenuHandler``;
``run_context_menu`` can pick an item with ``callback.continue_()``). The wrapper's own
"Show DevTools" items are off by default: ``app.devtools_menu = True``.

Process messages are available too (``Client.on_process_message_received``,
``Frame.send_process_message``, ``ProcessMessage``, ``ListValue`` ...). The renderer is C++, so
the only message it sends is the answer to ``cefweaver-ping`` (``cefweaver-pong``); JavaScript
calls Python through ``add_javascript_binding``.

Browsers use the Alloy runtime style (as java-cef does). CEF can be initialized
only once per process, also after ``shutdown()``.

CEF runs with an external message pump: the thread that calls ``initialize()`` is
the CEF UI thread, and JavaScript bindings are called inside ``do_message_loop_work()``.
On Linux ``libcef.so``, ``icudtl.dat``, the ``.pak`` files, ``locales/`` and the
``cefsubprocess`` executable must be deployed next to the extension module.

Production readiness
====================

The automated tests run on all three platforms (the tests that only make sense on Linux are skipped on the others).
The stability tests below ran on Linux x86_64 (offscreen browser, CEF 154, virtual X server); their scripts are in
``tools/stability/`` and the details in ``llm-wiki/pages/reference/production-readiness.md``.

==========================================  ===================================================================
Test                                        Result
==========================================  ===================================================================
Automated tests (Linux)                     549 pass (144 seconds; 9 skipped)
Start, call Python from a page, shut down   180 runs, each in a new process: no failure
Soak, 20 minutes                            4,610 page loads, 4,610 calls into Python, no error, clean exit;
                                            file descriptors and threads stay flat
A renderer that crashes                     the application keeps running and loads the next page
Python exceptions in handlers and hooks     reported to ``sys.excepthook``, the application keeps running
Unreachable hosts, shutdown while loading   no hang (shutdown in 0.05 seconds)
Parent killed with ``SIGKILL``              no process is left behind
Idle                                        about 0.7 percent of one CPU
==========================================  ===================================================================

What to know before you ship:

- **No sandbox.** The renderer runs without the Chromium sandbox (``no_sandbox``). Use CEFWeaver for content you
  control, not for browsing the open web.
- **Memory grows slowly under load** (about 15 percent in 20 minutes; the cause is not known). For services that run for
  days, plan to restart the process. One browser uses about 1 GB across its processes.
- **One initialization per process.** CEF cannot be started again after ``shutdown()``.
- Windows and macOS build and run, and the automated tests pass on the developer's machines (the CI runner of Windows,
  which has no desktop, fails some of them), but the start-and-stop, soak and fault tests above were run on Linux only. The differences between the platforms are listed in ``llm-wiki/pages/reference/known-constraints.md``.

Testing
=======

The tests run against the installed wheel, on a virtual X server on Linux::

    env -u WAYLAND_DISPLAY xvfb-run -a python -P -m unittest discover -s tests -v

The suite is run on Linux (549 tests), macOS and Windows. It covers the CEF integration (every test in a new process), the generator, the toolkit adapters with real X events,
Cast against a fake router, the documentation and the wiki. The ``build-test`` workflow (run by hand from the Actions
tab) builds the wheels on Linux x86_64 and aarch64, macOS arm64 and x86_64, and Windows and runs the tests (``llm-wiki/pages/components/packaging.md``
lists the results per platform), and checks on Windows that the same ``abi3`` wheel starts with other Python versions.

Related projects
================

- `cefloom <https://github.com/search5/cefloom>`_: the same CEF binding for PHP, with documentation at https://search5.github.io/cefloom/. Its guide covers the same topics as this one.
- `cefpython <https://github.com/cztomczak/cefpython>`_: an earlier CEF binding for Python with the same purpose; this project's structure and build were compared with it (``llm-wiki/pages/reference/related-projects.md``).

License
=======

BSD 3-Clause License, see ``LICENSE``.

Project website:
https://github.com/search5/cefweaver
