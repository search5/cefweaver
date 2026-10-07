CEFWeaver
#########

Warning: This project is under development and not available for production.

CEFWeaver is an open source project founded by Lee Ji-Ho in 2023 to provide python bindings for the Chromium Embedded Framework. Examples of embedding CEF browser are available for many popular GUI toolkits including: wxPython, PyQt, PySide, Kivy, PyGObject, PyGame/PyOpenGL and PyWin32. (not ready: Panda3D)

There are many use cases for CEF. You can embed a web browser control based on Chromium with great HTML 5 support. You can use it to create a HTML 5 based GUI in an application, this can act as a replacement for standard GUI toolkits like wxWidgets, Qt or GTK. You can render web content off-screen in application that use custom drawing frameworks. You can use it for automated testing of existing applications. You can use it for web scraping or as a web crawler, or other kind of internet bots.

Supported platforms
===================

- Linux (x86_64): supported (under development)
- Windows: supported (under development)
- macOS: not supported yet. The build stops with an explicit error.

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

The CEF classes are available as generated, PEP 8 style wrappers
(``cefweaver.Request``, ``cefweaver.ResourceHandler``,
``cefweaver.SchemeHandlerFactory``, ``cefweaver.register_scheme_handler_factory()``,
...). They are generated from the CEF headers by ``tools/gen``; the part of the CEF
API covered so far is listed in ``tools/gen/COVERAGE.txt``.

CEF runs with an external message pump: the thread that calls ``initialize()`` is
the CEF UI thread, and JavaScript bindings are called inside ``do_message_loop_work()``.
On Linux ``libcef.so``, ``icudtl.dat``, the ``.pak`` files, ``locales/`` and the
``cefsubprocess/`` directory must be deployed next to the extension module.

Project website:
https://github.com/search5/cefweaver
