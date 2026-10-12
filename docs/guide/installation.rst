Installation and build
======================

CEFWeaver is built from source. You prepare CEF (Chromium) and the native library first, then build the Python package (a wheel).

Requirements
------------

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Item
     - Details
   * - Operating system
     - Linux x86_64, macOS arm64 (Apple Silicon) and Windows 11 x86_64. macOS x86_64 is not verified.
   * - Python
     - The project declares 3.11 or later. 3.13 is the version tested in this repository (the examples point at the 3.13 wheel).
   * - Tools
     - `uv <https://docs.astral.sh/uv/>`_ and a C++ compiler (Xcode or the Command Line Tools on macOS, the Visual Studio C++ build tools on Windows). The build fetches ``cmake`` and ``Cython`` by itself.
   * - Disk and network
     - A prebuilt CEF is downloaded: about 660 MB compressed and 3.2 GB unpacked on Linux, about 307 MB and 791 MB on macOS arm64, about 348 MB and 911 MB on Windows x86_64.

Build
-----

From the repository root, run:

.. code-block:: sh

   python tools/prepare.py                            # prepare CEF and build the native part
   CEF_ROOT=$PWD/build/native/cef uv build --wheel    # write the wheel to dist/

On Linux the wheel build (scikit-build-core and CMake) builds the wrapper library and the extension module and lays out the runtime, so ``uv build --wheel`` alone is enough: without ``CEF_ROOT`` CMake downloads CEF. On Windows the same command works when the Visual Studio C++ build tools are installed; ``CEF_ROOT`` selects a distribution you already have.

macOS uses the same commands (verified on arm64). The result is a ``macosx_12_0_arm64`` wheel of about 147 MB that contains ``cefsubprocess.app`` (the CEF framework and the helper app). If ``--list-versions`` fails with a certificate error on a Python from python.org, point ``--cef-root`` at a distribution you downloaded yourself.

The options of ``prepare.py``:

.. code-block:: sh

   python tools/prepare.py --list-versions [FILTER]       # the CEF versions you can download
   python tools/prepare.py --cef-version "154.0.34+g14c5a08+chromium-154.0.8037.98"
   python tools/prepare.py --cef-root /path/cef           # use a CEF you built yourself
   python tools/prepare.py --build-cef --dry-run          # only show the plan for a source build

Building CEF from source (``--build-cef``) needs about 120 GB of disk, 16 GB of RAM or more and several hours, and works on Linux x86_64 only. A prebuilt CEF is enough for most uses.

Choosing a toolkit
------------------

The toolkit adapters of :mod:`cefweaver.ui` never import each other: install only the toolkit you use.

.. list-table::
   :header-rows: 1
   :widths: 25 30 45

   * - Install
     - Toolkit
     - Notes
   * - ``cefweaver[qt]``
     - Qt (PyQt6)
     - PySide6 works too: install it yourself and set the environment variable ``CEFQT_BINDING=pyside6``.
   * - ``cefweaver[gtk3]``
     - GTK 3 (PyGObject, pycairo)
     - PyGObject is built from source and needs system packages (Debian and Ubuntu: ``libgirepository-2.0-dev``, ``libcairo2-dev``, ``gir1.2-gtk-3.0``, ``pkg-config``).
   * - ``cefweaver[tk]``
     - Tk
     - Uses Pillow.
   * - ``cefweaver[sdl2]``
     - SDL2
     - Uses ``pysdl2`` and ``pysdl2-dll``.
   * - ``cefweaver[kivy]``
     - Kivy
     -
   * - ``cefweaver[pywin32]``
     - Win32 window (pywin32)
     - Windows only. It uses the Win32 window and message loop directly, with no widget.
   * - ``cefweaver[pygame]``
     - (for sound output)
     - The fallback when a toolkit cannot play the sound of a page. See :doc:`media`.
   * - (no extras)
     - wxPython
     - PyPI has only the source, which takes very long to build. Take a wheel for your system from the `wxPython extras <https://extras.wxpython.org/wxPython4/extras/>`_. ``examples/wx/pyproject.toml`` shows how.

Running the examples
--------------------

Each example runs from its own folder with ``uv``. Build the wheel first (the examples point at the wheel in ``dist/``).

.. code-block:: sh

   cd examples/tk
   uv sync
   uv run python quickstart.py            # the address can be given as an argument

The examples are in ``examples/gtk3``, ``examples/qt``, ``examples/tk``, ``examples/sdl2``, ``examples/wx``, ``examples/kivy`` and ``examples/pywin32`` (Windows); the ``README.md`` of each folder lists what that toolkit needs. Printing is in ``examples/print``: on Linux it uses CUPS and a dialog the application draws (``libcups2-dev`` is required), on macOS the system print panel and a PDF path (``quickstart.py`` chooses).

Good to know
------------

- **Cache folder**: without a cache path CEF creates ``cache/`` in the working directory. Point programs at a temporary folder (``ui.Session(adapter, cache_path=...)``, or ``app.set_cache_path()`` in window mode).
- **Once per process**: CEF can be initialized only once per process, and not again after ``shutdown()``.
- **Layout**: on Linux ``libcef.so``, ``icudtl.dat``, the ``.pak`` files, ``locales/`` and the ``cefsubprocess`` executable must sit next to the extension module; on Windows ``libcef.dll`` and its DLLs, ``icudtl.dat``, the ``.pak`` files, ``locales/`` and ``cefsubprocess.exe``; on macOS ``cefsubprocess.app``. The wheel build does this layout (including ``cefsubprocess.app`` on macOS).
