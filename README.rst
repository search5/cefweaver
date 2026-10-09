CEFWeaver
#########

Warning: This project is under development and not available for production.

CEFWeaver is an open source project founded by Lee Ji-Ho in 2023 to provide python bindings for the Chromium Embedded Framework. Examples of embedding CEF browser are available for many popular GUI toolkits including: wxPython, PyQt, PySide, Kivy, PyGObject, PyGame/PyOpenGL and PyWin32. (not ready: Panda3D)

There are many use cases for CEF. You can embed a web browser control based on Chromium with great HTML 5 support. You can use it to create a HTML 5 based GUI in an application, this can act as a replacement for standard GUI toolkits like wxWidgets, Qt or GTK. You can render web content off-screen in application that use custom drawing frameworks. You can use it for automated testing of existing applications. You can use it for web scraping or as a web crawler, or other kind of internet bots.

Supported platforms
===================

- Linux (x86_64): supported (under development)
- macOS (arm64, Apple Silicon): supported (under development). It builds and runs offscreen and with a native window,
  and works in Tk; other toolkits and the differences from Linux are in ``docs/limitations.md``. macOS x86_64 is not built yet.
- Windows: not verified yet

Showing a page in a GUI toolkit
===============================

``cefweaver.ui`` shows an offscreen browser in a window of a GUI toolkit. Adapters for GTK 3, Qt (PyQt6 and PySide6),
Tk, SDL2, wxPython and Kivy are in ``cefweaver.ui.toolkits``; install the toolkit you use (``cefweaver[qt]``,
``[gtk3]``, ``[tk]``, ``[sdl2]``, ``[kivy]``; wxPython: see ``examples/wx``). The smallest program, with Tk::

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
them; a real input method (Korean) only with GTK 3 (each module says what it was checked on). The documentation for
people is in ``docs/`` (a Jekyll site for GitHub Pages).

Building from source
====================

CEF and the native libraries must be prepared before building the Python package::

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

Project website:
https://github.com/search5/cefweaver
